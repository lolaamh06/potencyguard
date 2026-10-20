"""Free-run mode: a random trip built from a seed, with no scenario file (Phase 2A).

The climate and the faults come from the "freerun_*" block of config/product_default.yaml
(placeholder values, not sourced [SOURCE NEEDED]). Faults are planned one simulated hour at a
time, in order, from a dedicated random stream, so a finite trip and an endless trip with the
same seed start identically.

Rules:
- some trips have no fault at all (freerun_clean_trip_prob);
- at most one spoof is active at a time;
- a spoof can only start after a physical fault (cooling loss or heat) has begun.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from shared.config import BoxConfig, ConfigError, read_yaml_mapping
from simulator.events import (
    KIND_AMBIENT,
    KIND_COOLING,
    KIND_GLITCH,
    KIND_HEAT,
    KIND_SHOCK,
    KIND_SPOOF,
    ORIGIN_FREERUN,
    EventRecord,
)

PREFIX = "freerun_"


class FreerunConfig(BaseModel):
    """All free-run tunables. Every value is a placeholder [SOURCE NEEDED]."""

    model_config = ConfigDict(extra="forbid")

    sample_interval_s: float = Field(gt=0)
    default_hours: float = Field(gt=0)
    rh_base_pct: float = Field(ge=0, le=100)
    clean_trip_prob: float = Field(ge=0, le=1)
    base_temp_min_c: float
    base_temp_max_c: float
    swing_min_c: float = Field(ge=0)
    swing_max_c: float = Field(ge=0)
    kill_cooling_prob: float = Field(ge=0, le=1)
    kill_cooling_hours_min: float = Field(gt=0)
    kill_cooling_hours_max: float = Field(gt=0)
    derate_cooling_prob: float = Field(ge=0, le=1)
    derate_factor_min: float = Field(ge=0, le=1)
    derate_factor_max: float = Field(ge=0, le=1)
    derate_hours_min: float = Field(gt=0)
    derate_hours_max: float = Field(gt=0)
    open_door_prob: float = Field(ge=0, le=1)
    open_door_minutes_min: float = Field(gt=0)
    open_door_minutes_max: float = Field(gt=0)
    heat_soak_prob: float = Field(ge=0, le=1)
    heat_soak_delta_min_c: float = Field(gt=0)
    heat_soak_delta_max_c: float = Field(gt=0)
    heat_soak_hours_min: float = Field(gt=0)
    heat_soak_hours_max: float = Field(gt=0)
    heat_soak_ramp_hours_min: float = Field(ge=0)
    heat_soak_ramp_hours_max: float = Field(ge=0)
    cold_snap_prob: float = Field(ge=0, le=1)
    cold_snap_delta_min_c: float = Field(lt=0)
    cold_snap_delta_max_c: float = Field(lt=0)
    cold_snap_hours_min: float = Field(gt=0)
    cold_snap_hours_max: float = Field(gt=0)
    cold_snap_ramp_hours_min: float = Field(ge=0)
    cold_snap_ramp_hours_max: float = Field(ge=0)
    spoof_prob: float = Field(ge=0, le=1)
    spoof_hours_min: float = Field(gt=0)
    spoof_hours_max: float = Field(gt=0)
    spoof_hold_c_min: float
    spoof_hold_c_max: float
    spoof_offset_c_min: float = Field(gt=0)
    spoof_offset_c_max: float = Field(gt=0)
    spoof_replay_len_hours_min: float = Field(gt=0)
    spoof_replay_len_hours_max: float = Field(gt=0)
    glitch_prob: float = Field(ge=0, le=1)
    glitch_value_min_c: float
    glitch_value_max_c: float
    shock_prob: float = Field(ge=0, le=1)
    shock_peak_min_g: float = Field(gt=0)
    shock_peak_max_g: float = Field(gt=0)

    @model_validator(mode="after")
    def _ranges_ordered(self) -> FreerunConfig:
        """Every *_min* field must not exceed its *_max* partner."""
        for name in type(self).model_fields:
            if "_min" in name:
                partner = name.replace("_min", "_max", 1)
                if partner in type(self).model_fields and getattr(self, name) > getattr(
                    self, partner
                ):
                    raise ValueError(f"{PREFIX}{name} must not exceed {PREFIX}{partner}")
        return self


def load_freerun_config(path: Path | str | None = None) -> FreerunConfig:
    """Read the freerun_* keys from the product YAML file."""
    raw = read_yaml_mapping(path)
    values = {key[len(PREFIX) :]: value for key, value in raw.items() if key.startswith(PREFIX)}
    for key, value in values.items():
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ConfigError(f"{PREFIX}{key} must be a number (got {value!r})")
    try:
        return FreerunConfig.model_validate(values)
    except ValidationError as exc:
        raise ConfigError(f"invalid freerun settings: {exc}") from exc


@dataclass(frozen=True)
class FreeRun:
    """What to simulate: a random trip. hours None means endless."""

    config: FreerunConfig
    hours: float | None = None


class FreeRunPlanner:
    """Builds the climate at construction and plans faults lazily, one hour at a time."""

    def __init__(self, spec: FreeRun, box: BoxConfig, rng: np.random.Generator) -> None:
        cfg = spec.config
        self._cfg = cfg
        self._box = box
        self._rng = rng
        self.clean_trip = bool(rng.random() < cfg.clean_trip_prob)
        base = float(rng.uniform(cfg.base_temp_min_c, cfg.base_temp_max_c))
        swing = float(rng.uniform(cfg.swing_min_c, cfg.swing_max_c))
        phase = float(rng.uniform(0.0, 2.0 * math.pi))
        self.climate = {
            "base_c": round(base, 4),
            "swing_c": round(swing, 4),
            "phase": round(phase, 4),
        }
        self._planned_hours = 0
        self._counter = 0
        self._first_physical_s: float | None = None
        self._spoof_end_s = -math.inf

    def ambient_function(self) -> Callable[[float], float]:
        base, swing, phase = (self.climate[k] for k in ("base_c", "swing_c", "phase"))
        return lambda t_s: base + swing * math.sin(2.0 * math.pi * t_s / 86400.0 + phase)

    def _uniform(self, low: float, high: float) -> float:
        return round(float(self._rng.uniform(low, high)), 4)

    def _event(self, type_: str, kind: str, start_s: float, end_s: float, params: dict):
        self._counter += 1
        return EventRecord(
            id=f"fr-{self._counter:03d}-{type_}",
            type=type_,
            kind=kind,
            origin=ORIGIN_FREERUN,
            start_s=round(start_s, 1),
            end_s=round(end_s, 1),
            params=params,
        )

    def plan_through(self, time_s: float, interval_s: float) -> list[EventRecord]:
        """Plan every not yet planned hour that starts before time_s; return the new events."""
        new: list[EventRecord] = []
        while self._planned_hours * 3600.0 < time_s:
            new.extend(self._plan_hour(self._planned_hours, interval_s))
            self._planned_hours += 1
        return new

    def _plan_hour(self, hour: int, interval_s: float) -> list[EventRecord]:
        cfg, rng = self._cfg, self._rng
        events: list[EventRecord] = []

        def chance(prob: float) -> bool:
            return rng.random() < prob and not self.clean_trip

        def start() -> float:
            return (hour + float(rng.random())) * 3600.0

        if chance(cfg.kill_cooling_prob):
            s = start()
            e = s + self._uniform(cfg.kill_cooling_hours_min, cfg.kill_cooling_hours_max) * 3600
            events.append(self._event("kill_cooling", KIND_COOLING, s, e, {"factor": 0.0}))
        if chance(cfg.derate_cooling_prob):
            s = start()
            e = s + self._uniform(cfg.derate_hours_min, cfg.derate_hours_max) * 3600
            factor = self._uniform(cfg.derate_factor_min, cfg.derate_factor_max)
            events.append(self._event("derate_cooling", KIND_COOLING, s, e, {"factor": factor}))
        if chance(cfg.open_door_prob):
            s = start()
            e = s + self._uniform(cfg.open_door_minutes_min, cfg.open_door_minutes_max) * 60
            params = {"power_w": self._box.door_default_power_w, "rh_delta_pct": 0.0}
            events.append(self._event("open_door", KIND_HEAT, s, e, params))
        if chance(cfg.heat_soak_prob):
            s = start()
            hours = self._uniform(cfg.heat_soak_hours_min, cfg.heat_soak_hours_max)
            ramp = min(
                self._uniform(cfg.heat_soak_ramp_hours_min, cfg.heat_soak_ramp_hours_max), hours / 2
            )
            delta = self._uniform(cfg.heat_soak_delta_min_c, cfg.heat_soak_delta_max_c)
            params = {"delta_c": delta, "ramp_h": ramp}
            events.append(self._event("heat_soak", KIND_AMBIENT, s, s + hours * 3600, params))
        if chance(cfg.cold_snap_prob):
            s = start()
            hours = self._uniform(cfg.cold_snap_hours_min, cfg.cold_snap_hours_max)
            ramp = min(
                self._uniform(cfg.cold_snap_ramp_hours_min, cfg.cold_snap_ramp_hours_max), hours / 2
            )
            delta = self._uniform(cfg.cold_snap_delta_min_c, cfg.cold_snap_delta_max_c)
            params = {"delta_c": delta, "ramp_h": ramp}
            events.append(self._event("cold_snap", KIND_AMBIENT, s, s + hours * 3600, params))

        for event in events:
            if event.type in ("kill_cooling", "derate_cooling", "open_door", "heat_soak"):
                if self._first_physical_s is None or event.start_s < self._first_physical_s:
                    self._first_physical_s = event.start_s

        if chance(cfg.spoof_prob):
            s = start()
            hours = self._uniform(cfg.spoof_hours_min, cfg.spoof_hours_max)
            mode = ("hold", "offset", "replay")[int(rng.integers(0, 3))]
            params: dict = {"mode": mode, "add_noise": mode != "replay"}
            if mode == "hold":
                params["reported_c"] = self._uniform(cfg.spoof_hold_c_min, cfg.spoof_hold_c_max)
            elif mode == "offset":
                params["delta_c"] = self._uniform(cfg.spoof_offset_c_min, cfg.spoof_offset_c_max)
            else:
                length = self._uniform(
                    cfg.spoof_replay_len_hours_min, cfg.spoof_replay_len_hours_max
                )
                latest_from = s / 3600.0 - length
                if latest_from >= 0:
                    params["replay_len_h"] = length
                    params["replay_from_h"] = round(float(rng.uniform(0.0, latest_from)), 4)
                else:
                    params = {}
            allowed = (
                params
                and self._first_physical_s is not None
                and s >= self._first_physical_s
                and s >= self._spoof_end_s
            )
            if allowed:
                events.append(self._event("spoof_sensor", KIND_SPOOF, s, s + hours * 3600, params))
                self._spoof_end_s = s + hours * 3600
        if chance(cfg.glitch_prob):
            s = round(start() / interval_s) * interval_s
            value = self._uniform(cfg.glitch_value_min_c, cfg.glitch_value_max_c)
            events.append(
                self._event("glitch_spike", KIND_GLITCH, s, s + interval_s, {"value_c": value})
            )
        if chance(cfg.shock_prob):
            s = round(start() / interval_s) * interval_s
            peak = self._uniform(cfg.shock_peak_min_g, cfg.shock_peak_max_g)
            events.append(self._event("shock", KIND_SHOCK, s, s + interval_s, {"peak_g": peak}))
        return events
