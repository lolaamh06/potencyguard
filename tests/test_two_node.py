"""Phase 3C: the two-node box (air node and payload node), a structurally different box model."""

import dataclasses

import numpy as np
import pytest

from shared.config import ConfigError, load_box_config
from simulator.box_model import TwoNodeBox, two_node_for
from simulator.live import LiveSimulator
from simulator.recording import recording_text
from simulator.scenario import load_all_scenarios
from simulator.simulate import simulate


def two_node(box, **changes):
    return dataclasses.replace(box, box_model="two_node", **changes)


def test_the_slow_time_constant_equals_box_tau_and_the_fast_one_is_faster(box):
    model = two_node_for(two_node(box))
    assert model.slow_tau_s == pytest.approx(box.box_tau_h * 3600.0, rel=1e-9)
    assert 0 < model.fast_tau_s < model.slow_tau_s
    assert model.c_air > 0 and model.c_payload > 0 and model.r_ap > 0


def test_the_steady_state_is_the_single_node_value_for_both_nodes(box):
    model = two_node_for(two_node(box))
    transition = model.transition(600.0)
    x = np.array([30.0, -5.0])
    t_inf = 12.5  # ambient + R_wall * Q for some constant input
    for _ in range(4000):
        x = t_inf + transition @ (x - t_inf)
    assert x == pytest.approx([t_inf, t_inf], abs=1e-9)
    # and it is the fixed point: starting there nothing moves
    assert t_inf + transition @ (np.array([t_inf, t_inf]) - t_inf) == pytest.approx([t_inf] * 2)


def test_without_cooling_both_nodes_converge_to_the_ambient_temperature(box):
    scenario = load_all_scenarios()["reefer_failure"]
    result = simulate(scenario, two_node(box), seed=7)
    last = result.truth[-1]
    assert last.true_payload_temp_c is not None
    # in the reefer failure the box ends warm; the payload follows the air node closely
    assert abs(last.true_payload_temp_c - last.true_temp_c) < 3.0


def test_the_payload_lags_the_air_node_after_a_step(box):
    model = two_node_for(two_node(box))
    transition = model.transition(600.0)
    x = np.array([5.0, 5.0])
    for _ in range(6):  # one hour in a 35 C surrounding
        x = 35.0 + transition @ (x - 35.0)
    assert x[0] > x[1] > 5.0  # the air warms first, the payload lags behind


def test_a_payload_fraction_of_zero_is_the_single_node_box(box):
    scenario = load_all_scenarios()["door_open_excursion"]
    single = simulate(scenario, box, seed=11)
    zero = simulate(scenario, two_node(box, two_node_payload_fraction=0.0), seed=11)
    assert [r.model_dump() for r in single.readings] == [r.model_dump() for r in zero.readings]
    assert [s.true_temp_c for s in single.truth] == [s.true_temp_c for s in zero.truth]
    assert recording_text(single) == recording_text(zero)  # no payload series is written


def test_the_two_node_run_is_deterministic_and_keeps_the_noise_draws(box):
    scenario = load_all_scenarios()["baseline_ok"]
    a = simulate(scenario, two_node(box), seed=3)
    b = simulate(scenario, two_node(box), seed=3)
    assert recording_text(a) == recording_text(b)
    single = simulate(scenario, box, seed=3)
    # humidity and shock use the same random draws whatever the box physics is
    assert [r.rh_pct for r in a.readings] == [r.rh_pct for r in single.readings]
    assert [r.shock_g for r in a.readings] == [r.shock_g for r in single.readings]
    assert [r.ambient_c for r in a.readings] == [r.ambient_c for r in single.readings]


def test_the_sensor_measures_the_air_node_and_both_series_are_kept(box):
    scenario = load_all_scenarios()["baseline_ok"]
    result = simulate(scenario, two_node(box), seed=5)
    truth = result.truth
    assert all(s.true_payload_temp_c is not None for s in truth)
    noise = [r.temp_c - s.true_temp_c for r, s in zip(result.readings, truth, strict=True)]
    assert abs(float(np.mean(noise))) < 0.02 and float(np.std(noise)) < 0.1
    text = recording_text(result)[1]
    assert '"true_payload_temp_c"' in text and '"true_temp_c"' in text


def test_the_single_node_recording_has_no_payload_series(box):
    result = simulate(load_all_scenarios()["baseline_ok"], box, seed=5)
    assert '"true_payload_temp_c"' not in recording_text(result)[1]


def test_two_node_box_config_keys_are_validated(tmp_path):
    source = (load_box_config.__globals__["DEFAULT_CONFIG_PATH"]).read_text(encoding="utf-8")
    good = tmp_path / "good.yaml"
    good.write_text(source.replace("box_model: single_node", "box_model: two_node"), "utf-8")
    assert load_box_config(good).box_model == "two_node"
    for bad_text in (
        source.replace("box_model: single_node", "box_model: three_node"),
        source.replace("two_node_payload_fraction: 0.5", "two_node_payload_fraction: 1.0"),
        source.replace("two_node_coupling_tau_h: 1.5", "two_node_coupling_tau_h: 0"),
    ):
        bad = tmp_path / "bad.yaml"
        bad.write_text(bad_text, "utf-8")
        with pytest.raises(ConfigError):
            load_box_config(bad)


def test_the_default_box_is_single_node_and_the_builder_rejects_bad_parameters(box):
    assert box.box_model == "single_node" and two_node_for(box) is None
    with pytest.raises(ValueError):
        TwoNodeBox.build(0.5, 6 * 3600.0, 1.0, 5400.0)


def test_live_simulator_runs_the_two_node_box_step_by_step(box):
    sim = LiveSimulator(load_all_scenarios()["baseline_ok"], two_node(box), 1)
    reading, sample = sim.step()
    assert reading is not None and sample.true_payload_temp_c == pytest.approx(box.box_setpoint_c)
