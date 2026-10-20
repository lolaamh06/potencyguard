"""Phase 0 smoke tests: packages import and the product config loads and validates."""

from pathlib import Path

import pytest

from shared.config import DEFAULT_CONFIG_PATH, ConfigError, load_product_config


def _write_variant(tmp_path: Path, old: str, new: str | None) -> Path:
    """Copy the default YAML into tmp_path, replacing one line (or removing it if new is None)."""
    lines = DEFAULT_CONFIG_PATH.read_text(encoding="utf-8").splitlines()
    out = []
    for line in lines:
        if line.startswith(old):
            if new is not None:
                out.append(new)
        else:
            out.append(line)
    target = tmp_path / "variant.yaml"
    target.write_text("\n".join(out) + "\n", encoding="utf-8")
    return target


def test_packages_import():
    import backend
    import edge
    import planner
    import shared
    import simulator

    assert all([shared, simulator, edge, planner, backend])


def test_default_config_loads():
    cfg = load_product_config()
    assert cfg.Ea_over_R == 10000
    assert cfg.T_ref_c == 5.0
    assert cfg.tau_max_h == 17520
    assert cfg.P_min == 0.90
    assert cfg.hard_limit_low_c == 0.0
    assert cfg.hard_limit_high_c == 40.0
    assert cfg.hard_limit_consecutive_samples == 2
    assert cfg.alpha == 0.95
    assert cfg.monte_carlo_n == 5000
    assert cfg.k_ref_per_h == pytest.approx(6.0137e-06, rel=1e-4)
    assert cfg.T_ref_k == pytest.approx(278.15)


def test_invalid_p_min_raises(tmp_path):
    with pytest.raises(ConfigError, match="P_min"):
        load_product_config(_write_variant(tmp_path, "P_min:", "P_min: 1.5"))


def test_missing_key_raises(tmp_path):
    with pytest.raises(ConfigError, match="Ea_over_R"):
        load_product_config(_write_variant(tmp_path, "Ea_over_R:", None))


def test_t_ref_outside_limits_raises(tmp_path):
    with pytest.raises(ConfigError):
        load_product_config(_write_variant(tmp_path, "T_ref_c:", "T_ref_c: 45.0"))


def test_boolean_is_not_a_number(tmp_path):
    with pytest.raises(ConfigError):
        load_product_config(_write_variant(tmp_path, "alpha:", "alpha: true"))
