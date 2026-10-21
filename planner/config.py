"""Planner settings, read from config/planner.yaml and validated (Phase 5).

Every number in the file is an illustrative placeholder, not sourced [SOURCE NEEDED].
The planner recommends; it never executes. Final authority stays with QA.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from shared.config import REPO_ROOT, ConfigError, read_yaml_mapping

DEFAULT_PLANNER_PATH = REPO_ROOT / "config" / "planner.yaml"
ACTIONS = ("continue", "expedite", "reroute_to_depot", "re_source", "quarantine")


class ActionConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    cost: float = Field(ge=0, allow_inf_nan=False)
    time_factor: float = Field(ge=0, allow_inf_nan=False)
    time_offset_h: float = Field(ge=0, allow_inf_nan=False)
    delay_mean_h: float = Field(ge=0, allow_inf_nan=False)
    delay_sd_h: float = Field(ge=0, allow_inf_nan=False)
    extra_delay_h: float = Field(ge=0, allow_inf_nan=False)
    cooling_fail_probability: float = Field(ge=0, le=1, allow_inf_nan=False)
    ambient_mode: Literal["route", "depot"]
    fresh_start: bool


class AmbientConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    route_mean_mode: Literal["persistence", "fixed"]
    route_mean_c: float = Field(allow_inf_nan=False)
    route_theta_per_h: float = Field(gt=0, allow_inf_nan=False)
    route_sigma_c: float = Field(ge=0, allow_inf_nan=False)
    depot_mean_c: float = Field(allow_inf_nan=False)
    depot_theta_per_h: float = Field(gt=0, allow_inf_nan=False)
    depot_sigma_c: float = Field(ge=0, allow_inf_nan=False)
    heatwave_probability: float = Field(ge=0, le=1, allow_inf_nan=False)
    heatwave_offset_c: float = Field(ge=0, allow_inf_nan=False)
    heatwave_duration_h: float = Field(gt=0, allow_inf_nan=False)


class PlannerConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    planner_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9_.-]+$")
    alpha: float = Field(ge=0, lt=1, allow_inf_nan=False)
    n_scenarios: int = Field(ge=100)
    seed: int = Field(ge=0)
    V: float = Field(gt=0, allow_inf_nan=False)
    beta: float = Field(ge=0, allow_inf_nan=False)
    dt_h: float = Field(gt=0, le=6, allow_inf_nan=False)
    max_horizon_h: float = Field(gt=0, allow_inf_nan=False)
    v_thr: float = Field(gt=0, allow_inf_nan=False)
    confidence_gap_thr: float = Field(gt=0, allow_inf_nan=False)
    anomaly_cooling_fail_probability: float = Field(ge=0, le=1, allow_inf_nan=False)
    ambient: AmbientConfig
    actions: dict[str, ActionConfig]

    @model_validator(mode="after")
    def _check(self) -> PlannerConfig:
        if set(self.actions) != set(ACTIONS):
            raise ValueError(
                f"actions must be exactly {list(ACTIONS)} (got {sorted(self.actions)})"
            )
        if self.max_horizon_h < self.dt_h:
            raise ValueError("max_horizon_h must be at least dt_h")
        return self

    def action_names(self) -> tuple[str, ...]:
        return ACTIONS


def load_planner_config(path: Path | str | None = None) -> PlannerConfig:
    raw = read_yaml_mapping(Path(path) if path is not None else DEFAULT_PLANNER_PATH)
    try:
        return PlannerConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(f"invalid planner settings: {exc}") from exc
