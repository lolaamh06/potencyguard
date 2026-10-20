"""Tests for the scenario library, recordings and RecordedSource (Phase 1, step 5)."""

import hashlib
import json

import numpy as np
import pytest

from edge.recorded_source import RecordedSource
from shared.config import load_box_config, load_product_config
from simulator.cli import main as cli_main
from simulator.recording import DEFAULT_RECORDINGS_DIR, write_recording
from simulator.scenario import Scenario, load_all_scenarios
from simulator.sim_source import SimSource

BOX = load_box_config()
PRODUCT = load_product_config()
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
}


def _truth(scenario_id: str, tmp_path) -> dict:
    _, truth_path = write_recording(SCENARIOS[scenario_id], BOX, tmp_path)
    return json.loads(truth_path.read_text(encoding="utf-8"))


def _sha(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_all_eight_scenarios_exist():
    assert set(SCENARIOS) == EXPECTED_IDS


@pytest.mark.parametrize("scenario_id", sorted(EXPECTED_IDS))
def test_each_scenario_generates_and_is_reproducible(scenario_id, tmp_path):
    first = write_recording(SCENARIOS[scenario_id], BOX, tmp_path / "a")
    second = write_recording(SCENARIOS[scenario_id], BOX, tmp_path / "b")
    for path_a, path_b in zip(first, second, strict=True):
        assert _sha(path_a) == _sha(path_b)
    lines = first[0].read_text(encoding="utf-8").splitlines()
    header = json.loads(lines[0])
    assert header["scenario_id"] == scenario_id
    assert header["seed"] == SCENARIOS[scenario_id].seed
    assert header["schema_version"] == "0.1"
    assert len(lines) == 1 + SCENARIOS[scenario_id].n_samples


@pytest.mark.parametrize("scenario_id", sorted(EXPECTED_IDS))
def test_committed_recordings_match_the_generator(scenario_id, tmp_path):
    fresh = write_recording(SCENARIOS[scenario_id], BOX, tmp_path)
    committed = (
        DEFAULT_RECORDINGS_DIR / f"{scenario_id}.jsonl",
        DEFAULT_RECORDINGS_DIR / f"{scenario_id}.ground_truth.json",
    )
    for new, old in zip(fresh, committed, strict=True):
        assert old.exists(), f"missing {old}; run: python -m simulator generate --all"
        assert _sha(new) == _sha(old)


def test_scenario_descriptions_carry_no_percentages_or_placeholders():
    for scenario in SCENARIOS.values():
        assert "%" not in scenario.description
        assert "[SOURCE NEEDED]" not in scenario.description


def test_baseline_stays_cold(tmp_path):
    truth = _truth("baseline_ok", tmp_path)
    assert min(truth["true_temp_c"]) > 4.9 and max(truth["true_temp_c"]) < 5.1
    assert truth["labels"] == []


def test_door_open_warms_then_recovers(tmp_path):
    truth = _truth("door_open_excursion", tmp_path)
    true = np.array(truth["true_temp_c"])
    assert true.max() > 10.0
    assert true[-1] < 6.0
    assert truth["labels"][0]["type"] == "heat_load"


def test_reefer_failure_exceeds_hard_limit_for_consecutive_samples(tmp_path):
    truth = _truth("reefer_failure", tmp_path)
    beyond = np.array(truth["reported_temp_c"]) > PRODUCT.hard_limit_high_c
    run = longest = 0
    for flag in beyond:
        run = run + 1 if flag else 0
        longest = max(longest, run)
    assert longest >= PRODUCT.hard_limit_consecutive_samples


def test_freeze_event_goes_below_zero(tmp_path):
    truth = _truth("freeze_event", tmp_path)
    assert min(truth["true_temp_c"]) < PRODUCT.hard_limit_low_c
    assert min(truth["reported_temp_c"]) < PRODUCT.hard_limit_low_c


def test_heatwave_runs_warm_for_a_long_time(tmp_path):
    true = np.array(_truth("heatwave_transit", tmp_path)["true_temp_c"])
    assert (true > 8.0).sum() > 100
    assert true.max() < PRODUCT.hard_limit_high_c


def test_spoof_reported_differs_from_true_only_in_labelled_window(tmp_path):
    truth = _truth("spoof_attempt", tmp_path)
    true = np.array(truth["true_temp_c"])
    reported = np.array(truth["reported_temp_c"])
    label = next(item for item in truth["labels"] if item["type"] == "spoof")
    first, last = label["first_sample_index"], label["last_sample_index"]
    diff = np.abs(reported - true)
    assert diff[first : last + 1].min() > 3.0
    assert diff[:first].max() < 0.5
    # The lie is flat while the box warms, so it breaks the thermal model.
    assert reported[first : last + 1].std() < 0.2
    assert true[last] - true[first] > 10.0


def test_sensor_glitch_is_exactly_one_sample(tmp_path):
    truth = _truth("sensor_glitch", tmp_path)
    diff = np.abs(np.array(truth["reported_temp_c"]) - np.array(truth["true_temp_c"]))
    outliers = np.flatnonzero(diff > 5.0)
    label = truth["labels"][0]
    assert list(outliers) == [label["sample_index"]]
    assert label["type"] == "glitch"


def test_shock_drop_has_one_large_shock(tmp_path):
    _, _ = write_recording(SCENARIOS["shock_drop"], BOX, tmp_path)
    source = RecordedSource(tmp_path / "shock_drop.jsonl")
    source.start()
    shocks = []
    while (reading := source.read()) is not None:
        shocks.append(reading.shock_g)
    source.close()
    assert sum(1 for g in shocks if g > 5.0) == 1
    assert max(shocks) > 10.0
    assert sorted(shocks)[-2] < 0.5


@pytest.mark.parametrize("scenario_id", sorted(EXPECTED_IDS))
def test_recorded_source_replays_exactly_what_was_written(scenario_id, tmp_path):
    recording, _ = write_recording(SCENARIOS[scenario_id], BOX, tmp_path)
    live = SimSource(SCENARIOS[scenario_id], BOX)
    live.start()
    replay = RecordedSource(recording)
    replay.start()
    assert replay.header["scenario_id"] == scenario_id
    while (expected := live.read()) is not None:
        assert replay.read() == expected
    assert replay.read() is None
    replay.close()


def test_recorded_source_requires_start_and_a_header(tmp_path):
    with pytest.raises(RuntimeError):
        RecordedSource(tmp_path / "x.jsonl").read()
    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"t_s":0}\n', encoding="utf-8")
    source = RecordedSource(bad)
    with pytest.raises(ValueError):
        source.start()
    source.close()


