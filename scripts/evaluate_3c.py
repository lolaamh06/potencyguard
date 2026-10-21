"""Phase 3C evaluation: per-box calibration, pre-trip check, a structurally different box, the bound
safety factor and interval, and a larger false-alarm study.

Run from the repo root:  python scripts/evaluate_3c.py [--quick] [--workers N]
  --sf-sweep-only   only the bound safety-factor sweep on the TRAINING seeds
  --fa-only         only the false-alarm study for k and h (blocks 60001-61000 and training)

Everything is a simulation result on a synthetic box. Final numbers come ONLY from block
50001-50200 (mismatch and two-node runs use its first 100 seeds), each seed scored once with no
tuning. The safety factor is chosen on the training seeds; k and h are examined on 60001-61000.

Runs are independent, so they are spread over worker processes (standard library). Tasks are built
in a fixed order and results are put back in that order before anything is aggregated, so the
numbers are identical for any number of workers.
"""
# ruff: noqa: E501  (report text lines)

from __future__ import annotations

import argparse
import functools
import json
import os
import sys
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
for _p in (str(REPO_ROOT), str(SCRIPTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import evaluate_detectors as ev  # noqa: E402

from edge.assessment import TrustAssessor, worst_case_bound  # noqa: E402
from edge.detector_config import DetectorConfig, load_detector_config  # noqa: E402
from edge.potency import potency_from_tau_eq  # noqa: E402
from edge.precheck import DEFAULT_PRECHECK_HOURS, precheck, window  # noqa: E402
from edge.tamper_monitor import TamperMonitor  # noqa: E402
from edge.thermal_twin import TwinParams, load_twin_params, load_variant_twins  # noqa: E402
from shared.config import BoxConfig, load_box_config  # noqa: E402
from simulator.calibration_set import (  # noqa: E402
    VARIANT_LABELS,
    VARIANT_SEEDS,
    calibrate_for_box,
    variant_boxes,
    variant_seed_plan,
)

DEFAULT_MARKDOWN = REPO_ROOT / "docs" / "02-phase-reports" / "phase-03c-evaluation.md"
DEFAULT_JSON = REPO_ROOT / "data" / "generated" / "evaluation_3c.json"
FOOTER = ev.FOOTER
QUICK = 5
MISMATCH_RUNS = 100  # seeds per family on the +/-15 percent and two-node boxes
SF_GRID = (1.0, 0.9, 0.8, 0.7, 0.6)
FA_K = (0.25, 0.5, 0.75, 1.0)
FA_H = (4.0, 6.0, 8.0, 12.0)
# Clean families only (the same ones the Phase 3 selection used). door_open_excursion is NOT clean:
# it contains a real heat event, so CUSUM alarms there are correct detections, not false alarms.
FA_FAMILIES = ev.CLEAN_NAMES
FA_MISMATCH_RUNS = 200
DELAY_FAMILIES = ("spoof_attempt", "hidden_spoilage", "injected_offset", "injected_replay")
PRECHECK_HOURS = DEFAULT_PRECHECK_HOURS

CLEAN_PHYSICAL = ev.CLEAN_NAMES + ev.PHYSICAL_NAMES
FIVE = ev.LIE_FAMILIES_PHASE3
DRIFTS = tuple(f"injected_drift_{r:g}_{v}" for r in ev.DRIFT_RATES for v in ("clean", "fault"))
MIMICS = ("injected_mimic_at_failure", "injected_mimic_late")
LIES = (*FIVE, "harmless_hold", *DRIFTS, *MIMICS)
ALL_FAMILIES = CLEAN_PHYSICAL + LIES
TAMPER_BOUND_FAMILIES = LIES  # families whose bound validity is reported

# ----------------------------------------------------------------------------- worker pool

_POOL: ProcessPoolExecutor | None = None


def pmap(fn: Callable, tasks: Sequence, workers: int) -> list:
    """fn over tasks, results in task order (so the output never depends on the worker count)."""
    if workers <= 1 or len(tasks) < 2 or _POOL is None:
        return [fn(task) for task in tasks]
    return list(_POOL.map(fn, tasks, chunksize=max(1, len(tasks) // (workers * 8))))


@functools.lru_cache(maxsize=1)
def _families() -> dict:
    return {**ev.build_families(), **ev.build_lie_families()}


@functools.lru_cache(maxsize=1)
def _product():
    return ev._product()


# ----------------------------------------------------------------------------- tasks (top level)


def _score_task(task: tuple) -> dict:
    """Score one run and add the pre-trip check of its first hours (with the same twin)."""
    name, seed, box, twin, config, confirm, sigma = task
    family = _families()[name]
    monitor = TamperMonitor(twin, config, confirm, sigma)
    run = family.make(seed, box)
    row = ev.score_run(run, family, monitor)
    pre = precheck(window(run.readings, PRECHECK_HOURS), twin, config)
    starts = [t for t in (run.divergence_s, run.physical_start_s) if t is not None]
    row["precheck_ok"] = pre.ok
    row["precheck_checked"] = pre.checked
    row["precheck_gain"] = pre.gain
    row["event_in_window"] = bool(starts) and min(starts) <= PRECHECK_HOURS * 3600.0
    return row


def _residual_task(task: tuple) -> tuple[list, float]:
    """Residuals (in sigma) of one clean run, for the CUSUM false-alarm count."""
    name, seed, box, twin, config, confirm, sigma = task
    run = _families()[name].make(seed, box)
    monitor = TamperMonitor(twin, config, confirm, sigma)
    out = []
    for reading in run.readings:
        state = monitor.update(reading)
        out.append((state.residual_sigma, state.cusum_skipped))
    hours = (run.readings[-1].t_s - run.readings[0].t_s) / 3600.0
    return out, hours


def _sf_task(task: tuple):
    """Bound for every safety factor on one run (the monitor and t0 do not depend on it)."""
    name, seed, box, twin, config, confirm, sigma, grid = task
    family = _families()[name]
    product = _product()
    monitor = TamperMonitor(twin, config, confirm, sigma)
    run = family.make(seed, box)
    assessor = TrustAssessor(product, monitor)
    assessor.reset()
    for reading in run.readings:
        assessor.update(reading)
    bound = assessor.last_bound
    if bound is None:
        return None
    true_tau = ev._true_tau_eq_h(run, bound.t0_s, product)
    out = {}
    for sf in grid:
        high = worst_case_bound(
            run.readings,
            bound.t0_s,
            bound.tau_eq_before_t0_h,
            product,
            twin,
            config.heat_allowance_c,
            sf,
        )
        out[sf] = (
            high.tau_eq_from_t0_h >= true_tau - 1e-9,
            high.tau_eq_from_t0_h / true_tau if true_tau > 0 else None,
        )
    return out


@functools.lru_cache(maxsize=4)
def _training_spoof_runs(seeds: tuple, box: BoxConfig) -> list:
    families = _families()
    return [families[n].make(seed, box) for n in DELAY_FAMILIES for seed in seeds]


def _delay_task(task: tuple) -> dict:
    """CUSUM detection delay of the negative side on the training spoof runs for one (k, h)."""
    k, h, seeds, box, twin, config, confirm, sigma = task
    cfg = config.model_copy(update={"cusum_k": k, "cusum_h": h})
    monitor = TamperMonitor(twin, cfg, confirm, sigma)
    delays, total = [], 0
    for run in _training_spoof_runs(tuple(seeds), box):
        if run.divergence_s is None:
            continue
        total += 1
        monitor.reset()
        for reading in run.readings:
            state = monitor.update(reading)
            if state.t_s >= run.divergence_s and state.flag_cusum_neg:
                delays.append(state.t_s - run.divergence_s)
                break
    return {
        "k": k,
        "h": h,
        "detection_rate": len(delays) / total if total else None,
        "median_delay_min": float(np.median(delays)) / 60.0 if delays else None,
    }


# ----------------------------------------------------------------------------- family scoring


def run_config(
    names: Sequence[str],
    seeds: Sequence[int],
    box: BoxConfig,
    twin: TwinParams,
    config: DetectorConfig,
    workers: int,
) -> dict[str, dict]:
    """Score families over seeds in parallel; returns {family: summary} (see summarise_rows)."""
    product = _product()
    confirm, sigma = product.hard_limit_consecutive_samples, box.sensor_sigma_c
    tasks = [(n, s, box, twin, config, confirm, sigma) for n in names for s in seeds]
    rows = pmap(_score_task, tasks, workers)
    out, i = {}, 0
    families = _families()
    for n in names:
        chunk = rows[i : i + len(seeds)]
        i += len(seeds)
        summary = ev.summarise_rows(families[n], list(seeds), chunk, chunk[0]["interval_s"])
        summary["precheck"] = _precheck_counts(chunk)
        summary["potency"] = _potency_counts(chunk, product)
        out[n] = summary
    return out


def _precheck_counts(rows: Sequence[dict]) -> dict:
    return {
        "runs": len(rows),
        "recalibrate": sum(r["precheck_checked"] and not r["precheck_ok"] for r in rows),
        "matches": sum(r["precheck_checked"] and r["precheck_ok"] for r in rows),
        "unchecked": sum(not r["precheck_checked"] for r in rows),
        "event_in_window": sum(r["event_in_window"] for r in rows),
        "recalibrate_event_in_window": sum(
            r["precheck_checked"] and not r["precheck_ok"] and r["event_in_window"] for r in rows
        ),
    }


def _potency_counts(rows: Sequence[dict], product) -> dict:
    ratios = [
        r["reported_tau_eq_h"] / r["true_tau_eq_total_h"]
        for r in rows
        if r["true_tau_eq_total_h"] > 0
    ]
    rep = [potency_from_tau_eq(r["reported_tau_eq_h"], product) for r in rows]
    tru = [potency_from_tau_eq(r["true_tau_eq_total_h"], product) for r in rows]
    return {
        "tau_ratio_median": float(np.median(ratios)) if ratios else None,
        "reported_potency_median": float(np.median(rep)),
        "true_potency_median": float(np.median(tru)),
        "potency_gap_median": float(np.median([a - b for a, b in zip(rep, tru, strict=True)])),
    }


def _merge_precheck(blocks: Sequence[dict]) -> dict:
    keys = (
        "runs",
        "recalibrate",
        "matches",
        "unchecked",
        "event_in_window",
        "recalibrate_event_in_window",
    )
    return {k: sum(b[k] for b in blocks) for k in keys}


def summarise_config(summ: dict[str, dict], seeds: Sequence[int]) -> dict:
    """The numbers of one (box, twin) configuration that the tables and targets use."""
    cp = [summ[n] for n in CLEAN_PHYSICAL if n in summ]
    runs = sum(e["runs"] for e in cp)
    false = {
        "runs": runs,
        "any_tamper": sum(e["runs_with_tamper_verdict"] for e in cp),
        "ended_tamper": sum(e["runs_ended_with_tamper"] for e in cp),
        "ood_any": sum(e["runs_with_ood_verdict"] for e in cp),
        "low_confidence": sum(e["runs_level_low_confidence"] for e in cp),
        "untrusted": sum(e["runs_level_untrusted"] for e in cp),
        "ended_by_family": {e["family"]: e["runs_ended_with_tamper"] for e in cp},
        "any_by_family": {e["family"]: e["runs_with_tamper_verdict"] for e in cp},
    }
    lies = {}
    for n in (*FIVE, *DRIFTS, *MIMICS):
        if n in summ:
            e = summ[n]
            lies[n] = {
                "detection_rate": e["detection_rate"],
                "median_min": e["delay"]["median_min"],
                "p90_min": e["delay"]["p90_min"],
                "median_samples": e["delay"]["median_samples"],
                "ends_as": e["final_verdicts"],
            }
    bound_families = [summ[n] for n in TAMPER_BOUND_FAMILIES if n in summ]
    violations = [(e["family"], s) for e in bound_families for s in e["violations"]]
    bound = {
        "computed": sum(e["bound"]["computed"] for e in bound_families),
        "valid": sum(e["bound"]["valid"] for e in bound_families),
        "violations": violations,
        "per_family": {
            e["family"]: {
                "runs": e["runs"],
                "computed": e["bound"]["computed"],
                "valid": e["bound"]["valid"],
                "ratio_median": e["bound"]["ratio_median"],
                "ratio_p90": e["bound"]["ratio_p90"],
                "ratio_max": e["bound"]["ratio_max"],
            }
            for e in bound_families
            if e["bound"]["computed"]
        },
    }
    pre_cp = _merge_precheck([summ[n]["precheck"] for n in CLEAN_PHYSICAL if n in summ])
    return {
        "false": false,
        "lies": lies,
        "bound": bound,
        "precheck": pre_cp,
        "potency": {n: summ[n]["potency"] for n in CLEAN_PHYSICAL if n in summ},
        "seeds": [seeds[0], seeds[-1], len(seeds)],
    }


# ----------------------------------------------------------------------------- calibration table


def calibration_table(box: BoxConfig) -> dict:
    """Refit each variant from its per-box set and compare with what the simulator was told."""
    nominal = load_twin_params()
    stored = load_variant_twins()
    out = {
        "nominal": {
            "tau_h": nominal.tau_h,
            "dT_cool_c": nominal.dT_cool_c,
            "sigma_r_c": nominal.sigma_r_c,
            "true_tau_h": box.box_tau_h,
            "true_dT_cool_c": box.box_R_th_k_per_w * box.box_cooling_capacity_w,
        }
    }
    for name, variant in variant_boxes(box).items():
        result = calibrate_for_box(variant, variant_seed_plan(name))
        p = result.params
        entry = {
            "label": VARIANT_LABELS[name],
            "seeds": [VARIANT_SEEDS[name][0], VARIANT_SEEDS[name][-1]],
            "tau_h": p.tau_h,
            "dT_cool_c": p.dT_cool_c,
            "sigma_r_c": p.sigma_r_c,
            "r_squared": result.r_squared,
            "condition_number": result.condition_number,
            "b_minus_expected": result.b_minus_expected,
            "fit_intercept_d": result.d,
            "matches_stored_file": (
                abs(stored[name].tau_h - p.tau_h) < 1e-9
                and abs(stored[name].dT_cool_c - p.dT_cool_c) < 1e-9
            ),
            "true_dT_cool_c": variant.box_R_th_k_per_w * variant.box_cooling_capacity_w,
        }
        if name == "two_node":
            from simulator.box_model import two_node_for

            model = two_node_for(variant)
            entry["true_tau_h"] = model.slow_tau_s / 3600.0
            entry["true_fast_tau_h"] = model.fast_tau_s / 3600.0
        else:
            entry["true_tau_h"] = variant.box_tau_h
        out[name] = entry
    return out


# ----------------------------------------------------------------------------- bound safety factor


def run_sf_sweep(
    box: BoxConfig, config: DetectorConfig, seeds: Sequence[int], workers: int
) -> dict:
    """Largest safety factor with zero violations in every lie family on three boxes (training seeds)."""
    twin = load_twin_params()
    product = _product()
    confirm, sigma = product.hard_limit_consecutive_samples, box.sensor_sigma_c
    plus, minus = (variant_boxes(box)[k] for k in ("plus15", "minus15"))
    boxes = {"nominal": box, "plus15": plus, "minus15": minus}
    tasks, keys = [], []
    for label, bx in boxes.items():
        for n in LIES:
            for s in seeds:
                tasks.append((n, s, bx, twin, config, confirm, sigma, SF_GRID))
                keys.append((label, n))
    results = pmap(_sf_task, tasks, workers)
    table = []
    for sf in SF_GRID:
        violations, computed, ratios = [], 0, []
        for (label, n), res in zip(keys, results, strict=True):
            if res is None:
                continue
            computed += 1
            valid, ratio = res[sf]
            if not valid:
                violations.append((label, n))
            if label == "nominal" and ratio is not None:
                ratios.append(ratio)
        by_box: dict[str, int] = {}
        for label, _ in violations:
            by_box[label] = by_box.get(label, 0) + 1
        table.append(
            {
                "sf": sf,
                "computed": computed,
                "violations": len(violations),
                "violations_by_box": by_box,
                "violating_families": sorted({n for _, n in violations}),
                "looseness_median_nominal": float(np.median(ratios)) if ratios else None,
            }
        )
    ok = [r["sf"] for r in table if r["violations"] == 0]
    return {
        "grid": list(SF_GRID),
        "seeds": [seeds[0], seeds[-1], len(seeds)],
        "table": table,
        "selected": max(ok) if ok else None,
    }


# ----------------------------------------------------------------------------- false alarms


def cusum_episodes(sequences: Sequence[Sequence], k: float, h: float, cap_factor: float) -> int:
    """CUSUM alarm episodes (either side) from residuals in sigma (same update as the monitor)."""
    cap, episodes = cap_factor * h, 0
    for seq in sequences:
        s_pos = s_neg = 0.0
        previous = False
        for r, skipped in seq:
            if r is None or skipped:
                continue
            s_pos = min(cap, max(0.0, s_pos + r - k))
            s_neg = min(cap, max(0.0, s_neg - r - k))
            flag = s_pos > h or s_neg > h
            episodes += flag and not previous
            previous = flag
    return episodes


def run_false_alarm_study(
    box: BoxConfig,
    config: DetectorConfig,
    train_seeds: Sequence[int],
    fa_seeds: Sequence[int],
    mismatch_runs: int,
    grid_k: Sequence[float],
    grid_h: Sequence[float],
    workers: int,
) -> dict:
    twin = load_twin_params()
    product = _product()
    confirm = product.hard_limit_consecutive_samples
    boxes = {"nominal": box, **{k: v for k, v in variant_boxes(box).items() if k != "two_node"}}
    sets: dict[str, list] = {}
    hours: dict[str, float] = {}
    for label, bx in boxes.items():
        seeds = list(fa_seeds) if label == "nominal" else list(fa_seeds)[:mismatch_runs]
        tasks = [
            (n, s, bx, twin, config, confirm, bx.sensor_sigma_c) for n in FA_FAMILIES for s in seeds
        ]
        res = pmap(_residual_task, tasks, workers)
        sets[label] = [r[0] for r in res]
        hours[label] = float(sum(r[1] for r in res))
    delay_tasks = [
        (k, h, list(train_seeds), box, twin, config, confirm, box.sensor_sigma_c)
        for k in grid_k
        for h in grid_h
    ]
    delays = {(d["k"], d["h"]): d for d in pmap(_delay_task, delay_tasks, workers)}
    table = []
    for k in grid_k:
        for h in grid_h:
            row = {"k": k, "h": h}
            for label in boxes:
                eps = cusum_episodes(sets[label], k, h, config.cusum_cap_factor)
                key = "" if label == "nominal" else f"_{label}"
                row[f"episodes{key}"] = eps
                row[f"false_alarms_per_1000h{key}"] = eps / hours[label] * 1000.0
            row["cusum_neg_median_delay_min"] = delays[(k, h)]["median_delay_min"]
            row["cusum_neg_detection_rate"] = delays[(k, h)]["detection_rate"]
            table.append(row)
    target = config.cusum_false_alarm_target_per_1000h
    selected = ev.select_setting(table, target)
    current = (config.cusum_k, config.cusum_h)
    return {
        "target_per_1000h": target,
        "runs": {
            "nominal": len(sets["nominal"]),
            **{k: len(v) for k, v in sets.items() if k != "nominal"},
        },
        "hours": hours,
        "families": list(FA_FAMILIES),
        "table": table,
        "selected": selected and {"k": selected["k"], "h": selected["h"]},
        "current": {"k": current[0], "h": current[1]},
        "same_as_current": bool(selected) and (selected["k"], selected["h"]) == current,
        "seeds": [fa_seeds[0], fa_seeds[-1], len(fa_seeds)],
        "train_seeds": [train_seeds[0], train_seeds[-1], len(train_seeds)],
    }


# ----------------------------------------------------------------------------- the whole study


def _targets(study: dict) -> list[dict]:
    """The Phase 3C targets with the numbers behind them (placeholders)."""
    cfgs = study["configs"]
    nominal = cfgs["nominal"]
    nom_rate = nominal["false"]["any_tamper"] / nominal["false"]["runs"]
    out = []
    for key, label in (("plus15_own", "+15% box"), ("minus15_own", "-15% box")):
        c = cfgs[key]
        rate = c["false"]["any_tamper"] / c["false"]["runs"]
        five_ok = all(
            c["lies"][n]["detection_rate"] >= 0.95
            and abs(c["lies"][n]["median_samples"] - nominal["lies"][n]["median_samples"]) <= 1.0
            for n in FIVE
        )
        out.append(
            {
                "name": f"{label}, own calibration: false tamper verdicts at most the nominal rate plus 1 percentage point",
                "met": rate <= nom_rate + 0.01,
                "value": f"{c['false']['any_tamper']} of {c['false']['runs']} ({rate * 100:.1f} percent) against nominal {nom_rate * 100:.1f} percent",
            }
        )
        out.append(
            {
                "name": f"{label}, own calibration: five lie families detected at least 95 percent, delay within one sample of nominal",
                "met": five_ok,
                "value": ", ".join(
                    f"{n} {c['lies'][n]['detection_rate'] * 100:.0f}% / {c['lies'][n]['median_min']:.0f} min"
                    for n in FIVE
                ),
            }
        )
    bound_nominal = nominal["bound"]
    out.append(
        {
            "name": "nominal box: high bound never below the true damage (200 final seeds, every lie family)",
            "met": not bound_nominal["violations"],
            "value": f"{len(bound_nominal['violations'])} violations in {bound_nominal['computed']} bounds",
        }
    )
    return out


def run_study(quick: bool = False, workers: int = 1, log: Callable[[str], None] = print) -> dict:
    global _POOL
    started = time.time()
    box = load_box_config()
    config = load_detector_config()
    nominal_twin = load_twin_params()
    variants_twin = load_variant_twins()
    boxes = variant_boxes(box)
    # quick mode (smoke tests) uses the second development block, never the Phase 3C final block
    final = ev.FINAL_SEEDS[:QUICK] if quick else ev.FINAL3C_SEEDS
    mm = final[: (QUICK if quick else MISMATCH_RUNS)]
    train = ev.TRAIN_SEEDS[:QUICK] if quick else ev.TRAIN_SEEDS
    fa_seeds = ev.FALSE_ALARM_SEEDS[:20] if quick else ev.FALSE_ALARM_SEEDS
    own = {
        "plus15": variants_twin["plus15"],
        "minus15": variants_twin["minus15"],
        "two_node": variants_twin["two_node"],
    }
    timings: dict[str, float] = {}
    study: dict = {"note": FOOTER, "quick": quick, "workers": workers}
    pool = ProcessPoolExecutor(max_workers=workers) if workers > 1 else None
    _POOL = pool
    try:
        t = time.time()
        study["calibration"] = calibration_table(box)
        timings["calibration"] = time.time() - t

        t = time.time()
        study["sf_sweep"] = run_sf_sweep(box, config, train, workers)
        timings["sf_sweep"] = time.time() - t
        log(
            f"sf sweep done: selected {study['sf_sweep']['selected']} ({timings['sf_sweep']:.0f} s)"
        )

        t = time.time()
        grid_k, grid_h = ((0.25, 0.5), (4.0, 8.0)) if quick else (FA_K, FA_H)
        study["false_alarms"] = run_false_alarm_study(
            box, config, train, fa_seeds, 20 if quick else FA_MISMATCH_RUNS, grid_k, grid_h, workers
        )
        timings["false_alarms"] = time.time() - t
        log(f"false-alarm study done ({timings['false_alarms']:.0f} s)")

        plan = {
            "nominal": (box, nominal_twin, final),
            "plus15_nominal_twin": (boxes["plus15"], nominal_twin, mm),
            "plus15_own": (boxes["plus15"], own["plus15"], mm),
            "minus15_nominal_twin": (boxes["minus15"], nominal_twin, mm),
            "minus15_own": (boxes["minus15"], own["minus15"], mm),
            "two_node_nominal_twin": (boxes["two_node"], nominal_twin, mm),
            "two_node_own": (boxes["two_node"], own["two_node"], mm),
        }
        study["configs"] = {}
        study["families"] = {}
        for key, (bx, twin, seeds) in plan.items():
            t = time.time()
            summ = run_config(ALL_FAMILIES, seeds, bx, twin, config, workers)
            study["configs"][key] = summarise_config(summ, seeds)
            study["families"][key] = {n: _slim(e) for n, e in summ.items()}
            timings[key] = time.time() - t
            log(f"{key} done ({timings[key]:.0f} s)")
        study["targets"] = _targets(study)
        study["stop"] = {
            "nominal_bound_violations": study["configs"]["nominal"]["bound"]["violations"],
            "sf_none_found": study["sf_sweep"]["selected"] is None,
            "false_alarm_setting_changes": not study["false_alarms"]["same_as_current"],
        }
        study["config_used"] = {
            "bound_tau_safety_factor": config.bound_tau_safety_factor,
            "cusum_k": config.cusum_k,
            "cusum_h": config.cusum_h,
            "precheck_hours": PRECHECK_HOURS,
        }
    finally:
        if pool is not None:
            pool.shutdown()
        _POOL = None
    study["runtime_s"] = time.time() - started
    study["timings_s"] = timings
    study["ledger"] = [list(r) for r in ev.SEED_LEDGER_3C]
    return study


def _slim(summary: dict) -> dict:
    keep = (
        "family", "kind", "runs", "detection_rate", "delay", "final_verdicts",
        "runs_with_tamper_verdict", "runs_ended_with_tamper", "runs_with_ood_verdict",
        "runs_level_low_confidence", "runs_level_untrusted", "bound", "violations", "precheck", "potency",
    )  # fmt: skip
    return {k: summary[k] for k in keep if k in summary}


# ----------------------------------------------------------------------------- text output


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.0f}%"


def _n(x: float | None, d: int = 0) -> str:
    return "n/a" if x is None else f"{x:.{d}f}"


def _table(head: Sequence[str], rows: Sequence[Sequence]) -> list[str]:
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return lines


CONFIG_LABELS = {
    "nominal": "nominal box, nominal twin",
    "plus15_nominal_twin": "+15% box, nominal twin",
    "plus15_own": "+15% box, own twin",
    "minus15_nominal_twin": "-15% box, nominal twin",
    "minus15_own": "-15% box, own twin",
    "two_node_nominal_twin": "two-node box, nominal twin",
    "two_node_own": "two-node box, own (single-node) twin",
}


def render_markdown(study: dict) -> str:
    cfgs = study["configs"]
    lines = [
        "# Phase 3C evaluation (generated by scripts/evaluate_3c.py)",
        "",
        FOOTER,
        "",
        f"Quick mode: {study['quick']}. Workers: {study['workers']}. Runtime: {study['runtime_s'] / 60:.1f} minutes.",
        "",
        "## Seed ledger",
        "",
        *_table(["block", "seeds", "used for", "status"], study["ledger"]),
        "",
        "Final numbers below come only from 50001 to 50200 (mismatch and two-node rows use the first 100), each seed scored once.",
        "",
        "## Per-box calibration",
        "",
        "Each variant is fitted from its own clean calibration set (same two scenarios and same restricted regression as the nominal twin). 'True' is what the simulator was told; for the two-node box the true slow and fast time constants are those of the two-node model.",
        "",
    ]
    cal = study["calibration"]
    rows = []
    for key, c in cal.items():
        rows.append(
            [
                CONFIG_LABELS.get(key, key).split(",")[0] if key == "nominal" else c["label"],
                c.get("seeds", ["9001", "9010"]),
                f"{c['true_tau_h']:.3f}"
                + (f" (fast {c['true_fast_tau_h']:.2f})" if "true_fast_tau_h" in c else ""),
                f"{c['tau_h']:.3f}",
                f"{c['true_dT_cool_c']:.2f}",
                f"{c['dT_cool_c']:.2f}",
                _n(c.get("sigma_r_c"), 4),
                _n(c.get("r_squared"), 4),
                _n(c.get("b_minus_expected"), 4),
            ]
        )
    lines += _table(
        [
            "box",
            "seeds",
            "true tau (h)",
            "fitted tau (h)",
            "true dT_cool (K)",
            "fitted dT_cool (K)",
            "sigma_r",
            "R squared",
            "b minus (1-a)",
        ],
        rows,
    )
    lines += ["", "## Targets (placeholders)", ""]
    lines += _table(
        ["target", "result", "numbers"],
        [[t["name"], "met" if t["met"] else "**missed**", t["value"]] for t in study["targets"]],
    )
    lines += [
        "",
        "## False tamper verdicts, out-of-date and trust levels (clean and physical families)",
        "",
    ]
    rows = []
    for key, c in cfgs.items():
        f = c["false"]
        rows.append(
            [
                CONFIG_LABELS[key], f["runs"], f"{f['any_tamper']} ({_pct(f['any_tamper'] / f['runs'])})",
                f["ended_tamper"], f["ood_any"], f["low_confidence"], f["untrusted"],
            ]
        )  # fmt: skip
    lines += _table(
        [
            "configuration",
            "runs",
            "any tamper verdict",
            "ends tamper",
            "went out of date",
            "low confidence",
            "untrusted",
        ],
        rows,
    )
    lines += ["", "Runs that END with a tamper verdict, by family:", ""]
    fam_names = list(next(iter(cfgs.values()))["false"]["ended_by_family"])
    lines += _table(
        ["configuration", *fam_names],
        [[CONFIG_LABELS[k], *c["false"]["ended_by_family"].values()] for k, c in cfgs.items()],
    )
    lines += ["", "## Lie families: detection and delay", ""]
    lines += [
        "Detected = a tamper verdict at or after the first divergence; delay is the median in minutes. Mimic rows are expected to be near 0 percent (physics cannot see them).",
        "",
    ]
    names = [*FIVE, *DRIFTS, *MIMICS]
    lines += _table(
        ["family", *[CONFIG_LABELS[k] for k in cfgs]],
        [
            [
                n,
                *[
                    f"{_pct(c['lies'][n]['detection_rate'])} / {_n(c['lies'][n]['median_min'])}"
                    for c in cfgs.values()
                ],
            ]
            for n in names
        ],
    )
    lines += ["", "## Pre-trip check (first 6 hours, with the twin shown)", ""]
    lines += [
        "'Recalibrate' = the gain was measurable and away from 1. 'Not checkable' = the gain could not be measured in the window (this is NOT a confirmation). 'Event in window' = a lie or fault starts inside the first 6 hours (expected to confuse the check). Runs are the clean and physical families.",
        "",
    ]
    rows = []
    for k, c in cfgs.items():
        p = c["precheck"]
        rows.append(
            [CONFIG_LABELS[k], p["runs"], f"{p['recalibrate']} ({_pct(p['recalibrate'] / p['runs'])})", p["matches"], p["unchecked"], p["event_in_window"], p["recalibrate_event_in_window"]]
        )  # fmt: skip
    lines += _table(
        [
            "configuration",
            "runs",
            "says recalibrate",
            "says matches",
            "not checkable",
            "event in window",
            "recalibrate with event in window",
        ],
        rows,
    )
    lines += ["", "## Two-node box: payload potency (truth) against reported potency", ""]
    lines += [
        "Median over runs of each family. tau ratio = equivalent reference time from the reported series divided by that of the payload node (the truth for a two-node box).",
        "",
    ]
    rows = []
    for k in ("nominal", "two_node_nominal_twin", "two_node_own"):
        for n, p in cfgs[k]["potency"].items():
            rows.append(
                [
                    CONFIG_LABELS[k],
                    n,
                    _n(p["tau_ratio_median"], 3),
                    _n(p["reported_potency_median"], 4),
                    _n(p["true_potency_median"], 4),
                    _n(p["potency_gap_median"], 4),
                ]
            )
    lines += _table(
        [
            "configuration",
            "family",
            "tau ratio",
            "reported potency",
            "true potency",
            "gap (reported minus true)",
        ],
        rows,
    )
    lines += ["", "## Worst-case bound: validity and interval", ""]
    lines += [
        f"High bound uses bound_tau_safety_factor = {study['config_used']['bound_tau_safety_factor']}. A violation = high bound below the true damage (payload for the two-node box).",
        "",
    ]
    rows = []
    for k, c in cfgs.items():
        b = c["bound"]
        v = b["violations"]
        rows.append(
            [
                CONFIG_LABELS[k],
                b["computed"],
                b["valid"],
                len(v),
                ", ".join(sorted({f for f, _ in v})) or "-",
            ]
        )
    lines += _table(
        ["configuration", "bounds computed", "valid", "violations", "families with violations"],
        rows,
    )
    lines += ["", "Looseness (bound over true), nominal box, final seeds:", ""]
    lines += _table(
        ["family", "bounds", "valid", "ratio median", "ratio p90", "ratio max"],
        [
            [
                n,
                e["computed"],
                e["valid"],
                _n(e["ratio_median"], 2),
                _n(e["ratio_p90"], 2),
                _n(e["ratio_max"], 2),
            ]
            for n, e in cfgs["nominal"]["bound"]["per_family"].items()
        ],
    )
    sf = study["sf_sweep"]
    lines += ["", "## Bound safety factor sweep (training seeds)", ""]
    lines += [
        f"Training seeds {sf['seeds'][0]} to {sf['seeds'][1]} ({sf['seeds'][2]} per family), nominal box and the +15 and -15 percent boxes with the nominal twin, every lie family. Rule: the largest factor with zero violations. Selected: {sf['selected']}.",
        "",
    ]
    lines += _table(
        [
            "sf",
            "bounds computed",
            "violations",
            "violations by box",
            "families",
            "median looseness (nominal)",
        ],
        [
            [
                r["sf"],
                r["computed"],
                r["violations"],
                r["violations_by_box"] or "-",
                ", ".join(r["violating_families"]) or "-",
                _n(r["looseness_median_nominal"], 2),
            ]
            for r in sf["table"]
        ],
    )
    fa = study["false_alarms"]
    lines += ["", "## CUSUM false alarms for k and h", ""]
    lines += [
        f"Clean runs of {', '.join(fa['families'])} on seeds {fa['seeds'][0]} to {fa['seeds'][1]} ({fa['runs']['nominal']} runs, {fa['hours']['nominal']:.0f} simulated hours on the nominal box). The mismatched-box columns use {fa['runs'].get('plus15', 0)} runs with the nominal twin ({fa['hours'].get('plus15', 0):.0f} and {fa['hours'].get('minus15', 0):.0f} hours). Delay is the median of the negative CUSUM on the training spoof runs. Target: at most {fa['target_per_1000h']} alarm episodes per 1000 hours (placeholder). Episodes are counts; at the target rate the expected count on the nominal box would be {fa['target_per_1000h'] * fa['hours']['nominal'] / 1000:.0f}.",
        "",
    ]
    lines += _table(
        [
            "k",
            "h",
            "episodes (nominal)",
            "per 1000 h",
            "per 1000 h +15%",
            "per 1000 h -15%",
            "median delay (min)",
            "detected",
        ],
        [
            [
                r["k"],
                r["h"],
                r["episodes"],
                _n(r["false_alarms_per_1000h"], 2),
                _n(r["false_alarms_per_1000h_plus15"], 2),
                _n(r["false_alarms_per_1000h_minus15"], 2),
                _n(r["cusum_neg_median_delay_min"]),
                _pct(r["cusum_neg_detection_rate"]),
            ]
            for r in fa["table"]
        ],
    )
    lines += [
        "",
        f"The selection rule picks {fa['selected']}; the setting in config/detectors.yaml is {fa['current']}. "
        + (
            "They are the same."
            if fa["same_as_current"]
            else "THEY DIFFER: the proposal is in the report and nothing was changed."
        ),
        "",
        FOOTER,
    ]
    return "\n".join(lines) + "\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 3C evaluation.")
    parser.add_argument("--quick", action="store_true", help="a few seeds per family (for tests)")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    parser.add_argument("--sf-sweep-only", action="store_true")
    parser.add_argument("--fa-only", action="store_true")
    parser.add_argument("--markdown", default=str(DEFAULT_MARKDOWN))
    parser.add_argument("--json", default=str(DEFAULT_JSON))
    args = parser.parse_args(argv)
    global _POOL
    if args.sf_sweep_only or args.fa_only:
        box, config = load_box_config(), load_detector_config()
        if args.workers > 1:
            _POOL = ProcessPoolExecutor(max_workers=args.workers)
        try:
            if args.sf_sweep_only:
                result = run_sf_sweep(box, config, ev.TRAIN_SEEDS, args.workers)
            else:
                result = run_false_alarm_study(
                    box,
                    config,
                    ev.TRAIN_SEEDS,
                    ev.FALSE_ALARM_SEEDS,
                    FA_MISMATCH_RUNS,
                    FA_K,
                    FA_H,
                    args.workers,
                )
        finally:
            if _POOL is not None:
                _POOL.shutdown()
                _POOL = None
        print(json.dumps(result, indent=1, default=float))
        return 0
    study = run_study(quick=args.quick, workers=args.workers)
    _write(Path(args.markdown), render_markdown(study))
    _write(Path(args.json), json.dumps(study, indent=1, default=float) + "\n")
    print(f"wrote {args.markdown} and {args.json} in {study['runtime_s'] / 60:.1f} minutes")
    stop = study["stop"]
    if (
        stop["nominal_bound_violations"]
        or stop["sf_none_found"]
        or stop["false_alarm_setting_changes"]
    ):
        print("STOP CONDITION:", {k: v for k, v in stop.items() if v})
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
