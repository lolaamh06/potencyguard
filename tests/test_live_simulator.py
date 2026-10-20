"""Tests for LiveSimulator: injection, noise independence, spoof modes, invalid input."""

import numpy as np
import pytest

from simulator.live import LiveSimulator
from simulator.simulate import simulate

SEED = 11


def _run(sim: LiveSimulator, steps: int):
    pairs = [sim.step() for _ in range(steps)]
    return [r for r, _ in pairs], [t for _, t in pairs]


def _sim(make_scenario, box, **overrides) -> LiveSimulator:
    return LiveSimulator(make_scenario(duration_h=48, **overrides), box, seed=SEED)


def _control(make_scenario, box, steps: int):
    return _run(_sim(make_scenario, box), steps)


# ----------------------------------------------------------------- noise independence


@pytest.mark.parametrize(
    "event",
    [
        {"type": "kill_cooling"},
        {"type": "open_door", "duration_min": 30},
        {"type": "spoof_sensor", "mode": "hold", "reported_c": 5.0},
        {"type": "glitch_spike", "value_c": 60.0},
        {"type": "shock", "peak_g": 9.0},
    ],
)
def test_injection_does_not_change_the_noise_stream(make_scenario, box, event):
    k, total = 20, 60
    base_readings, base_truth = _control(make_scenario, box, total)
    sim = _sim(make_scenario, box)
    readings, truth = _run(sim, k)
    assert sim.inject(event).accepted
    more_r, more_t = _run(sim, total - k)
    readings, truth = readings + more_r, truth + more_t
    assert readings[:k] == base_readings[:k]
    # Humidity and shock draw from the same stream and are untouched by these faults
    # (a shock injection adds its peak to exactly one shock sample).
    for i in range(k, total):
        if event["type"] != "open_door":
            assert readings[i].rh_pct == base_readings[i].rh_pct
        if event["type"] != "shock":
            assert readings[i].shock_g == base_readings[i].shock_g
        if event["type"] in ("spoof_sensor", "glitch_spike", "shock"):
            assert truth[i].true_temp_c == base_truth[i].true_temp_c
        noise = readings[i].temp_c - truth[i].true_temp_c
        base_noise = base_readings[i].temp_c - base_truth[i].true_temp_c
        if event["type"] in ("kill_cooling", "open_door", "shock"):
            assert noise == pytest.approx(base_noise, abs=2e-4)


# ----------------------------------------------------------------- the catalogue


def _after(sim, steps):
    return _run(sim, steps)[1]


def test_kill_cooling_warms_and_restore_recovers(make_scenario, box):
    base = _control(make_scenario, box, 100)[1]
    sim = _sim(make_scenario, box)
    _run(sim, 10)
    result = sim.inject({"type": "kill_cooling"})
    assert result.accepted and result.event_id.startswith("inj-")
    truth = _after(sim, 1)
    assert result.event_id in truth[0].active_event_ids
    assert truth[0].cooling_factor == 0.0
    warm = _after(sim, 29)
    assert warm[-1].true_temp_c > base[39].true_temp_c + 4
    assert sim.inject({"type": "restore_cooling"}).accepted
    rest = _after(sim, 60)
    assert rest[-1].true_temp_c < warm[-1].true_temp_c
    assert rest[-1].true_temp_c < 6.0
    history = {e.id: e for e in sim.events()}
    assert history[result.event_id].origin == "injected"
    assert history[result.event_id].end_s is not None


def test_derate_cooling_sets_the_factor(make_scenario, box):
    sim = _sim(make_scenario, box)
    _run(sim, 5)
    assert sim.inject({"type": "derate_cooling", "factor": 0.4}).accepted
    assert _after(sim, 2)[-1].cooling_factor == pytest.approx(0.4)


def test_restore_ends_a_scheduled_failure_too(make_scenario, box):
    failure = [{"type": "cooling_factor", "start_h": 1, "end_h": 40, "factor": 0.0}]
    sim = _sim(make_scenario, box, events=failure)
    _run(sim, 20)
    assert sim.inject({"type": "restore_cooling"}).accepted
    assert _after(sim, 1)[0].cooling_factor == 1.0


