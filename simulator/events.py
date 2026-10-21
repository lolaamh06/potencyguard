"""Event models: scheduled events (with resolved numbers), injected events, and the history record.

Three origins share one record type (EventRecord): "scheduled" (from a scenario file),
"freerun" (generated from a seed) and "injected" (typed in while a run is going).
Every event has a kind that tells the engine how it acts:

  cooling_factor  scales the cooling capacity (0 = stopped, 1 = normal)
  heat_load       extra heat inside the box, in watts (for example a door held open)
  ambient_offset  trapezoid shaped change of the temperature around the box (the cargo area)
  spoof           the REPORTED temperature is falsified; the true series never changes
  glitch          one isolated extreme reported temperature (one sample)
  shock           one large shock reading (one sample)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from edge.sensor_reading import TEMP_MAX_C, TEMP_MIN_C

KIND_COOLING = "cooling_factor"
KIND_HEAT = "heat_load"
KIND_AMBIENT = "ambient_offset"
KIND_SPOOF = "spoof"
KIND_GLITCH = "glitch"
KIND_SHOCK = "shock"
PHYSICAL_KINDS = (KIND_COOLING, KIND_HEAT, KIND_AMBIENT)
ONE_SHOT_KINDS = (KIND_GLITCH, KIND_SHOCK)

ORIGIN_SCHEDULED = "scheduled"
ORIGIN_FREERUN = "freerun"
ORIGIN_INJECTED = "injected"


@dataclass
class EventRecord:
    """One event in the history. Times are simulated seconds; end_s None means still open.

    One-shot events (glitch, shock) cover exactly one sample: end_s = start_s + sample interval.
    """

    id: str
    type: str
    kind: str
    origin: str
    start_s: float
    end_s: float | None
    params: dict = field(default_factory=dict)
    # True for an event that ends exactly at the end of the trip: it then also covers the
    # final sample (a window is otherwise open at the start and closed at the end).
    covers_final_sample: bool = False

    def active_at(self, t_s: float) -> bool:
        if t_s < self.start_s:
            return False
        if self.end_s is None or t_s < self.end_s:
            return True
        return self.covers_final_sample and t_s == self.end_s

    def overlaps(self, t0_s: float, t1_s: float) -> bool:
        return self.start_s < t1_s and (self.end_s is None or self.end_s > t0_s)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "kind": self.kind,
            "origin": self.origin,
            "start_s": self.start_s,
            "end_s": self.end_s,
            "covers_final_sample": self.covers_final_sample,
            "params": self.params,
        }

    def ambient_offset_c(self, t_s: float) -> float:
        """Trapezoid: ramp up, hold, ramp down. Only meaningful for ambient_offset events."""
        if self.end_s is None or not self.active_at(t_s):
            return 0.0
        delta = self.params["delta_c"]
        ramp_s = self.params["ramp_h"] * 3600.0
        if ramp_s <= 0:
            return delta
        share = min(1.0, (t_s - self.start_s) / ramp_s, (self.end_s - t_s) / ramp_s)
        return delta * max(0.0, share)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _check_window(start_h: float, end_h: float) -> None:
    if not end_h > start_h:
        raise ValueError(f"end_h ({end_h}) must be greater than start_h ({start_h})")


class HeatLoadEvent(_Strict):
    """Extra heat entering the box, for example a door held open. Watts, positive."""

    type: Literal["heat_load"]
    start_h: float = Field(ge=0)
    end_h: float
    power_w: float = Field(gt=0)
    rh_delta_pct: float = 0.0

    @model_validator(mode="after")
    def _window(self) -> HeatLoadEvent:
        _check_window(self.start_h, self.end_h)
        return self


class CoolingFactorEvent(_Strict):
    """Scales the cooling capacity: 0 is a full cooling failure, 1 is normal."""

    type: Literal["cooling_factor"]
    start_h: float = Field(ge=0)
    end_h: float
    factor: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _window(self) -> CoolingFactorEvent:
        _check_window(self.start_h, self.end_h)
        return self


class AmbientOffsetEvent(_Strict):
    """Offset of the temperature around the box that ramps up, holds and ramps down."""

    type: Literal["ambient_offset"]
    start_h: float = Field(ge=0)
    end_h: float
    delta_c: float
    ramp_h: float = Field(default=0.0, ge=0)

    @model_validator(mode="after")
    def _window(self) -> AmbientOffsetEvent:
        _check_window(self.start_h, self.end_h)
        if 2 * self.ramp_h > self.end_h - self.start_h:
            raise ValueError("two ramps must fit inside the event (2 * ramp_h <= end_h - start_h)")
        return self


SPOOF_MODES = ("hold", "offset", "replay", "drift", "mimic")
_SPOOF_PARAMETERS = (
    "reported_c",
    "delta_c",
    "replay_from_h",
    "replay_len_h",
    "rate_c_per_h",
    "max_offset_c",
)
# Phase 3B parameters. They are left out of dumps while unset, so every older event (and every
# golden recording that records its events) keeps exactly the bytes it had before they existed.
_PHASE_3B_PARAMETERS = ("rate_c_per_h", "max_offset_c")
_SPOOF_REQUIRED = {
    "hold": {"reported_c"},
    "offset": {"delta_c"},
    "replay": {"replay_from_h", "replay_len_h"},
    "drift": {"rate_c_per_h"},
    "mimic": set(),
}
_SPOOF_OPTIONAL = {"drift": {"max_offset_c"}}


def _check_spoof_parameters(model: _Strict) -> None:
    """Each spoof mode takes exactly its own parameters (plus the optional ones listed)."""
    needed = _SPOOF_REQUIRED[model.mode]  # type: ignore[attr-defined]
    allowed = needed | _SPOOF_OPTIONAL.get(model.mode, set())  # type: ignore[attr-defined]
    given = {name for name in _SPOOF_PARAMETERS if getattr(model, name) is not None}
    if not needed <= given or not given <= allowed:
        raise ValueError(
            f"spoof mode {model.mode!r} needs exactly {sorted(needed)}"  # type: ignore[attr-defined]
            + (f" and may add {sorted(allowed - needed)}" if allowed - needed else "")
            + f" (got {sorted(given)})"
        )


class _SpoofFields(_Strict):
    """Fields shared by the scheduled and the injectable spoof."""

    mode: Literal["hold", "offset", "replay", "drift", "mimic"]
    reported_c: float | None = Field(default=None, ge=TEMP_MIN_C, le=TEMP_MAX_C)
    delta_c: float | None = None
    replay_from_h: float | None = Field(default=None, ge=0)
    replay_len_h: float | None = Field(default=None, gt=0)
    # drift: the offset grows linearly from 0 at the start, in kelvin per hour, up to max_offset_c
    rate_c_per_h: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    max_offset_c: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    add_noise: bool | None = None

    def model_dump(self, **kwargs):  # type: ignore[override]
        data = super().model_dump(**kwargs)
        for name in _PHASE_3B_PARAMETERS:
            if data.get(name, 0) is None:
                del data[name]
        return data


class SpoofEvent(_SpoofFields):
    """The reported temperature is falsified. Modes: hold, offset, replay, drift, mimic.

    drift: reported = true - offset, offset = rate_c_per_h * hours since the start, capped at
    max_offset_c when given. mimic: the reported value follows a healthy copy of the box (an
    attacker with a model of the box); it needs no parameters.
    """

    type: Literal["spoof"]
    start_h: float = Field(ge=0)
    end_h: float

    @model_validator(mode="after")
    def _mode_parameters(self) -> SpoofEvent:
        _check_window(self.start_h, self.end_h)
        _check_spoof_parameters(self)
        if self.mode == "replay" and self.replay_from_h + self.replay_len_h > self.start_h:
            raise ValueError("replayed period must end before the spoof starts")
        return self

    @property
    def noise_enabled(self) -> bool:
        """Noise is added to every mode by default, except replay (only when asked)."""
        if self.add_noise is None:
            return self.mode != "replay"
        return self.add_noise


class GlitchEvent(_Strict):
    """A single isolated extreme reading at the sample nearest to at_h."""

    type: Literal["glitch"]
    at_h: float = Field(ge=0)
    value_c: float = Field(ge=TEMP_MIN_C, le=TEMP_MAX_C)


class ShockEvent(_Strict):
    """One large shock reading at the sample nearest to at_h."""

    type: Literal["shock"]
    at_h: float = Field(ge=0)
    peak_g: float = Field(gt=0)


ScheduledEvent = Annotated[
    HeatLoadEvent | CoolingFactorEvent | AmbientOffsetEvent | SpoofEvent | GlitchEvent | ShockEvent,
    Field(discriminator="type"),
]
SCHEDULED_MODELS: dict[str, type[_Strict]] = {
    "heat_load": HeatLoadEvent,
    "cooling_factor": CoolingFactorEvent,
    "ambient_offset": AmbientOffsetEvent,
    "spoof": SpoofEvent,
    "glitch": GlitchEvent,
    "shock": ShockEvent,
}


# ---------------------------------------------------------------------------
# Injectable events: the exact catalogue available while a run is going.
# ---------------------------------------------------------------------------


class KillCooling(_Strict):
    type: Literal["kill_cooling"]


class DerateCooling(_Strict):
    type: Literal["derate_cooling"]
    factor: float = Field(ge=0, le=1)


class RestoreCooling(_Strict):
    type: Literal["restore_cooling"]


class OpenDoor(_Strict):
    type: Literal["open_door"]
    duration_min: float = Field(gt=0)
    # Larger than the configured door_max_power_w is rejected by LiveSimulator.inject().
    power_w: float | None = Field(default=None, gt=0)


class _Soak(_Strict):
    duration_h: float = Field(gt=0)
    ramp_h: float = Field(default=0.0, ge=0)

    @model_validator(mode="after")
    def _ramps_fit(self):
        if 2 * self.ramp_h > self.duration_h:
            raise ValueError("two ramps must fit inside the event (2 * ramp_h <= duration_h)")
        return self


class HeatSoak(_Soak):
    type: Literal["heat_soak"]
    delta_c: float = Field(gt=0)


class ColdSnap(_Soak):
    type: Literal["cold_snap"]
    delta_c: float = Field(lt=0)


class SpoofSensor(_SpoofFields):
    type: Literal["spoof_sensor"]
    duration_min: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _mode_parameters(self) -> SpoofSensor:
        _check_spoof_parameters(self)
        return self


class StopSpoof(_Strict):
    type: Literal["stop_spoof"]


class GlitchSpike(_Strict):
    type: Literal["glitch_spike"]
    value_c: float = Field(ge=TEMP_MIN_C, le=TEMP_MAX_C)


class ShockInjection(_Strict):
    type: Literal["shock"]
    peak_g: float = Field(gt=0)


INJECTABLE_MODELS: dict[str, type[_Strict]] = {
    "kill_cooling": KillCooling,
    "derate_cooling": DerateCooling,
    "restore_cooling": RestoreCooling,
    "open_door": OpenDoor,
    "heat_soak": HeatSoak,
    "cold_snap": ColdSnap,
    "spoof_sensor": SpoofSensor,
    "stop_spoof": StopSpoof,
    "glitch_spike": GlitchSpike,
    "shock": ShockInjection,
}
InjectedEvent = _Strict


@dataclass(frozen=True)
class InjectionResult:
    """Outcome of LiveSimulator.inject(). A rejected injection never changes the run."""

    accepted: bool
    event_id: str | None = None
    message: str = ""
    error: str | None = None


def is_finite_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)
