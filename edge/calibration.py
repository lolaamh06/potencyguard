"""Fit the thermal twin from a clean calibration run by (restricted) ordinary least squares.

The interval from sample n to n+1 (see edge/thermal_twin.py for which sample drives which interval):

    unrestricted:  T[n+1] = a * T[n] + b * T_amb_avg + c * u[n+1] + d
                   theory: a = exp(-dt/tau), b = 1 - a, c = -(1 - a) * dT_cool, d = 0
    restricted:    T[n+1] - T[n] = k * (T_amb_avg - T[n]) - k * dT_cool * u[n+1] + d'
                   with k = 1 - a. This imposes the brief's structure b = 1 - a.

THE ESTIMATE USED is the restricted fit: tau = -dt / ln(1 - k), dT_cool = -(coefficient of u) / k,
and sigma_r = standard deviation of its residuals. Both fits use numpy.linalg.lstsq.

WHY RESTRICTED. T[n] on the right-hand side is a noisy measurement (errors-in-variables), which
biases its coefficient towards zero. In a thermostat-controlled box this is severe in the
unrestricted fit, because the cooling duty follows the box temperature, so very little
independent variation is left in T[n] for the noise to hide behind: on the synthetic data the
unrestricted fit gave a time constant about a third of the true one (see the Phase 3 report). In
the restricted fit the regressor T_amb - T[n] varies mostly with the ambient, which swamps the
noise, and the bias is negligible. The unrestricted fit is still computed and reported as a
consistency check (b should be close to 1 - a and d close to 0) and to show the bias.

Calibration data must be clean (no tamper, glitch or unobserved heat/cooling faults) and must
never be the data used to score detectors: recordings are accepted only if their scenario id
starts with "calibration_" and is not in the evaluation set.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np

from edge.recorded_source import RecordedSource
from edge.sensor_reading import SensorReading
from edge.thermal_twin import TwinParams

CALIBRATION_PREFIX = "calibration_"
# Event kinds that make a run unsuitable for calibration (tamper, or physics the twin cannot see).
FORBIDDEN_EVENT_KINDS = ("spoof", "glitch", "heat_load", "cooling_factor")
# placeholder, not sourced [SOURCE NEEDED]: quality gates for calibration data.
MIN_ROWS = 500
MIN_AMBIENT_STD_C = 2.0
MIN_DUTY_STD = 0.1
MAX_CONDITION_NUMBER = 50.0
DT_TOLERANCE_S = 1e-6


class CalibrationError(ValueError):
    """Raised when calibration data is unsuitable or the fit is not physical."""


@dataclass(frozen=True)
class CalibrationResult:
    params: TwinParams
    k: float  # restricted fit: 1 - exp(-dt/tau)
    c: float  # restricted fit: coefficient of the cooling duty (= -k * dT_cool)
    d: float  # restricted fit: intercept, should be close to 0
    n_rows: int
    dt_s: float
    r_squared: float
    condition_number: float
    ambient_std_c: float
    duty_std: float
    # Unrestricted fit, kept as a diagnostic (see the module docstring).
    a_unrestricted: float
    b_unrestricted: float
    c_unrestricted: float
    d_unrestricted: float
    tau_h_unrestricted: float | None
    dT_cool_unrestricted: float | None

    @property
    def b_minus_expected(self) -> float:
        """Unrestricted b minus (1 - a): close to 0 when the model structure fits."""
        return self.b_unrestricted - (1.0 - self.a_unrestricted)


def _rows(run: Sequence[SensorReading]) -> tuple[np.ndarray, np.ndarray, float]:
    """Return (columns T[n], T_amb_avg, u[n+1], T[n+1]) stacked for one run, and dt."""
    if len(run) < 3:
        raise CalibrationError("a calibration run needs at least 3 readings")
    for reading in run:
        if reading.ambient_c is None or reading.cooling_duty is None:
            raise CalibrationError("calibration readings need ambient_c and cooling_duty")
    t = np.array([r.t_s for r in run])
    steps = np.diff(t)
    dt = float(steps[0])
    if dt <= 0 or np.any(np.abs(steps - dt) > DT_TOLERANCE_S):
        raise CalibrationError("calibration readings must be evenly spaced in time")
    temp = np.array([r.temp_c for r in run])
    amb = np.array([r.ambient_c for r in run], dtype=float)
    duty = np.array([r.cooling_duty for r in run], dtype=float)
    amb_avg = (amb[:-1] + amb[1:]) / 2.0
    return np.column_stack([temp[:-1], amb_avg, duty[1:]]), temp[1:], dt


def calibrate(runs: Sequence[Sequence[SensorReading]]) -> CalibrationResult:
    """Fit TwinParams from clean calibration runs. Raises CalibrationError if unsuitable."""
    if not runs:
        raise CalibrationError("no calibration runs given")
    parts = [_rows(run) for run in runs]
    dts = {round(dt, 6) for _, _, dt in parts}
    if len(dts) != 1:
        raise CalibrationError(f"all runs must use the same sample interval (got {sorted(dts)})")
    dt = parts[0][2]
    x = np.vstack([p[0] for p in parts])  # columns: T[n], T_amb_avg, u[n+1]
    y = np.concatenate([p[1] for p in parts])  # T[n+1]
    if len(y) < MIN_ROWS:
        raise CalibrationError(f"too short: {len(y)} intervals, need at least {MIN_ROWS}")
    amb_std, duty_std = float(x[:, 1].std()), float(x[:, 2].std())
    if amb_std < MIN_AMBIENT_STD_C:
        raise CalibrationError(
            f"too flat: ambient standard deviation {amb_std:.2f} C, need {MIN_AMBIENT_STD_C}"
        )
    if duty_std < MIN_DUTY_STD:
        raise CalibrationError(
            f"too flat: cooling duty standard deviation {duty_std:.3f}, need {MIN_DUTY_STD}"
        )

    # Restricted fit (the one used): increment = k*(T_amb - T) + c*u + d
    dy = y - x[:, 0]
    design = np.column_stack([x[:, 1] - x[:, 0], x[:, 2], np.ones(len(y))])
    standard = design.copy()
    for col in range(2):
        standard[:, col] = (design[:, col] - design[:, col].mean()) / design[:, col].std()
    condition = float(np.linalg.cond(standard))
    if condition > MAX_CONDITION_NUMBER:
        raise CalibrationError(
            f"poorly conditioned: condition number {condition:.1f}, need at most "
            f"{MAX_CONDITION_NUMBER} (the inputs are too correlated to separate)"
        )
    (k, c, d), *_ = np.linalg.lstsq(design, dy, rcond=None)
    k, c, d = float(k), float(c), float(d)
    if not 0.0 < k < 1.0:
        raise CalibrationError(f"not physical: k = {k:.4f} must lie strictly between 0 and 1")
    dt_cool = -c / k
    if not dt_cool > 0:
        raise CalibrationError(f"not physical: fitted cooling depression {dt_cool:.2f} K")
    residuals = dy - design @ np.array([k, c, d])
    ss_res = float(residuals @ residuals)
    sigma_r = math.sqrt(ss_res / (len(y) - 3))
    params = TwinParams(
        tau_h=-dt / math.log(1.0 - k) / 3600.0, dT_cool_c=dt_cool, sigma_r_c=sigma_r
    )

    # Unrestricted fit (diagnostic only)
    full = np.column_stack([x, np.ones(len(y))])
    coef, *_ = np.linalg.lstsq(full, y, rcond=None)
    a_u, b_u, c_u, d_u = (float(v) for v in coef)
    physical = 0.0 < a_u < 1.0 and (1.0 - a_u) != 0.0
    return CalibrationResult(
        params=params,
        k=k,
        c=c,
        d=d,
        n_rows=len(y),
        dt_s=dt,
        r_squared=1.0 - ss_res / float(((y - y.mean()) ** 2).sum()),
        condition_number=condition,
        ambient_std_c=amb_std,
        duty_std=duty_std,
        a_unrestricted=a_u,
        b_unrestricted=b_u,
        c_unrestricted=c_u,
        d_unrestricted=d_u,
        tau_h_unrestricted=(-dt / math.log(a_u) / 3600.0) if physical else None,
        dT_cool_unrestricted=(-c_u / (1.0 - a_u)) if physical else None,
    )


def _ground_truth_path(recording: Path) -> Path:
    return recording.with_name(recording.name.removesuffix(".jsonl") + ".ground_truth.json")


def load_calibration_run(
    path: Path | str, evaluation_ids: Sequence[str] = ()
) -> list[SensorReading]:
    """Read one calibration recording, refusing evaluation recordings and tampered data."""
    recording = Path(path)
    source = RecordedSource(recording)
    source.start()
    scenario_id = str(source.header.get("scenario_id", ""))
    try:
        if scenario_id in set(evaluation_ids) or not scenario_id.startswith(CALIBRATION_PREFIX):
            raise CalibrationError(
                f"{recording.name}: scenario {scenario_id!r} is not calibration data; only "
                f"recordings whose scenario id starts with {CALIBRATION_PREFIX!r} are accepted, "
                "and never an evaluation recording"
            )
        truth_file = _ground_truth_path(recording)
        if not truth_file.exists():
            raise CalibrationError(f"{recording.name}: ground-truth labels are missing")
        events = json.loads(truth_file.read_text(encoding="utf-8")).get("events", [])
        bad = sorted({e["kind"] for e in events if e["kind"] in FORBIDDEN_EVENT_KINDS})
        if bad:
            raise CalibrationError(
                f"{recording.name}: contains labelled events the twin cannot model ({bad}); "
                "calibration data must be clean"
            )
        readings = []
        while (reading := source.read()) is not None:
            readings.append(reading)
        return readings
    finally:
        source.close()


def calibrate_from_recordings(
    paths: Sequence[Path | str], evaluation_ids: Sequence[str] = ()
) -> CalibrationResult:
    """Calibrate from recording files, refusing any that are evaluation data."""
    return calibrate([load_calibration_run(p, evaluation_ids) for p in paths])


def write_calibrated_config(
    result: CalibrationResult, path: Path | str, seeds: Sequence[int], files: Sequence[str]
) -> None:
    """Write config/twin_calibrated.yaml (text written by hand to keep the header comments)."""
    p = result.params

    def number(value: float | None) -> str:
        return "null" if value is None else repr(float(value))

    lines = [
        "# Fitted from data/calibration/, simulation only. Not real-world evidence.",
        "# placeholder, not sourced [SOURCE NEEDED]: these numbers describe the synthetic box.",
        "# Regenerate with: python -m edge calibrate",
        f"fit_date: {date.today().isoformat()}",
        f"calibration_seeds: [{', '.join(str(s) for s in seeds)}]",
        f"calibration_files: [{', '.join(files)}]",
        "estimator: restricted least squares on the increment (see edge/calibration.py)",
        f"n_intervals: {result.n_rows}",
        f"sample_interval_s: {result.dt_s:g}",
        f"tau_h: {p.tau_h!r}",
        f"dT_cool_c: {p.dT_cool_c!r}",
        f"sigma_r_c: {p.sigma_r_c!r}",
        f"r_squared: {result.r_squared!r}",
        f"condition_number: {result.condition_number!r}",
        f"fit_intercept_d: {result.d!r}",
        "# Unrestricted fit, kept only as a diagnostic (biased by measurement noise in T[n]):",
        f"unrestricted_tau_h: {number(result.tau_h_unrestricted)}",
        f"unrestricted_dT_cool_c: {number(result.dT_cool_unrestricted)}",
        f"unrestricted_b_minus_expected: {result.b_minus_expected!r}",
    ]
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")


def write_variant_twins(
    path: Path | str, fitted: dict[str, tuple[CalibrationResult, Sequence[int], str]]
) -> None:
    """Write config/twin_calibrated_variants.yaml: one fitted twin per box variant.

    `fitted` maps a variant name to (result, seeds, label). The nominal twin stays in
    config/twin_calibrated.yaml and is never touched by this.
    """
    lines = [
        "# Simulation only, fitted from per-box calibration sets. Not real-world evidence.",
        "# placeholder, not sourced [SOURCE NEEDED]: these numbers describe synthetic boxes.",
        "# Each variant is fitted by the same restricted regression as the nominal twin, from",
        "# clean calibration runs generated for THAT box.",
        "# Regenerate with: python scripts/calibrate_variants.py",
        f"fit_date: {date.today().isoformat()}",
        "variants:",
    ]
    for name, (result, seeds, label) in fitted.items():
        p = result.params
        lines += [
            f"  {name}:",
            f"    description: {label}",
            f"    calibration_seeds: [{', '.join(str(s) for s in seeds)}]",
            f"    n_intervals: {result.n_rows}",
            f"    tau_h: {p.tau_h!r}",
            f"    dT_cool_c: {p.dT_cool_c!r}",
            f"    sigma_r_c: {p.sigma_r_c!r}",
            f"    r_squared: {result.r_squared!r}",
            f"    condition_number: {result.condition_number!r}",
            f"    fit_intercept_d: {result.d!r}",
            f"    unrestricted_b_minus_expected: {result.b_minus_expected!r}",
        ]
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")
