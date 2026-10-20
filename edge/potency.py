"""Potency engine: Arrhenius kinetics, mean kinetic temperature and a streaming tracker.

Formulas (master brief section 3.2, amendment A6; constants from config/product_default.yaml,
which are synthetic product defaults for an imaginary vaccine, not measured values):

    AF(T)   = exp( (Ea/R) * (1 / T_ref_K - 1 / T_K) )      acceleration factor
    tau_eq  = sum_i AF(T_i) * dt_i                          hours at the reference temperature
    P       = exp( -k_ref * tau_eq ),  k_ref = ln(1 / P_min) / tau_max
    used    = tau_eq / tau_max                              fraction of shelf life used
    T_MKT_K      = (Ea/R) / ( -ln( sum_i w_i * exp(-(Ea/R) / T_i_K) ) ),  w_i = dt_i / sum(dt)

All temperatures enter in Celsius and are converted to kelvin (+273.15) inside the functions.
Times are hours unless a name ends in _s. Plain floats, no hidden rounding. Sums are plain
left-to-right loops so a TypeScript port that does the same reproduces the same numbers.

Potency is a model output for an imaginary product with assumed Ea and P_min.
Freezing and heat damage are not Arrhenius effects, so the hard limits (below 0 C, above 40 C)
are handled separately by the tracker's suspect-reading rule (amendment A5).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict

from edge.sensor_reading import SensorReading
from shared.config import ProductConfig

KELVIN_OFFSET = 273.15
SECONDS_PER_HOUR = 3600.0


def _kelvin(temp_c: float) -> float:
    if not isinstance(temp_c, int | float) or isinstance(temp_c, bool) or not math.isfinite(temp_c):
        raise ValueError(f"temperature must be a finite number (got {temp_c!r})")
    kelvin = temp_c + KELVIN_OFFSET
    if kelvin <= 0:
        raise ValueError(f"absolute temperature must be positive (got {temp_c} C)")
    return kelvin


def _check_dt(dt_h: float) -> None:
    if not isinstance(dt_h, int | float) or isinstance(dt_h, bool) or not math.isfinite(dt_h):
        raise ValueError(f"time step must be a finite number (got {dt_h!r})")
    if dt_h < 0:
        raise ValueError(f"time step must not be negative (got {dt_h} h)")


def _check_series(temps_c: Sequence[float], dts_h: Sequence[float]) -> None:
    if len(temps_c) != len(dts_h):
        raise ValueError(
            f"temps_c and dts_h must have the same length (got {len(temps_c)} and {len(dts_h)})"
        )


def arrhenius_acceleration_factor(temp_c: float, cfg: ProductConfig) -> float:
    """AF(T): how many times faster the damage runs at temp_c than at the reference temperature.

    Exactly 1 at T_ref, above 1 when warmer, below 1 when colder. Unitless.
    """
    return math.exp(cfg.Ea_over_R * (1.0 / cfg.T_ref_k - 1.0 / _kelvin(temp_c)))


def equivalent_reference_time_h(
    temps_c: Sequence[float], dts_h: Sequence[float], cfg: ProductConfig
) -> float:
    """tau_eq = sum AF(T_i) * dt_i, in hours at the reference temperature. Zero dt adds nothing."""
    _check_series(temps_c, dts_h)
    total = 0.0
    for temp_c, dt_h in zip(temps_c, dts_h, strict=True):
        _check_dt(dt_h)
        total += arrhenius_acceleration_factor(temp_c, cfg) * dt_h
    return total


def potency_from_tau_eq(tau_eq_h: float, cfg: ProductConfig) -> float:
    """P = exp(-k_ref * tau_eq), between 0 and 1 (1 when nothing has been spent)."""
    if not math.isfinite(tau_eq_h) or tau_eq_h < 0:
        raise ValueError(f"tau_eq_h must be a finite number >= 0 (got {tau_eq_h})")
    return math.exp(-cfg.k_ref_per_h * tau_eq_h)


def shelf_life_used_fraction(tau_eq_h: float, cfg: ProductConfig) -> float:
    """tau_eq / tau_max. Multiply by 100 for percent."""
    if not math.isfinite(tau_eq_h) or tau_eq_h < 0:
        raise ValueError(f"tau_eq_h must be a finite number >= 0 (got {tau_eq_h})")
    return tau_eq_h / cfg.tau_max_h


@dataclass
class _MktAccumulator:
    """Running sum of dt * exp(a), a = -(Ea/R)/T_K, kept as sum * exp(max_a) to avoid underflow."""

    max_a: float = -math.inf
    scaled_sum: float = 0.0
    duration_h: float = 0.0

    def add(self, temp_c: float, dt_h: float, ea_over_r: float) -> None:
        _check_dt(dt_h)
        if dt_h == 0.0:
            return
        a = -ea_over_r / _kelvin(temp_c)
        if a > self.max_a:
            self.scaled_sum = self.scaled_sum * math.exp(self.max_a - a) + dt_h
            self.max_a = a
        else:
            self.scaled_sum += dt_h * math.exp(a - self.max_a)
        self.duration_h += dt_h

    def mkt_c(self, ea_over_r: float) -> float | None:
        if self.duration_h <= 0.0:
            return None
        # ln(sum w_i exp(a_i)) = max_a + ln(scaled_sum / duration)
        log_mean = self.max_a + math.log(self.scaled_sum / self.duration_h)
        return ea_over_r / (-log_mean) - KELVIN_OFFSET

    def copy(self) -> _MktAccumulator:
        return _MktAccumulator(self.max_a, self.scaled_sum, self.duration_h)


def time_weighted_mkt_c(
    temps_c: Sequence[float], dts_h: Sequence[float], cfg: ProductConfig
) -> float:
    """Mean kinetic temperature in Celsius, weighted by time (amendment A6).

    T_MKT_K = (Ea/R) / ( -ln( sum w_i exp(-(Ea/R)/T_i_K) ) ), w_i = dt_i / sum(dt).
    The log of the weighted sum is computed in a scaled form (log-sum-exp), so very low
    temperatures cannot underflow to zero. Intervals with zero duration carry no weight.
    Raises ValueError for empty input or a total duration of zero.
    """
    _check_series(temps_c, dts_h)
    if len(temps_c) == 0:
        raise ValueError("cannot compute a mean kinetic temperature from empty input")
    acc = _MktAccumulator()
    for temp_c, dt_h in zip(temps_c, dts_h, strict=True):
        acc.add(temp_c, dt_h, cfg.Ea_over_R)
    result = acc.mkt_c(cfg.Ea_over_R)
    if result is None:
        raise ValueError("total duration is zero; a mean kinetic temperature needs elapsed time")
    return result


def hours_to_min_potency_at_temp(tau_eq_h: float, temp_c: float, cfg: ProductConfig) -> float:
    """Hours until potency reaches P_min if the box stayed at temp_c from now on.

    DERIVED HELPER for the later planner, not a formula from the brief. The brief defines the
    remaining life at the reference temperature, L_rem = tau_max - tau_eq; this divides that by
    AF(temp_c) to turn it into real hours at temp_c. Never negative.
    """
    if not math.isfinite(tau_eq_h) or tau_eq_h < 0:
        raise ValueError(f"tau_eq_h must be a finite number >= 0 (got {tau_eq_h})")
    remaining_h = max(0.0, cfg.tau_max_h - tau_eq_h)
    return remaining_h / arrhenius_acceleration_factor(temp_c, cfg)


# ----------------------------------------------------------------------------------------------
# Streaming tracker
# ----------------------------------------------------------------------------------------------

Status = Literal["ok", "suspect", "excursion_confirmed"]


class PotencyState(BaseModel):
    """Everything the edge program knows about the potency after one reading."""

    model_config = ConfigDict(frozen=True)

    t_s: float
    tau_eq_h: float
    potency: float
    shelf_life_used_fraction: float
    mkt_c: float | None
    effective_temp_c: float | None
    current_af: float | None
    hours_to_min_potency_at_current_temp: float | None
    status: Status
    below_min_potency: bool
    samples_seen: int
    samples_excluded: int


@dataclass
class _Pending:
    """An out-of-range interval that is not yet decided: kept apart from the committed sums."""

    actual_temp_c: float
    held_temp_c: float | None
    dt_h: float


@dataclass
class _Totals:
    """Committed (decided) sums."""

    tau_eq_h: float = 0.0
    mkt: _MktAccumulator = field(default_factory=_MktAccumulator)


class PotencyTracker:
    """Feed it one reading at a time; it returns the potency state after each reading.

    Integration rule: right endpoint. Sample i (after the first) stands for the interval from
    the previous sample time to its own time, dt = t_i - t_(i-1), and that whole interval is
    integrated with the temperature of sample i. For a constant temperature the result is the
    same as any other rule, so the worked examples are unaffected.

    Suspect-reading rule (amendment A5; N = hard_limit_consecutive_samples from the config):
    - A reading outside [low, high] is "suspect" the first time. It is EXCLUDED from the maths:
      its interval is integrated with the last accepted temperature instead (hold-last-valid)
      and it counts in samples_excluded. If no temperature has been accepted yet, the interval
      adds nothing.
    - N readings in a row outside the limits CONFIRM the excursion. The earlier suspect readings
      are then counted as valid: their intervals are redone with their own temperatures
      (exactly once, no double counting) and they leave samples_excluded. Status becomes
      "excursion_confirmed" and further out-of-range readings count as valid.
    - A reading back inside the limits ends the episode: a lone suspect stays excluded (its
      held value is committed), a confirmed excursion stays in tau_eq. Status returns to "ok".
    The undecided intervals live in a small pending list, so no sum is ever subtracted from.

    Only reported readings are ever fed in; the tracker never sees ground truth.
    No wall-clock time and no randomness.
    """

    def __init__(self, cfg: ProductConfig) -> None:
        self._cfg = cfg
        self.reset()

    def reset(self) -> None:
        self._totals = _Totals()
        self._pending: list[_Pending] = []
        self._prev_t_s: float | None = None
        self._last_valid_c: float | None = None
        self._consecutive_out = 0
        self._excluded_committed = 0
        self._seen = 0
        self._status: Status = "ok"
        self._effective_c: float | None = None

    # ------------------------------------------------------------------ input

    def update(self, reading: SensorReading) -> PotencyState:
        """Take one reported reading."""
        return self.update_sample(reading.t_s, reading.temp_c)

    def update_sample(self, t_s: float, temp_c: float) -> PotencyState:
        """Same as update() for a bare time and temperature (used for analysis of other series)."""
        cfg = self._cfg
        _kelvin(temp_c)  # validates the number
        if not math.isfinite(t_s):
            raise ValueError(f"time must be finite (got {t_s})")
        if self._prev_t_s is not None and t_s < self._prev_t_s:
            raise ValueError(f"time went backwards ({t_s} s after {self._prev_t_s} s)")
        dt_h = 0.0 if self._prev_t_s is None else (t_s - self._prev_t_s) / SECONDS_PER_HOUR
        self._prev_t_s = t_s
        self._seen += 1

        outside = temp_c < cfg.hard_limit_low_c or temp_c > cfg.hard_limit_high_c
        if not outside:
            self._commit_pending(use_actual=False)
            self._accept(temp_c, dt_h)
            self._consecutive_out = 0
            self._status = "ok"
        else:
            self._consecutive_out += 1
            if self._consecutive_out < cfg.hard_limit_consecutive_samples:
                self._pending.append(_Pending(temp_c, self._last_valid_c, dt_h))
                self._effective_c = self._last_valid_c
                self._status = "suspect"
            else:
                self._commit_pending(use_actual=True)
                self._accept(temp_c, dt_h)
                self._status = "excursion_confirmed"
        return self.snapshot()

    def _accept(self, temp_c: float, dt_h: float) -> None:
        self._totals.tau_eq_h += arrhenius_acceleration_factor(temp_c, self._cfg) * dt_h
        self._totals.mkt.add(temp_c, dt_h, self._cfg.Ea_over_R)
        self._last_valid_c = temp_c
        self._effective_c = temp_c

    def _commit_pending(self, use_actual: bool) -> None:
        """Decide the pending intervals: with their own temperatures (confirmed) or held ones."""
        for item in self._pending:
            temp_c = item.actual_temp_c if use_actual else item.held_temp_c
            if temp_c is not None:
                self._totals.tau_eq_h += (
                    arrhenius_acceleration_factor(temp_c, self._cfg) * item.dt_h
                )
                self._totals.mkt.add(temp_c, item.dt_h, self._cfg.Ea_over_R)
            if not use_actual:
                self._excluded_committed += 1
        self._pending = []

    # ------------------------------------------------------------------ output

    def snapshot(self) -> PotencyState:
        """The current state, including undecided suspect intervals (integrated as held)."""
        cfg = self._cfg
        tau_eq = self._totals.tau_eq_h
        mkt = self._totals.mkt
        if self._pending:
            mkt = mkt.copy()
            for item in self._pending:
                if item.held_temp_c is not None:
                    tau_eq += arrhenius_acceleration_factor(item.held_temp_c, cfg) * item.dt_h
                    mkt.add(item.held_temp_c, item.dt_h, cfg.Ea_over_R)
        potency = potency_from_tau_eq(tau_eq, cfg)
        effective = self._effective_c
        return PotencyState(
            t_s=0.0 if self._prev_t_s is None else self._prev_t_s,
            tau_eq_h=tau_eq,
            potency=potency,
            shelf_life_used_fraction=shelf_life_used_fraction(tau_eq, cfg),
            mkt_c=mkt.mkt_c(cfg.Ea_over_R),
            effective_temp_c=effective,
            current_af=None if effective is None else arrhenius_acceleration_factor(effective, cfg),
            hours_to_min_potency_at_current_temp=(
                None if effective is None else hours_to_min_potency_at_temp(tau_eq, effective, cfg)
            ),
            status=self._status,
            below_min_potency=potency < cfg.P_min,
            samples_seen=self._seen,
            samples_excluded=self._excluded_committed + len(self._pending),
        )
