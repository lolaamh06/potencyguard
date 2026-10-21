"""Phase 3B: the drift and mimic lie modes, the door power limit and the golden recordings."""

import dataclasses
import math
from pathlib import Path

import pytest

from simulator.commands import parse_command, parse_scheduled
from simulator.divergence import first_divergence_s
from simulator.live import LiveSimulator
from simulator.recording import recording_text
from simulator.scenario import ScenarioError, load_all_scenarios, validate_raw_event
from simulator.simulate import simulate

ROOT = Path(__file__).resolve().parent.parent
RECORDINGS = ROOT / "data" / "recordings"
SCENARIOS = load_all_scenarios()


def _drift(start_h=4, end_h=20, rate=1.0, **extra):
    return {
        "type": "spoof",
        "start_h": start_h,
        "end_h": end_h,
        "mode": "drift",
        "rate_c_per_h": rate,
        **extra,
    }


def _mimic(start_h=4, end_h=20, **extra):
    return {"type": "spoof", "start_h": start_h, "end_h": end_h, "mode": "mimic", **extra}


# ----------------------------------------------------------------- drift


def test_drift_offset_grows_linearly_from_zero(box, make_scenario):
    events = [_drift(rate=0.5, add_noise=False)]
    run = simulate(make_scenario(events=events), box, seed=3)
    for hour in (4.5, 6, 10, 16, 19.5):
        i = round(hour * 6)
        offset = run.truth[i].true_temp_c - run.readings[i].temp_c
        assert offset == pytest.approx(0.5 * (hour - 4), abs=2e-4)
    assert run.truth[24].spoof_mode == "drift"  # hour 4: the spoof starts, offset 0
    assert run.truth[24].true_temp_c == pytest.approx(run.readings[24].temp_c, abs=2e-4)
    assert run.truth[23].spoof_mode is None


def test_drift_stops_growing_at_max_offset(box, make_scenario):
    events = [_drift(rate=2.0, max_offset_c=3.0, add_noise=False)]
    run = simulate(make_scenario(events=events), box, seed=3)
    for hour, expected in ((4.5, 1.0), (5.5, 3.0), (12, 3.0), (19, 3.0)):
        i = round(hour * 6)
        assert run.truth[i].true_temp_c - run.readings[i].temp_c == pytest.approx(
            expected, abs=2e-4
        )


def test_drift_adds_sensor_noise_by_default(box, make_scenario):
    run = simulate(make_scenario(events=[_drift(rate=0.5)]), box, seed=3)
    errors = [
        run.truth[i].true_temp_c - run.readings[i].temp_c - 0.5 * (i / 6 - 4)
        for i in range(25, 120)
    ]
    assert max(abs(e) for e in errors) > 1e-3  # noise is there
    assert max(abs(e) for e in errors) < 8 * box.sensor_sigma_c


def test_drift_is_deterministic(box, make_scenario):
    scenario = make_scenario(events=[_drift()])
    a, b = simulate(scenario, box, seed=8), simulate(scenario, box, seed=8)
    assert a.readings == b.readings and a.truth == b.truth


@pytest.mark.parametrize(
    "bad",
    [
        {"rate_c_per_h": 0.0},
        {"rate_c_per_h": -1.0},
        {"rate_c_per_h": math.inf},
        {"max_offset_c": 0.0},
        {"max_offset_c": -2.0},
        {"reported_c": 5.0},  # a hold parameter on a drift
        {"delta_c": 3.0},
    ],
)
def test_drift_rejects_invalid_parameters(bad):
    event = _drift()
    event.update(bad)
    with pytest.raises(ScenarioError):
        validate_raw_event(event, 24, "event")


def test_drift_needs_its_rate():
    event = _drift()
    del event["rate_c_per_h"]
    with pytest.raises(ScenarioError):
        validate_raw_event(event, 24, "event")


def test_max_offset_belongs_to_drift_only():
    event = {"type": "spoof", "start_h": 1, "end_h": 5, "mode": "offset", "delta_c": 3.0}
    event["max_offset_c"] = 2.0
    with pytest.raises(ScenarioError):
        validate_raw_event(event, 24, "event")


# ----------------------------------------------------------------- mimic


def test_mimic_needs_no_parameters_and_rejects_others():
    validate_raw_event(_mimic(), 24, "event")
    with pytest.raises(ScenarioError):
        validate_raw_event(_mimic(reported_c=5.0), 24, "event")
    with pytest.raises(ScenarioError):
        validate_raw_event(_mimic(rate_c_per_h=1.0), 24, "event")


def test_mimic_is_deterministic(box, make_scenario):
    scenario = make_scenario(events=[_mimic()])
    a, b = simulate(scenario, box, seed=8), simulate(scenario, box, seed=8)
    assert a.readings == b.readings and a.truth == b.truth


def _failing_cooling_scenario(make_scenario, mode_event):
    events = [{"type": "cooling_factor", "start_h": 3, "end_h": 22, "factor": 0.0}]
    if mode_event is not None:
        events.append(mode_event)
    return make_scenario(events=events, ambient=[(0, 18), (12, 30), (24, 22)])


