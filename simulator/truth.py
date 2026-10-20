"""Ground truth for one sample: what was really true, next to what the sensor reported."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TruthSample(BaseModel):
    """True state of the box at one sample time (Phase 2A). Values rounded to 4 decimals."""

    model_config = ConfigDict(frozen=True)

    t_s: float
    true_temp_c: float
    reported_temp_c: float
    ambient_c: float
    compressor_on: bool
    cooling_factor: float
    spoof_mode: str | None = None
    active_event_ids: list[str] = Field(default_factory=list)
    rh_pct: float
