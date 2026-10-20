"""Calibration: recovery of the box parameters, input gates and the separation from scoring."""

import dataclasses
import glob
import json
import shutil
from pathlib import Path

import pytest
import yaml

from edge.calibration import (
    CALIBRATION_PREFIX,
    MIN_ROWS,
    CalibrationError,
    calibrate,
    calibrate_from_recordings,
    load_calibration_run,
)
from edge.thermal_twin import load_twin_params
from simulator.calibration_set import (
    CALIBRATION_PLAN,
    CALIBRATION_SCENARIOS_DIR,
    CALIBRATION_SEEDS,
    DEFAULT_CALIBRATION_DIR,
    generate_calibration,
)
from simulator.scenario import load_all_scenarios
from simulator.simulate import simulate

ROOT = Path(__file__).resolve().parent.parent
CAL_SCENARIOS = load_all_scenarios(CALIBRATION_SCENARIOS_DIR)
TRUE_TAU_H = 6.0  # config box_tau_h, the value the fit must recover
TRUE_DT_COOL = 30.0  # R_th * capacity = 0.5 * 60


def _runs(box, seeds=(1, 2, 3), names=("calibration_baseline", "calibration_wide")):
    return [simulate(CAL_SCENARIOS[n], box, seed=s).readings for n in names for s in seeds]


def _noise_free(box):
    return dataclasses.replace(
        box,
        sensor_sigma_c=0.0,
        sensor_sigma_rh_pct=0.0,
        sensor_sigma_shock_g=0.0,
        sensor_sigma_ambient_c=0.0,
    )


def test_recovers_the_parameters_on_a_noise_free_run(box):
    result = calibrate(_runs(_noise_free(box)))
    assert result.params.tau_h == pytest.approx(TRUE_TAU_H, rel=0.01)
    assert result.params.dT_cool_c == pytest.approx(TRUE_DT_COOL, rel=0.01)
    assert result.params.sigma_r_c < 0.03  # only the within-interval timing remains
    assert abs(result.d) < 0.01


def test_recovers_the_parameters_on_a_noisy_run(box):
    result = calibrate(_runs(box, seeds=range(1, 6)))
    assert result.params.tau_h == pytest.approx(TRUE_TAU_H, rel=0.04)
    assert result.params.dT_cool_c == pytest.approx(TRUE_DT_COOL, rel=0.04)
    assert result.params.sigma_r_c == pytest.approx(0.07, abs=0.015)
    assert 0.9 < result.r_squared < 1.0


def test_the_unrestricted_fit_is_biased_by_measurement_noise(box):
    result = calibrate(_runs(box, seeds=range(1, 6)))
    # Documented weakness (edge/calibration.py): the noisy regressor T[n] biases the
    # unrestricted fit; the restricted fit used for the twin does not suffer from it.
    assert result.tau_h_unrestricted is not None
    assert result.tau_h_unrestricted < 0.6 * TRUE_TAU_H
    assert result.b_minus_expected < -0.01


def test_rejects_short_flat_and_missing_channel_input(box):
    short = simulate(CAL_SCENARIOS["calibration_wide"], box, seed=1).readings[:100]
    with pytest.raises(CalibrationError, match="too short"):
        calibrate([short])
    flat_scenario = CAL_SCENARIOS["calibration_wide"].model_copy(
        update={"ambient": [(0, 22), (48, 22)], "ambient_jitter_c": 0, "ambient_shift_h": 0}
    )
    flat = [simulate(flat_scenario, box, seed=s).readings for s in range(1, 6)]
    with pytest.raises(CalibrationError, match="too flat"):
        calibrate(flat)
    bare = [r.model_copy(update={"ambient_c": None}) for r in short]
    with pytest.raises(CalibrationError, match="ambient_c"):
        calibrate([bare])
    with pytest.raises(CalibrationError):
        calibrate([])
    assert MIN_ROWS > 100


def test_rejects_unevenly_spaced_readings(box):
    run = simulate(CAL_SCENARIOS["calibration_wide"], box, seed=1).readings
    uneven = list(run)
    uneven[10] = uneven[10].model_copy(update={"t_s": uneven[10].t_s + 100.0})
    with pytest.raises(CalibrationError, match="evenly"):
        calibrate([uneven])


def test_refuses_evaluation_recordings():
    golden = ROOT / "data" / "recordings" / "baseline_ok.jsonl"
    with pytest.raises(CalibrationError, match="not calibration data"):
        load_calibration_run(golden)
    with pytest.raises(CalibrationError, match="not calibration data"):
        calibrate_from_recordings([golden])


