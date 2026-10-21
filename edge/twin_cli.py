"""Commands that show the thermal twin at work: python -m edge twin ... and ... calibrate.

Phase 3B: the view also shows whether the reported data are trusted and, when they are not, the
worst-case bound on the damage (edge/assessment.py).
"""

from __future__ import annotations

import glob
import json
from dataclasses import dataclass
from pathlib import Path

from edge.assessment import PotencyAssessment, TrustAssessor, WorstCaseBound
from edge.calibration import calibrate_from_recordings, write_calibrated_config
from edge.potency import PotencyState
from edge.recorded_source import RecordedSource
from edge.sensor_reading import SensorReading
from edge.tamper_monitor import (
    FALSIFICATION,
    MonitorState,
    TamperMonitor,
    sigma_units,
)
from edge.thermal_twin import DEFAULT_TWIN_PATH
from shared.config import REPO_ROOT, BoxConfig, ProductConfig

DEFAULT_RECORDINGS_DIR = REPO_ROOT / "data" / "recordings"
DEFAULT_CALIBRATION_DIR = REPO_ROOT / "data" / "calibration"
PRINT_EVERY = 12
FOOTER = "Simulation result on a synthetic box. Not real-world evidence."
FLAG_NAMES = (
    ("flag_cusum_pos", "cusum+"),
    ("flag_cusum_neg", "cusum-"),
    ("flag_step", "step"),
    ("flag_state", "state"),
    ("flag_flat", "flat"),
)


@dataclass(frozen=True)
class TwinAnalysis:
    scenario_id: str
    seed: int
    interval_s: float
    readings: list[SensorReading]
    states: list[MonitorState]
    potency: list[PotencyState]
    monitor: TamperMonitor
    first_divergence_s: float | None
    assessments: list[PotencyAssessment]
    bound: WorstCaseBound | None

    def detection_delay_s(self) -> float | None:
        """Seconds from the first divergence to the first falsification verdict at or after it."""
        if self.first_divergence_s is None:
            return None
        for state in self.states:
            if state.t_s >= self.first_divergence_s and state.verdict == FALSIFICATION:
                return state.t_s - self.first_divergence_s
        return None


def analyse(path: Path | str, product: ProductConfig, box: BoxConfig) -> TwinAnalysis:
    """Replay a recording through the tamper monitor and the potency tracker together."""
    recording = Path(path)
    source = RecordedSource(recording)
    source.start()
    monitor = TamperMonitor.from_defaults(product, box)
    assessor = TrustAssessor(product, monitor)
    readings, states, potency, assessments = [], [], [], []
    try:
        while (reading := source.read()) is not None:
            readings.append(reading)
            assessment, potency_state, monitor_state = assessor.update(reading)
            states.append(monitor_state)
            potency.append(potency_state)
            assessments.append(assessment)
    finally:
        source.close()
    header = source.header
    truth_file = recording.with_name(recording.name.removesuffix(".jsonl") + ".ground_truth.json")
    divergence = None
    if truth_file.exists():
        divergence = json.loads(truth_file.read_text(encoding="utf-8")).get("first_divergence_s")
    return TwinAnalysis(
        header["scenario_id"],
        header["seed"],
        header["sample_interval_s"],
        readings,
        states,
        potency,
        monitor,
        divergence,
        assessments,
        assessor.last_bound,
    )


def _hour(seconds: float | None) -> str:
    return "never" if seconds is None else f"{seconds / 3600.0:.2f} h"


def _flags(state: MonitorState) -> str:
    active = [name for attr, name in FLAG_NAMES if getattr(state, attr)]
    return ",".join(active) or "-"


def timeline(analysis: TwinAnalysis) -> list[tuple[str, float, float]]:
    """(verdict, start_s, end_s) per stretch of one verdict; the last ends at the last sample."""
    history = analysis.monitor.verdict_history
    end = analysis.states[-1].t_s
    return [
        (verdict, start, history[i + 1][0] if i + 1 < len(history) else end)
        for i, (start, verdict) in enumerate(history)
    ]


