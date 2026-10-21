"""Measure the tamper detectors with the real simulator, monitor and calibration (Phases 3, 3B).

Run from the repo root:  python scripts/evaluate_detectors.py [--quick]
Phase 3B adds: the drift and mimic lie families, the "twin out of date" verdict and its threshold
sweep (training seeds only), the worst-case damage bound, and a before/after comparison with the
Phase 3 behaviour (the same code with the self-check switched off).

Seed blocks (disjoint; asserted below and in the tests):
  calibration  9001 to 9010    used only to fit the twin
  training    10001 to 10100   used only to choose the CUSUM settings and the ood settings
  development 20001 to 20200   scored once in Phase 3B; its seed 20090 exposed a bound violation,
                               so it was used for DIAGNOSIS and is no longer a final block
  validity    30001 to 30200   used to validate the first bound-start repair: development as well
  final       40001 to 40200   final scoring of the Phase 3B fix; second development block from
                               Phase 3C on
  Phase 3C: per-box calibration 9101-9110, 9201-9210, 9301-9310; final 50001 to 50200; false-alarm
  study 60001 to 61000 (SEED_LEDGER_3C below)

Everything is a simulation result on a synthetic box. The twin and the simulator use the same
family of equations, so the final scoring is repeated against boxes that differ from the
calibration (mismatch runs).
"""
# ruff: noqa: E501  (report text lines)

from __future__ import annotations

import argparse
import dataclasses
import functools
import json
import statistics
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from edge.assessment import TrustAssessor  # noqa: E402
from edge.detector_config import DetectorConfig, load_detector_config  # noqa: E402
from edge.potency import arrhenius_acceleration_factor  # noqa: E402
from edge.sensor_reading import SensorReading  # noqa: E402
from edge.tamper_monitor import (  # noqa: E402
    FALSIFICATION,
    GLITCH,
    OUT_OF_DATE,
    THERMAL_ANOMALY,
    TamperMonitor,
)
from edge.thermal_twin import load_twin_params  # noqa: E402
from shared.config import BoxConfig, ProductConfig, load_box_config, load_product_config  # noqa: E402, E501
from simulator.calibration_set import CALIBRATION_SEEDS  # noqa: E402
from simulator.divergence import first_divergence_s  # noqa: E402
from simulator.events import KIND_COOLING, KIND_HEAT  # noqa: E402
from simulator.live import LiveSimulator  # noqa: E402
from simulator.scenario import load_all_scenarios  # noqa: E402
from simulator.truth import TruthSample  # noqa: E402

DEFAULT_MARKDOWN = REPO_ROOT / "docs" / "02-phase-reports" / "phase-03b-evaluation.md"
DEFAULT_JSON = REPO_ROOT / "data" / "generated" / "evaluation_3b.json"
FOOTER = "Simulation result on a synthetic box. Not real-world evidence."

TRAIN_SEEDS = list(range(10001, 10101))
DEVELOPMENT_SEEDS = list(range(20001, 20201))
VALIDITY_DEV_SEEDS = list(range(30001, 30201))
FINAL_SEEDS = list(range(40001, 40201))
TEST_SEEDS = FINAL_SEEDS  # the final scoring block (the name is kept for the tests that sample it)
SEED_LEDGER = (
    ("calibration", "9001 to 9010", "fit the twin", "calibration only"),
    ("training", "10001 to 10100", "chose CUSUM settings and the out-of-date settings", "tuning"),
    (
        "development",
        "20001 to 20200",
        "scored the first Phase 3B build; seed 20090 showed a bound violation",
        "diagnosis (no longer unseen)",
    ),
    (
        "validity (development)",
        "30001 to 30200",
        "validated the first bound-start repair (both statistics quiet)",
        "diagnosis (no longer unseen)",
    ),
    (
        "final",
        "40001 to 40200",
        "scores the episode-latched bound start; mismatch runs use the first 100",
        "final scoring, used once",
    ),
)
# Phase 3C blocks (nothing above is touched; 40001-40200 is now a second development block).
FINAL3C_SEEDS = list(range(50001, 50201))
FALSE_ALARM_SEEDS = list(range(60001, 61001))
SEED_LEDGER_3C = (
    ("calibration", "9001 to 9010", "fit the nominal twin", "calibration only"),
    (
        "per-box calibration, +15% box",
        "9101 to 9110",
        "fit the twin of the +15% box",
        "calibration only",
    ),
    (
        "per-box calibration, -15% box",
        "9201 to 9210",
        "fit the twin of the -15% box",
        "calibration only",
    ),
    (
        "per-box calibration, two-node box",
        "9301 to 9310",
        "fit the single-node twin to the two-node box",
        "calibration only",
    ),
    (
        "training",
        "10001 to 10100",
        "CUSUM and out-of-date settings (3B); bound safety factor (3C)",
        "tuning",
    ),
    (
        "development",
        "20001 to 20200",
        "3B first scoring; diagnosis of the bound violation",
        "used (development)",
    ),
    (
        "validity (development)",
        "30001 to 30200",
        "validated the first bound repair",
        "used (development)",
    ),
    (
        "second development",
        "40001 to 40200",
        "3B fix final scoring; now development for anything touched in 3C",
        "used (development)",
    ),
    (
        "final (3C)",
        "50001 to 50200",
        "all Phase 3C final numbers; mismatch and two-node runs use the first 100",
        "final scoring, each seed scored once, no tuning",
    ),
    (
        "false-alarm study",
        "60001 to 61000",
        "clean runs only: CUSUM false alarms for k and h",
        "tuning allowed",
    ),
)
QUICK_COUNT = 5
MISMATCH_SWEEP_SEEDS = 30  # training seeds used for the informational mismatch columns of the sweep
MISMATCH_COUNT = 100  # seeds per family in the mismatch runs (the first ones of the test block)
SWEEP_K = (0.25, 0.5, 1.0)
SWEEP_H = (4.0, 8.0, 12.0)
OOD_SWEEP_MISMATCH_SEEDS = 40  # training seeds per family on the +/-15% boxes in the ood sweep
OOD_SWEEP_WINDOWS = (36, 72, 144)
OOD_SWEEP_MARGINS = (0.06, 0.08, 0.10)
OOD_SWEEP_SUSTAINED = (6, 12, 24)
OOD_FALSE_TARGET = 0.02  # largest share of nominal-box clean and physical runs that may go ood
OOD_LIE_LOSS_TARGET = 0.01  # largest drop in any nominal lie family's detection rate
DRIFT_RATES = (0.25, 0.5, 1.0, 2.0)
assert not set(CALIBRATION_SEEDS) & set(TRAIN_SEEDS)
from simulator.calibration_set import VARIANT_SEEDS  # noqa: E402

_BLOCKS = [
    CALIBRATION_SEEDS,
    TRAIN_SEEDS,
    DEVELOPMENT_SEEDS,
    VALIDITY_DEV_SEEDS,
    FINAL_SEEDS,
    *VARIANT_SEEDS.values(),
    FINAL3C_SEEDS,
    FALSE_ALARM_SEEDS,
]
assert sum(len(set(b)) for b in _BLOCKS) == len(set().union(*map(set, _BLOCKS)))

DETECTORS = ("cusum_pos", "cusum_neg", "impossible_step", "impossible_state", "flat_line")
FLAG_OF = {
    "cusum_pos": "flag_cusum_pos",
    "cusum_neg": "flag_cusum_neg",
    "impossible_step": "flag_step",
    "impossible_state": "flag_state",
    "flat_line": "flag_flat",
}


