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
  flat line, impossible state, a jump that stays, a held falsification   -> suspected_falsification
  negative CUSUM alarm while the twin is NOT out of date                  -> suspected_falsification
  a jump that reverts at once (a lone impossible step)                    -> sensor_glitch
  the twin is out of date (Phase 3B, below)                               -> twin_out_of_date
  positive CUSUM alarm with none of the flags above                       -> thermal_anomaly
  otherwise                                                               -> ok
Proof of a falsification (a persistent impossible step, the impossible state, a flat line) is
LATCHED until reset(): a lie that is physically consistent after its first jump, such as a
reading held at a plausible value, would otherwise look like a harmless cooling shortfall again.
A negative CUSUM alarm alone is not latched; it is held for falsification_hold_samples.
A positive residual means the box is warmer than the twin expects (cooling shortfall or a door
open: a physical event). A negative residual means the box is reported colder than physics allows.

Twin out of date (Phase 3B, decision 0006). A rolling least-squares fit y = g * x + b * dt_h over
the last ood_window_samples intervals, with x = (twin's predicted change) and y = (observed
change), measures how well the twin's dynamics match the box. A real box that differs from the
calibration (another time constant, wall resistance or cooling capacity) shows a gain g away
from 1 with no jump. When |g - 1| exceeds ood_gain_margin (g inside a plausible band, and
measurable: its standard error is small enough) for ood_sustained_samples evaluations in a row,
the verdict is twin_out_of_date and the CUSUM-based tamper verdict is SUPPRESSED (the CUSUM
values are still reported). Hard physical proofs (impossible step, impossible state, flat line)
are never suppressed, and once one has fired in the trip the self-check is switched off for the
rest of the trip. A reading pair that belongs to an undecided jump is left out of the fit. A lone
jump that reverts (a glitch) does not switch the self-check off: only a jump that stays is proof.
RESIDUAL RISK: a patient attacker could imitate a gain error, and while twin_out_of_date is
active a slow lie is no longer reported as falsification. The design reports and logs
twin_out_of_date itself, flags a trip that is out of date from its first window
(out_of_date_from_start), and the potency assessment (edge/assessment.py) marks the data
untrusted with a worst-case bound instead of silently accepting them.

Trust record. The monitor remembers the earliest time the reported data became doubtful
(untrusted_since_s). For a falsification verdict this is the start a0 of the ANOMALY EPISODE, or
the start of a proof such as a jump, whichever is earlier. a0 is the last sample at which both CUSUM
statistics were zero BEFORE the first anomaly flag of the trip (either CUSUM alarm, impossible
step, impossible state or flat line). It is LATCHED: once an episode has started a0 never moves
later, even when the statistics go quiet again. This matters because a physical fault or a mimic
lie can cancel a statistic and make "the last quiet time" look recent, while the reported value is
already false (the 3B defect). A sudden jump out of a quiet state starts at the last reading
before the jump. The rule can only make the start earlier, never later, so it can only make the
worst-case bound looser, never tighter; the cost is a looser bound after any earlier anomaly. For
an out-of-date twin it is the start of the first flagged window. In both
cases trust_lookback_samples are subtracted. Once set it stays for the rest of the trip (until
reset()): data reported before a lie was noticed remain doubtful.

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

import bisect
import math
from collections import deque
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
OUT_OF_DATE = "twin_out_of_date"
VERDICT_TEXT = {
    OK: "consistent with the physics",
    THERMAL_ANOMALY: "thermal anomaly: cooling shortfall or door open",
    FALSIFICATION: "reported value inconsistent with the physics: suspected falsification or "
    "sensor fault",
    GLITCH: "sensor glitch: a lone impossible reading",
    OUT_OF_DATE: "twin out of date: the box differs from the calibration, so physics-based "
    "tamper verdicts are suspended",
}
# A CUSUM statistic counts as zero at or below this (the statistics are clipped at exactly 0).
ZERO_EPS = 1e-9
# Trust levels. untrusted: a latched falsification (a hard proof, or sustained negative evidence
# that the out-of-date self-check did not explain). low_confidence: the twin is suspected not to
# match this box, with no hard proof. trusted: no evidence against the readings.
TRUSTED = "trusted"
LOW_CONFIDENCE = "low_confidence"
UNTRUSTED = "untrusted"
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
    # Phase 3B: the model-health estimate and the trust record.
    gain: float | None = None
    gain_se: float | None = None
    drift_c_per_h: float | None = None
    twin_out_of_date: bool = False
    out_of_date_from_start: bool = False
    untrusted_since_s: float | None = None
    untrusted_reason: str | None = None
    trust_level: str = TRUSTED
    # Phase 3C: True when this sample did not feed the CUSUM (it belongs to an undecided jump).
    cusum_skipped: bool = False


@dataclass
class _Pending:
    """A jump that has not been decided yet."""

    index: int
    t_before_c: float
    t_before_s: float = 0.0
    waited: int = 0


