"""Tests for the box physics, the hysteresis cooling unit and the seeded engine."""

import math

import numpy as np
import pytest

from shared.config import ConfigError, load_box_config
from simulator.box_model import steady_state_temp_c, step_box_temp_c
from simulator.live import LiveSimulator
from simulator.sim_source import SimSource
from simulator.simulate import run_to_end, simulate

TOL = 6e-5  # values are stored rounded to 4 decimals


def _tau_s(box) -> float:
    return box.box_tau_h * 3600.0


def test_box_config_loads_placeholder_values(box):
    assert box.box_R_th_k_per_w > 0
    assert box.box_deadband_c > 0 and box.sim_substep_s > 0 and box.door_default_power_w > 0
    assert box.heat_capacity_j_per_k == pytest.approx(box.box_tau_h * 3600 / box.box_R_th_k_per_w)


@pytest.mark.parametrize(
    "key", ["box_deadband_c", "sim_substep_s", "door_default_power_w", "door_max_power_w"]
)
def test_box_config_rejects_non_positive_new_keys(key, tmp_path):
    text = (
        "box_R_th_k_per_w: 0.5\nbox_tau_h: 6\nbox_setpoint_c: 5\nbox_cooling_capacity_w: 60\n"
        "sensor_sigma_c: 0.05\nsensor_sigma_rh_pct: 0.5\nsensor_sigma_shock_g: 0.01\n"
        "box_deadband_c: 0.8\nsim_substep_s: 60\ndoor_default_power_w: 100\n"
        "sensor_sigma_ambient_c: 0.1\ndetect_divergence_c: 1.0\ndoor_max_power_w: 120\n"
    )
    good = tmp_path / "good.yaml"
    good.write_text(text, encoding="utf-8")
    load_box_config(good)
    bad = tmp_path / "bad.yaml"
    bad.write_text(text.replace(f"{key}: ", f"{key}: -", 1), encoding="utf-8")
    with pytest.raises(ConfigError, match=key):
        load_box_config(bad)


def test_step_matches_closed_form_exactly(box):
    t_inf = steady_state_temp_c(30.0, 0.5, 0.0)
    assert t_inf == 30.0
    tau = _tau_s(box)
    assert step_box_temp_c(5.0, t_inf, tau, tau) == pytest.approx(30 - 25 * math.exp(-1))
    assert step_box_temp_c(5.0, t_inf, 0.0, tau) == 5.0
    with pytest.raises(ValueError):
        step_box_temp_c(5.0, t_inf, 1.0, 0.0)


def test_hysteresis_keeps_temperature_inside_the_band(box, make_scenario):
    run = simulate(make_scenario(ambient=[(0, 22), (24, 22)]), box)
    settled = run.true_temp_c[12:]  # skip the first two hours
    half_band = box.box_deadband_c / 2
    tolerance = 0.15  # overshoot within one internal substep
    assert settled.min() >= box.box_setpoint_c - half_band - tolerance
    assert settled.max() <= box.box_setpoint_c + half_band + tolerance


def test_baseline_is_no_longer_flat_and_cycles(box, make_scenario):
    run = simulate(make_scenario(), box)
    assert run.true_temp_c.std() > 0.1
    switches = int(np.count_nonzero(np.diff(run.compressor_on.astype(int))))
    assert switches > 10


def test_compressor_follows_the_band(box, make_scenario):
    run = simulate(make_scenario(ambient=[(0, 28), (24, 28)]), box)
    half_band = box.box_deadband_c / 2
    for temp, on in zip(run.true_temp_c, run.compressor_on, strict=True):
        if temp < box.box_setpoint_c - half_band - 0.15:
            assert not on
        if temp > box.box_setpoint_c + half_band + 0.15:
            assert on


def test_cooling_never_heats(box, make_scenario):
    cold = simulate(make_scenario(ambient=[(0, 2), (24, 2)]), box)
    assert not cold.compressor_on.any()
    assert cold.true_temp_c.max() <= box.box_setpoint_c + 1e-6
    # Passive cooling toward 2 C from 5 C for 24 h (four time constants).
    assert cold.true_temp_c[-1] == pytest.approx(2.0 + 3.0 * math.exp(-24 / box.box_tau_h), abs=TOL)


def test_same_seed_gives_identical_run(box, make_scenario):
    a = simulate(make_scenario(), box, seed=7)
    b = simulate(make_scenario(), box, seed=7)
    assert a.readings == b.readings and a.truth == b.truth


def test_different_seed_changes_only_the_noise(box, make_scenario):
    a = simulate(make_scenario(), box, seed=1)
    b = simulate(make_scenario(), box, seed=2)
    assert np.array_equal(a.true_temp_c, b.true_temp_c)
    assert not np.array_equal(a.reported_temp_c, b.reported_temp_c)