def test_heat_soak_raises_and_cold_snap_lowers_the_temperature(make_scenario, box):
    base = _control(make_scenario, box, 100)[1]
    hot = _sim(make_scenario, box)
    _run(hot, 10)
    hot_event = hot.inject({"type": "heat_soak", "delta_c": 25, "duration_h": 10, "ramp_h": 1})
    assert hot_event.accepted
    hot_truth = _after(hot, 60)
    assert max(t.true_temp_c for t in hot_truth) > 8.0
    assert max(t.ambient_c for t in hot_truth) > base[30].ambient_c + 20
    assert hot_event.event_id in hot_truth[5].active_event_ids

    cold = _sim(make_scenario, box)
    _run(cold, 10)
    assert cold.inject(
        {"type": "cold_snap", "delta_c": -30, "duration_h": 10, "ramp_h": 0.5}
    ).accepted
    cold_truth = _after(cold, 60)
    assert min(t.true_temp_c for t in cold_truth) < 0.0


def test_open_door_warms_then_ends_on_its_own(make_scenario, box):
    sim = _sim(make_scenario, box)
    _run(sim, 10)
    result = sim.inject({"type": "open_door", "duration_min": 60, "power_w": 120})
    truth = _after(sim, 40)
    assert result.event_id in truth[0].active_event_ids
    assert result.event_id not in truth[-1].active_event_ids
    assert max(t.true_temp_c for t in truth) > 9.0


def test_open_door_uses_the_default_power(make_scenario, box):
    sim = _sim(make_scenario, box)
    sim.inject({"type": "open_door", "duration_min": 10})
    assert sim.events()[-1].params["power_w"] == box.door_default_power_w


def test_glitch_and_shock_apply_to_exactly_the_next_sample(make_scenario, box):
    sim = _sim(make_scenario, box)
    _run(sim, 5)
    glitch = sim.inject({"type": "glitch_spike", "value_c": 77.0})
    shock = sim.inject({"type": "shock", "peak_g": 12.0})
    readings, truth = _run(sim, 3)
    assert readings[0].temp_c == 77.0 and readings[0].shock_g > 12.0
    assert readings[1].temp_c < 10 and readings[1].shock_g < 1.0
    assert {glitch.event_id, shock.event_id} <= set(truth[0].active_event_ids)
    assert glitch.event_id not in truth[1].active_event_ids


def test_snapshot_describes_the_current_state(make_scenario, box):
    sim = _sim(make_scenario, box)
    assert sim.snapshot()["true_temp_c"] is None
    _run(sim, 3)
    sim.inject({"type": "kill_cooling"})
    _run(sim, 1)
    snap = sim.snapshot()
    assert snap["seed"] == SEED and snap["seed_mode"] == "fixed"
    assert snap["sim_time_s"] == 1800.0
    assert [e["type"] for e in snap["active_events"]] == ["kill_cooling"]


# ----------------------------------------------------------------- spoof modes


def test_spoof_modes_change_only_the_reported_series(make_scenario, box):
    control_r, control_t = _control(make_scenario, box, 60)
    cases = {
        "hold": {"type": "spoof_sensor", "mode": "hold", "reported_c": 5.0},
        "offset": {"type": "spoof_sensor", "mode": "offset", "delta_c": 9.0},
        "replay": {
            "type": "spoof_sensor",
            "mode": "replay",
            "replay_from_h": 0.5,
            "replay_len_h": 1.0,
        },
    }
    for mode, event in cases.items():
        sim = _sim(make_scenario, box)
        _run(sim, 30)
        assert sim.inject(event).accepted
        readings, truth = _run(sim, 30)
        assert [t.true_temp_c for t in truth] == [t.true_temp_c for t in control_t[30:]], mode
        assert [t.ambient_c for t in truth] == [t.ambient_c for t in control_t[30:]], mode
        assert [r.rh_pct for r in readings] == [r.rh_pct for r in control_r[30:]], mode
        assert {t.spoof_mode for t in truth} == {mode}


def test_hold_and_offset_values(make_scenario, box):
    sim = _sim(make_scenario, box)
    _run(sim, 10)
    sim.inject({"type": "spoof_sensor", "mode": "hold", "reported_c": 3.0})
    readings, _ = _run(sim, 20)
    assert all(abs(r.temp_c - 3.0) < 0.5 for r in readings)
    sim.inject({"type": "spoof_sensor", "mode": "offset", "delta_c": 7.0})
    readings, truth = _run(sim, 20)
    assert all(
        abs((t.true_temp_c - 7.0) - r.temp_c) < 0.5 for r, t in zip(readings, truth, strict=True)
    )


