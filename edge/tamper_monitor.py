"""Streaming tamper monitor: four detectors on the thermal twin's residual, and a classification.

It consumes readings that carry ambient_c and cooling_duty and NEVER sees ground truth.

Detectors
1. CUSUM drift (brief section 3.3), two-sided: S+ = max(0, S+ + r/sigma - k) and S- likewise for
   -r, each capped at cap_factor * h. An alarm is S > h. The brief writes |r|; two sides give the
   sign, which the classification needs.
2. Impossible step (brief): |T[n] - T[n-1]| above max_step_bound.
3. Impossible state (addition, decision 0005): the reported temperature stays below the lag-aware
   lower envelope (the coldest the box could be with full cooling all the time, starting from the
   first reading; see advance_floor) minus a margin for several samples in a row. The steady
   floor T_amb - dT_cool is only reached after several time constants, so using it directly
   gave false alarms while the ambient was rising. There is NO ceiling check: heat loads are not
   observed, so no upper limit follows from the physics.
4. Flat line (brief): the window standard deviation is far below the sensor noise. Falsified
   values that carry noise (the simulator's spoof modes) are NOT caught by this detector; it
   catches crude freezes only.

Classification (a small table, checked in this order)
  flat line, impossible state, negative CUSUM alarm, a jump that stays   -> suspected_falsification
  a jump that reverts at once (a lone impossible step)                    -> sensor_glitch
  positive CUSUM alarm with none of the flags above                       -> thermal_anomaly
  otherwise                                                               -> ok
Proof of a falsification (a persistent impossible step, the impossible state, a flat line) is
LATCHED until reset(): a lie that is physically consistent after its first jump, such as a
reading held at a plausible value, would otherwise look like a harmless cooling shortfall again.
A negative CUSUM alarm alone is not latched; it is held for falsification_hold_samples.
A positive residual means the box is warmer than the twin expects (cooling shortfall or a door
open: a physical event). A negative residual means the box is reported colder than physics allows.

Lone jumps and the potency tracker: an impossible step waits N - 1 samples (N = the hard-limit
confirmation count in the product config, 2 by default) before it is called a falsification,
the same way PotencyTracker calls a single out-of-range reading "suspect" until N readings in a
row confirm it. A jump that reverts within that wait is a glitch. While a jump is undecided its
samples do not feed the CUSUM (the twin would otherwise be driven by the bad value).

Warm-up: the first reading has no previous state, so residual, CUSUM, step and flat-line results
start with the second (flat line needs a full window); the state check can fire from the first
reading but needs several in a row.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import pstdev

from pydantic import BaseModel, ConfigDict

from edge.detector_config import DetectorConfig, load_detector_config
from edge.sensor_reading import SensorReading
from edge.thermal_twin import (
    TwinParams,
    advance_floor,
    load_twin_params,
    max_step_bound,
    predict_next,
)
from shared.config import BoxConfig, ProductConfig

OK = "ok"
THERMAL_ANOMALY = "thermal_anomaly"
FALSIFICATION = "suspected_falsification"
GLITCH = "sensor_glitch"
VERDICT_TEXT = {
    OK: "consistent with the physics",
    THERMAL_ANOMALY: "thermal anomaly: cooling shortfall or door open",
    FALSIFICATION: "reported value inconsistent with the physics: suspected falsification or "
    "sensor fault",
    GLITCH: "sensor glitch: a lone impossible reading",
}
DETECTORS = ("cusum_pos", "cusum_neg", "impossible_step", "impossible_state", "flat_line")


class MonitorState(BaseModel):
    """What the monitor knows after one reading."""

    model_config = ConfigDict(frozen=True)

    t_s: float
    predicted_c: float | None
    residual_c: float | None
    residual_sigma: float | None
    cusum_pos: float
    cusum_neg: float
    flag_cusum_pos: bool
    flag_cusum_neg: bool
    flag_step: bool
    flag_state: bool
    flag_flat: bool
    verdict: str
    verdict_text: str
    samples_seen: int


@dataclass
class _Pending:
    """A jump that has not been decided yet."""

    index: int
    t_before_c: float
    waited: int = 0


class TamperMonitor:
    """Feed it one reading at a time; it returns a MonitorState."""

    def __init__(
        self,
        params: TwinParams,
        config: DetectorConfig,
        confirm_count: int,
        sensor_sigma_c: float,
    ) -> None:
        if confirm_count < 1:
            raise ValueError("confirm_count must be at least 1")
        self._params = params
        self._cfg = config
        self._confirm = confirm_count
        self._sensor_sigma = sensor_sigma_c
        self.reset()

    @classmethod
    def from_defaults(cls, product: ProductConfig, box: BoxConfig) -> TamperMonitor:
        """Monitor with the calibrated twin and the detector settings from config/."""
        return cls(
            load_twin_params(),
            load_detector_config(),
            product.hard_limit_consecutive_samples,
            box.sensor_sigma_c,
        )

    def reset(self) -> None:
        self._prev: SensorReading | None = None
        self._temps: list[float] = []
        self._s_pos = 0.0
        self._s_neg = 0.0
        self._state_run = 0
        self._floor: float | None = None
        self._latched = False
        self._hold_left = 0
        self._pending: _Pending | None = None
        self._seen = 0
        self._last: MonitorState | None = None
        self.verdict_history: list[tuple[float, str]] = []
        self.first_alarm_s: dict[str, float] = {}

    # ------------------------------------------------------------------ input

    def update(self, reading: SensorReading) -> MonitorState:
        """Take one reading. It must carry ambient_c and cooling_duty."""
        if reading.ambient_c is None or reading.cooling_duty is None:
            raise ValueError(
                "the thermal monitor needs readings with ambient_c and cooling_duty "
                f"(t = {reading.t_s} s has none)"
            )
        prev = self._prev
        if prev is not None and reading.t_s <= prev.t_s:
            raise ValueError(f"time must increase ({reading.t_s} s after {prev.t_s} s)")
        cfg, params = self._cfg, self._params
        sigma = params.sigma_r_c
        t_now = reading.temp_c
        self._seen += 1
        self._temps.append(t_now)

        # impossible state: below the lag-aware lower envelope (starts at the first reading)
        if prev is None:
            self._floor = t_now
        else:
            amb_for_floor = (prev.ambient_c + reading.ambient_c) / 2.0
            self._floor = advance_floor(self._floor, amb_for_floor, reading.t_s - prev.t_s, params)
        below = t_now < self._floor - cfg.state_margin_sigma * sigma
        self._state_run = self._state_run + 1 if below else 0
        flag_state = self._state_run >= cfg.state_consecutive_samples

        # flat line (needs a full window)
        flag_flat = False
        if len(self._temps) >= cfg.flat_window_samples:
            window = self._temps[-cfg.flat_window_samples :]
            flag_flat = pstdev(window) < cfg.flat_sigma_factor * self._sensor_sigma

        predicted = residual = rsig = None
        flag_step = False
        step_decision: str | None = None  # "glitch", "falsification" or None
        if prev is not None:
            dt = reading.t_s - prev.t_s
            amb_avg = (prev.ambient_c + reading.ambient_c) / 2.0
            predicted = predict_next(prev.temp_c, amb_avg, reading.cooling_duty, dt, params)
            residual = t_now - predicted
            rsig = residual / sigma
            bound = max_step_bound(
                prev.temp_c, amb_avg, dt, params, cfg.heat_allowance_c, cfg.step_tolerance_sigma
            )
            flag_step = abs(t_now - prev.temp_c) > bound
            step_decision, skip_cusum = self._resolve_jump(reading, prev, amb_avg, dt, flag_step)
            if not skip_cusum:
                cap = cfg.cusum_cap_factor * cfg.cusum_h
                self._s_pos = min(cap, max(0.0, self._s_pos + rsig - cfg.cusum_k))
                self._s_neg = min(cap, max(0.0, self._s_neg - rsig - cfg.cusum_k))

        flag_pos = self._s_pos > cfg.cusum_h
        flag_neg = self._s_neg > cfg.cusum_h
        proof = flag_flat or flag_state or step_decision == "falsification"
        self._latched = self._latched or proof
        triggered = proof or flag_neg or self._latched
        if triggered:
            self._hold_left = cfg.falsification_hold_samples
        if triggered or self._hold_left > 0:
            if not triggered:
                self._hold_left -= 1
            verdict = FALSIFICATION
        elif step_decision == "glitch":
            verdict = GLITCH
        elif flag_pos:
            verdict = THERMAL_ANOMALY
        else:
            verdict = OK

        for name, flag in (
            ("cusum_pos", flag_pos),
            ("cusum_neg", flag_neg),
            ("impossible_step", flag_step),
            ("impossible_state", flag_state),
            ("flat_line", flag_flat),
        ):
            if flag:
                self.first_alarm_s.setdefault(name, reading.t_s)
        if not self.verdict_history or self.verdict_history[-1][1] != verdict:
            self.verdict_history.append((reading.t_s, verdict))

        state = MonitorState(
            t_s=reading.t_s,
            predicted_c=predicted,
            residual_c=residual,
            residual_sigma=rsig,
            cusum_pos=self._s_pos,
            cusum_neg=self._s_neg,
            flag_cusum_pos=flag_pos,
            flag_cusum_neg=flag_neg,
            flag_step=flag_step,
            flag_state=flag_state,
            flag_flat=flag_flat,
            verdict=verdict,
            verdict_text=VERDICT_TEXT[verdict],
            samples_seen=self._seen,
        )
        self._prev = reading
        self._last = state
        return state

    def _resolve_jump(
        self,
        reading: SensorReading,
        prev: SensorReading,
        amb_avg: float,
        dt: float,
        flag_step: bool,
    ) -> tuple[str | None, bool]:
        """Decide what an impossible step means. Returns (decision, skip_cusum)."""
        cfg = self._cfg
        pending = self._pending
        if pending is None:
            if not flag_step:
                return None, False
            if self._confirm == 1:
                return "falsification", True
            self._pending = _Pending(self._seen - 1, prev.temp_c)
            return "glitch", True  # provisional: assumed lone until it persists
        pending.waited += 1
        span = dt * (pending.waited + 1)
        reverted = abs(reading.temp_c - pending.t_before_c) <= max_step_bound(
            pending.t_before_c, amb_avg, span, self._params, cfg.heat_allowance_c,
            cfg.step_tolerance_sigma,
        )  # fmt: skip
        if reverted:
            self._pending = None
            return "glitch", True
        if pending.waited >= self._confirm - 1:
            self._pending = None
            return "falsification", False
        return "glitch", True

    # ------------------------------------------------------------------ output

    def snapshot(self) -> MonitorState:
        """The current state without a new reading."""
        if self._last is not None:
            return self._last
        return MonitorState(
            t_s=0.0,
            predicted_c=None,
            residual_c=None,
            residual_sigma=None,
            cusum_pos=0.0,
            cusum_neg=0.0,
            flag_cusum_pos=False,
            flag_cusum_neg=False,
            flag_step=False,
            flag_state=False,
            flag_flat=False,
            verdict=OK,
            verdict_text=VERDICT_TEXT[OK],
            samples_seen=0,
        )


def sigma_units(value: float | None) -> str:
    return "n/a" if value is None or not math.isfinite(value) else f"{value:+.1f}"