# ----------------------------------------------------------------------------- run generation


@dataclass(frozen=True)
class RunData:
    readings: list[SensorReading]
    truth: list[TruthSample]
    interval_s: float
    divergence_s: float | None
    physical_start_s: float | None


@dataclass(frozen=True)
class Family:
    name: str
    kind: str  # clean | physical | tamper | control
    expected: str  # the correct verdict class
    make: Callable[[int, BoxConfig], RunData]


def _finish(sim: LiveSimulator, box: BoxConfig) -> RunData:
    readings, truth = [], []
    while True:
        reading, sample = sim.step()
        if reading is None or sample is None:
            break
        readings.append(reading)
        truth.append(sample)
    physical = [
        e.start_s
        for e in sim.events()
        if e.kind == KIND_HEAT or (e.kind == KIND_COOLING and e.params.get("factor", 1.0) < 1.0)
    ]
    return RunData(
        readings,
        truth,
        sim.sample_interval_s,
        first_divergence_s(truth, box.detect_divergence_c),
        min(physical) if physical else None,
    )


def _scenario_family(name: str, kind: str, expected: str) -> Family:
    scenarios = load_all_scenarios()

    def make(seed: int, box: BoxConfig) -> RunData:
        return _finish(LiveSimulator(scenarios[name], box, seed), box)

    return Family(name, kind, expected, make)


def _injected_family(
    name: str, kind: str, expected: str, base: str, hours: tuple[float, float], event: Callable
) -> Family:
    """A base scenario with a spoof injected at a random time (the harness's own generator)."""
    scenarios = load_all_scenarios()

    def make(seed: int, box: BoxConfig) -> RunData:
        rng = np.random.default_rng(seed + 777)
        sim = LiveSimulator(scenarios[base], box, seed)
        at_s = float(rng.uniform(*hours)) * 3600.0
        injected = False
        readings, truth = [], []
        while True:
            if not injected and sim.engine.next_sample_s >= at_s:
                commands = event(rng, sim.engine.now_s)
                for command in commands if isinstance(commands, list) else [commands]:
                    result = sim.inject(command)
                    if not result.accepted:
                        raise RuntimeError(f"injection rejected: {result.error}")
                injected = True
            reading, sample = sim.step()
            if reading is None or sample is None:
                break
            readings.append(reading)
            truth.append(sample)
        return RunData(
            readings,
            truth,
            sim.sample_interval_s,
            first_divergence_s(truth, box.detect_divergence_c),
            None,
        )

    return Family(name, kind, expected, make)


def build_families() -> dict[str, Family]:
    families = [
        _scenario_family("baseline_ok", "clean", "ok"),
        _scenario_family("shock_drop", "clean", "ok"),
        _scenario_family("sensor_glitch", "clean", "ok"),
        _scenario_family("freeze_event", "clean", "ok"),
        _scenario_family("door_open_excursion", "physical", THERMAL_ANOMALY),
        _scenario_family("reefer_failure", "physical", THERMAL_ANOMALY),
        _scenario_family("heatwave_transit", "physical", THERMAL_ANOMALY),
        _scenario_family("spoof_attempt", "tamper", FALSIFICATION),
        _scenario_family("hidden_spoilage", "tamper", FALSIFICATION),
        _injected_family(
            "injected_offset",
            "tamper",
            FALSIFICATION,
            "baseline_ok",
            (8.0, 36.0),
            lambda rng, _now: {
                "type": "spoof_sensor",
                "mode": "offset",
                "delta_c": round(float(rng.uniform(6.0, 12.0)), 2),
            },
        ),
        _injected_family(
            "injected_offset_small",
            "tamper",
            FALSIFICATION,
            "baseline_ok",
            (8.0, 36.0),
            lambda rng, _now: {
                "type": "spoof_sensor",
                "mode": "offset",
                "delta_c": round(float(rng.uniform(1.5, 3.0)), 2),
            },
        ),
        _injected_family(
            "injected_replay",
            "tamper",
            FALSIFICATION,
            "reefer_failure",
            (16.0, 24.0),
            lambda rng, now: {
                "type": "spoof_sensor",
                "mode": "replay",
                "replay_from_h": round(float(rng.uniform(1.0, 3.0)), 2),
                "replay_len_h": 2.0,
            },
        ),
        _injected_family(
            "harmless_hold",
            "control",
            "ok",
            "baseline_ok",
            (8.0, 36.0),
            lambda rng, _now: {"type": "spoof_sensor", "mode": "hold", "reported_c": 5.0},
        ),
    ]
    return {f.name: f for f in families}


def build_lie_families() -> dict[str, Family]:
    """Phase 3B lies: slow drifts and a knowledgeable liar (the mimic). All are tamper families.

    injected_drift_R_clean   baseline_ok, no physical fault, the drift starts at a random time
    injected_drift_R_fault   reefer_failure, the cooling fault is already active when it starts
    injected_mimic_at_failure  baseline_ok, the cooling is killed and the mimic starts together
    injected_mimic_late      reefer_failure, the mimic starts hours after the cooling failed
    """
    families = []
    for rate in DRIFT_RATES:
        for variant, base, hours in (
            ("clean", "baseline_ok", (8.0, 36.0)),
            ("fault", "reefer_failure", (16.0, 24.0)),
        ):
            families.append(
                _injected_family(
                    f"injected_drift_{rate:g}_{variant}",
                    "tamper",
                    FALSIFICATION,
                    base,
                    hours,
                    lambda _rng, _now, rate=rate: {
                        "type": "spoof_sensor",
                        "mode": "drift",
                        "rate_c_per_h": rate,
                    },
                )
            )
    families.append(
        _injected_family(
            "injected_mimic_at_failure",
            "tamper",
            FALSIFICATION,
            "baseline_ok",
            (8.0, 36.0),
            lambda _rng, _now: [
                {"type": "kill_cooling"},
                {"type": "spoof_sensor", "mode": "mimic"},
            ],
        )
    )
    families.append(
        _injected_family(
            "injected_mimic_late",
            "tamper",
            FALSIFICATION,
            "reefer_failure",
            (16.0, 24.0),
            lambda _rng, _now: {"type": "spoof_sensor", "mode": "mimic"},
        )
    )
    return {f.name: f for f in families}


LIE_FAMILIES_PHASE3 = (
    "spoof_attempt",
    "hidden_spoilage",
    "injected_offset",
    "injected_offset_small",
    "injected_replay",
)
CLEAN_NAMES = ("baseline_ok", "shock_drop", "sensor_glitch", "freeze_event")
PHYSICAL_NAMES = ("door_open_excursion", "reefer_failure", "heatwave_transit")


@functools.lru_cache(maxsize=1)
def _product() -> ProductConfig:
    return load_product_config()


# ----------------------------------------------------------------------------- scoring one run


def _damage_temp_c(sample: TruthSample) -> float:
    """The temperature the product really sits at: the payload node of a two-node box, else the box."""
    return sample.true_temp_c if sample.true_payload_temp_c is None else sample.true_payload_temp_c


def _true_tau_eq_h(run: RunData, t0_s: float, product: ProductConfig) -> float:
    """tau_eq of the TRUE temperatures after t0 (scoring only; the monitor never sees truth)."""
    dt_h = run.interval_s / 3600.0
    index = round(t0_s / run.interval_s)
    return sum(
        arrhenius_acceleration_factor(_damage_temp_c(sample), product) * dt_h
        for sample in run.truth[index + 1 :]
    )


