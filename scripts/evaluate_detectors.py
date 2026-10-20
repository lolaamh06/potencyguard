"""Measure the tamper detectors with the real simulator, monitor and calibration (Phase 3).

Run from the repo root:  python scripts/evaluate_detectors.py [--quick]

Seed blocks (disjoint; asserted below and in the tests):
  calibration  9001 to 9010    used only to fit the twin
  training    10001 to 10100   used only to choose the CUSUM settings (the sweep)
  test        20001 to 20200   used only for the final scoring

Everything is a simulation result on a synthetic box. The twin and the simulator use the same
family of equations, so the final scoring is repeated against boxes that differ from the
calibration (mismatch runs).
"""

from __future__ import annotations

import argparse
import dataclasses
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

from edge.detector_config import load_detector_config  # noqa: E402
from edge.sensor_reading import SensorReading  # noqa: E402
from edge.tamper_monitor import FALSIFICATION, GLITCH, THERMAL_ANOMALY, TamperMonitor  # noqa: E402
from edge.thermal_twin import load_twin_params  # noqa: E402
from shared.config import BoxConfig, ProductConfig, load_box_config, load_product_config  # noqa: E402, E501
from simulator.calibration_set import CALIBRATION_SEEDS  # noqa: E402
from simulator.divergence import first_divergence_s  # noqa: E402
from simulator.events import KIND_COOLING, KIND_HEAT  # noqa: E402
from simulator.live import LiveSimulator  # noqa: E402
from simulator.scenario import load_all_scenarios  # noqa: E402
from simulator.truth import TruthSample  # noqa: E402

DEFAULT_MARKDOWN = REPO_ROOT / "docs" / "02-phase-reports" / "phase-03-evaluation.md"
DEFAULT_JSON = REPO_ROOT / "data" / "generated" / "evaluation.json"
FOOTER = "Simulation result on a synthetic box. Not real-world evidence."

TRAIN_SEEDS = list(range(10001, 10101))
TEST_SEEDS = list(range(20001, 20201))
QUICK_COUNT = 5
MISMATCH_SWEEP_SEEDS = 30  # training seeds used for the informational mismatch columns of the sweep
MISMATCH_COUNT = 100  # seeds per family in the mismatch runs (the first ones of the test block)
SWEEP_K = (0.25, 0.5, 1.0)
SWEEP_H = (4.0, 8.0, 12.0)
assert not set(CALIBRATION_SEEDS) & set(TRAIN_SEEDS)
assert not set(CALIBRATION_SEEDS) & set(TEST_SEEDS)
assert not set(TRAIN_SEEDS) & set(TEST_SEEDS)

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
                result = sim.inject(event(rng, sim.engine.now_s))
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


# ----------------------------------------------------------------------------- scoring one run


def score_run(
    run: RunData, family: Family, monitor: TamperMonitor
) -> dict[str, float | int | bool | None]:
    """Run the monitor over one run and return plain scoring numbers."""
    monitor.reset()
    ref_s = {
        "tamper": run.divergence_s,
        "physical": run.physical_start_s,
    }.get(family.kind, 0.0)
    first_after: dict[str, float | None] = {name: None for name in DETECTORS}
    verdict_first: dict[str, float | None] = {
        v: None for v in (FALSIFICATION, THERMAL_ANOMALY, GLITCH)
    }
    episodes = {FALSIFICATION: 0, THERMAL_ANOMALY: 0}
    previous = "ok"
    for reading in run.readings:
        state = monitor.update(reading)
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
    return {
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


def evaluate_family(
    family: Family, seeds: Sequence[int], box: BoxConfig, monitor: TamperMonitor
) -> dict:
    """Score a family over many seeds and summarise (the numbers behind the tables)."""
    rows, interval_s = [], 600.0
    for seed in seeds:
        run = family.make(seed, box)
        interval_s = run.interval_s
        rows.append(score_run(run, family, monitor))
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
    }
    if family.kind == "tamper":
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
            "control_runs_with_tamper_verdict": (
                None if control is None else control["runs_with_tamper_verdict"]
            ),
            "families": evaluated,
        }
    return out


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
    sweep = run_sweep(families, train, box, product)
    final = {n: evaluate_family(f, test, box, monitor) for n, f in families.items()}
    mismatch = summarise_boxes(families, mismatch_seeds, mismatch_boxes(box), monitor)
    return {
        "note": FOOTER,
        "quick": quick,
        "seeds": {
            "calibration": [CALIBRATION_SEEDS[0], CALIBRATION_SEEDS[-1]],
            "training": [train[0], train[-1], len(train)],
            "test": [test[0], test[-1], len(test)],
            "mismatch": [mismatch_seeds[0], mismatch_seeds[-1], len(mismatch_seeds)],
        },
        "config": {"cusum_k": config.cusum_k, "cusum_h": config.cusum_h},
        "twin": twin.model_dump(),
        "sweep": sweep,
        "final": final,
        "mismatch": mismatch,
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
        "# Phase 3: Detector evaluation",
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
    lines += ["", f"*{FOOTER}*", ""]
    return "\n".join(lines)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate the tamper detectors.")
    parser.add_argument("--quick", action="store_true", help="a few seeds per family (for tests)")
    parser.add_argument("--sweep-only", action="store_true", help="print only the CUSUM sweep")
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
    study = run_evaluation(quick=args.quick)
    markdown = render_markdown(study)
    _write(Path(args.markdown), markdown)
    _write(Path(args.json), json.dumps(study, indent=1, default=float) + "\n")
    print(markdown)
    print(f"wrote {args.markdown} and {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
