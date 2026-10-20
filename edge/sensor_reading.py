"""One sensor reading on the simulated clock (master brief section 3.4, fields before signing)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

# ASSUMPTION: generous physical sanity bounds, wide enough to hold an injected sensor glitch.
TEMP_MIN_C = -100.0
TEMP_MAX_C = 150.0


class SensorReading(BaseModel):
    """A single sample from a sensor feed. Immutable; NaN and infinity are rejected."""

    model_config = ConfigDict(frozen=True)

    t_s: float = Field(ge=0.0, allow_inf_nan=False, description="Seconds since scenario start")
    temp_c: float = Field(ge=TEMP_MIN_C, le=TEMP_MAX_C, allow_inf_nan=False)
    rh_pct: float = Field(ge=0.0, le=100.0, allow_inf_nan=False)
    shock_g: float = Field(ge=0.0, allow_inf_nan=False)
    source: str = Field(min_length=1, description='Feed type; "sim" for the simulator')