def score_run(
    run: RunData, family: Family, monitor: TamperMonitor
) -> dict[str, float | int | bool | None]:
    """Run the monitor over one run and return plain scoring numbers."""
    product = _product()
    assessor = TrustAssessor(product, monitor)
    assessor.reset()
    ref_s = {
        "tamper": run.divergence_s,
        "physical": run.physical_start_s,
    }.get(family.kind, 0.0)
    first_after: dict[str, float | None] = {name: None for name in DETECTORS}
    verdict_first: dict[str, float | None] = {
        v: None for v in (FALSIFICATION, THERMAL_ANOMALY, GLITCH, OUT_OF_DATE)
    }
    episodes = {FALSIFICATION: 0, THERMAL_ANOMALY: 0, OUT_OF_DATE: 0}
    previous = "ok"
    state = None
    for reading in run.readings:
        _, potency_state, state = assessor.update(reading)
        if ref_s is not None and state.t_s >= ref_s:
            for name, attr in FLAG_OF.items():
                if first_after[name] is None and getattr(state, attr):
                    first_after[name] = state.t_s - ref_s
            if state.verdict in verdict_first and verdict_first[state.verdict] is None:
                verdict_first[state.verdict] = state.t_s - ref_s
        if state.verdict != previous and state.verdict in episodes:
            episodes[state.verdict] += 1
        previous = state.verdict
    hours = (run.readings[-1].t_s - run.readings[0].t_s) / 3600.0
    anywhere = {v for _, v in monitor.verdict_history}
    bound = assessor.last_bound
    trust: dict[str, float | int | bool | str | None] = {
        "untrusted": state.untrusted_since_s is not None,
        "untrusted_reason": state.untrusted_reason,
        "trust_level": state.trust_level,
        "untrusted_since_s": state.untrusted_since_s,
        "ood_from_start": monitor.out_of_date_from_start,
        "bound_computed": bound is not None,
        "bound_valid": None,
        "bound_tau_h": None,
        "true_tau_h": None,
        "bound_ratio": None,
        "bound_start_before_divergence_s": None,
        "bound_low_tau_h": None,
        "low_valid": None,
    }
    if bound is not None:
        true_tau = _true_tau_eq_h(run, bound.t0_s, product)
        trust["bound_tau_h"] = bound.tau_eq_from_t0_h
        trust["true_tau_h"] = true_tau
        trust["bound_valid"] = bound.tau_eq_from_t0_h >= true_tau - 1e-9
        trust["bound_low_tau_h"] = bound.tau_eq_low_from_t0_h
        trust["low_valid"] = bound.tau_eq_low_from_t0_h <= true_tau + 1e-9
        trust["bound_ratio"] = bound.tau_eq_from_t0_h / true_tau if true_tau > 0 else None
        if run.divergence_s is not None:
            trust["bound_start_before_divergence_s"] = run.divergence_s - bound.t0_s
    dt_h = run.interval_s / 3600.0
    true_total = sum(
        arrhenius_acceleration_factor(_damage_temp_c(sample), product) * dt_h
        for sample in run.truth[1:]
    )
    return {
        **trust,
        "interval_s": run.interval_s,
        "reported_tau_eq_h": potency_state.tau_eq_h,
        "true_tau_eq_total_h": true_total,
        "final_verdict": previous,
        "final_ood": previous == OUT_OF_DATE,
        "any_ood": OUT_OF_DATE in anywhere,
        "ood_episodes": episodes[OUT_OF_DATE],
        "first_ood": verdict_first[OUT_OF_DATE],
        "hours": hours,
        "divergence_s": run.divergence_s,
        "ref_s": ref_s,
        "final_falsification": previous == FALSIFICATION,
        "falsification_episodes": episodes[FALSIFICATION],
        "anomaly_episodes": episodes[THERMAL_ANOMALY],
        "any_falsification": FALSIFICATION in anywhere,
        "any_anomaly": THERMAL_ANOMALY in anywhere,
        "any_glitch": GLITCH in anywhere,
        **{f"first_{name}": first_after[name] for name in DETECTORS},
        "first_falsification": verdict_first[FALSIFICATION],
        "first_anomaly": verdict_first[THERMAL_ANOMALY],
    }


def _stats(values: Sequence[float], interval_s: float) -> dict[str, float | None]:
    if not values:
        return {"median_min": None, "p90_min": None, "median_samples": None, "p90_samples": None}
    arr = np.array(values)
    median, p90 = float(np.median(arr)), float(np.percentile(arr, 90))
    return {
        "median_min": median / 60.0,
        "p90_min": p90 / 60.0,
        "median_samples": median / interval_s,
        "p90_samples": p90 / interval_s,
    }


