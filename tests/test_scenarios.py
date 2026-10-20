"""Tests for the scenario library, ranges, expectations, recordings and RecordedSource."""

import hashlib
import json

import numpy as np
import pytest

from edge.recorded_source import RecordedSource
from shared.config import ConfigError
from simulator.cli import main as cli_main
from simulator.expectations import check_expectations, validate_expect_block
from simulator.live import LiveSimulator
from simulator.recording import DEFAULT_RECORDINGS_DIR, SCHEMA_VERSION, write_recording
from simulator.scenario import (
    Scenario,
    ScenarioError,
    load_all_scenarios,
    resolve_scenario,
)
from simulator.simulate import simulate

SCENARIOS = load_all_scenarios()
EXPECTED_IDS = {
    "baseline_ok",
    "door_open_excursion",
    "reefer_failure",
    "freeze_event",
    "heatwave_transit",
    "spoof_attempt",
    "sensor_glitch",
    "shock_drop",
    "hidden_spoilage",
}
SEEDS_PER_SCENARIO = 200


def _sha(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _truth_file(scenario_id, box, tmp_path) -> dict:
    _, truth_path = write_recording(SCENARIOS[scenario_id], box, tmp_path)
    return json.loads(truth_path.read_text(encoding="utf-8"))


def test_all_nine_scenarios_exist():
    assert set(SCENARIOS) == EXPECTED_IDS


def test_every_scenario_protects_its_defining_behaviour():
    for scenario in SCENARIOS.values():
        assert scenario.expect, scenario.id


@pytest.mark.parametrize("scenario_id", sorted(EXPECTED_IDS))
def test_expectations_hold_for_many_seeds(scenario_id, box, product):
    scenario = SCENARIOS[scenario_id]
    for seed in range(1000, 1000 + SEEDS_PER_SCENARIO):
        run = simulate(scenario, box, seed=seed)
        problems = check_expectations(
            scenario.expect, run.events, run.truth, run.readings, box, product
        )
        assert not problems, f"seed {seed}: {problems}"


def test_runs_differ_between_seeds(box):
    a = simulate(SCENARIOS["door_open_excursion"], box, seed=1)
    b = simulate(SCENARIOS["door_open_excursion"], box, seed=2)
    assert a.events[0].start_s != b.events[0].start_s
    assert a.events[0].params["power_w"] != b.events[0].params["power_w"]


# ----------------------------------------------------------------- expectations


def test_expectation_checker_detects_violations(box, product):
    run = simulate(SCENARIOS["baseline_ok"], box, seed=1)
    args = (run.events, run.truth, run.readings, box, product)
    assert check_expectations({"true_max_c_gt": "hard_limit_high_c"}, *args)
    assert check_expectations({"true_min_c_lt": "hard_limit_low_c"}, *args)
    assert check_expectations({"true_within_setpoint_c": 0.1}, *args)
    assert check_expectations({"reported_true_gap_c_gt": 10}, *args)
    assert check_expectations({"exactly_one_reported_outlier": True}, *args)
    assert check_expectations({"exactly_one_shock_above_g": 5}, *args)
    assert check_expectations({"spoof_begins_after_failure": True}, *args)
    assert check_expectations({"true_within_setpoint_c": 2}, *args) == []


def test_expect_block_validation():
    validate_expect_block({"true_max_c_gt": "hard_limit_high_c", "outlier_jump_c": 20})
    for bad in ({"unknown": 1}, {"true_max_c_gt": "nope"}, {"true_max_c_gt": True}):
        with pytest.raises(ValueError):
            validate_expect_block(bad)
    with pytest.raises(ValueError):
        validate_expect_block({"spoof_begins_after_failure": 1})


# ----------------------------------------------------------------- ranges


def test_resolved_values_fall_inside_their_ranges(box):
    scenario = SCENARIOS["door_open_excursion"]
    for seed in range(50):
        run = simulate(scenario, box, seed=seed)
        event = run.resolved.events[0]
        assert 4 <= event.start_h <= 5.5 and 7 <= event.end_h <= 8
        assert 90 <= event.power_w <= 120
        assert -2 <= run.resolved.ambient_jitter_c <= 2
        assert run.resolved.ambient_shift_h == 0.0


def test_shift_and_jitter_are_resolved_and_recorded(box):
    run = simulate(SCENARIOS["baseline_ok"], box, seed=3)
    assert -3 <= run.resolved.ambient_shift_h <= 3
    assert run.resolved.parameters()["ambient_jitter_c"] == run.resolved.ambient_jitter_c


BASE = {
    "id": "x",
    "title": "x",
    "description": "x",
    "seed": 1,
    "duration_h": 10,
    "sample_interval_s": 600,
    "ambient": [(0, 20)],
}


def _event(**fields):
    return {**BASE, "events": [{"type": "heat_load", "power_w": 50, **fields}]}


@pytest.mark.parametrize(
    ("fields", "fragment"),
    [
        ({"start_h": 1, "end_h": 2, "power_w": {"min": 9, "max": 5}}, "min must not exceed"),
        ({"start_h": 1, "end_h": 12}, "outside the trip"),
        ({"start_h": 3, "end_h": 2}, "end_h"),
        ({"start_h": {"min": 1, "max": 5}, "end_h": {"min": 4, "max": 6}}, "reach or pass"),
        ({"start_h": 1, "end_h": 2, "power_w": {"min": 1}}, "min and max"),
        ({"start_h": 1, "end_h": 2, "power_w": "lots"}, "number or a range"),
        ({"start_h": -1, "end_h": 2}, "start_h"),
        ({"start_h": 1, "end_h": 2, "colour": 3}, "colour"),
    ],
)
def test_invalid_event_ranges_are_rejected(fields, fragment):
    with pytest.raises(ValueError, match=fragment):
        Scenario(**_event(**fields))


def test_spoof_parameters_are_validated():
    base = {"type": "spoof", "start_h": 2, "end_h": 5}
    for event in (
        {**base, "mode": "hold"},
        {**base, "mode": "offset", "reported_c": 5},
        {**base, "mode": "replay", "replay_from_h": 1},
        {**base, "mode": "replay", "replay_from_h": 1.5, "replay_len_h": 1},
        {**base, "mode": "fade", "reported_c": 5},
    ):
        with pytest.raises(ValueError):
            Scenario(**{**BASE, "events": [event]})
    Scenario(**{**BASE, "events": [{**base, "mode": "hold", "reported_c": 5}]})
    Scenario(
        **{**BASE, "events": [{**base, "mode": "replay", "replay_from_h": 0, "replay_len_h": 1}]}
    )


def test_unknown_event_type_and_bad_scenario_fields():
    with pytest.raises(ValueError):
        Scenario(**{**BASE, "events": [{"type": "unknown"}]})
    with pytest.raises(ValueError):
        Scenario(**{**BASE, "ambient": [(1, 20)]})
    with pytest.raises(ValueError):
        Scenario(**{**BASE, "sample_interval_s": 700})
    with pytest.raises(ValueError):
        Scenario(**{**BASE, "expect": {"nonsense": 1}})


def test_resolution_is_deterministic_and_rejects_a_bad_draw():
    scenario = SCENARIOS["spoof_attempt"]
    a = resolve_scenario(scenario, np.random.default_rng(5))
    b = resolve_scenario(scenario, np.random.default_rng(5))
    assert a.parameters() == b.parameters()
    broken = scenario.model_copy(
        update={"events": [{"type": "shock", "at_h": 99, "peak_g": 5}]}, deep=True
    )
    with pytest.raises(ScenarioError, match="outside the trip"):
        resolve_scenario(broken, np.random.default_rng(1))


def test_load_scenario_reports_a_readable_error(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("id: x\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="bad.yaml"):
        from simulator.scenario import load_scenario

        load_scenario(bad)


# ----------------------------------------------------------------- recordings


@pytest.mark.parametrize("scenario_id", sorted(EXPECTED_IDS))
def test_fixed_seed_recordings_are_byte_identical(scenario_id, box, tmp_path):
    first = write_recording(SCENARIOS[scenario_id], box, tmp_path / "a")
    second = write_recording(SCENARIOS[scenario_id], box, tmp_path / "b")
    for path_a, path_b in zip(first, second, strict=True):
        assert _sha(path_a) == _sha(path_b)
    lines = first[0].read_text(encoding="utf-8").splitlines()
    header = json.loads(lines[0])
    assert header["scenario_id"] == scenario_id
    assert header["seed"] == SCENARIOS[scenario_id].seed
    assert header["seed_mode"] == "fixed"
    assert header["schema_version"] == SCHEMA_VERSION == "0.3"
    assert len(lines) == 1 + SCENARIOS[scenario_id].n_samples


@pytest.mark.parametrize("scenario_id", sorted(EXPECTED_IDS))
def test_committed_recordings_match_the_generator(scenario_id, box, tmp_path):
    fresh = write_recording(SCENARIOS[scenario_id], box, tmp_path)
    committed = (
        DEFAULT_RECORDINGS_DIR / f"{scenario_id}.jsonl",
        DEFAULT_RECORDINGS_DIR / f"{scenario_id}.ground_truth.json",
    )
    for new, old in zip(fresh, committed, strict=True):
        assert old.exists(), f"missing {old}; run: python -m simulator generate --all"
        assert _sha(new) == _sha(old)


def test_golden_folder_holds_exactly_the_nine_scenarios():
    names = sorted(p.name for p in DEFAULT_RECORDINGS_DIR.iterdir() if p.name != "README.md")
    expected = sorted(
        [f"{i}.jsonl" for i in EXPECTED_IDS] + [f"{i}.ground_truth.json" for i in EXPECTED_IDS]
    )
    assert names == expected


def test_different_seeds_give_different_files(box, tmp_path):
    scenario = SCENARIOS["baseline_ok"]
    a = write_recording(scenario, box, tmp_path / "a", seed=1)
    b = write_recording(scenario, box, tmp_path / "b", seed=2)
    assert _sha(a[0]) != _sha(b[0])


def test_random_seed_is_recorded_and_reproduces_the_run(box, tmp_path):
    scenario = SCENARIOS["door_open_excursion"]
    recording, _ = write_recording(scenario, box, tmp_path / "r", random_seed=True)
    header = json.loads(recording.read_text(encoding="utf-8").splitlines()[0])
    assert header["seed_mode"] == "random"
    again, _ = write_recording(scenario, box, tmp_path / "again", seed=header["seed"])
    body = recording.read_text(encoding="utf-8").splitlines()[1:]
    assert again.read_text(encoding="utf-8").splitlines()[1:] == body


def test_ground_truth_sidecar_has_the_new_fields(box, tmp_path):
    truth = _truth_file("spoof_attempt", box, tmp_path)
    n = SCENARIOS["spoof_attempt"].n_samples
    for key in ("compressor_on", "cooling_factor", "ambient_c", "true_temp_c", "reported_temp_c"):
        assert len(truth[key]) == n
    assert truth["seed_mode"] == "fixed" and truth["seed"] == 106
    kinds = {event["kind"]: event for event in truth["events"]}
    assert set(kinds) == {"cooling_factor", "spoof"}
    assert all(e["origin"] == "scheduled" for e in truth["events"])
    spoof = kinds["spoof"]
    assert spoof["first_sample_index"] is not None
    assert truth["resolved_parameters"]["events"][1]["type"] == "spoof"
    assert spoof["id"] in truth["active_event_ids"][spoof["first_sample_index"]]
    assert truth["spoof_mode"][spoof["first_sample_index"]] == "hold"


def test_injected_events_reach_the_ground_truth(box, tmp_path):
    from simulator.recording import write_run
    from simulator.simulate import run_to_end

    sim = LiveSimulator(SCENARIOS["baseline_ok"], box, seed=4)
    for _ in range(10):
        sim.step()
    assert sim.inject({"type": "kill_cooling"}).accepted
    run = run_to_end(sim)
    _, truth_path = write_run(run, tmp_path)
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    injected = [e for e in truth["events"] if e["origin"] == "injected"]
    assert [e["type"] for e in injected] == ["kill_cooling"]


def test_baseline_wobbles_and_failure_scenarios_behave(box, product, tmp_path):
    base = np.array(_truth_file("baseline_ok", box, tmp_path)["true_temp_c"])
    assert base.std() > 0.1
    freeze = np.array(_truth_file("freeze_event", box, tmp_path)["true_temp_c"])
    assert freeze.min() < product.hard_limit_low_c
    reefer = np.array(_truth_file("reefer_failure", box, tmp_path)["reported_temp_c"])
    beyond = reefer > product.hard_limit_high_c
    assert beyond.sum() >= product.hard_limit_consecutive_samples


def test_sensor_glitch_is_one_sample_and_shock_is_one_sample(box, tmp_path):
    truth = _truth_file("sensor_glitch", box, tmp_path)
    diff = np.abs(np.array(truth["reported_temp_c"]) - np.array(truth["true_temp_c"]))
    glitch = next(e for e in truth["events"] if e["kind"] == "glitch")
    assert list(np.flatnonzero(diff > 15.0)) == [glitch["first_sample_index"]]
    recording, _ = write_recording(SCENARIOS["shock_drop"], box, tmp_path)
    source = RecordedSource(recording)
    source.start()
    shocks = []
    while (reading := source.read()) is not None:
        shocks.append(reading.shock_g)
    source.close()
    assert sum(1 for g in shocks if g > 5.0) == 1


# ----------------------------------------------------------------- RecordedSource


@pytest.mark.parametrize("scenario_id", sorted(EXPECTED_IDS))
def test_recorded_source_replays_exactly_what_was_written(scenario_id, box, tmp_path):
    recording, _ = write_recording(SCENARIOS[scenario_id], box, tmp_path)
    live = LiveSimulator(SCENARIOS[scenario_id], box, seed=SCENARIOS[scenario_id].seed)
    replay = RecordedSource(recording)
    replay.start()
    assert replay.header["scenario_id"] == scenario_id
    while (expected := live.step()[0]) is not None:
        assert replay.read() == expected
    assert replay.read() is None
    replay.close()


def test_recorded_source_reads_the_new_version_and_refuses_the_old(tmp_path):
    new = tmp_path / "new.jsonl"
    new.write_text('{"type":"header","schema_version":"0.2"}\n', encoding="utf-8")
    source = RecordedSource(new)
    source.start()
    assert source.read() is None
    source.close()
    old = tmp_path / "old.jsonl"
    old.write_text('{"type":"header","schema_version":"0.1"}\n', encoding="utf-8")
    source = RecordedSource(old)
    with pytest.raises(ValueError, match=r"0\.1.*Regenerate"):
        source.start()
    source.close()


def test_recorded_source_requires_start_and_a_header(tmp_path):
    with pytest.raises(RuntimeError):
        RecordedSource(tmp_path / "x.jsonl").read()
    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"t_s":0}\n', encoding="utf-8")
    source = RecordedSource(bad)
    with pytest.raises(ValueError):
        source.start()
    source.close()


# ----------------------------------------------------------------- command line


def test_cli_generates_one_scenario(tmp_path, capsys):
    assert cli_main(["generate", "--scenario", "baseline_ok", "--out-dir", str(tmp_path)]) == 0
    assert (tmp_path / "baseline_ok.jsonl").exists()
    assert (tmp_path / "baseline_ok.ground_truth.json").exists()
    assert "baseline_ok" in capsys.readouterr().out


def test_cli_generates_all_and_rejects_bad_input(tmp_path):
    assert cli_main(["generate", "--all", "--out-dir", str(tmp_path)]) == 0
    assert len(list(tmp_path.glob("*.jsonl"))) == len(EXPECTED_IDS)
    assert cli_main(["generate", "--scenario", "nope", "--out-dir", str(tmp_path)]) == 2
    assert cli_main(["generate", "--all", "--seed", "3", "--out-dir", str(tmp_path)]) == 2


def test_cli_seed_options(tmp_path, capsys):
    args = ["generate", "--scenario", "door_open_excursion", "--out-dir", str(tmp_path)]
    assert cli_main([*args, "--seed", "9"]) == 0
    header = json.loads((tmp_path / "door_open_excursion.jsonl").read_text().splitlines()[0])
    assert header["seed"] == 9 and header["seed_mode"] == "fixed"
    assert cli_main([*args, "--random-seed"]) == 0
    assert "seed used:" in capsys.readouterr().out


def test_cli_freerun_writes_a_recording(tmp_path, capsys):
    assert cli_main(["freerun", "--seed", "5", "--hours", "6", "--out-dir", str(tmp_path)]) == 0
    assert (tmp_path / "freerun_5.jsonl").exists()
    assert "seed used: 5" in capsys.readouterr().out
