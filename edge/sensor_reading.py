"""One sensor reading on the simulated clock (master brief section 3.4, fields before signing)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

# ASSUMPTION: generous physical sanity bounds, wide enough to hold an injected sensor glitch.
TEMP_MIN_C = -100.0
TEMP_MAX_C = 150.0
# ASSUMPTION: sane range for the temperature measured around the box (the cargo area).
AMBIENT_MIN_C = -60.0
AMBIENT_MAX_C = 80.0


class SensorReading(BaseModel):
    """A single sample from a sensor feed. Immutable; NaN and infinity are rejected."""

    model_config = ConfigDict(frozen=True)

    t_s: float = Field(ge=0.0, allow_inf_nan=False, description="Seconds since scenario start")
    temp_c: float = Field(ge=TEMP_MIN_C, le=TEMP_MAX_C, allow_inf_nan=False)
    rh_pct: float = Field(ge=0.0, le=100.0, allow_inf_nan=False)
    shock_g: float = Field(ge=0.0, allow_inf_nan=False)
    source: str = Field(min_length=1, description='Feed type; "sim" for the simulator')
    ambient_c: float | None = Field(
        default=None,
        ge=AMBIENT_MIN_C,
        le=AMBIENT_MAX_C,
        allow_inf_nan=False,
        description="Measured temperature around the box (the cargo area); None if not measured",
    )
    cooling_duty: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        allow_inf_nan=False,
        description="Fraction of the last interval the compressor ran; None if unknown",
    )