def verdict_summary(analysis: TwinAnalysis) -> str:
    """The verdicts that occurred, in order, for the one-line view."""
    groups: list[list] = []
    for verdict, _, _ in timeline(analysis):
        if verdict == "ok":
            continue
        if groups and groups[-1][0] == verdict:
            groups[-1][1] += 1
        else:
            groups.append([verdict, 1])
    parts = [v if n == 1 else f"{v} (x{n})" for v, n in groups]
    return " > ".join(parts) if parts else "ok"


def print_recording(analysis: TwinAnalysis, out, verbose: bool) -> None:
    print(f"Recording: scenario {analysis.scenario_id}, seed {analysis.seed}", file=out)
    print(
        "\n  sim hour  reported C  twin C  resid (sigma)  flags              verdict"
        "                   potency %",
        file=out,
    )
    last_verdict = None
    for i, (reading, state, pot) in enumerate(
        zip(analysis.readings, analysis.states, analysis.potency, strict=True)
    ):
        if not (verbose or i % PRINT_EVERY == 0 or state.verdict != last_verdict):
            last_verdict = state.verdict
            continue
        last_verdict = state.verdict
        predicted = "   n/a" if state.predicted_c is None else f"{state.predicted_c:6.2f}"
        print(
            f"  {state.t_s / 3600.0:8.2f}  {reading.temp_c:10.2f}  {predicted}  "
            f"{sigma_units(state.residual_sigma):>13}  {_flags(state):<18} {state.verdict:<24}"
            f" {pot.potency * 100:8.3f}",
            file=out,
        )
    print("\nFirst alarm per detector:", file=out)
    for name in ("cusum_pos", "cusum_neg", "impossible_step", "impossible_state", "flat_line"):
        print(f"  {name:<17} {_hour(analysis.monitor.first_alarm_s.get(name))}", file=out)
    print("\nVerdict timeline:", file=out)
    for verdict, start, end in timeline(analysis):
        print(f"  {start / 3600.0:7.2f} h to {end / 3600.0:7.2f} h  {verdict}", file=out)
    print("\nGround truth (used only for this summary):", file=out)
    print(f"  true divergence starts  {_hour(analysis.first_divergence_s)}", file=out)
    delay = analysis.detection_delay_s()
    if analysis.first_divergence_s is None:
        print("  detection delay         n/a (no divergence)", file=out)
    elif delay is None:
        print("  detection delay         not detected", file=out)
    else:
        print(
            f"  detection delay         {delay / 60.0:.0f} minutes"
            f" ({delay / analysis.interval_s:.0f} samples)",
            file=out,
        )
    print_trust(analysis, out)
    print(f"\n{FOOTER}", file=out)


def trust_summary(analysis: TwinAnalysis) -> str:
    """Short trust text for the one-line view."""
    final = analysis.assessments[-1]
    if final.trusted:
        return "trusted"
    if final.trust_level == "low_confidence":
        return f"low confidence from {final.untrusted_since_s / 3600.0:.1f} h"
    return f"untrusted from {final.untrusted_since_s / 3600.0:.1f} h"