def test_mimic_hides_a_cooling_failure_and_stays_in_the_healthy_envelope(box, make_scenario):
    scenario = _failing_cooling_scenario(make_scenario, _mimic(start_h=4, end_h=24))
    run = simulate(scenario, box, seed=11)
    floor_margin = 6 * box.sensor_sigma_c
    lie_samples = [i for i, s in enumerate(run.truth) if s.spoof_mode == "mimic"]
    assert lie_samples
    for i in lie_samples:
        reported = run.readings[i].temp_c
        ambient = run.truth[i].ambient_c
        floor = ambient - box.box_R_th_k_per_w * box.box_cooling_capacity_w
        assert reported >= floor - floor_margin
        assert reported <= max(ambient, box.box_setpoint_c) + floor_margin
    # the box really warms up while the lie stays near the set point
    end = lie_samples[-1]
    assert run.truth[end].true_temp_c - run.readings[end].temp_c > 5.0
    assert abs(run.readings[end].temp_c - box.box_setpoint_c) < 2.0
    assert first_divergence_s(run.truth, box.detect_divergence_c) is not None


def test_mimic_starts_from_the_true_temperature(box, make_scenario):
    run = simulate(make_scenario(events=[_mimic(start_h=4, end_h=20)]), box, seed=5)
    i = 24
    assert run.truth[i].spoof_mode == "mimic"
    assert abs(run.readings[i].temp_c - run.truth[i].true_temp_c) < 6 * box.sensor_sigma_c


def test_mimic_on_a_healthy_box_has_no_divergence(box, make_scenario):
    run = simulate(make_scenario(events=[_mimic(start_h=4, end_h=20)]), box, seed=5)
    # The copy and the real box obey the same physics here, so the lie matches the truth.
    assert first_divergence_s(run.truth, box.detect_divergence_c) is None


# ----------------------------------------------------------------- both modes


@pytest.mark.parametrize("mode_event", [_drift(rate=1.0), _mimic()])
def test_the_true_series_and_other_channels_do_not_depend_on_the_lie(
    box, make_scenario, mode_event
):
    plain = simulate(_failing_cooling_scenario(make_scenario, None), box, 4)
    lied = simulate(_failing_cooling_scenario(make_scenario, mode_event), box, 4)
    for a, b in zip(plain.truth, lied.truth, strict=True):
        assert (a.true_temp_c, a.ambient_c, a.cooling_duty, a.measured_ambient_c, a.rh_pct) == (
            b.true_temp_c,
            b.ambient_c,
            b.cooling_duty,
            b.measured_ambient_c,
            b.rh_pct,
        )
    for a, b in zip(plain.readings, lied.readings, strict=True):
        assert (a.ambient_c, a.cooling_duty, a.rh_pct, a.shock_g) == (
            b.ambient_c,
            b.cooling_duty,
            b.rh_pct,
            b.shock_g,
        )


@pytest.mark.parametrize("mode_event", [_drift(rate=1.0), _mimic()])
def test_first_divergence_is_the_first_time_the_lie_exceeds_the_threshold(
    box, make_scenario, mode_event
):
    run = simulate(_failing_cooling_scenario(make_scenario, mode_event), box, seed=6)
    found = first_divergence_s(run.truth, box.detect_divergence_c)
    assert found is not None
    index = round(found / 600.0)
    assert run.truth[index].spoof_mode is not None
    assert abs(run.truth[index].reported_temp_c - run.truth[index].true_temp_c) > (
        box.detect_divergence_c
    )
    for sample in run.truth[:index]:
        assert sample.spoof_mode is None or (
            abs(sample.reported_temp_c - sample.true_temp_c) <= box.detect_divergence_c
        )


def test_the_events_record_the_mode_and_the_parameters(box, make_scenario):
    run = simulate(make_scenario(events=[_drift(rate=0.5, max_offset_c=4.0)]), box, seed=3)
    event = next(e for e in run.events if e.kind == "spoof")
    assert event.params["mode"] == "drift"
    assert event.params["rate_c_per_h"] == 0.5 and event.params["max_offset_c"] == 4.0
    mimic = simulate(make_scenario(events=[_mimic()]), box, seed=3)
    assert next(e for e in mimic.events if e.kind == "spoof").params["mode"] == "mimic"


def test_a_spoof_without_the_new_parameters_dumps_the_old_fields_only(make_scenario, box):
    run = simulate(make_scenario(events=[_drift()]), box, seed=3)  # keeps the new ones
    hold = {"type": "spoof", "start_h": 1, "end_h": 5, "mode": "hold", "reported_c": 4.0}
    run2 = simulate(make_scenario(events=[hold]), box, seed=3)
    keys = next(e for e in run2.events if e.kind == "spoof").params
    assert "rate_c_per_h" not in keys and "max_offset_c" not in keys
    assert "rate_c_per_h" in next(e for e in run.events if e.kind == "spoof").params


