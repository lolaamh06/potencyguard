"""Scenario definitions loaded from YAML, with random ranges resolved once per run (Phase 2A).

Any numeric event field may be a number or a range {min: a, max: b}. A range is drawn once per
run (uniform) by the parameter random stream. Ranges for start and end of one event must not
overlap (start max < end min), so every possible draw is a valid event.
"""

from __future__ import annotations

import bisect
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from shared.config import REPO_ROOT, ConfigError
from simulator.events import SCHEDULED_MODELS, ScheduledEvent
from simulator.expectations import validate_expect_block

DEFAULT_SCENARIOS_DIR = REPO_ROOT / "simulator" / "scenarios"
RESOLVED_DECIMALS = 4
_NON_NUMERIC_KEYS = ("type", "mode", "add_noise")


class ScenarioError(ValueError):
    """Raised when a scenario file or one of its events is invalid."""


def _is_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _range_bounds(value: object) -> tuple[float, float] | None:
    """Return (min, max) if value is a range mapping, None if it is a plain number."""
    if isinstance(value, dict):
        if set(value) != {"min", "max"} or not all(_is_number(v) for v in value.values()):
            raise ScenarioError(f"a range needs numeric min and max (got {value!r})")
        if value["min"] > value["max"]:
            raise ScenarioError(f"range min must not exceed max (got {value!r})")
        return float(value["min"]), float(value["max"])
    return None


def _split_event(raw: dict, label: str) -> tuple[dict, dict]:
    """Return (all-minimum values, all-maximum values) for a raw event dict."""
    low, high = {}, {}
    for key, value in raw.items():
        if key in _NON_NUMERIC_KEYS:
            low[key] = high[key] = value
            continue
        bounds = _range_bounds(value)
        if bounds is None:
            if not _is_number(value):
                raise ScenarioError(f"{label}: {key} must be a number or a range (got {value!r})")
            low[key] = high[key] = value
        else:
            low[key], high[key] = bounds
    return low, high


def validate_raw_event(raw: dict, duration_h: float, label: str) -> None:
    """Check one event dict (with ranges) without drawing anything."""
    if not isinstance(raw, dict) or raw.get("type") not in SCHEDULED_MODELS:
        kind = raw.get("type") if isinstance(raw, dict) else raw
        raise ScenarioError(f"{label}: unknown event type {kind!r}")
    model = SCHEDULED_MODELS[raw["type"]]
    low, high = _split_event(raw, label)
    try:
        model.model_validate(low)
        model.model_validate(high)
    except ValidationError as exc:
        raise ScenarioError(f"{label}: {exc}") from exc
    if "start_h" in raw and "end_h" in raw and not high["start_h"] < low["end_h"]:
        raise ScenarioError(f"{label}: start_h range can reach or pass the end_h range")
    for key in ("end_h", "at_h"):
        if key in high and high[key] > duration_h:
            raise ScenarioError(f"{label}: {key} can lie outside the trip ({duration_h} h)")
    if (
        raw["type"] == "ambient_offset"
        and 2 * high.get("ramp_h", 0.0) > low["end_h"] - high["start_h"]
    ):
        raise ScenarioError(f"{label}: two ramps may not fit inside every possible event")
    if raw["type"] == "spoof" and raw.get("mode") == "replay":
        if high["replay_from_h"] + high["replay_len_h"] > low["start_h"]:
            raise ScenarioError(f"{label}: replayed period may end after the spoof starts")


