"""Tests for the box physics and the seeded simulator (Phase 1, step 4)."""

import math

import numpy as np
import pytest

from edge.sensor_reading import SensorReading
from shared.config import ConfigError, load_box_config
from simulator.box_model import cooling_power_w, steady_state_temp_c, step_box_temp_c
from simulator.scenario import Scenario
from simulator.sim_source import SimSource
from simulator.simulate import simulate

BOX = load_box_config()
TAU_S = BOX.box_tau_h * 3600.0
# Values are stored rounded to 4 decimals, so closed-form checks allow just over half of that.
ROUNDING_TOL = 6e-5


def _scenario(**overrides) -> Scenario:
    values = {
        "id": "test",
        "title": "test",
        "description": "test scenario",
        "seed": 1,
        "duration_h": 24,
        "sample_interval_s": 600,
        "ambient": [(0, 30), (24, 30)],
        "events": [],
    }
    values.update(overrides)
    return Scenario(**values)


def test_box_config_loads_placeholder_values():
    assert BOX.box_R_th_k_per_w > 0
    assert BOX.heat_capacity_j_per_k == pytest.approx(BOX.box_tau_h * 3600 / BOX.box_R_th_k_per_w)


def test_box_config_rejects_bad_values(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("box_R_th_k_per_w: -1\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_box_config(bad)


def test_step_matches_closed_form_exactly():
    t_inf = steady_state_temp_c(30.0, 0.5, 0.0)
    assert t_inf == 30.0
    assert step_box_temp_c(5.0, t_inf, TAU_S, TAU_S) == pytest.approx(30 - 25 * math.exp(-1))
    assert step_box_temp_c(5.0, t_inf, 0.0, TAU_S) == 5.0


def test_cooling_never_heats_and_saturates():
    assert cooling_power_w(2.0, 5.0, 0.5, 60.0) == 0.0
    assert cooling_power_w(25.0, 5.0, 0.5, 60.0) == pytest.approx(-40.0)
    assert cooling_power_w(60.0, 5.0, 0.5, 60.0) == -60.0
    assert cooling_power_w(60.0, 5.0, 0.5, 0.0) == 0.0


def test_same_seed_gives_identical_trace():
    a = simulate(_scenario(), BOX)
    b = simulate(_scenario(), BOX)
    for name in ("t_s", "true_temp_c", "reported_temp_c", "rh_pct", "shock_g"):
        assert np.array_equal(getattr(a, name), getattr(b, name))


def test_different_seed_changes_noise_only():
    a = simulate(_scenario(seed=1), BOX)
    b = simulate(_scenario(seed=2), BOX)
    assert np.array_equal(a.true_temp_c, b.true_temp_c)
    assert not np.array_equal(a.reported_temp_c, b.reported_temp_c)


def test_steady_ambient_converges_to_t_inf():
    cooling_off = [{"type": "cooling_factor", "start_h": 0, "end_h": 200, "factor": 0.0}]
    trace = simulate(_scenario(duration_h=200, events=cooling_off), BOX)
    assert trace.true_temp_c[-1] == pytest.approx(30.0, abs=ROUNDING_TOL)


def test_step_change_follows_exponential_response():
    # Cooling holds 5 C until hour 5, then fails: T_inf steps from 5 to 30 C at hour 5.
    step = [{"type": "cooling_factor", "start_h": 5, "end_h": 60, "factor": 0.0}]
    trace = simulate(_scenario(duration_h=60, events=step), BOX)
    for hours in (5, 6, 8, 11, 17, 30, 59):
        i = round(hours * 3600 / 600)
        expected = 30.0 - 25.0 * math.exp(-(hours - 5) * 3600.0 / TAU_S)
        assert trace.true_temp_c[i] == pytest.approx(expected, abs=ROUNDING_TOL)


def test_heat_load_raises_t_inf_by_r_th_times_power():
    load = [{"type": "heat_load", "start_h": 0, "end_h": 200, "power_w": 50}]
    cooling_off = [{"type": "cooling_factor", "start_h": 0, "end_h": 200, "factor": 0.0}]
    trace = simulate(_scenario(duration_h=200, events=load + cooling_off), BOX)
    assert trace.true_temp_c[-1] == pytest.approx(
        30.0 + BOX.box_R_th_k_per_w * 50, abs=ROUNDING_TOL
    )


def test_noise_has_configured_sigma():
    long_run = _scenario(duration_h=500, ambient=[(0, 20), (500, 20)])  # 3001 samples
    trace = simulate(long_run, BOX)
    noise = trace.reported_temp_c - trace.true_temp_c
    assert noise.std() == pytest.approx(BOX.sensor_sigma_c, rel=0.05)
    assert abs(noise.mean()) < 0.01


def test_sim_source_streams_all_samples_then_none():
    source = SimSource(_scenario(duration_h=1), BOX)
    with pytest.raises(RuntimeError):
        source.read()
    source.start()
    readings = []
    while (reading := source.read()) is not None:
        readings.append(reading)
    assert len(readings) == 7
    assert all(isinstance(r, SensorReading) and r.source == "sim" for r in readings)
    assert [r.t_s for r in readings] == [0.0, 600.0, 1200.0, 1800.0, 2400.0, 3000.0, 3600.0]
    source.close()
