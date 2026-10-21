"""Thermal twin: a small physics model of the box that predicts what the temperature should do.

Model (master brief section 3.3), written in terms of what the edge program can observe:

    T_inf[n] = T_amb[n] - dT_cool * u[n]
    T_pred[n+1] = T_inf[n] + (T[n] - T_inf[n]) * exp(-dt / tau)

T is the box temperature, T_amb the temperature around the box (the cargo area), u the cooling
duty (the fraction 0..1 of the interval during which the compressor ran) and dT_cool = R_th * Q_cap
the largest temperature depression the cooling unit can produce relative to ambient (kelvin).

Which sample drives which interval: the interval from sample n to sample n+1 is predicted from the
measured temperature T[n], the AVERAGE of the measured ambient at n and n+1 (the ambient moves
during the interval), and the duty reported with sample n+1 (a reading's duty describes the
interval that just ended). The first reading of a run therefore has no prediction.

Heat that the edge cannot observe (a door held open) is deliberately absent from the model: it
shows up as a positive residual, which is how a physical event is told apart from a lie.

The twin and the simulator use the same family of equations. The evaluation tests the twin
against boxes that differ from its calibration for exactly that reason (Phase 3 report).
"""

from __future__ import annotations

import math
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from shared.config import REPO_ROOT, ConfigError

DEFAULT_TWIN_PATH = REPO_ROOT / "config" / "twin_calibrated.yaml"
VARIANT_TWIN_PATH = REPO_ROOT / "config" / "twin_calibrated_variants.yaml"


class TwinParams(BaseModel):
    """Fitted parameters of the twin. Immutable."""

    model_config = ConfigDict(frozen=True)

    tau_h: float = Field(gt=0, allow_inf_nan=False, description="Thermal time constant, hours")
    dT_cool_c: float = Field(gt=0, allow_inf_nan=False, description="Largest cooling depression, K")
    sigma_r_c: float = Field(gt=0, allow_inf_nan=False, description="Residual std deviation, C")

    @property
    def tau_s(self) -> float:
        return self.tau_h * 3600.0


def _finite(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number (got {value!r})")
    return float(value)


def _check_step(dt_s: float) -> float:
    dt = _finite("dt_s", dt_s)
    if dt <= 0:
        raise ValueError(f"dt_s must be greater than 0 (got {dt})")
    return dt


def equilibrium_c(t_amb_c: float, duty: float, params: TwinParams) -> float:
    """T_inf: where the box would settle at this ambient temperature and cooling duty."""
    amb = _finite("t_amb_c", t_amb_c)
    u = _finite("duty", duty)
    if not 0.0 <= u <= 1.0:
        raise ValueError(f"duty must be between 0 and 1 (got {u})")
    return amb - params.dT_cool_c * u


def predict_next(
    t_n_c: float, t_amb_c: float, duty: float, dt_s: float, params: TwinParams
) -> float:
    """Predicted box temperature one sample later (see the module docstring for the inputs)."""
    t_n = _finite("t_n_c", t_n_c)
    dt = _check_step(dt_s)
    t_inf = equilibrium_c(t_amb_c, duty, params)
    return t_inf + (t_n - t_inf) * math.exp(-dt / params.tau_s)


def max_step_bound(
    t_n_c: float,
    t_amb_c: float,
    dt_s: float,
    params: TwinParams,
    heat_allowance_c: float = 0.0,
    tolerance_sigma: float = 5.0,
) -> float:
    """Largest |dT| the box can physically show in one step (brief section 3.3), plus a tolerance.

    |dT| <= |T_inf,max - T_n| * (1 - exp(-dt/tau)). T_inf,max is the farthest equilibrium the box
    can be pulled towards: ambient with no cooling, or ambient minus dT_cool with full cooling;
    the larger distance from T_n is used. heat_allowance_c (default 0, the brief's form) raises the
    warm end by the largest rise a heat load such as an open door can cause; the monitor sets it
    from its configuration because that heat is not observed. The tolerance is
    tolerance_sigma * sigma_r_c, for sensor noise.
    """
    t_n = _finite("t_n_c", t_n_c)
    amb = _finite("t_amb_c", t_amb_c)
    allowance = _finite("heat_allowance_c", heat_allowance_c)
    if allowance < 0:
        raise ValueError("heat_allowance_c must not be negative")
    dt = _check_step(dt_s)
    warm_end = amb + allowance
    cold_end = amb - params.dT_cool_c
    distance = max(abs(warm_end - t_n), abs(cold_end - t_n))
    return distance * (1.0 - math.exp(-dt / params.tau_s)) + tolerance_sigma * params.sigma_r_c


def floor_bound(t_amb_c: float, params: TwinParams) -> float:
    """The coldest steady temperature full cooling can reach at this ambient: T_amb - dT_cool.

    ADDITION to the brief (decision 0005): a reported temperature well below this is an
    impossible state, whatever the dynamics.
    """
    return _finite("t_amb_c", t_amb_c) - params.dT_cool_c


def advance_floor(floor_n_c: float, t_amb_c: float, dt_s: float, params: TwinParams) -> float:
    """Move the lag-aware lower envelope one step: the coldest the box could be.

    The steady floor_bound() is only reached after several time constants; after the ambient rises
    the box can lawfully stay colder than T_amb - dT_cool for hours. The lower envelope follows
    the same dynamics as the twin with full cooling all the time, starting from the first
    reading: F[n+1] = (T_amb - dT_cool) + (F[n] - (T_amb - dT_cool)) * exp(-dt/tau). By the
    comparison principle the real box (less cooling, plus any heat) is never colder than F.
    ADDITION to the brief (decision 0005).
    """
    f_inf = floor_bound(t_amb_c, params)
    return f_inf + (_finite("floor_n_c", floor_n_c) - f_inf) * math.exp(
        -_check_step(dt_s) / params.tau_s
    )


def load_twin_params(path: Path | str | None = None) -> TwinParams:
    """Read the calibrated parameters from config/twin_calibrated.yaml (or another file)."""
    file = Path(path) if path is not None else DEFAULT_TWIN_PATH
    try:
        raw = yaml.safe_load(file.read_text(encoding="utf-8"))
        return TwinParams(
            tau_h=raw["tau_h"], dT_cool_c=raw["dT_cool_c"], sigma_r_c=raw["sigma_r_c"]
        )
    except (OSError, yaml.YAMLError, KeyError, TypeError, ValueError) as exc:
        raise ConfigError(f"cannot load twin parameters from {file}: {exc}") from exc


def load_variant_twins(path: Path | str | None = None) -> dict[str, TwinParams]:
    """The per-box fitted twins in config/twin_calibrated_variants.yaml (Phase 3C)."""
    target = Path(path) if path is not None else VARIANT_TWIN_PATH
    try:
        raw = yaml.safe_load(target.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"cannot read {target}: {exc}") from exc
    variants = raw.get("variants") if isinstance(raw, dict) else None
    if not isinstance(variants, dict) or not variants:
        raise ConfigError(f"{target} has no 'variants' section")
    out = {}
    for name, block in variants.items():
        try:
            out[name] = TwinParams(
                tau_h=block["tau_h"], dT_cool_c=block["dT_cool_c"], sigma_r_c=block["sigma_r_c"]
            )
        except (KeyError, ValueError) as exc:
            raise ConfigError(f"variant {name!r} in {target} is invalid: {exc}") from exc
    return out