class Scenario(BaseModel):
    """One simulated journey of one box (the file, before ranges are drawn)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    seed: int = Field(ge=0)
    duration_h: float = Field(gt=0)
    sample_interval_s: float = Field(gt=0)
    ambient: list[tuple[float, float]] = Field(
        min_length=1, description="Keyframes (hours, deg C), linearly interpolated"
    )
    rh_base_pct: float = Field(default=45.0, ge=0, le=100)
    ambient_jitter_c: float = Field(default=0.0, ge=0)
    ambient_shift_h: float = Field(default=0.0, ge=0)
    events: list[dict] = Field(default_factory=list)
    expect: dict = Field(default_factory=dict)

    @field_validator("ambient")
    @classmethod
    def _ambient_sorted_from_zero(cls, value: list[tuple[float, float]]):
        times = [t for t, _ in value]
        if times[0] != 0 or any(b <= a for a, b in zip(times, times[1:], strict=False)):
            raise ValueError("ambient keyframes must start at hour 0 and increase strictly")
        return value

    @field_validator("expect")
    @classmethod
    def _expect_known(cls, value: dict):
        validate_expect_block(value)
        return value

    @model_validator(mode="after")
    def _check(self) -> Scenario:
        steps = self.duration_h * 3600.0 / self.sample_interval_s
        if abs(steps - round(steps)) > 1e-9:
            raise ValueError("duration_h must be a whole number of sample intervals")
        for index, raw in enumerate(self.events):
            try:
                validate_raw_event(raw, self.duration_h, f"event {index + 1}")
            except ScenarioError as exc:
                raise ValueError(str(exc)) from exc
        return self

    @property
    def n_samples(self) -> int:
        return round(self.duration_h * 3600.0 / self.sample_interval_s) + 1


@dataclass(frozen=True)
class ResolvedScenario:
    """A scenario after every range was drawn: plain numbers only."""

    scenario: Scenario
    ambient_jitter_c: float
    ambient_shift_h: float
    events: list[ScheduledEvent] = field(default_factory=list)

    def parameters(self) -> dict:
        """Resolved numbers, for the ground-truth file."""
        return {
            "ambient_jitter_c": self.ambient_jitter_c,
            "ambient_shift_h": self.ambient_shift_h,
            "events": [event.model_dump() for event in self.events],
        }

    def ambient_function(self) -> Callable[[float], float]:
        """Outside temperature at a simulated time in seconds.

        The keyframes are moved later by ambient_shift_h and the whole profile is moved by
        ambient_jitter_c. Before the first and after the last keyframe the value is held
        constant (clamped), because a journey is not periodic.
        """
        times = [(t + self.ambient_shift_h) * 3600.0 for t, _ in self.scenario.ambient]
        temps = [c + self.ambient_jitter_c for _, c in self.scenario.ambient]
        return piecewise_linear(times, temps)


def piecewise_linear(times: list[float], values: list[float]) -> Callable[[float], float]:
    """Linear interpolation that holds the end values outside the range."""

    def at(t_s: float) -> float:
        if t_s <= times[0]:
            return values[0]
        if t_s >= times[-1]:
            return values[-1]
        i = bisect.bisect_right(times, t_s)
        t0, t1 = times[i - 1], times[i]
        v0, v1 = values[i - 1], values[i]
        return v0 + (v1 - v0) * (t_s - t0) / (t1 - t0)

    return at


def _draw(value: object, rng: np.random.Generator) -> object:
    bounds = _range_bounds(value)
    if bounds is None:
        return value
    return round(float(rng.uniform(bounds[0], bounds[1])), RESOLVED_DECIMALS)


def resolve_scenario(scenario: Scenario, rng: np.random.Generator) -> ResolvedScenario:
    """Draw every range once, in file order. The same generator state gives the same result."""
    jitter = (
        round(float(rng.uniform(-scenario.ambient_jitter_c, scenario.ambient_jitter_c)), 4)
        if scenario.ambient_jitter_c > 0
        else 0.0
    )
    shift = (
        round(float(rng.uniform(-scenario.ambient_shift_h, scenario.ambient_shift_h)), 4)
        if scenario.ambient_shift_h > 0
        else 0.0
    )
    events: list[ScheduledEvent] = []
    for index, raw in enumerate(scenario.events):
        resolved = {key: _draw(value, rng) for key, value in raw.items()}
        try:
            event = SCHEDULED_MODELS[raw["type"]].model_validate(resolved)
        except ValidationError as exc:
            raise ScenarioError(f"event {index + 1}: {exc}") from exc
        for key in ("end_h", "at_h"):
            if getattr(event, key, 0.0) > scenario.duration_h:
                raise ScenarioError(f"event {index + 1}: {key} lies outside the trip")
        events.append(event)
    return ResolvedScenario(scenario, jitter, shift, events)


def load_scenario(path: Path | str) -> Scenario:
    """Load one scenario YAML file."""
    file = Path(path)
    try:
        raw = yaml.safe_load(file.read_text(encoding="utf-8"))
        return Scenario.model_validate(raw)
    except (OSError, yaml.YAMLError, ValueError) as exc:
        raise ConfigError(f"cannot load scenario {file}: {exc}") from exc


def load_all_scenarios(directory: Path | str | None = None) -> dict[str, Scenario]:
    """Load every *.yaml scenario in a folder, keyed by scenario id (sorted by file name)."""
    folder = Path(directory) if directory is not None else DEFAULT_SCENARIOS_DIR
    scenarios: dict[str, Scenario] = {}
    for file in sorted(folder.glob("*.yaml")):
        scenario = load_scenario(file)
        if scenario.id in scenarios:
            raise ConfigError(f"duplicate scenario id {scenario.id!r} in {file}")
        scenarios[scenario.id] = scenario
    return scenarios
