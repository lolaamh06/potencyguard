"""BoxEngine: the one physics path. It advances the box by one SAMPLE per call to step().

Physics (master brief section 3.3), applied in equal internal substeps of at most
sim_substep_s seconds:

    T_next = T_inf + (T - T_inf) * exp(-dt / tau),   T_inf = T_amb + R_th * Q
    Q = Q_heat_loads + Q_cooling,   Q_cooling = -(capacity * cooling_factor) while the unit is ON

The cooling unit is a hysteresis (on/off) controller. It switches ON above setpoint + deadband/2
and OFF below setpoint - deadband/2, decided at the start of each substep. It never heats. This
produces the realistic wobble around the setpoint. The sample interval is split into
ceil(interval / substep) equal substeps, so the last step is never a short leftover.

Cooling duty: the fraction of the internal substeps of the interval that ended at this sample during
which the compressor was running (decided at the start of each substep). The first sample has no
interval behind it, so its duty is 0. The measured ambient temperature (the cargo area around the
box) is the true value plus Gaussian noise drawn from its OWN random stream, so adding this
channel changed none of the temperature, humidity or shock noise. A spoof changes only the
reported box temperature; the ambient and duty channels stay honest.

Order inside step(): first the physics moves from the previous sample time to this one, then the
sample is emitted. A fault injected after sample k was emitted therefore acts on the physics
leading to sample k + 1, and first shows in that sample.

Random numbers: the sensor-noise generator is used here and ONLY here, and every sample consumes
exactly three standard normal draws (temperature, humidity, shock) whatever events are active.
So injecting a fault, or changing a scenario's events, never changes the noise that follows.
Scenario parameter ranges and free-run faults use separate generators (see simulator/live.py).
"""

from __future__ import annotations

import math

import numpy as np

from edge.sensor_reading import TEMP_MAX_C, TEMP_MIN_C, SensorReading
from shared.config import BoxConfig
from simulator.box_model import decay_factor, steady_state_temp_c, step_with_decay
from simulator.events import (
    KIND_AMBIENT,
    KIND_COOLING,
    KIND_GLITCH,
    KIND_HEAT,
    KIND_SHOCK,
    KIND_SPOOF,
    PHYSICAL_KINDS,
    EventRecord,
)
from simulator.truth import TruthSample

# Values are rounded so that the engine and the recording files agree exactly.
DECIMALS = 4
SOURCE_NAME = "sim"


def _r(value: float) -> float:
    return round(float(value), DECIMALS)


