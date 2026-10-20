"""Scenario definitions loaded from YAML (Phase 1). Plain data only; no physics here."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from shared.config import REPO_ROOT, ConfigError

DEFAULT_SCENARIOS_DIR = REPO_ROOT / "simulator" / "scenarios"


class _Event(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HeatLoadEvent(_Event):
    """Extra heat entering the box, for example a door held open. Watts, positive."""

    type: Literal["heat_load"]
    start_h: float = Field(ge=0)
    end_h: float = Field(gt=0)
    power_w: float = Field(gt=0)
    rh_delta_pct: float = 0.0


class CoolingFactorEvent(_Event):
    """Scales the cooling capacity: 0 is a full cooling failure, 1 is normal."""

    type: Literal["cooling_factor"]
    start_h: float = Field(ge=0)
    end_h: float = Field(gt=0)
    factor: float = Field(ge=0, le=1)


class SpoofEvent(_Event):
    """The reported temperature is replaced by a false value; the box itself is unaffected."""

    type: Literal["spoof"]
    start_h: float = Field(ge=0)
    end_h: float = Field(gt=0)
    reported_c: float


class GlitchEvent(_Event):
    """A single isolated extreme reading at the sample nearest to at_h."""

    type: Literal["glitch"]
    at_h: float = Field(ge=0)
    value_c: float


class ShockEvent(_Event):
    """One large shock reading at the sample nearest to at_h."""

    type: Literal["shock"]
    at_h: float = Field(ge=0)
    peak_g: float = Field(gt=0)


Event = Annotated[
    HeatLoadEvent | CoolingFactorEvent | SpoofEvent | GlitchEvent | ShockEvent,
    Field(discriminator="type"),
]


class Scenario(BaseModel):
    """One simulated journey of one box."""

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
    events: list[Event] = Field(default_factory=list)

    @field_validator("ambient")
    @classmethod
    def _ambient_sorted_from_zero(cls, value: list[tuple[float, float]]):
        times = [t for t, _ in value]
        if times[0] != 0 or any(b <= a for a, b in zip(times, times[1:], strict=False)):
            raise ValueError("ambient keyframes must start at hour 0 and increase strictly")
        return value

    @model_validator(mode="after")
    def _interval_divides_duration(self) -> Scenario:
        steps = self.duration_h * 3600.0 / self.sample_interval_s
        if abs(steps - round(steps)) > 1e-9:
            raise ValueError("duration_h must be a whole number of sample intervals")
        return self

    @property
    def n_samples(self) -> int:
        return round(self.duration_h * 3600.0 / self.sample_interval_s) + 1


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