def test_scenario_validation_rejects_bad_input():
    base = {
        "id": "x",
        "title": "x",
        "description": "x",
        "seed": 1,
        "duration_h": 1,
        "sample_interval_s": 600,
        "ambient": [(0, 20)],
    }
    Scenario(**base)
    with pytest.raises(ValueError):
        Scenario(**{**base, "ambient": [(1, 20)]})
    with pytest.raises(ValueError):
        Scenario(**{**base, "sample_interval_s": 700})
    with pytest.raises(ValueError):
        Scenario(**{**base, "events": [{"type": "unknown"}]})


def test_cli_generates_one_scenario(tmp_path, capsys):
    assert cli_main(["generate", "--scenario", "baseline_ok", "--out-dir", str(tmp_path)]) == 0
    assert (tmp_path / "baseline_ok.jsonl").exists()
    assert (tmp_path / "baseline_ok.ground_truth.json").exists()
    assert "baseline_ok" in capsys.readouterr().out


def test_cli_generates_all_and_rejects_unknown(tmp_path):
    assert cli_main(["generate", "--all", "--out-dir", str(tmp_path)]) == 0
    assert len(list(tmp_path.glob("*.jsonl"))) == len(EXPECTED_IDS)
    assert cli_main(["generate", "--scenario", "nope", "--out-dir", str(tmp_path)]) == 2
