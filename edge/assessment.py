"""Potency assessment: the reported potency together with how far it can be trusted (Phase 3B).

When the tamper monitor has declared the reported data untrusted from a time t0 (a falsification
verdict, or a twin that is out of date), the reported potency is only a label. This module also
gives an UPPER BOUND on the damage, computed from readings only:

    from the last trusted reading at t0, integrate the box forward with NO cooling at all
    (duty 0), driven by the measured ambient temperature, and feed that worst-case temperature
    series to the potency maths (same Arrhenius factor and right-endpoint rule as PotencyTracker).

Worst-case series (twin dynamics, the monitor's own tau):
    T_w[t0] = reported temperature at t0
    T_w[n+1] = T_inf + (T_w[n] - T_inf) * exp(-dt / tau),  T_inf = ambient (average of both ends)
    in the FIRST step only, T_inf = ambient + heat_allowance_c (one unseen heat load, at most the
    configured allowance, see config/detectors.yaml); later steps add none.

What the bound ASSUMES: the ambient channel is honest (the threat model: only the box thermistor
is tampered with); the box obeys the twin's time constant; the cooling unit does nothing after t0.
What it IGNORES: unseen heat loads beyond one allowance, a falsified ambient channel, and any
error of the twin's time constant for the real box. Where those do not hold, the bound can be
wrong. It never uses ground truth.

It is an upper bound, not an estimate: it is deliberately pessimistic (it assumes the cooling
unit failed), so a trusted-looking trip that was lied about can look worse than it was.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from edge.potency import (
    PotencyState,
    PotencyTracker,
    arrhenius_acceleration_factor,
    potency_from_tau_eq,
    shelf_life_used_fraction,
)
from edge.sensor_reading import SensorReading
from edge.tamper_monitor import (
    FALSIFICATION,
    LOW_CONFIDENCE,
    OUT_OF_DATE,
    TRUSTED,
    UNTRUSTED,
    MonitorState,
    TamperMonitor,
)
from edge.thermal_twin import TwinParams
from shared.config import ProductConfig

SECONDS_PER_HOUR = 3600.0


class WorstCaseBound(BaseModel):
    """An upper bound on the damage since t0, and the potency it implies."""

    model_config = ConfigDict(frozen=True)

    t0_s: float
    t0_h: float
    tau_eq_from_t0_h: float  # the bound on tau_eq accumulated from t0 to the latest reading
    tau_eq_before_t0_h: float  # tau_eq of the reported readings up to t0 (trusted by assumption)
    tau_eq_total_h: float
    potency: float
    shelf_life_used_fraction: float
    worst_case_temp_c: float  # the worst-case box temperature at the latest reading
    samples_after_t0: int


class WorstCaseIntegrator:
    """Incremental worst-case integration from a start reading (one call per later reading)."""

    def __init__(
        self,
        product: ProductConfig,
        params: TwinParams,
        heat_allowance_c: float,
        start: SensorReading,
        tau_eq_before_h: float,
    ) -> None:
        if start.ambient_c is None:
            raise ValueError("the worst-case bound needs the ambient channel")
        self._product = product
        self._params = params
        self._allowance = heat_allowance_c
        self._t0_s = start.t_s
        self._tau_before = tau_eq_before_h
        self._prev_t_s = start.t_s
        self._prev_amb = start.ambient_c
        self._temp_c = start.temp_c
        self._added_h = 0.0
        self._count = 0

    def advance(self, reading: SensorReading) -> None:
        """Move one reading on. Uses the time and the measured ambient only (never the duty)."""
        if reading.ambient_c is None:
            raise ValueError("the worst-case bound needs the ambient channel")
        dt_s = reading.t_s - self._prev_t_s
        if dt_s <= 0:
            raise ValueError(f"time must increase ({reading.t_s} s after {self._prev_t_s} s)")
        ambient = (self._prev_amb + reading.ambient_c) / 2.0
        t_inf = ambient + (self._allowance if self._count == 0 else 0.0)
        decay = math.exp(-dt_s / self._params.tau_s)
        self._temp_c = t_inf + (self._temp_c - t_inf) * decay
        self._added_h += (
            arrhenius_acceleration_factor(self._temp_c, self._product) * dt_s / SECONDS_PER_HOUR
        )
        self._prev_t_s, self._prev_amb = reading.t_s, reading.ambient_c
        self._count += 1

    def bound(self) -> WorstCaseBound:
        total = self._tau_before + self._added_h
        return WorstCaseBound(
            t0_s=self._t0_s,
            t0_h=self._t0_s / SECONDS_PER_HOUR,
            tau_eq_from_t0_h=self._added_h,
            tau_eq_before_t0_h=self._tau_before,
            tau_eq_total_h=total,
            potency=potency_from_tau_eq(total, self._product),
            shelf_life_used_fraction=shelf_life_used_fraction(total, self._product),
            worst_case_temp_c=self._temp_c,
            samples_after_t0=self._count,
        )


def worst_case_bound(
    readings: Sequence[SensorReading],
    t0_s: float,
    tau_eq_before_t0_h: float,
    product: ProductConfig,
    params: TwinParams,
    heat_allowance_c: float,
) -> WorstCaseBound:
    """Upper bound from the reading at t0 to the last reading of `readings` (see module docs).

    `tau_eq_before_t0_h` is the equivalent reference time the potency tracker had accumulated at
    t0. `readings` must contain a reading at exactly t0_s.
    """
    index = next((i for i, r in enumerate(readings) if r.t_s == t0_s), None)
    if index is None:
        raise ValueError(f"no reading at t0 = {t0_s} s")
    integrator = WorstCaseIntegrator(
        product, params, heat_allowance_c, readings[index], tau_eq_before_t0_h
    )
    for reading in readings[index + 1 :]:
        integrator.advance(reading)
    return integrator.bound()


class PotencyAssessment(BaseModel):
    """The reported potency, whether to trust it, and the worst case when it is not trusted."""

    model_config = ConfigDict(frozen=True)

    t_s: float
    reported_potency: float
    reported_shelf_life_used_fraction: float
    trust_level: str  # "trusted", "low_confidence" or "untrusted"
    trusted: bool  # derived: trust_level == "trusted"
    trust_reason: str
    untrusted_since_s: float | None
    worst_case_potency: float | None
    worst_case_shelf_life_used_fraction: float | None
    verdict: str
    operator_message: str | None = None


TRUST_TEXT = {
    None: "no evidence against the reported readings",
    FALSIFICATION: "the monitor found the reported temperature inconsistent with the physics",
    OUT_OF_DATE: "the twin is out of date for this box, so the readings cannot be checked",
}
OPERATOR_REVIEW_TEXT = "operator review recommended: the twin may not match this box"


def assess(
    potency_state: PotencyState, monitor_state: MonitorState, bound: WorstCaseBound | None
) -> PotencyAssessment:
    """Combine the potency tracker, the monitor and (when untrusted) the worst-case bound.

    Pure function. A bound is required to be consistent with the monitor: it must start at the
    time the monitor says the data became doubtful, and only an UNTRUSTED trip has one.

    Why no bound for low_confidence: the bound assumes the twin's dynamics describe the box (its
    time constant), and a low-confidence trip is exactly the case where the twin is suspected not
    to match, so a number computed from it would look more certain than it is. The operator is
    asked to review instead.
    """
    untrusted_since = monitor_state.untrusted_since_s
    level = monitor_state.trust_level
    if level != UNTRUSTED and bound is not None:
        if level == TRUSTED:
            raise ValueError("a worst-case bound was given for data the monitor still trusts")
        raise ValueError(
            f"a worst-case bound was given for a {level} trip (it needs a trusted twin)"
        )
    if bound is not None and bound.t0_s != untrusted_since:
        raise ValueError(
            f"the bound starts at {bound.t0_s} s but the data became doubtful at "
            f"{untrusted_since} s"
        )
    if level == UNTRUSTED:
        reason_text = TRUST_TEXT[FALSIFICATION]
    else:
        reason_text = TRUST_TEXT[monitor_state.untrusted_reason]
    return PotencyAssessment(
        t_s=potency_state.t_s,
        reported_potency=potency_state.potency,
        reported_shelf_life_used_fraction=potency_state.shelf_life_used_fraction,
        trust_level=level,
        trusted=level == TRUSTED,
        operator_message=OPERATOR_REVIEW_TEXT if level == LOW_CONFIDENCE else None,
        trust_reason=reason_text,
        untrusted_since_s=untrusted_since,
        worst_case_potency=None if bound is None else bound.potency,
        worst_case_shelf_life_used_fraction=None
        if bound is None
        else bound.shelf_life_used_fraction,
        verdict=monitor_state.verdict,
    )


class TrustAssessor:
    """Streaming wrapper: monitor + potency tracker + worst-case bound, one reading at a time."""

    def __init__(self, product: ProductConfig, monitor: TamperMonitor) -> None:
        self._product = product
        self.monitor = monitor
        self.tracker = PotencyTracker(product)
        self.reset()

    def reset(self) -> None:
        self.monitor.reset()
        self.tracker.reset()
        self._readings: list[SensorReading] = []
        self._tau_eq: list[float] = []
        self._integrator: WorstCaseIntegrator | None = None
        self._t0_s: float | None = None
        self.last_bound: WorstCaseBound | None = None

    def update(
        self, reading: SensorReading
    ) -> tuple[PotencyAssessment, PotencyState, MonitorState]:
        monitor_state = self.monitor.update(reading)
        potency_state = self.tracker.update(reading)
        self._readings.append(reading)
        self._tau_eq.append(potency_state.tau_eq_h)
        t0 = monitor_state.untrusted_since_s
        bound = None
        if t0 is not None and monitor_state.trust_level == UNTRUSTED:
            if self._integrator is None or t0 != self._t0_s:
                self._start_from(t0)
            else:
                self._integrator.advance(reading)
            bound = self._integrator.bound()  # type: ignore[union-attr]
        self.last_bound = bound
        return assess(potency_state, monitor_state, bound), potency_state, monitor_state

    def _start_from(self, t0_s: float) -> None:
        """(Re)start the integration at t0 and catch up with the readings so far."""
        index = next(i for i, r in enumerate(self._readings) if r.t_s == t0_s)
        params, cfg = self.monitor.params, self.monitor.config
        self._integrator = WorstCaseIntegrator(
            self._product, params, cfg.heat_allowance_c, self._readings[index], self._tau_eq[index]
        )
        for reading in self._readings[index + 1 :]:
            self._integrator.advance(reading)
        self._t0_s = t0_s