@pytest.mark.parametrize(
    "command",
    [
        {"type": "spoof_sensor", "mode": "drift", "rate_c_per_h": 1.0},
        {"type": "spoof_sensor", "mode": "drift", "rate_c_per_h": 1.0, "max_offset_c": 4.0},
        {"type": "spoof_sensor", "mode": "mimic"},
    ],
)
def test_injection_works_mid_run(box, make_scenario, command):
    scenario = _failing_cooling_scenario(make_scenario, {"type": "heat_load", "start_h": 1,
                                                          "end_h": 2, "power_w": 10})  # fmt: skip
    sim = LiveSimulator(scenario, box, seed=2)
    for _ in range(30):
        sim.step()
    result = sim.inject(command)
    assert result.accepted, result.error
    modes = []
    while (pair := sim.step())[0] is not None:
        modes.append(pair[1].spoof_mode)
    assert modes and all(m == command["mode"] for m in modes)
    assert sim.inject({"type": "stop_spoof"}).accepted


@pytest.mark.parametrize(
    "command",
    [
        {"type": "spoof_sensor", "mode": "drift"},
        {"type": "spoof_sensor", "mode": "drift", "rate_c_per_h": 0.0},
        {"type": "spoof_sensor", "mode": "drift", "rate_c_per_h": -1.0},
        {"type": "spoof_sensor", "mode": "drift", "rate_c_per_h": 1.0, "max_offset_c": 0.0},
        {"type": "spoof_sensor", "mode": "mimic", "reported_c": 5.0},
        {"type": "spoof_sensor", "mode": "mimic", "rate_c_per_h": 1.0},
        {"type": "spoof_sensor", "mode": "offset", "delta_c": 2.0, "rate_c_per_h": 1.0},
    ],
)
def test_invalid_injections_are_rejected_and_change_nothing(box, make_scenario, command):
    sim = LiveSimulator(make_scenario(), box, seed=2)
    sim.step()
    before = len(sim.events())
    assert not sim.inject(command).accepted
    assert len(sim.events()) == before


def test_the_commands_parse():
    assert parse_command("spoof_sensor drift 0.5") == {
        "type": "spoof_sensor",
        "mode": "drift",
        "rate_c_per_h": 0.5,
    }
    assert parse_command("spoof_sensor drift 0.5 120 4") == {
        "type": "spoof_sensor",
        "mode": "drift",
        "rate_c_per_h": 0.5,
        "duration_min": 120.0,
        "max_offset_c": 4.0,
    }
    assert parse_command("spoof_sensor mimic") == {"type": "spoof_sensor", "mode": "mimic"}
    assert parse_command("spoof_sensor mimic 90")["duration_min"] == 90.0
    assert parse_scheduled("spoof_sensor mimic@3h") == (
        3 * 3600.0,
        {"type": "spoof_sensor", "mode": "mimic"},
    )
    with pytest.raises(ValueError):
        parse_command("spoof_sensor mimic 1 2")


# ----------------------------------------------------------------- door power limit


def test_open_door_above_the_maximum_is_rejected(box, make_scenario):
    sim = LiveSimulator(make_scenario(), box, seed=2)
    sim.step()
    before = len(sim.events())
    result = sim.inject(
        {"type": "open_door", "duration_min": 10, "power_w": box.door_max_power_w + 1}
    )
    assert not result.accepted and "door power" in result.error
    assert len(sim.events()) == before
    assert sim.inject(
        {"type": "open_door", "duration_min": 10, "power_w": box.door_max_power_w}
    ).accepted
    assert sim.inject({"type": "open_door", "duration_min": 10}).accepted


def test_the_default_door_power_is_within_the_maximum(box):
    assert box.door_default_power_w <= box.door_max_power_w


def test_every_shipped_scenario_stays_within_the_maximum_door_power(box):
    for scenario in SCENARIOS.values():
        for raw in scenario.events:
            if raw["type"] != "heat_load":
                continue
            power = raw["power_w"]
            top = power["max"] if isinstance(power, dict) else power
            assert top <= box.door_max_power_w, scenario.id


def test_a_smaller_maximum_is_enforced(box, make_scenario):
    small = dataclasses.replace(box, door_max_power_w=box.door_default_power_w)
    sim = LiveSimulator(make_scenario(), small, seed=2)
    sim.step()
    assert not sim.inject(
        {"type": "open_door", "duration_min": 5, "power_w": small.door_default_power_w * 1.5}
    ).accepted


# ----------------------------------------------------------------- the golden recordings


@pytest.mark.parametrize("scenario_id", sorted(SCENARIOS))
def test_the_golden_recordings_are_byte_identical_to_a_fresh_run(box, scenario_id):
    """No shipped scenario uses the new modes, so Phase 3B must not change any golden file."""
    scenario = SCENARIOS[scenario_id]
    jsonl, truth = recording_text(simulate(scenario, box))
    assert (RECORDINGS / f"{scenario_id}.jsonl").read_bytes() == jsonl.encode("utf-8")
    assert (RECORDINGS / f"{scenario_id}.ground_truth.json").read_bytes() == truth.encode("utf-8")
