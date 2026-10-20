"""Settings of the tamper detectors, read from config/detectors.yaml (Phase 3)."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from shared.config import REPO_ROOT, ConfigError, read_yaml_mapping

DEFAULT_DETECTOR_PATH = REPO_ROOT / "config" / "detectors.yaml"


class DetectorConfig(BaseModel):
    """All detector settings. Every value is a placeholder [SOURCE NEEDED]."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cusum_k: float = Field(ge=0, allow_inf_nan=False)
    cusum_h: float = Field(gt=0, allow_inf_nan=False)
    cusum_cap_factor: float = Field(gt=1, allow_inf_nan=False)
    cusum_false_alarm_target_per_1000h: float = Field(gt=0, allow_inf_nan=False)
    step_tolerance_sigma: float = Field(ge=0, allow_inf_nan=False)
    heat_allowance_c: float = Field(ge=0, allow_inf_nan=False)
    state_margin_sigma: float = Field(ge=0, allow_inf_nan=False)
    state_consecutive_samples: int = Field(ge=1)
    falsification_hold_samples: int = Field(ge=0)
    flat_window_samples: int = Field(ge=2)
    flat_sigma_factor: float = Field(gt=0, allow_inf_nan=False)


def load_detector_config(path: Path | str | None = None) -> DetectorConfig:
    """Load and validate the detector settings."""
    raw = read_yaml_mapping(Path(path) if path is not None else DEFAULT_DETECTOR_PATH)
    try:
        return DetectorConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(f"invalid detector settings: {exc}") from exc