def test_replay_really_repeats_earlier_reported_values(make_scenario, box):
    sim = _sim(make_scenario, box)
    history, _ = _run(sim, 40)
    # Replay hour 1 to hour 2 (samples 6 to 11), a loop of 6 samples.
    event = {"type": "spoof_sensor", "mode": "replay", "replay_from_h": 1.0, "replay_len_h": 1.0}
    assert sim.inject(event).accepted
    readings, _ = _run(sim, 18)
    # The loop starts at the injection time, so the first spoofed sample is one sample into it.
    expected = [history[6 + ((i + 1) % 6)].temp_c for i in range(18)]
    assert [r.temp_c for r in readings] == expected


def test_stop_spoof_and_timed_spoof_end(make_scenario, box):
    sim = _sim(make_scenario, box)
    _run(sim, 5)
    sim.inject({"type": "spoof_sensor", "mode": "hold", "reported_c": 2.0})
    assert _after(sim, 1)[0].spoof_mode == "hold"
    assert sim.inject({"type": "stop_spoof"}).accepted
    assert _after(sim, 1)[0].spoof_mode is None
    sim.inject({"type": "spoof_sensor", "mode": "hold", "reported_c": 2.0, "duration_min": 30})
    modes = [t.spoof_mode for t in _after(sim, 6)]
    # 30 minutes from the injection time cover the next two samples (600 s apart), not the third.
    assert modes[:2] == ["hold"] * 2 and modes[2:] == [None] * 4


# ----------------------------------------------------------------- invalid input


@pytest.mark.parametrize(
    ("event", "fragment"),
    [
        ({"type": "explode"}, "unknown event type"),
        ({"type": "derate_cooling", "factor": 1.7}, "factor"),
        ({"type": "open_door", "duration_min": -5}, "duration_min"),
        ({"type": "heat_soak", "delta_c": 5, "duration_h": 1, "ramp_h": 2}, "ramp"),
        ({"type": "cold_snap", "delta_c": 5, "duration_h": 4}, "delta_c"),
        ({"type": "spoof_sensor", "mode": "hold"}, "reported_c"),
        ({"type": "spoof_sensor", "mode": "replay", "replay_from_h": 5, "replay_len_h": 1}, "past"),
        ({"type": "spoof_sensor", "mode": "hold", "reported_c": 5, "delta_c": 2}, "hold"),
        ({"type": "glitch_spike", "value_c": 900}, "value_c"),
        ({"type": "shock", "peak_g": 0}, "peak_g"),
        ({"type": "stop_spoof"}, "no spoof"),
        ({"type": "restore_cooling"}, "no cooling fault"),
        ({"type": "kill_cooling", "bogus": 1}, "bogus"),
        ({}, "unknown event type"),
        ("not a mapping", "mapping"),
    ],
)
def test_invalid_injections_are_rejected_and_do_not_corrupt_the_run(
    make_scenario, box, event, fragment
):
    control_r, control_t = _control(make_scenario, box, 40)
    sim = _sim(make_scenario, box)
    _run(sim, 20)
    result = sim.inject(event)
    assert not result.accepted
    assert fragment in result.error
    readings, truth = _run(sim, 20)
    assert readings == control_r[20:]
    assert truth == control_t[20:]
    assert sim.events() == _sim(make_scenario, box).events()


def test_a_finished_run_returns_none(make_scenario, box):
    sim = LiveSimulator(make_scenario(duration_h=1), box, seed=1)
    for _ in range(7):
        assert sim.step()[0] is not None
    assert sim.finished
    assert sim.step() == (None, None)


# ----------------------------------------------------------------- seeds


def test_random_seed_is_recorded_and_reproducible(make_scenario, box):
    scenario = make_scenario(duration_h=6)
    sim = LiveSimulator(scenario, box)
    assert sim.seed_mode == "random" and isinstance(sim.seed, int)
    first = [sim.step() for _ in range(10)]
    again = LiveSimulator(scenario, box, seed=sim.seed)
    assert again.seed_mode == "fixed"
    assert [again.step() for _ in range(10)] == first


def test_two_random_runs_differ(make_scenario, box):
    a = simulate(make_scenario(duration_h=6), box, random_seed=True)
    b = simulate(make_scenario(duration_h=6), box, random_seed=True)
    assert a.seed != b.seed
    assert not np.array_equal(a.reported_temp_c, b.reported_temp_c)