def fit_gain(pairs) -> tuple[float, float, float] | None:
    """Least squares y = g * x + b * dt_h over (x, y, dt_h) triples: (g, b, standard error of g).

    None when the fit cannot be made (fewer than three pairs, or x carries no information beyond
    the dt_h column). b is in kelvin per hour; the fit is exact normal equations on a 2 x 2 system.
    """
    n = len(pairs)
    if n < 3:
        return None
    sxx = sxd = sdd = sxy = sdy = syy = 0.0
    for x, y, d in pairs:
        sxx += x * x
        sxd += x * d
        sdd += d * d
        sxy += x * y
        sdy += d * y
        syy += y * y
    sxx_res = sxx - sxd * sxd / sdd if sdd > 0 else sxx
    if sdd <= 0 or sxx_res <= 1e-12:
        return None
    g = (sxy - sxd * sdy / sdd) / sxx_res
    b = (sdy - g * sxd) / sdd
    rss = max(0.0, syy - g * sxy - b * sdy)
    se = math.sqrt(rss / (n - 2) / sxx_res)
    return g, b, se


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
        # Phase 3B: model health (the rolling gain fit) and the trust record.
        self._times: list[float] = []
        self._pairs: deque[tuple[float, float, float]] = deque(maxlen=self._cfg.ood_window_samples)
        self._ood_hits = 0
        self._ood_clear = 0
        self._ood_active = False
        self._ood_disabled = False
        self._ood_since_s: float | None = None
        self._ood_first_eval_idx: int | None = None
        self._first_window_t_s: float | None = None
        self._last_zero_s: float | None = None
        self._episode_a0_s: float | None = None
        self._jump_before_s: float | None = None
        self._falsification_recorded = False
        self._last_gain: tuple[float | None, float | None, float | None] = (None, None, None)
        self._streak_start_s: float | None = None
        self._state_run_start_s: float | None = None
        self._untrusted_since_s: float | None = None
        self._untrusted_reason: str | None = None
        self.out_of_date_from_start = False

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
        self._times.append(reading.t_s)

        # impossible state: below the lag-aware lower envelope (starts at the first reading)
        if prev is None:
            self._floor = t_now
        else:
            amb_for_floor = (prev.ambient_c + reading.ambient_c) / 2.0
            self._floor = advance_floor(self._floor, amb_for_floor, reading.t_s - prev.t_s, params)
        below = t_now < self._floor - cfg.state_margin_sigma * sigma
        if below and self._state_run == 0:
            self._state_run_start_s = prev.t_s if prev is not None else reading.t_s
        self._state_run = self._state_run + 1 if below else 0
        flag_state = self._state_run >= cfg.state_consecutive_samples

        # flat line (needs a full window)
        flag_flat = False
        if len(self._temps) >= cfg.flat_window_samples:
            window = self._temps[-cfg.flat_window_samples :]
            flag_flat = pstdev(window) < cfg.flat_sigma_factor * self._sensor_sigma

        predicted = residual = rsig = None
        flag_step = False
        skip_cusum = False
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
                self._pairs.append((predicted - prev.temp_c, t_now - prev.temp_c, dt / 3600.0))
        flag_pos = self._s_pos > cfg.cusum_h
        flag_neg = self._s_neg > cfg.cusum_h
        self._track_episode(reading, flag_pos or flag_neg or flag_step or flag_state or flag_flat)
        proof = flag_flat or flag_state or step_decision == "falsification"
        self._latched = self._latched or proof
        if self._latched:
            self._ood_disabled = True
            self._ood_active = False

        gain, gain_se, drift = self._update_model_health(
            reading, prev is not None and not skip_cusum
        )
        ood = self._ood_active
        triggered = proof or (flag_neg and not ood) or self._latched
        if triggered:
            self._hold_left = cfg.falsification_hold_samples
        if triggered or self._hold_left > 0:
            if not triggered:
                self._hold_left -= 1
            verdict = FALSIFICATION
        elif step_decision == "glitch":
            verdict = GLITCH
        elif ood:
            verdict = OUT_OF_DATE
        elif flag_pos:
            verdict = THERMAL_ANOMALY
        else:
            verdict = OK
        self._record_trust(reading, verdict, prev, step_decision, flag_flat)

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
            gain=gain,
            gain_se=gain_se,
            drift_c_per_h=drift,
            twin_out_of_date=self._ood_active,
            out_of_date_from_start=self.out_of_date_from_start,
            untrusted_since_s=self._untrusted_since_s,
            untrusted_reason=self._untrusted_reason,
            trust_level=self.trust_level,
            cusum_skipped=skip_cusum,
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
                self._jump_before_s = prev.t_s
                return "falsification", True
            self._pending = _Pending(self._seen - 1, prev.temp_c, prev.t_s)
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
            self._jump_before_s = pending.t_before_s
            self._pending = None
            return "falsification", False
        return "glitch", True

    # ------------------------------------------------------------------ model health and trust

    def _update_model_health(
        self, reading: SensorReading, took_pair: bool
    ) -> tuple[float | None, float | None, float | None]:
        """Refit the gain when a new pair arrived; track the sustained out-of-date condition."""
        cfg = self._cfg
        if not took_pair:
            return self._last_gain
        if len(self._pairs) < cfg.ood_window_samples:
            self._last_gain = (None, None, None)
            return self._last_gain
        fit = fit_gain(self._pairs)
        if fit is None:
            self._last_gain = (None, None, None)
            flagged = False
        else:
            g, b, se = fit
            self._last_gain = (g, se, b)
            flagged = (
                se <= cfg.ood_max_gain_se
                and abs(g - 1.0) > cfg.ood_gain_margin
                and cfg.ood_gain_band_low < g < cfg.ood_gain_band_high
            )
        if self._ood_disabled:
            return self._last_gain
        if flagged:
            if self._ood_hits == 0:
                # the window that first showed the mismatch started this many samples back
                index = max(0, len(self._times) - 1 - cfg.ood_window_samples)
                self._streak_start_s = self._times[index]
            self._ood_hits += 1
            self._ood_clear = 0
            if not self._ood_active and self._ood_hits >= cfg.ood_sustained_samples:
                self._ood_active = True
                if self._ood_since_s is None:
                    self._ood_since_s = self._streak_start_s
                    self.out_of_date_from_start = self._streak_start_s == self._times[0]
                self._mark_untrusted(self._streak_start_s, OUT_OF_DATE)
        else:
            self._ood_hits = 0
            self._ood_clear += 1
            if self._ood_active and self._ood_clear >= cfg.ood_sustained_samples:
                self._ood_active = False
        return self._last_gain

    def _mark_untrusted(self, evidence_start_s: float | None, reason: str) -> None:
        """Remember the earliest time the data became doubtful, a lookback before the evidence."""
        if evidence_start_s is None:
            return
        index = bisect.bisect_left(self._times, evidence_start_s)
        t0 = self._times[max(0, index - self._cfg.trust_lookback_samples)]
        earlier = self._untrusted_since_s is None or t0 < self._untrusted_since_s
        # Doubt that starts at the same time is explained by the twin when the twin is the cause:
        # a mismatched box raises false CUSUM alarms before the slower self-check can speak.
        same_but_better = t0 == self._untrusted_since_s and reason == OUT_OF_DATE
        if earlier or same_but_better:
            self._untrusted_since_s = t0
            self._untrusted_reason = reason

    def _track_episode(self, reading: SensorReading, anomaly: bool) -> None:
        """Latch the start of the anomaly episode (a0) at the first anomaly of any kind.

        a0 is the last sample, BEFORE the first anomaly flag of the trip (either CUSUM alarm, an
        impossible-step, impossible-state or flat-line flag), at which both CUSUM statistics were
        zero. Once latched it never moves, even when the statistics go quiet again.
        """
        if self._episode_a0_s is not None:
            return
        if anomaly:
            self._episode_a0_s = self._last_zero_s if self._last_zero_s is not None else reading.t_s
        elif self._s_neg <= ZERO_EPS and self._s_pos <= ZERO_EPS:
            self._last_zero_s = reading.t_s

    @property
    def episode_start_s(self) -> float | None:
        """The latched start a0 of the anomaly episode, or None while nothing has been flagged."""
        return self._episode_a0_s

    def _record_trust(
        self,
        reading: SensorReading,
        verdict: str,
        prev: SensorReading | None,
        step_decision: str | None,
        flag_flat: bool,
    ) -> None:
        """On the first falsification verdict, remember where its evidence began."""
        if verdict != FALSIFICATION or self._falsification_recorded:
            return
        self._falsification_recorded = True
        candidates = [self._episode_a0_s, reading.t_s]
        if step_decision == "falsification":
            candidates.append(self._jump_before_s)
        if flag_flat:
            candidates.append(self._times[max(0, len(self._times) - self._cfg.flat_window_samples)])
        if self._state_run >= self._cfg.state_consecutive_samples:
            candidates.append(self._state_run_start_s)
        self._mark_untrusted(min(c for c in candidates if c is not None), FALSIFICATION)

    @property
    def trust_level(self) -> str:
        """trusted, low_confidence or untrusted.

        A hard proof always gives untrusted, also when the twin was out of date before it, and
        never clears. A CUSUM-only alarm gives untrusted until the self-check explains it as a
        mismatch (the reason becomes twin_out_of_date); then the level is low_confidence.
        """
        if self._untrusted_since_s is None:
            return TRUSTED
        if self._latched or self._untrusted_reason == FALSIFICATION:
            return UNTRUSTED
        return LOW_CONFIDENCE

    @property
    def untrusted_since_s(self) -> float | None:
        return self._untrusted_since_s

    @property
    def self_check_off(self) -> bool:
        """True once a hard proof of falsification switched the out-of-date self-check off."""
        return self._ood_disabled

    @property
    def params(self) -> TwinParams:
        return self._params

    @property
    def config(self) -> DetectorConfig:
        return self._cfg

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