class BoxEngine:
    """Physical state of one box. The event list is shared with, and edited by, LiveSimulator."""

    def __init__(
        self,
        box: BoxConfig,
        sample_interval_s: float,
        ambient_fn,
        rh_base_pct: float,
        noise_rng: np.random.Generator,
        events: list[EventRecord],
        ambient_noise_rng: np.random.Generator,
    ) -> None:
        self._box = box
        self.sample_interval_s = sample_interval_s
        self._ambient_fn = ambient_fn
        self._rh_base_pct = rh_base_pct
        self._rng = noise_rng
        self._ambient_rng = ambient_noise_rng
        self._events = events
        self._last_duty = 0.0  # no interval has elapsed before the first sample
        self._n_sub = max(1, math.ceil(sample_interval_s / box.sim_substep_s - 1e-9))
        self._dt_s = sample_interval_s / self._n_sub
        self._decay = decay_factor(self._dt_s, box.box_tau_h * 3600.0)
        self._half_band = box.box_deadband_c / 2.0
        self.true_temp_c = box.box_setpoint_c
        self.compressor_on = self.true_temp_c > box.box_setpoint_c + self._half_band
        self.n = 0
        self.reported_history: list[float] = []

    @property
    def now_s(self) -> float:
        """Time of the last emitted sample (0 before the first step)."""
        return max(self.n - 1, 0) * self.sample_interval_s

    @property
    def next_sample_s(self) -> float:
        return self.n * self.sample_interval_s

    def _active(self, kind: str, t_s: float) -> list[EventRecord]:
        return [e for e in self._events if e.kind == kind and e.active_at(t_s)]

    def _cooling_factor(self, t_s: float) -> float:
        factor = 1.0
        for event in self._active(KIND_COOLING, t_s):
            factor *= event.params["factor"]
        return factor

    def _ambient_c(self, t_s: float) -> float:
        offset = sum(e.ambient_offset_c(t_s) for e in self._active(KIND_AMBIENT, t_s))
        return self._ambient_fn(t_s) + offset

    def _advance(self, t_from_s: float) -> None:
        """Move the physics from t_from_s to t_from_s + one sample interval."""
        t_to_s = t_from_s + self.sample_interval_s
        relevant = [
            e for e in self._events if e.kind in PHYSICAL_KINDS and e.overlaps(t_from_s, t_to_s)
        ]
        box = self._box
        on_substeps = 0
        for k in range(self._n_sub):
            t_s = t_from_s + k * self._dt_s
            factor, heat_w, offset_c = 1.0, 0.0, 0.0
            for event in relevant:
                if not event.active_at(t_s):
                    continue
                if event.kind == KIND_COOLING:
                    factor *= event.params["factor"]
                elif event.kind == KIND_HEAT:
                    heat_w += event.params["power_w"]
                else:
                    offset_c += event.ambient_offset_c(t_s)
            if self.true_temp_c > box.box_setpoint_c + self._half_band:
                self.compressor_on = True
            elif self.true_temp_c < box.box_setpoint_c - self._half_band:
                self.compressor_on = False
            on_substeps += self.compressor_on
            cooling_w = -(box.box_cooling_capacity_w * factor) if self.compressor_on else 0.0
            t_inf = steady_state_temp_c(
                self._ambient_fn(t_s) + offset_c, box.box_R_th_k_per_w, heat_w + cooling_w
            )
            self.true_temp_c = step_with_decay(self.true_temp_c, t_inf, self._decay)
        self._last_duty = on_substeps / self._n_sub

    def step(self) -> tuple[SensorReading, TruthSample]:
        """Advance one sample and return what the sensor reported and what was really true."""
        if self.n > 0:
            self._advance((self.n - 1) * self.sample_interval_s)
        else:
            self._last_duty = 0.0
        t_s = self.n * self.sample_interval_s
        box = self._box
        noise_t, noise_rh, noise_shock = self._rng.standard_normal(3)
        # The ambient channel has its own stream, so the three draws above never change.
        noise_ambient = self._ambient_rng.standard_normal()
        true_ambient_c = self._ambient_c(t_s)
        measured_ambient_c = true_ambient_c + noise_ambient * box.sensor_sigma_ambient_c

        true_c = self.true_temp_c
        reported = true_c + noise_t * box.sensor_sigma_c
        rh = self._rh_base_pct + noise_rh * box.sensor_sigma_rh_pct
        shock = abs(noise_shock * box.sensor_sigma_shock_g)
        active = [e for e in self._events if e.active_at(t_s)]

        spoof_mode = None
        spoofs = [e for e in active if e.kind == KIND_SPOOF]
        if spoofs:
            spoof = max(spoofs, key=lambda e: e.start_s)  # the latest started spoof wins
            spoof_mode = spoof.params["mode"]
            noise = noise_t * box.sensor_sigma_c if spoof.params["add_noise"] else 0.0
            if spoof_mode == "hold":
                reported = spoof.params["reported_c"] + noise
            elif spoof_mode == "offset":
                reported = true_c - spoof.params["delta_c"] + noise
            else:
                length_s = spoof.params["replay_len_h"] * 3600.0
                into_s = (t_s - spoof.start_s) % length_s
                source_s = spoof.params["replay_from_h"] * 3600.0 + into_s
                index = min(
                    round(source_s / self.sample_interval_s), len(self.reported_history) - 1
                )
                reported = self.reported_history[index] + noise
        for event in active:
            if event.kind == KIND_HEAT:
                rh += event.params.get("rh_delta_pct", 0.0)
            elif event.kind == KIND_GLITCH:
                reported = event.params["value_c"]
            elif event.kind == KIND_SHOCK:
                shock += event.params["peak_g"]

        reading = SensorReading(
            t_s=_r(t_s),
            temp_c=_r(min(max(reported, TEMP_MIN_C), TEMP_MAX_C)),  # the sensor saturates
            rh_pct=_r(min(max(rh, 0.0), 100.0)),
            shock_g=_r(shock),
            source=SOURCE_NAME,
            ambient_c=_r(measured_ambient_c),
            cooling_duty=_r(self._last_duty),
        )
        truth = TruthSample(
            t_s=_r(t_s),
            true_temp_c=_r(true_c),
            reported_temp_c=reading.temp_c,
            ambient_c=_r(true_ambient_c),
            compressor_on=self.compressor_on,
            cooling_factor=_r(self._cooling_factor(t_s)),
            spoof_mode=spoof_mode,
            active_event_ids=[e.id for e in active],
            rh_pct=reading.rh_pct,
            cooling_duty=reading.cooling_duty,
            measured_ambient_c=reading.ambient_c,
        )
        self.reported_history.append(reading.temp_c)
        self.n += 1
        return reading, truth
