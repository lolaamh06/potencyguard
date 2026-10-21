"""Pre-trip check: does the twin match this box? (Phase 3C)

The twin must be calibrated to the box it is used with. Before a trip, the first few hours of
readings are fed through the same rolling gain estimate that the tamper monitor uses during the
trip (edge/tamper_monitor.py, fit_gain): a least-squares fit of the observed change against the
change the twin predicts. A gain away from 1 means the box responds differently from the
calibration. The result is advice to the operator, not a tamper verdict.

Limits, stated plainly:
- A short window gives a less certain gain. When the gain cannot be measured (too little
  variation in the inputs, or a standard error above the configured limit) the check says so and
  does NOT claim that the twin matches.
- A lie or a fault that starts inside the window can confuse the check.
- Only the box thermistor is assumed to be honest here; the check is no defence against tampering.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from edge.detector_config import DetectorConfig
from edge.sensor_reading import SensorReading
from edge.tamper_monitor import fit_gain
from edge.thermal_twin import TwinParams, predict_next

DEFAULT_PRECHECK_HOURS = 6.0  # placeholder, not sourced [SOURCE NEEDED]
MIN_PAIRS = 12  # placeholder, not sourced [SOURCE NEEDED]: fewest intervals the check will use


class PrecheckResult(BaseModel):
    """Outcome of the pre-trip check. Immutable."""

    model_config = ConfigDict(frozen=True)

    ok: bool  # False only when the check measured a gain that is away from 1
    checked: bool  # False when the gain could not be measured in this window
    gain: float | None
    standard_error: float | None
    n_pairs: int
    message: str


def precheck(
    readings: Sequence[SensorReading], twin: TwinParams, config: DetectorConfig
) -> PrecheckResult:
    """Fit the gain over the given readings (already cut to the pre-trip window)."""
    pairs = []
    for prev, now in zip(readings, readings[1:], strict=False):
        if prev.ambient_c is None or now.ambient_c is None or now.cooling_duty is None:
            raise ValueError("the pre-trip check needs readings with ambient_c and cooling_duty")
        dt = now.t_s - prev.t_s
        if dt <= 0:
            raise ValueError(f"time must increase ({now.t_s} s after {prev.t_s} s)")
        predicted = predict_next(
            prev.temp_c, (prev.ambient_c + now.ambient_c) / 2.0, now.cooling_duty, dt, twin
        )
        pairs.append((predicted - prev.temp_c, now.temp_c - prev.temp_c, dt / 3600.0))
    fit = fit_gain(pairs) if len(pairs) >= MIN_PAIRS else None
    if fit is None or fit[2] > config.ood_max_gain_se:
        gain, se = (None, None) if fit is None else (fit[0], fit[2])
        return PrecheckResult(
            ok=True,
            checked=False,
            gain=gain,
            standard_error=se,
            n_pairs=len(pairs),
            message="could not check the twin: the gain is not measurable in this window "
            "(too little data or too little variation); this is NOT a confirmation",
        )
    gain, _, se = fit
    mismatched = (
        abs(gain - 1.0) > config.ood_gain_margin
        and config.ood_gain_band_low < gain < config.ood_gain_band_high
    )
    if mismatched:
        return PrecheckResult(
            ok=False,
            checked=True,
            gain=gain,
            standard_error=se,
            n_pairs=len(pairs),
            message=f"twin may be out of date: recalibrate before departure (gain {gain:.2f})",
        )
    low, high = 1.0 - config.ood_gain_margin, 1.0 + config.ood_gain_margin
    return PrecheckResult(
        ok=True,
        checked=True,
        gain=gain,
        standard_error=se,
        n_pairs=len(pairs),
        message=f"twin matches this box (gain {gain:.2f}, band {low:.2f} to {high:.2f})",
    )


def window(readings: Sequence[SensorReading], hours: float) -> list[SensorReading]:
    """The readings of the first `hours` hours of a trip."""
    if hours <= 0:
        raise ValueError(f"hours must be greater than 0 (got {hours})")
    if not readings:
        return []
    start = readings[0].t_s
    return [r for r in readings if r.t_s - start <= hours * 3600.0 + 1e-9]