def test_refuses_a_calibration_named_recording_in_the_evaluation_set(tmp_path):
    source = DEFAULT_CALIBRATION_DIR / "calibration_wide_9006.jsonl"
    copy = tmp_path / source.name
    shutil.copy(source, copy)
    shutil.copy(source.with_suffix(".ground_truth.json"), copy.with_suffix(".ground_truth.json"))
    assert load_calibration_run(copy)
    with pytest.raises(CalibrationError, match="not calibration data"):
        load_calibration_run(copy, evaluation_ids=["calibration_wide"])


def test_refuses_recordings_with_tamper_or_unmodelled_labels(tmp_path):
    source = DEFAULT_CALIBRATION_DIR / "calibration_wide_9006.jsonl"
    copy = tmp_path / source.name
    shutil.copy(source, copy)
    truth = json.loads(source.with_suffix(".ground_truth.json").read_text(encoding="utf-8"))
    truth["events"] = [{"kind": "spoof", "id": "x", "type": "spoof"}]
    copy.with_suffix(".ground_truth.json").write_text(json.dumps(truth), encoding="utf-8")
    with pytest.raises(CalibrationError, match="clean"):
        load_calibration_run(copy)
    truth["events"] = [{"kind": "heat_load", "id": "x", "type": "heat_load"}]
    copy.with_suffix(".ground_truth.json").write_text(json.dumps(truth), encoding="utf-8")
    with pytest.raises(CalibrationError, match="clean"):
        load_calibration_run(copy)
    copy.with_suffix(".ground_truth.json").unlink()
    with pytest.raises(CalibrationError, match="labels are missing"):
        load_calibration_run(copy)


# ----------------------------------------------------------------- the stored calibration


def test_calibration_scenarios_are_clean_and_separate_from_the_golden_set():
    assert set(CAL_SCENARIOS) == set(CALIBRATION_PLAN)
    assert all(name.startswith(CALIBRATION_PREFIX) for name in CAL_SCENARIOS)
    assert all(not s.events for s in CAL_SCENARIOS.values())
    golden = {p.name.removesuffix(".jsonl") for p in (ROOT / "data" / "recordings").glob("*.jsonl")}
    assert not set(CAL_SCENARIOS) & golden


def test_calibration_seeds_are_disjoint_from_training_and_test_seeds():
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    import evaluate_detectors as ev

    assert not set(CALIBRATION_SEEDS) & set(ev.TRAIN_SEEDS)
    assert not set(CALIBRATION_SEEDS) & set(ev.TEST_SEEDS)
    assert not set(ev.TRAIN_SEEDS) & set(ev.TEST_SEEDS)
    assert len(CALIBRATION_SEEDS) == 10


def test_committed_calibration_recordings_match_a_fresh_generation(box, tmp_path):
    fresh = generate_calibration(box, tmp_path)
    committed = sorted(glob.glob(str(DEFAULT_CALIBRATION_DIR / "*.jsonl")))
    assert [p.name for p in fresh] == [Path(c).name for c in committed]
    for new, old in zip(fresh, committed, strict=True):
        assert new.read_bytes() == Path(old).read_bytes(), new.name
        sidecar = new.with_suffix(".ground_truth.json")
        assert sidecar.read_bytes() == Path(old).with_suffix(".ground_truth.json").read_bytes()


def test_the_stored_twin_equals_a_fresh_fit_of_the_committed_data():
    files = sorted(glob.glob(str(DEFAULT_CALIBRATION_DIR / "*.jsonl")))
    fresh = calibrate_from_recordings(files).params
    stored = load_twin_params()
    assert stored.tau_h == pytest.approx(fresh.tau_h, rel=1e-12)
    assert stored.dT_cool_c == pytest.approx(fresh.dT_cool_c, rel=1e-12)
    assert stored.sigma_r_c == pytest.approx(fresh.sigma_r_c, rel=1e-12)


def test_the_stored_file_records_where_it_came_from():
    text = (ROOT / "config" / "twin_calibrated.yaml").read_text(encoding="utf-8")
    assert text.startswith("# Fitted from data/calibration/, simulation only")
    data = yaml.safe_load(text)
    assert data["calibration_seeds"] == CALIBRATION_SEEDS
    assert len(data["calibration_files"]) == 10
    assert "fit_date" in data
    assert all(f.startswith("calibration_") for f in data["calibration_files"])