def print_trust(analysis: TwinAnalysis, out) -> None:
    """Is the reported data trusted, is the twin in date, and what is the worst case?"""
    final = analysis.assessments[-1]
    state = analysis.states[-1]
    print("\nTrust:", file=out)
    print(f"  trust level     {final.trust_level}", file=out)
    if final.trusted:
        print("  reported data   trusted (no evidence against them)", file=out)
    elif final.trust_level == "low_confidence":
        print(
            f"  reported data   LOW CONFIDENCE since hour {final.untrusted_since_s / 3600.0:.2f}"
            f" ({final.trust_reason})",
            file=out,
        )
        print(f"  {final.operator_message}", file=out)
    else:
        print(
            f"  reported data   NOT trusted since hour {final.untrusted_since_s / 3600.0:.2f}"
            f" ({final.trust_reason})",
            file=out,
        )
    if state.twin_out_of_date:
        start = " from the first window" if state.out_of_date_from_start else ""
        print(
            f"  twin            out of date{start}: the box differs from the calibration", file=out
        )
    elif analysis.monitor.self_check_off:
        print(
            "  twin            self-check switched off (a physical proof of falsification was "
            "found)",
            file=out,
        )
    elif state.gain is None:
        print("  twin            in date (gain not measurable: too little variation)", file=out)
    else:
        print(
            f"  twin            in date (gain {state.gain:.2f}, "
            f"drift {state.drift_c_per_h:+.2f} K per hour)",
            file=out,
        )
    reported = final.reported_shelf_life_used_fraction * 100.0
    if final.trusted:
        print(f"  shelf life used {reported:.1f} percent (reported)", file=out)
        return
    if final.trust_level == "low_confidence":
        print(
            f"  reported (low confidence): {reported:.1f} percent of shelf life used;"
            " no worst-case bound is given (it needs a twin that matches the box)",
            file=out,
        )
        return
    print(f"  reported (untrusted): {reported:.1f} percent of shelf life used", file=out)
    bound = analysis.bound
    print(
        f"  worst case from hour {bound.t0_h:.2f}: at most "
        f"{bound.shelf_life_used_fraction * 100.0:.1f} percent of shelf life used",
        file=out,
    )
    print(
        f"  interval: between {bound.shelf_life_used_fraction_low * 100.0:.1f} percent (cooling "
        f"worked fully) and {bound.shelf_life_used_fraction * 100.0:.1f} percent (no cooling) of "
        "shelf life used",
        file=out,
    )
    print(
        "  (only the upper end is meant as a limit; the lower end is not a guarantee: a heat load "
        "could add damage beyond it)",
        file=out,
    )
    print(
        "  (the bound assumes no cooling at all after that hour and an honest ambient reading;"
        " it is an upper bound, not an estimate)",
        file=out,
    )


def print_all(folder: Path, product: ProductConfig, box: BoxConfig, out) -> None:
    print(
        f"{'recording':<22}{'verdicts (in order)':<58}{'divergence':>12}{'delay':>10}  trust",
        file=out,
    )
    for path in sorted(folder.glob("*.jsonl")):
        analysis = analyse(path, product, box)
        delay = analysis.detection_delay_s()
        delay_text = "-" if delay is None else f"{delay / 60.0:.0f} min"
        print(
            f"{analysis.scenario_id:<22}{verdict_summary(analysis):<58}"
            f"{_hour(analysis.first_divergence_s) if analysis.first_divergence_s else '-':>12}"
            f"{delay_text:>10}  {trust_summary(analysis)}",
            file=out,
        )
    print(f"\n{FOOTER}", file=out)


def run_calibrate(directory: Path, out_path: Path, out) -> int:
    """Fit the twin from the calibration recordings and write config/twin_calibrated.yaml."""
    files = sorted(glob.glob(str(directory / "calibration_*.jsonl")))
    if not files:
        print(
            f"no calibration recordings in {directory}; run: "
            "python -m simulator generate-calibration"
        )
        return 2
    result = calibrate_from_recordings(files)
    seeds = [int(Path(f).stem.rsplit("_", 1)[1]) for f in files]
    write_calibrated_config(result, out_path, seeds, [Path(f).name for f in files])
    p = result.params
    print(f"fitted from {len(files)} runs ({result.n_rows} intervals)", file=out)
    print(
        f"  tau = {p.tau_h:.3f} h, dT_cool = {p.dT_cool_c:.2f} K, sigma_r = {p.sigma_r_c:.4f} C",
        file=out,
    )
    print(
        f"  R^2 = {result.r_squared:.4f}, condition number = {result.condition_number:.2f}",
        file=out,
    )
    if result.tau_h_unrestricted is not None:
        print(
            f"  unrestricted fit (diagnostic): tau = {result.tau_h_unrestricted:.3f} h,"
            f" dT_cool = {result.dT_cool_unrestricted:.2f} K",
            file=out,
        )
    print(f"wrote {out_path}", file=out)
    return 0


__all__ = [
    "DEFAULT_CALIBRATION_DIR",
    "DEFAULT_RECORDINGS_DIR",
    "DEFAULT_TWIN_PATH",
    "analyse",
    "print_all",
    "print_trust",
    "print_recording",
    "run_calibrate",
]
