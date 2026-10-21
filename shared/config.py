"""Product configuration loader (master brief section 3.1, amendment A5)."""

from __future__ import annotations

import math
from dataclasses import dataclass, fields
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "product_default.yaml"
_KELVIN_OFFSET = 273.15


class ConfigError(ValueError):
    """Raised when a configuration file is missing keys or has invalid values."""


@dataclass(frozen=True)
class ProductConfig:
    """Synthetic product parameters for an imaginary 2 to 8 C vaccine."""

    Ea_over_R: float
    T_ref_c: float
    tau_max_h: float
    P_min: float
    hard_limit_low_c: float
    hard_limit_high_c: float
    hard_limit_consecutive_samples: int
    alpha: float
    monte_carlo_n: int

    @property
    def k_ref_per_h(self) -> float:
        """Reference degradation rate per hour: ln(1 / P_min) / tau_max_h."""
        return math.log(1.0 / self.P_min) / self.tau_max_h

    @property
    def T_ref_k(self) -> float:
        """Reference temperature in kelvin."""
        return self.T_ref_c + _KELVIN_OFFSET


def _is_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _is_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def read_yaml_mapping(path: Path | str | None) -> dict:
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"cannot read config file {config_path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"config file {config_path} is not valid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"config file {config_path} must contain key: value pairs")
    return raw


@dataclass(frozen=True)
class BoxConfig:
    """Synthetic insulated box and sensor-noise parameters (master brief section 3.3).

    Placeholder values, not sourced [SOURCE NEEDED]; see config/product_default.yaml.
    """

    box_R_th_k_per_w: float
    box_tau_h: float
    box_setpoint_c: float
    box_cooling_capacity_w: float
    sensor_sigma_c: float
    sensor_sigma_rh_pct: float
    sensor_sigma_shock_g: float
    box_deadband_c: float
    sim_substep_s: float
    door_default_power_w: float
    sensor_sigma_ambient_c: float
    detect_divergence_c: float
    door_max_power_w: float
    # Phase 3C: box physics. Optional in the file (default single_node, unchanged behaviour).
    box_model: str = "single_node"
    two_node_payload_fraction: float = 0.5
    two_node_coupling_tau_h: float = 1.5

    @property
    def heat_capacity_j_per_k(self) -> float:
        """C = tau / R_th, converted from hours to seconds."""
        return self.box_tau_h * 3600.0 / self.box_R_th_k_per_w


def _two_node_settings(raw: dict) -> dict:
    """Validate the optional Phase 3C box-physics keys; absent keys keep their defaults."""
    out: dict = {}
    if "box_model" in raw:
        if raw["box_model"] not in ("single_node", "two_node"):
            raise ConfigError(
                f"box_model must be single_node or two_node (got {raw['box_model']!r})"
            )
        out["box_model"] = raw["box_model"]
    for name in ("two_node_payload_fraction", "two_node_coupling_tau_h"):
        if name in raw:
            if not _is_number(raw[name]):
                raise ConfigError(f"{name} must be a number (got {raw[name]!r})")
            out[name] = raw[name]
    fraction = out.get("two_node_payload_fraction", 0.5)
    if not 0 <= fraction < 1:
        raise ConfigError(f"two_node_payload_fraction must be in [0, 1) (got {fraction})")
    if out.get("two_node_coupling_tau_h", 1.5) <= 0:
        raise ConfigError("two_node_coupling_tau_h must be greater than 0")
    return out


def load_box_config(path: Path | str | None = None) -> BoxConfig:
    """Load and validate the box simulator parameters from the same YAML file."""
    raw = read_yaml_mapping(path)
    optional = {"box_model", "two_node_payload_fraction", "two_node_coupling_tau_h"}
    names = [f.name for f in fields(BoxConfig) if f.name not in optional]
    missing = [name for name in names if name not in raw]
    if missing:
        raise ConfigError(f"missing config keys: {', '.join(missing)}")
    for name in names:
        if not _is_number(raw[name]):
            raise ConfigError(f"{name} must be a number (got {raw[name]!r})")
    extra = _two_node_settings(raw)
    for name in (
        "box_R_th_k_per_w",
        "box_tau_h",
        "box_cooling_capacity_w",
        "box_deadband_c",
        "sim_substep_s",
        "door_default_power_w",
        "detect_divergence_c",
        "door_max_power_w",
    ):
        if raw[name] <= 0:
            raise ConfigError(f"{name} must be greater than 0 (got {raw[name]})")
    if raw["door_max_power_w"] < raw["door_default_power_w"]:
        raise ConfigError(
            "door_max_power_w must be at least door_default_power_w "
            f"(got {raw['door_max_power_w']} and {raw['door_default_power_w']})"
        )
    for name in (
        "sensor_sigma_c",
        "sensor_sigma_rh_pct",
        "sensor_sigma_shock_g",
        "sensor_sigma_ambient_c",
    ):
        if raw[name] < 0:
            raise ConfigError(f"{name} must not be negative (got {raw[name]})")
    return BoxConfig(**{name: raw[name] for name in names}, **extra)


def load_product_config(path: Path | str | None = None) -> ProductConfig:
    """Load and validate a product config; default is config/product_default.yaml."""
    raw = read_yaml_mapping(path)

    names = [f.name for f in fields(ProductConfig)]
    missing = [name for name in names if name not in raw]
    if missing:
        raise ConfigError(f"missing config keys: {', '.join(missing)}")
    for name in names:
        if not _is_number(raw[name]):
            raise ConfigError(f"{name} must be a number (got {raw[name]!r})")

    p_min = raw["P_min"]
    if not 0 < p_min < 1:
        raise ConfigError(f"P_min must be strictly between 0 and 1 (got {p_min})")
    if raw["Ea_over_R"] <= 0:
        raise ConfigError(f"Ea_over_R must be greater than 0 (got {raw['Ea_over_R']})")
    if raw["tau_max_h"] <= 0:
        raise ConfigError(f"tau_max_h must be greater than 0 (got {raw['tau_max_h']})")
    low, ref, high = raw["hard_limit_low_c"], raw["T_ref_c"], raw["hard_limit_high_c"]
    if not low < ref < high:
        raise ConfigError(
            f"hard_limit_low_c < T_ref_c < hard_limit_high_c must hold (got {low}, {ref}, {high})"
        )
    consecutive = raw["hard_limit_consecutive_samples"]
    if not _is_integer(consecutive) or consecutive < 1:
        raise ConfigError(
            f"hard_limit_consecutive_samples must be an integer >= 1 (got {consecutive})"
        )
    if not 0 < raw["alpha"] < 1:
        raise ConfigError(f"alpha must be strictly between 0 and 1 (got {raw['alpha']})")
    n = raw["monte_carlo_n"]
    if not _is_integer(n) or n < 100:
        raise ConfigError(f"monte_carlo_n must be an integer >= 100 (got {n})")

    return ProductConfig(**{name: raw[name] for name in names})