def _count(values: Sequence[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _bound_summary(rows: Sequence[dict]) -> dict:
    """How often the worst-case bound was computed and valid, and how conservative it was."""
    computed = [r for r in rows if r["bound_computed"]]
    ratios = [r["bound_ratio"] for r in computed if r["bound_ratio"] is not None]
    return {
        "computed": len(computed),
        "valid": sum(bool(r["bound_valid"]) for r in computed),
        "ratio_median": float(np.median(ratios)) if ratios else None,
        "ratio_p90": float(np.percentile(ratios, 90)) if ratios else None,
        "ratio_max": float(np.max(ratios)) if ratios else None,
    }


def evaluate_family(
    family: Family, seeds: Sequence[int], box: BoxConfig, monitor: TamperMonitor
) -> dict:
    """Score a family over many seeds and summarise (the numbers behind the tables)."""
    rows, interval_s = [], 600.0
    for seed in seeds:
        run = family.make(seed, box)
        interval_s = run.interval_s
        rows.append(score_run(run, family, monitor))
    return summarise_rows(family, seeds, rows, interval_s)


def summarise_rows(
    family: Family, seeds: Sequence[int], rows: list[dict], interval_s: float
) -> dict:
    """Summarise already scored rows (one per seed, in seed order); see evaluate_family."""
    n = len(rows)
    hours = sum(r["hours"] for r in rows)
    result: dict = {
        "family": family.name,
        "kind": family.kind,
        "expected": family.expected,
        "runs": n,
        "hours": hours,
        "falsification_episodes": sum(r["falsification_episodes"] for r in rows),
        "anomaly_episodes": sum(r["anomaly_episodes"] for r in rows),
        "runs_with_tamper_verdict": sum(r["any_falsification"] for r in rows),
        "runs_with_anomaly_verdict": sum(r["any_anomaly"] for r in rows),
        "runs_with_glitch_verdict": sum(r["any_glitch"] for r in rows),
        "runs_with_divergence": sum(r["divergence_s"] is not None for r in rows),
        "runs_ended_with_tamper": sum(r["final_falsification"] for r in rows),
        "runs_with_ood_verdict": sum(r["any_ood"] for r in rows),
        "runs_ended_ood": sum(r["final_ood"] for r in rows),
        "runs_ood_from_start": sum(bool(r["ood_from_start"]) for r in rows),
        "runs_untrusted": sum(r["untrusted"] for r in rows),
        "runs_level_untrusted": sum(r["trust_level"] == "untrusted" for r in rows),
        "runs_level_low_confidence": sum(r["trust_level"] == "low_confidence" for r in rows),
        "violations": [
            seed
            for seed, r in zip(seeds, rows, strict=True)
            if r["bound_computed"] and not r["bound_valid"]
        ],
        "bound": _bound_summary(rows),
        "final_verdicts": _count([r["final_verdict"] for r in rows]),
    }
    if family.kind == "tamper":
        flagged = [r for r in rows if r["divergence_s"] is not None and r["untrusted"]]
        result["flagged_untrusted_rate"] = len(flagged) / n
        found = [r["first_falsification"] for r in rows if r["first_falsification"] is not None]
        result["detection_rate"] = len(found) / n
        result["correct_class_rate"] = len(found) / n
        result["flagged_at_end_rate"] = sum(r["final_falsification"] for r in rows) / n
        result["delay"] = _stats(found, interval_s)
        result["by_detector"] = {}
        for name in DETECTORS:
            times = [r[f"first_{name}"] for r in rows if r[f"first_{name}"] is not None]
            result["by_detector"][name] = {"rate": len(times) / n, **_stats(times, interval_s)}
    elif family.kind == "physical":
        found = [r["first_anomaly"] for r in rows if r["first_anomaly"] is not None]
        result["detection_rate"] = len(found) / n
        result["correct_class_rate"] = (
            sum(r["any_anomaly"] and not r["any_falsification"] for r in rows) / n
        )
        result["delay"] = _stats(found, interval_s)
    return result


# ----------------------------------------------------------------------------- the CUSUM sweep


def _cusum_episodes(monitor: TamperMonitor, runs: Sequence[RunData]) -> tuple[int, float]:
    """CUSUM alarm episodes (either side) and simulated hours over a set of clean runs."""
    episodes, hours = 0, 0.0
    for run in runs:
        hours += (run.readings[-1].t_s - run.readings[0].t_s) / 3600.0
        monitor.reset()
        previous = False
        for reading in run.readings:
            state = monitor.update(reading)
            flag = state.flag_cusum_pos or state.flag_cusum_neg
            episodes += flag and not previous
            previous = flag
    return int(episodes), hours


def select_setting(table: Sequence[dict], target_per_1000h: float) -> dict | None:
    """The selection rule: false alarms at most the target, then the smallest median delay.

    Ties: fewer false alarms, then the larger h.
    """
    eligible = [
        row
        for row in table
        if row["false_alarms_per_1000h"] <= target_per_1000h
        and row["cusum_neg_median_delay_min"] is not None
    ]
    if not eligible:
        return None
    return min(
        eligible,
        key=lambda r: (r["cusum_neg_median_delay_min"], r["false_alarms_per_1000h"], -r["h"]),
    )


def run_sweep(
    families: dict[str, Family], seeds: Sequence[int], box: BoxConfig, product: ProductConfig
) -> dict:
    """Grid over k and h on the TRAINING seeds. Returns the table and the selected setting.

    The selection uses the nominal box only. Two extra columns show the same false-alarm count on
    boxes that differ from the calibration, for information.
    """
    config = load_detector_config()
    clean_names = ("baseline_ok", "shock_drop", "sensor_glitch", "freeze_event")
    spoof_names = ("spoof_attempt", "hidden_spoilage", "injected_offset", "injected_replay")
    cache: dict[str, list[RunData]] = {
        n: [families[n].make(seed, box) for seed in seeds] for n in clean_names + spoof_names
    }
    variants = {
        key: mismatch_boxes(box)[label]
        for key, label in (
            ("plus15", "tau, R_th and capacity +15%"),
            ("minus15", "tau, R_th and capacity -15%"),
        )
    }  # noqa: E501
    variant_runs = {
        key: [
            families[n].make(seed, vbox)
            for n in clean_names
            for seed in seeds[:MISMATCH_SWEEP_SEEDS]
        ]
        for key, vbox in variants.items()
    }  # noqa: E501
    clean_runs = [run for n in clean_names for run in cache[n]]
    twin = load_twin_params()
    table = []
    for k in SWEEP_K:
        for h in SWEEP_H:
            cfg = config.model_copy(update={"cusum_k": k, "cusum_h": h})
            monitor = TamperMonitor(
                twin, cfg, product.hard_limit_consecutive_samples, box.sensor_sigma_c
            )
            episodes, hours = _cusum_episodes(monitor, clean_runs)
            delays, total = [], 0
            for name in spoof_names:
                for run in cache[name]:
                    if run.divergence_s is None:
                        continue
                    total += 1
                    monitor.reset()
                    for reading in run.readings:
                        state = monitor.update(reading)
                        if state.t_s >= run.divergence_s and state.flag_cusum_neg:
                            delays.append(state.t_s - run.divergence_s)
                            break
            row = {
                "k": k,
                "h": h,
                "false_alarm_episodes": episodes,
                "clean_hours": hours,
                "false_alarms_per_1000h": episodes / hours * 1000.0,
                "cusum_neg_detection_rate": len(delays) / total if total else None,
                "cusum_neg_median_delay_min": float(np.median(delays)) / 60.0 if delays else None,
            }
            for key, runs in variant_runs.items():
                v_episodes, v_hours = _cusum_episodes(monitor, runs)
                row[f"false_alarms_per_1000h_{key}"] = v_episodes / v_hours * 1000.0
            table.append(row)
    target = config.cusum_false_alarm_target_per_1000h
    return {
        "target_per_1000h": target,
        "table": table,
        "selected": select_setting(table, target),
    }


# ----------------------------------------------------------------------------- mismatch boxes


def mismatch_boxes(box: BoxConfig) -> dict[str, BoxConfig]:
    """Real boxes that differ from the nominal one the twin was calibrated on."""
    return {
        "nominal": box,
        "tau, R_th and capacity +15%": dataclasses.replace(
            box,
            box_tau_h=box.box_tau_h * 1.15,
            box_R_th_k_per_w=box.box_R_th_k_per_w * 1.15,
            box_cooling_capacity_w=box.box_cooling_capacity_w * 1.15,
        ),
        "tau, R_th and capacity -15%": dataclasses.replace(
            box,
            box_tau_h=box.box_tau_h * 0.85,
            box_R_th_k_per_w=box.box_R_th_k_per_w * 0.85,
            box_cooling_capacity_w=box.box_cooling_capacity_w * 0.85,
        ),
        "ambient sensor noise x2": dataclasses.replace(
            box, sensor_sigma_ambient_c=box.sensor_sigma_ambient_c * 2.0
        ),
    }


def summarise_boxes(
    families: dict[str, Family],
    seeds: Sequence[int],
    boxes: dict[str, BoxConfig],
    monitor: TamperMonitor,
) -> dict:
    """Per box variant: tamper detection, delay and false tamper verdicts on the other families."""
    out = {}
    for label, variant in boxes.items():
        evaluated = {n: evaluate_family(f, seeds, variant, monitor) for n, f in families.items()}
        tamper = [e for e in evaluated.values() if e["kind"] == "tamper"]
        notamper = [e for e in evaluated.values() if e["kind"] in ("clean", "physical")]
        control = evaluated.get("harmless_hold")
        delays = [e["delay"]["median_min"] for e in tamper if e["delay"]["median_min"] is not None]
        hours = sum(e["hours"] for e in notamper)
        out[label] = {
            "tamper_detection_rate": float(np.mean([e["detection_rate"] for e in tamper])),
            "median_delay_min": float(statistics.median(delays)) if delays else None,
            "false_tamper_verdicts": sum(e["runs_with_tamper_verdict"] for e in notamper),
            "false_tamper_episodes_per_1000h": sum(e["falsification_episodes"] for e in notamper)
            / hours
            * 1000.0,
            "physical_correct_class_rate": float(
                np.mean(
                    [e["correct_class_rate"] for e in evaluated.values() if e["kind"] == "physical"]
                )
            ),
            "false_by_family": {e["family"]: e["runs_with_tamper_verdict"] for e in notamper},
            "no_tamper_runs": sum(e["runs"] for e in notamper),
            "false_tamper_ended": sum(e["runs_ended_with_tamper"] for e in notamper),
            "ood_verdict_runs": sum(e["runs_with_ood_verdict"] for e in notamper),
            "ood_ended_runs": sum(e["runs_ended_ood"] for e in notamper),
            "ood_from_start_runs": sum(e["runs_ood_from_start"] for e in notamper),
            "untrusted_runs": sum(e["runs_untrusted"] for e in notamper),
            "false_ended_by_family": {e["family"]: e["runs_ended_with_tamper"] for e in notamper},
            "ood_by_family": {e["family"]: e["runs_with_ood_verdict"] for e in notamper},
            "control_runs_with_tamper_verdict": (
                None if control is None else control["runs_with_tamper_verdict"]
            ),
            "families": evaluated,
        }
    return out


# ----------------------------------------------------------------------------- the ood sweep


def phase3_config(config: DetectorConfig) -> DetectorConfig:
    """The Phase 3 behaviour: the self-check can never judge the gain, so it never fires."""
    return config.model_copy(update={"ood_max_gain_se": 1e-12})


def _light_score(monitor: TamperMonitor, run: RunData, kind: str) -> dict[str, bool]:
    """The few facts the ood sweep needs from one run (no trust or bound bookkeeping)."""
    monitor.reset()
    detected = ood = tamper = False
    previous = "ok"
    for reading in run.readings:
        state = monitor.update(reading)
        previous = state.verdict
        ood = ood or state.verdict == OUT_OF_DATE
        tamper = tamper or state.verdict == FALSIFICATION
        if (
            kind == "tamper"
            and run.divergence_s is not None
            and state.t_s >= run.divergence_s
            and state.verdict == FALSIFICATION
        ):
            detected = True
    return {
        "ood": ood,
        "tamper": tamper,
        "ended_tamper": previous == FALSIFICATION,
        "detected": detected,
    }


def select_ood_setting(
    table: Sequence[dict], false_target: float, loss_target: float
) -> dict | None:
    """Rule: nominal false out-of-date share at most the target, and no nominal lie family
    loses more than the loss target of its detection rate compared with the self-check switched
    off; then the smallest mean share of +/-15% clean and physical runs that END with a tamper
    verdict (the quantity the Phase 3B target is about, compared to the nearest percentage
    point); then the largest mean out-of-date share on those boxes.
    Ties: smaller window, larger margin, smaller sustained count.
    """
    eligible = [
        row
        for row in table
        if row["nominal_false_ood_rate"] <= false_target and row["max_lie_loss"] <= loss_target
    ]
    if not eligible:
        return None
    return min(
        eligible,
        key=lambda r: (
            round((r["plus15_ended_tamper_rate"] + r["minus15_ended_tamper_rate"]) * 50.0),
            -(r["plus15_ood_rate"] + r["minus15_ood_rate"]) / 2.0,
            r["window"],
            -r["margin"],
            r["sustained"],
        ),
    )


def run_ood_sweep(
    families: dict[str, Family],
    lies: dict[str, Family],
    seeds: Sequence[int],
    box: BoxConfig,
    product: ProductConfig,
    grid: tuple[Sequence[int], Sequence[float], Sequence[int]] | None = None,
) -> dict:
    """Grid over the self-check's window, margin and sustained count on the TRAINING seeds."""
    windows, margins, sustained_counts = grid or (
        OOD_SWEEP_WINDOWS,
        OOD_SWEEP_MARGINS,
        OOD_SWEEP_SUSTAINED,
    )
    config = load_detector_config()
    twin = load_twin_params()
    boxes = mismatch_boxes(box)
    variants = {
        "plus15": boxes["tau, R_th and capacity +15%"],
        "minus15": boxes["tau, R_th and capacity -15%"],
    }
    lie_names = [n for n in LIE_FAMILIES_PHASE3] + [
        "injected_drift_0.5_clean",
        "injected_drift_1_fault",
    ]
    everything = {**families, **lies}
    mismatch_seeds = list(seeds)[:OOD_SWEEP_MISMATCH_SEEDS]
    nominal = {
        n: [everything[n].make(sd, box) for sd in seeds] for n in CLEAN_NAMES + PHYSICAL_NAMES
    }
    lie_runs = {n: [everything[n].make(sd, box) for sd in seeds] for n in lie_names}
    mismatched = {
        key: {
            n: [everything[n].make(sd, vbox) for sd in mismatch_seeds]
            for n in CLEAN_NAMES + PHYSICAL_NAMES
        }
        for key, vbox in variants.items()
    }
    table = []
    base_monitor = TamperMonitor(
        twin, phase3_config(config), product.hard_limit_consecutive_samples, box.sensor_sigma_c
    )
    baseline_detection = {
        n: sum(_light_score(base_monitor, r, "tamper")["detected"] for r in lie_runs[n])
        / len(lie_runs[n])
        for n in lie_names
    }
    for window in windows:
        for margin in margins:
            for sustained in sustained_counts:
                cfg = config.model_copy(
                    update={
                        "ood_window_samples": window,
                        "ood_gain_margin": margin,
                        "ood_sustained_samples": sustained,
                    }
                )
                monitor = TamperMonitor(
                    twin, cfg, product.hard_limit_consecutive_samples, box.sensor_sigma_c
                )

                def share(runs_by_name, kind, field, _m=monitor):
                    scores = [
                        _light_score(_m, r, kind)[field] for rs in runs_by_name.values() for r in rs
                    ]
                    return sum(scores) / len(scores)

                lie_detection = {
                    n: share({n: lie_runs[n]}, "tamper", "detected") for n in lie_names
                }
                row = {
                    "window": window,
                    "margin": margin,
                    "sustained": sustained,
                    "nominal_false_ood_rate": share(nominal, "clean", "ood"),
                    "nominal_ended_tamper_rate": share(nominal, "clean", "ended_tamper"),
                    "min_lie_detection": min(lie_detection.values()),
                    "max_lie_loss": max(
                        baseline_detection[n] - lie_detection[n] for n in lie_names
                    ),
                    "lie_detection": lie_detection,
                    "lie_detection_without_check": baseline_detection,
                }
                for key, runs in mismatched.items():
                    row[f"{key}_ood_rate"] = share(runs, "clean", "ood")
                    row[f"{key}_ended_tamper_rate"] = share(runs, "clean", "ended_tamper")
                    row[f"{key}_any_tamper_rate"] = share(runs, "clean", "tamper")
                table.append(row)
    return {
        "false_target": OOD_FALSE_TARGET,
        "lie_loss_target": OOD_LIE_LOSS_TARGET,
        "lie_families": lie_names,
        "table": table,
        "selected": select_ood_setting(table, OOD_FALSE_TARGET, OOD_LIE_LOSS_TARGET),
    }


# ----------------------------------------------------------------------------- the whole study


def run_evaluation(quick: bool = False) -> dict:
    box, product = load_box_config(), load_product_config()
    families = build_families()
    train = TRAIN_SEEDS[:QUICK_COUNT] if quick else TRAIN_SEEDS
    test = TEST_SEEDS[:QUICK_COUNT] if quick else TEST_SEEDS
    mismatch_seeds = test if quick else TEST_SEEDS[:MISMATCH_COUNT]
    config = load_detector_config()
    twin = load_twin_params()
    monitor = TamperMonitor(
        twin, config, product.hard_limit_consecutive_samples, box.sensor_sigma_c
    )
    lies = build_lie_families()
    sweep = run_sweep(families, train, box, product)
    quick_grid = (
        [config.ood_window_samples],
        [config.ood_gain_margin],
        [config.ood_sustained_samples],
    )
    ood_sweep = run_ood_sweep(families, lies, train, box, product, quick_grid if quick else None)
    final = {n: evaluate_family(f, test, box, monitor) for n, f in families.items()}
    lie_final = {n: evaluate_family(f, test, box, monitor) for n, f in lies.items()}
    mismatch = summarise_boxes(families, mismatch_seeds, mismatch_boxes(box), monitor)
    before_monitor = TamperMonitor(
        twin, phase3_config(config), product.hard_limit_consecutive_samples, box.sensor_sigma_c
    )
    before_final = {n: evaluate_family(f, test, box, before_monitor) for n, f in families.items()}
    before_mismatch = summarise_boxes(families, mismatch_seeds, mismatch_boxes(box), before_monitor)
    dev_seeds = DEVELOPMENT_SEEDS[:QUICK_COUNT] if quick else DEVELOPMENT_SEEDS
    dev_final = {n: evaluate_family(f, dev_seeds, box, monitor) for n, f in families.items()}
    dev_lies = {n: evaluate_family(f, dev_seeds, box, monitor) for n, f in lies.items()}
    boxes = mismatch_boxes(box)
    lie_mismatch = {
        label: {
            n: evaluate_family(f, mismatch_seeds, boxes[label], monitor) for n, f in lies.items()
        }
        for label in ("tau, R_th and capacity +15%", "tau, R_th and capacity -15%")
    }
    return {
        "note": FOOTER,
        "quick": quick,
        "dev_final": dev_final,
        "dev_lies": dev_lies,
        "lie_mismatch": lie_mismatch,
        "ledger": [list(row) for row in SEED_LEDGER],
        "seeds": {
            "calibration": [CALIBRATION_SEEDS[0], CALIBRATION_SEEDS[-1]],
            "training": [train[0], train[-1], len(train)],
            "test": [test[0], test[-1], len(test)],
            "development": [dev_seeds[0], dev_seeds[-1], len(dev_seeds)],
            "mismatch": [mismatch_seeds[0], mismatch_seeds[-1], len(mismatch_seeds)],
        },
        "config": {"cusum_k": config.cusum_k, "cusum_h": config.cusum_h},
        "ood_config": {
            "window": config.ood_window_samples,
            "margin": config.ood_gain_margin,
            "sustained": config.ood_sustained_samples,
            "max_gain_se": config.ood_max_gain_se,
            "band": [config.ood_gain_band_low, config.ood_gain_band_high],
        },
        "twin": twin.model_dump(),
        "sweep": sweep,
        "ood_sweep": ood_sweep,
        "final": final,
        "lies": lie_final,
        "mismatch": mismatch,
        "before_final": before_final,
        "before_mismatch": before_mismatch,
    }


# ----------------------------------------------------------------------------- text output


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.0f}%"


def _num(value: float | None, digits: int = 0) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def render_markdown(study: dict) -> str:
    cfg = study["config"]
    seeds = study["seeds"]
    lines = [
        "# Phase 3B: Detector evaluation (Phase 3 tables re-measured, then the Phase 3B additions)",
        "",
        f"Measured with the real simulator, the real monitor and the stored calibration. {FOOTER}",
        "",
        "## Seed blocks (disjoint)",
        "",
        f"- calibration: seeds {seeds['calibration'][0]} to {seeds['calibration'][1]} (fit the twin only)",  # noqa: E501
        f"- training: seeds {seeds['training'][0]} to {seeds['training'][1]} "
        f"({seeds['training'][2]} per family; used only for the sweep below)",
        f"- test: seeds {seeds['test'][0]} to {seeds['test'][1]} "
        f"({seeds['test'][2]} per family; final scoring)",
        f"- mismatch runs: the first {seeds['mismatch'][2]} test seeds per family",
        "",
        "## CUSUM sweep (training seeds)",
        "",
        "False alarms are CUSUM alarm episodes (either side) on the clean families baseline_ok, "
        "shock_drop, sensor_glitch and freeze_event, per 1000 simulated hours. Delay is the "
        "median time from the first divergence to the negative-side CUSUM alarm on the spoof "
        "families (spoof_attempt, hidden_spoilage, injected offset, injected replay).",
        "",
        "| k | h | false alarms / 1000 h | CUSUM-neg detection | CUSUM-neg median delay (min) "
        "| false alarms / 1000 h on a +15% box | on a -15% box |",  # noqa: E501
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in study["sweep"]["table"]:
        lines.append(
            f"| {row['k']} | {row['h']} | {row['false_alarms_per_1000h']:.2f} "
            f"| {_pct(row['cusum_neg_detection_rate'])} "
            f"| {_num(row['cusum_neg_median_delay_min'], 1)} "
            f"| {row['false_alarms_per_1000h_plus15']:.1f} | {row['false_alarms_per_1000h_minus15']:.1f} |"  # noqa: E501
        )
    sel = study["sweep"]["selected"]
    lines += [
        "",
        f"Selection rule: keep the settings whose false alarms are at most "
        f"{study['sweep']['target_per_1000h']} per 1000 h, then take the smallest median delay "
        "(ties: fewer false alarms, then the larger h). "
        + (
            f"The rule selects k = {sel['k']}, h = {sel['h']}."
            if sel
            else "No setting met the target."
        )
        + f" The settings in config/detectors.yaml are k = {cfg['cusum_k']}, h = {cfg['cusum_h']}.",
        "",
        "## Final scoring (test seeds)",
        "",
        "Tamper families. Detection = a falsification verdict at or after the first divergence "
        "(the first sample where the reported temperature is more than the configured "
        "divergence threshold from the truth). Delay is measured from that divergence.",
        "",
        "| family | runs | detected | still flagged at the end | delay median (min / samples) "
        "| delay p90 (min / samples) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, e in study["final"].items():
        if e["kind"] != "tamper":
            continue
        d = e["delay"]
        lines.append(
            f"| {name} | {e['runs']} | {_pct(e['detection_rate'])} "
            f"| {_pct(e['flagged_at_end_rate'])} "
            f"| {_num(d['median_min'])} / {_num(d['median_samples'], 1)} "
            f"| {_num(d['p90_min'])} / {_num(d['p90_samples'], 1)} |"
        )
    lines += [
        "",
        "Per detector on the tamper families (share of runs flagged at or after the divergence, "
        "and median delay in minutes):",
        "",
        "| family | " + " | ".join(DETECTORS) + " |",
        "|---|" + "---:|" * len(DETECTORS),
    ]
    for name, e in study["final"].items():
        if e["kind"] != "tamper":
            continue
        cells = [
            f"{_pct(e['by_detector'][d]['rate'])} / {_num(e['by_detector'][d]['median_min'])}"
            for d in DETECTORS
        ]
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "Physical families (the correct verdict is thermal anomaly, not tamper). Detection = a "
        "thermal-anomaly verdict after the physical event starts; correct class = anomaly seen "
        "and no tamper verdict at any time.",
        "",
        "| family | runs | anomaly detected | correct class | delay median (min) | tamper verdicts (runs) |",  # noqa: E501
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, e in study["final"].items():
        if e["kind"] != "physical":
            continue
        lines.append(
            f"| {name} | {e['runs']} | {_pct(e['detection_rate'])} | {_pct(e['correct_class_rate'])} "  # noqa: E501
            f"| {_num(e['delay']['median_min'])} | {e['runs_with_tamper_verdict']} |"
        )
    lines += [
        "",
        "Clean and control families (any tamper verdict is a false positive).",
        "",
        "| family | runs | tamper verdicts (runs) | tamper episodes | glitch verdicts (runs) | anomaly verdicts (runs) |",  # noqa: E501
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, e in study["final"].items():
        if e["kind"] not in ("clean", "control"):
            continue
        lines.append(
            f"| {name} | {e['runs']} | {e['runs_with_tamper_verdict']} | {e['falsification_episodes']} "  # noqa: E501
            f"| {e['runs_with_glitch_verdict']} | {e['runs_with_anomaly_verdict']} |"
        )
    lines += [
        "",
        "## Mismatch: the real box differs from the calibration",
        "",
        "The twin stays calibrated on the nominal box. 'False tamper' counts tamper verdicts on "
        "the clean and physical families (the control family is reported in the table above).",
        "",
        "| real box | tamper detection (mean) | median delay (min) | false tamper verdicts | false tamper episodes / 1000 h | physical correct class |",  # noqa: E501
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, m in study["mismatch"].items():
        lines.append(
            f"| {label} | {_pct(m['tamper_detection_rate'])} | {_num(m['median_delay_min'])} "
            f"| {m['false_tamper_verdicts']} | {m['false_tamper_episodes_per_1000h']:.2f} "
            f"| {_pct(m['physical_correct_class_rate'])} |"
        )
    lines += [
        "",
        "False tamper verdicts by family (runs with a tamper verdict, out of the runs per family):",
        "",
        "| real box | "
        + " | ".join(next(iter(study["mismatch"].values()))["false_by_family"])
        + " |",
        "|---|" + "---:|" * len(next(iter(study["mismatch"].values()))["false_by_family"]),
    ]
    for label, m in study["mismatch"].items():
        lines.append(
            f"| {label} | " + " | ".join(str(v) for v in m["false_by_family"].values()) + " |"
        )
    lines += _markdown_3b(study)
    lines += ["", f"*{FOOTER}*", ""]
    return "\n".join(lines)


def _markdown_3b(study: dict) -> list[str]:
    ood = study["ood_sweep"]
    cfg = study["ood_config"]
    sel = ood["selected"]
    lines = [
        "",
        "## Seed ledger",
        "",
        "| block | seeds | what it was used for | status |",
        "|---|---|---|---|",
        *[f"| {a} | {b} | {c} | {d} |" for a, b, c, d in study["ledger"]],
        "",
        "The final numbers below come from the final block (40001 to 40200; mismatch runs use its "
        "first 100). The development blocks are reported only for comparison.",
        "",
        "## Phase 3B: the twin-out-of-date self-check, threshold sweep (training seeds)",
        "",
        "Tuned on the training seeds only. 'False out-of-date' is the share of NOMINAL-box clean "
        "and physical runs (7 families) in which the verdict twin_out_of_date appeared at any "
        "time. 'Worst lie loss' is the largest drop in detection rate, over the nominal lie families "
        + ", ".join(ood["lie_families"])
        + ", compared with the self-check switched off. The +15% and -15% columns are the share of clean and physical runs on a box whose "
        "tau, R_th and capacity differ by that much in which twin_out_of_date appeared, and the "
        "share that END with a tamper verdict.",
        "",
        "| window | margin | sustained | false out-of-date (nominal) | worst lie loss "
        "| +15% out-of-date | +15% ends tamper | -15% out-of-date | -15% ends tamper |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in ood["table"]:
        lines.append(
            f"| {r['window']} | {r['margin']} | {r['sustained']} "
            f"| {_pct(r['nominal_false_ood_rate'])} | {_pct(r['max_lie_loss'])} "
            f"| {_pct(r['plus15_ood_rate'])} | {_pct(r['plus15_ended_tamper_rate'])} "
            f"| {_pct(r['minus15_ood_rate'])} | {_pct(r['minus15_ended_tamper_rate'])} |"
        )
    lines += [
        "",
        f"Selection rule: keep the settings whose nominal false out-of-date share is at most "
        f"{_pct(ood['false_target'])} and whose worst lie loss is at most "
        f"{_pct(ood['lie_loss_target'])}; then take the smallest mean share of +/-15% runs that end with a tamper verdict "
        "(to the nearest percentage point), then the largest mean out-of-date share (ties: smaller "
        "window, larger margin, smaller sustained count). "
        + (
            f"The rule selects window = {sel['window']}, margin = {sel['margin']}, "
            f"sustained = {sel['sustained']}."
            if sel
            else "No setting met the targets."
        )
        + f" The settings in config/detectors.yaml are window = {cfg['window']}, "
        f"margin = {cfg['margin']}, sustained = {cfg['sustained']}.",
        "",
        "## Phase 3B: lie families (test seeds)",
        "",
        "Drift lies grow linearly from the start at the stated rate (kelvin per hour); the mimic "
        "is an attacker with a model of the box and is EXPECTED to be invisible to physics. "
        "'Detected' = a falsification verdict at or after the first divergence. 'Flagged "
        "untrusted' = the monitor declared the data untrusted (falsification or twin out of "
        "date). Delay is from the first divergence (minutes / samples).",
        "",
        "| family | runs | detected | flagged untrusted | ends as | delay median | delay p90 |",
        "|---|---:|---:|---:|---|---:|---:|",
    ]
    for name, e in study["lies"].items():
        d = e["delay"]
        ends = ", ".join(f"{v} {k}" for k, v in sorted(e["final_verdicts"].items()))
        lines.append(
            f"| {name} | {e['runs']} | {_pct(e['detection_rate'])} "
            f"| {_pct(e['flagged_untrusted_rate'])} | {ends} "
            f"| {_num(d['median_min'])} / {_num(d['median_samples'], 1)} "
            f"| {_num(d['p90_min'])} / {_num(d['p90_samples'], 1)} |"
        )
    lines += [
        "",
        "## Phase 3B: mismatch, with the new verdict space",
        "",
        "Clean and physical families on boxes that differ from the calibration (first "
        f"{study['seeds']['mismatch'][2]} test seeds per family). 'Any tamper' = a tamper verdict "
        "at any time; 'ends tamper' = the last verdict is a tamper verdict; 'out of date' = "
        "twin_out_of_date appeared; 'from start' = already out of date in the first window.",
        "",
        "| real box | runs | any tamper | ends tamper | out of date | ends out of date "
        "| out of date from start | untrusted |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, m in study["mismatch"].items():
        lines.append(
            f"| {label} | {m['no_tamper_runs']} | {m['false_tamper_verdicts']} "
            f"| {m['false_tamper_ended']} | {m['ood_verdict_runs']} | {m['ood_ended_runs']} "
            f"| {m['ood_from_start_runs']} | {m['untrusted_runs']} |"
        )
    lines += [
        "",
        "Runs that END with a tamper verdict, by family:",
        "",
        "| real box | "
        + " | ".join(next(iter(study["mismatch"].values()))["false_ended_by_family"])
        + " |",
        "|---|" + "---:|" * len(next(iter(study["mismatch"].values()))["false_ended_by_family"]),
    ]
    for label, m in study["mismatch"].items():
        lines.append(
            f"| {label} | " + " | ".join(str(v) for v in m["false_ended_by_family"].values()) + " |"
        )
    lines += [
        "",
        "## Phase 3B: before and after (same test seeds)",
        "",
        "'Before' is the Phase 3 behaviour (the same code with the self-check switched off). "
        "Detection and delay are for the five Phase 3 lie families.",
        "",
        "| family | detected before | detected after | delay median before (min) "
        "| delay median after (min) | delay p90 before | delay p90 after |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name in LIE_FAMILIES_PHASE3:
        b, a = study["before_final"][name], study["final"][name]
        lines.append(
            f"| {name} | {_pct(b['detection_rate'])} | {_pct(a['detection_rate'])} "
            f"| {_num(b['delay']['median_min'])} | {_num(a['delay']['median_min'])} "
            f"| {_num(b['delay']['p90_min'])} | {_num(a['delay']['p90_min'])} |"
        )

    def false_total(block: dict, key: str) -> int:
        return sum(e[key] for e in block.values() if e["kind"] in ("clean", "physical"))

    control_b = study["before_final"]["harmless_hold"]["runs_with_tamper_verdict"]
    control_a = study["final"]["harmless_hold"]["runs_with_tamper_verdict"]
    lines += [
        "",
        "| measure (nominal box, test seeds) | before | after |",
        "|---|---:|---:|",
        f"| clean + physical runs with a tamper verdict | "
        f"{false_total(study['before_final'], 'runs_with_tamper_verdict')} "
        f"| {false_total(study['final'], 'runs_with_tamper_verdict')} |",
        f"| clean + physical tamper episodes | "
        f"{false_total(study['before_final'], 'falsification_episodes')} "
        f"| {false_total(study['final'], 'falsification_episodes')} |",
        f"| control (harmless_hold) runs with a tamper verdict | {control_b} | {control_a} |",
        f"| clean + physical runs that went twin_out_of_date | 0 "
        f"| {false_total(study['final'], 'runs_with_ood_verdict')} |",
        "",
        "| real box | any tamper before | any tamper after | ends tamper before | ends tamper after |",
        "|---|---:|---:|---:|---:|",
    ]
    for label in study["mismatch"]:
        b, a = study["before_mismatch"][label], study["mismatch"][label]
        lines.append(
            f"| {label} | {b['false_tamper_verdicts']} | {a['false_tamper_verdicts']} "
            f"| {b['false_tamper_ended']} | {a['false_tamper_ended']} |"
        )
    lines += [
        "",
        "## Phase 3B: the worst-case bound",
        "",
        "For every run the monitor declared untrusted, the bound on the equivalent reference time "
        "accumulated from t0 to the end was compared with the TRUE value (the true temperature "
        "series fed to the potency maths, in the scoring code only). 'Valid' = bound >= true. "
        "Ratio = bound / true.",
        "",
        "| family | runs | untrusted | bound computed | valid | ratio median | ratio p90 | ratio max |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for block in (study["final"], study["lies"]):
        for name, e in block.items():
            b = e["bound"]
            if not b["computed"]:
                continue
            lines.append(
                f"| {name} | {e['runs']} | {e['runs_untrusted']} | {b['computed']} | {b['valid']} "
                f"| {_num(b['ratio_median'], 2)} | {_num(b['ratio_p90'], 2)} | {_num(b['ratio_max'], 2)} |"
            )
    lines += _bound_tables(study)
    return lines


def _bound_rows(block: dict) -> list[str]:
    out = []
    for name, e in block.items():
        b = e["bound"]
        if not b["computed"]:
            continue
        out.append(
            f"| {name} | {e['runs']} | {e['runs_level_untrusted']} | {b['computed']} | {b['valid']} "
            f"| {_num(b['ratio_median'], 2)} | {_num(b['ratio_p90'], 2)} | {_num(b['ratio_max'], 2)} |"
        )
    return out


def _bound_tables(study: dict) -> list[str]:
    head = [
        "| family | runs | level untrusted | bound computed | valid | ratio median | ratio p90 | ratio max |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    lines = ["", "## Phase 3B fix: bound validity, three places", ""]
    lines += ["### A. Nominal box, FINAL seeds (40001 to 40200)", "", *head]
    lines += _bound_rows(study["final"]) + _bound_rows(study["lies"])
    viol = sorted(
        {
            s
            for blk in (study["final"], study["lies"])
            for e in blk.values()
            for s in e["violations"]
        }
    )
    lines += ["", f"Violations on the nominal box, final seeds: {viol if viol else 'none'}."]
    lines += [
        "",
        "### B. Nominal box, DEVELOPMENT seeds (20001 to 20200), for comparison",
        "",
        *head,
    ]
    lines += _bound_rows(study["dev_final"]) + _bound_rows(study["dev_lies"])
    dviol = sorted(
        {
            s
            for blk in (study["dev_final"], study["dev_lies"])
            for e in blk.values()
            for s in e["violations"]
        }
    )
    lines += ["", f"Violations on the development seeds: {dviol if dviol else 'none'}."]
    for label, block in study["lie_mismatch"].items():
        lines += [
            "",
            f"### C. Mismatched box ({label}), lie families, first 100 final seeds",
            "",
            *head,
        ]
        lines += _bound_rows(block)
        n = sum(e["bound"]["computed"] for e in block.values())
        bad = sum(len(e["violations"]) for e in block.values())
        lines += [
            "",
            f"Bounds computed: {n}; violations: {bad}"
            + (" (reported as a limitation, not a stop)." if bad else "."),
        ]
    lines += ["", "### Trust levels of clean and physical runs on mismatched boxes", ""]
    lines += [
        "| real box | runs | trusted | low confidence | untrusted |",
        "|---|---:|---:|---:|---:|",
    ]
    for label, m in study["mismatch"].items():
        notamper = [e for e in m["families"].values() if e["kind"] in ("clean", "physical")]
        runs = sum(e["runs"] for e in notamper)
        lc = sum(e["runs_level_low_confidence"] for e in notamper)
        un = sum(e["runs_level_untrusted"] for e in notamper)
        lines.append(f"| {label} | {runs} | {runs - lc - un} | {lc} | {un} |")
    lines += ["", FOOTER]
    return lines


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate the tamper detectors.")
    parser.add_argument("--quick", action="store_true", help="a few seeds per family (for tests)")
    parser.add_argument("--sweep-only", action="store_true", help="print only the CUSUM sweep")
    parser.add_argument(
        "--ood-sweep-only",
        action="store_true",
        help="print only the twin-out-of-date threshold sweep (training seeds)",
    )
    parser.add_argument("--markdown", default=str(DEFAULT_MARKDOWN))
    parser.add_argument("--json", default=str(DEFAULT_JSON))
    args = parser.parse_args(argv)
    if args.sweep_only:
        box, product = load_box_config(), load_product_config()
        sweep = run_sweep(build_families(), TRAIN_SEEDS, box, product)
        for row in sweep["table"]:
            print(row)
        print("selected:", sweep["selected"])
        return 0
    if args.ood_sweep_only:
        box, product = load_box_config(), load_product_config()
        sweep = run_ood_sweep(build_families(), build_lie_families(), TRAIN_SEEDS, box, product)
        for row in sweep["table"]:
            print({k: v for k, v in row.items() if not k.startswith("lie_detection")})
        print(
            "selected:",
            sweep["selected"]
            and {k: v for k, v in sweep["selected"].items() if not k.startswith("lie_detection")},
        )
        print(
            "baseline lie detection (check off):", sweep["table"][0]["lie_detection_without_check"]
        )
        return 0
    study = run_evaluation(quick=args.quick)  # Phases 3 and 3B
    markdown = render_markdown(study)
    _write(Path(args.markdown), markdown)
    _write(Path(args.json), json.dumps(study, indent=1, default=float) + "\n")
    print(markdown)
    print(f"wrote {args.markdown} and {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