def test_steady_ambient_converges_to_t_inf(box, make_scenario):
    off = [{"type": "cooling_factor", "start_h": 0, "end_h": 200, "factor": 0.0}]
    run = simulate(make_scenario(duration_h=200, ambient=[(0, 30), (200, 30)], events=off), box)
    assert run.true_temp_c[-1] == pytest.approx(30.0, abs=TOL)


def test_cooling_failure_follows_the_exponential_response(box, make_scenario):
    off = [{"type": "cooling_factor", "start_h": 0, "end_h": 60, "factor": 0.0}]
    run = simulate(make_scenario(duration_h=60, ambient=[(0, 30), (60, 30)], events=off), box)
    for hours in (0, 1, 3, 6, 12, 30, 59):
        expected = 30.0 - 25.0 * math.exp(-hours * 3600.0 / _tau_s(box))
        assert run.true_temp_c[round(hours * 6)] == pytest.approx(expected, abs=TOL)


def test_ambient_step_follows_the_exponential_response(box, make_scenario):
    events = [
        {"type": "cooling_factor", "start_h": 0, "end_h": 60, "factor": 0.0},
        {"type": "ambient_offset", "start_h": 5, "end_h": 60, "delta_c": 10},
    ]
    run = simulate(make_scenario(duration_h=60, ambient=[(0, 30), (60, 30)], events=events), box)
    tau = _tau_s(box)
    at_step = 30.0 - 25.0 * math.exp(-5 * 3600.0 / tau)
    for hours in (5, 6, 8, 11, 17, 30, 59):
        expected = 40.0 - (40.0 - at_step) * math.exp(-(hours - 5) * 3600.0 / tau)
        assert run.true_temp_c[round(hours * 6)] == pytest.approx(expected, abs=TOL)


def test_heat_load_raises_t_inf_by_r_th_times_power(box, make_scenario):
    events = [
        {"type": "cooling_factor", "start_h": 0, "end_h": 200, "factor": 0.0},
        {"type": "heat_load", "start_h": 0, "end_h": 200, "power_w": 50},
    ]
    run = simulate(make_scenario(duration_h=200, ambient=[(0, 30), (200, 30)], events=events), box)
    assert run.true_temp_c[-1] == pytest.approx(30.0 + box.box_R_th_k_per_w * 50, abs=TOL)


def test_noise_has_configured_sigma(box, make_scenario):
    run = simulate(make_scenario(duration_h=500, ambient=[(0, 20), (500, 20)]), box)  # 3001 samples
    noise = run.reported_temp_c - run.true_temp_c
    assert noise.std() == pytest.approx(box.sensor_sigma_c, rel=0.05)
    assert abs(noise.mean()) < 0.01


def test_substeps_split_the_interval_evenly(box, make_scenario):
    sim = LiveSimulator(make_scenario(sample_interval_s=700, duration_h=7), box, seed=1)
    assert sim.engine._n_sub * sim.engine._dt_s == pytest.approx(700)
    assert sim.engine._dt_s <= box.sim_substep_s


def test_step_by_step_equals_batch(box, make_scenario):
    scenario = make_scenario()
    sim = LiveSimulator(scenario, box, seed=5)
    stepped = []
    while (pair := sim.step())[0] is not None:
        stepped.append(pair)
    batch = simulate(scenario, box, seed=5)
    assert [r for r, _ in stepped] == batch.readings
    assert [t for _, t in stepped] == batch.truth
    assert sim.step() == (None, None)


def test_sim_source_streams_all_samples_then_none(box, make_scenario):
    source = SimSource(make_scenario(duration_h=1), box)
    with pytest.raises(RuntimeError):
        source.read()
    source.start()
    readings = []
    while (reading := source.read()) is not None:
        readings.append(reading)
    assert [r.t_s for r in readings] == [0.0, 600.0, 1200.0, 1800.0, 2400.0, 3000.0, 3600.0]
    assert all(r.source == "sim" for r in readings)
    assert source.seed == 1  # the scenario's own seed
    source.close()


def test_sim_source_random_seed_is_reported_and_reproducible(box, make_scenario):
    scenario = make_scenario(duration_h=2)
    source = SimSource(scenario, box, random_seed=True)
    source.start()
    first = [source.read() for _ in range(5)]
    again = SimSource(scenario, box, seed=source.seed)
    again.start()
    assert [again.read() for _ in range(5)] == first


def test_run_to_end_respects_max_samples(box):
    from simulator.freerun import FreeRun, load_freerun_config

    run = run_to_end(LiveSimulator(FreeRun(load_freerun_config(), None), box, seed=3), 25)
    assert len(run.readings) == 25
