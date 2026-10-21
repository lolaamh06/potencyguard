"""Phase 3C: per-box calibration, pre-trip check, bound safety factor and interval, false-alarm study,
parallel evaluation, and the byte-identical golden files."""
# ruff: noqa: E501  (hash constants and section lines)

import hashlib
import io
import json
import sys
from pathlib import Path

import pytest
from test_trust import CONFIG, PARAMS, box_series

from edge.assessment import TrustAssessor, WorstCaseIntegrator, worst_case_bound
from edge.cli import main as edge_main
from edge.detector_config import DetectorConfig, load_detector_config
from edge.potency import arrhenius_acceleration_factor
from edge.precheck import PrecheckResult, precheck, window
from edge.tamper_monitor import TamperMonitor
from edge.thermal_twin import load_twin_params, load_variant_twins
from edge.twin_cli import analyse
from simulator.calibration_set import (
    VARIANT_SEEDS,
    calibrate_for_box,
    variant_boxes,
    variant_seed_plan,
)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import evaluate_3c as e3  # noqa: E402
import evaluate_detectors as ev  # noqa: E402

GOLDEN_SHA256 = {
    "data/recordings/baseline_ok.jsonl": "08A0688686DC1418F37CD098019DAA5FB1BB4F0C75E2C7D1C6676056ADFAA673",
    "data/recordings/door_open_excursion.jsonl": "5FCA1E8B13DC345FEE44DC1AA356E7CAEA9FFA5CC39756F510E66AC188928838",
    "data/recordings/freeze_event.jsonl": "842549AB74A290F1C00D32F141731B670B73479608E6CE22BA88E0D923D84004",
    "data/recordings/heatwave_transit.jsonl": "11BDC2FC1BCD849C5573ADE9A6275B21DB53A4A27B93CAA48ACC909EA2B9F173",
    "data/recordings/hidden_spoilage.jsonl": "5050E89DA04C946F08F7449832C850DBE95BE114EC3A4F89401310FAE55770A9",
    "data/recordings/reefer_failure.jsonl": "71D79CCA241D68E481AF9B7DFDE9F5EB0BDC91BE2FB2755F22A1629703FDBED9",
    "data/recordings/sensor_glitch.jsonl": "E06EBE5A70191795A142F6F2F5436EBFE2A50EC80695F7397C3CB17DE94EFA40",
    "data/recordings/shock_drop.jsonl": "3DD624C7419DBDAD9F4F0A9B8CA1E6C8A3E895DA76E456EC5C5B6CA0677249A4",
    "data/recordings/spoof_attempt.jsonl": "49FCD7BF3A62D537E44BCF12AB1171A250C144C8A161D733106AA3B717E35F66",
    "shared/test-vectors/potency_vectors.json": "9A96E51C4EF94CB043CFF42F1FB13C17937ED4BABB49BD7BFD92D71D20501029",
    "shared/test-vectors/potency_vectors_team_document.json": "F10B46A1EFFB75002E3FA089AF6E1EA9545D55EFD0C930A0577109CDEE4DC369",
}


def test_the_golden_recordings_and_shared_test_vectors_are_byte_identical_to_phase_3b():
    for relative, expected in GOLDEN_SHA256.items():
        digest = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest().upper()
        assert digest == expected, relative


def test_the_nominal_twin_file_is_untouched():
    twin = load_twin_params()
    assert twin.tau_h == pytest.approx(5.984, abs=0.001)
    assert twin.dT_cool_c == pytest.approx(29.849, abs=0.001)


# ----------------------------------------------------------------- seeds


def test_every_seed_block_is_disjoint_and_the_new_ranges_are_as_stated():
    blocks = ev._BLOCKS
    seen: set[int] = set()
    for block in blocks:
        assert not seen & set(block)
        seen |= set(block)
    assert (min(ev.FINAL3C_SEEDS), max(ev.FINAL3C_SEEDS), len(ev.FINAL3C_SEEDS)) == (
        50001,
        50200,
        200,
    )
    assert (min(ev.FALSE_ALARM_SEEDS), max(ev.FALSE_ALARM_SEEDS)) == (60001, 61000)
    assert (VARIANT_SEEDS["plus15"][0], VARIANT_SEEDS["plus15"][-1]) == (9101, 9110)
    assert (VARIANT_SEEDS["minus15"][0], VARIANT_SEEDS["minus15"][-1]) == (9201, 9210)
    assert (VARIANT_SEEDS["two_node"][0], VARIANT_SEEDS["two_node"][-1]) == (9301, 9310)
    assert len(ev.SEED_LEDGER_3C) == 10


# ----------------------------------------------------------------- per-box calibration


@pytest.mark.parametrize("name,factor", [("plus15", 1.15), ("minus15", 0.85)])
def test_per_box_calibration_recovers_the_variant_box_within_three_percent(box, name, factor):
    variant = variant_boxes(box)[name]
    fitted = calibrate_for_box(variant, variant_seed_plan(name)).params
    assert fitted.tau_h == pytest.approx(box.box_tau_h * factor, rel=0.03)
    true_dt = variant.box_R_th_k_per_w * variant.box_cooling_capacity_w
    assert fitted.dT_cool_c == pytest.approx(true_dt, rel=0.03)


def test_the_stored_variant_file_matches_a_refit(box):
    stored = load_variant_twins()
    assert set(stored) == {"plus15", "minus15", "two_node"}
    for name, variant in variant_boxes(box).items():
        fitted = calibrate_for_box(variant, variant_seed_plan(name)).params
        assert stored[name].tau_h == pytest.approx(fitted.tau_h, abs=1e-9)
        assert stored[name].dT_cool_c == pytest.approx(fitted.dT_cool_c, abs=1e-9)


def test_the_variant_file_is_labelled_simulation_only_with_its_seeds():
    text = (ROOT / "config" / "twin_calibrated_variants.yaml").read_text(encoding="utf-8")
    assert "Simulation only, fitted from per-box calibration sets" in text
    for seeds in ("9101", "9201", "9301"):
        assert seeds in text
    assert "\r" not in text and not text.startswith("﻿")


def test_the_two_node_box_is_fitted_by_a_single_node_twin_with_a_visible_gap(box):
    fitted = load_variant_twins()["two_node"]
    assert fitted.tau_h < 0.5 * box.box_tau_h  # the air node dominates what the sensor sees


# ----------------------------------------------------------------- the pre-trip check


def test_precheck_says_the_twin_matches_on_a_nominal_box():
    result = precheck(box_series(37), PARAMS, CONFIG)
    assert isinstance(result, PrecheckResult) and result.ok and result.checked
    assert result.message.startswith("twin matches this box (gain ")


@pytest.mark.parametrize("scale", [1.15, 0.85])
def test_precheck_says_recalibrate_on_a_box_15_percent_away(scale):
    result = precheck(box_series(37, tau_scale=scale), PARAMS, CONFIG)
    assert not result.ok and result.checked
    assert "recalibrate before departure" in result.message and "gain" in result.message


def test_precheck_does_not_claim_a_match_when_the_gain_cannot_be_measured():
    flat = precheck(box_series(37, tau_scale=1.0)[:8], PARAMS, CONFIG)
    assert flat.ok and not flat.checked and "NOT a confirmation" in flat.message


def test_precheck_result_is_frozen_and_window_cuts_by_hours():
    from pydantic import ValidationError

    result = precheck(box_series(37), PARAMS, CONFIG)
    with pytest.raises(ValidationError):
        result.ok = False
    readings = box_series(100)
    assert len(window(readings, 6.0)) == 37  # 0 to 6 hours at 10 minutes
    with pytest.raises(ValueError):
        window(readings, 0)


def test_precheck_command_prints_one_clear_line():
    out = io.StringIO()
    rc = edge_main(
        ["precheck", "--recording", str(ROOT / "data/recordings/baseline_ok.jsonl")], out
    )
    text = out.getvalue()
    assert rc == 0 and "twin matches this box" in text and "first 6 hours" in text
    assert text.rstrip().endswith("Not real-world evidence.")
    out = io.StringIO()
    assert edge_main(["precheck", "--recording", "missing.jsonl"], out) == 2


# ----------------------------------------------------------------- the bound safety factor and interval


def test_the_safety_factor_is_read_from_config_and_inside_the_grid():
    config = load_detector_config()
    assert config.bound_tau_safety_factor in e3.SF_GRID
    for bad in (0.0, 1.2, -0.5):
        raw = config.model_dump()
        raw["bound_tau_safety_factor"] = bad
        with pytest.raises(ValueError):
            DetectorConfig.model_validate(raw)


def test_the_assessor_uses_the_configured_factor(product):
    readings = box_series(200, jump=(80, 10**9, -6.0))
    results = {}
    for sf in (1.0, 0.8):
        cfg = CONFIG.model_copy(update={"bound_tau_safety_factor": sf})
        assessor = TrustAssessor(product, TamperMonitor(PARAMS, cfg, 2, 0.05))
        for r in readings:
            assessor.update(r)
        results[sf] = assessor.last_bound
    assert results[0.8].tau_eq_from_t0_h >= results[1.0].tau_eq_from_t0_h
    batch = worst_case_bound(
        readings,
        results[0.8].t0_s,
        results[0.8].tau_eq_before_t0_h,
        product,
        PARAMS,
        CONFIG.heat_allowance_c,
        0.8,
    )
    assert batch == results[0.8]


def test_a_smaller_factor_never_lowers_the_high_bound_and_must_be_in_range(product):
    readings = box_series(120, jump=(40, 10**9, -6.0))
    totals = []
    for sf in (1.0, 0.9, 0.8, 0.7, 0.6):
        totals.append(
            worst_case_bound(readings, 400 * 6.0, 0.0, product, PARAMS, 60.0, sf).tau_eq_from_t0_h
        )
    assert totals == sorted(totals)
    for bad in (0.0, 1.5):
        with pytest.raises(ValueError):
            WorstCaseIntegrator(product, PARAMS, 60.0, readings[0], 0.0, bad)


def test_the_sweep_is_deterministic_and_selects_the_largest_factor_without_violations(box):
    config = load_detector_config()
    a = e3.run_sf_sweep(box, config, ev.TRAIN_SEEDS[:3], 1)
    b = e3.run_sf_sweep(box, config, ev.TRAIN_SEEDS[:3], 1)
    assert a == b
    ok = [r["sf"] for r in a["table"] if r["violations"] == 0]
    assert a["selected"] == (max(ok) if ok else None)
    assert [r["sf"] for r in a["table"]] == list(e3.SF_GRID)


def test_the_low_bound_is_below_the_high_bound_and_below_the_truth_on_the_golden_spoofs(
    product, box
):
    import json as _json

    for name in ("spoof_attempt", "hidden_spoilage"):
        path = ROOT / "data" / "recordings" / f"{name}.jsonl"
        analysis = analyse(path, product, box)
        bound = analysis.bound
        truth = _json.loads(path.with_suffix(".ground_truth.json").read_text("utf-8"))
        dt_h = analysis.interval_s / 3600.0
        index = round(bound.t0_s / analysis.interval_s)
        true_tau = sum(
            arrhenius_acceleration_factor(t, product) * dt_h
            for t in truth["true_temp_c"][index + 1 :]
        )
        assert bound.tau_eq_low_from_t0_h <= true_tau <= bound.tau_eq_from_t0_h, name
        assert bound.tau_eq_low_total_h <= bound.tau_eq_total_h
        assessment = analysis.assessments[-1]
        assert assessment.bound_tau_eq_h == assessment.bound_high_tau_eq_h == bound.tau_eq_total_h
        assert assessment.bound_low_tau_eq_h == bound.tau_eq_low_total_h
        assert (
            assessment.bound_low_shelf_life_used_fraction
            <= assessment.bound_high_shelf_life_used_fraction
        )


def test_the_twin_command_prints_the_interval_and_says_the_low_end_is_not_a_guarantee():
    out = io.StringIO()
    assert (
        edge_main(["twin", "--recording", str(ROOT / "data/recordings/hidden_spoilage.jsonl")], out)
        == 0
    )
    text = out.getvalue()
    assert "interval: between" in text and "(cooling worked fully)" in text
    assert "(no cooling) of shelf life used" in text and "not a guarantee" in text


def test_low_confidence_trips_get_no_interval(product):
    assessor = TrustAssessor(product, TamperMonitor(PARAMS, CONFIG, 2, 0.05))
    for r in box_series(400, tau_scale=1.4):
        assessment, _, _ = assessor.update(r)
    assert assessment.trust_level == "low_confidence"
    assert assessment.bound_tau_eq_h is None and assessment.bound_low_tau_eq_h is None


# ----------------------------------------------------------------- payload truth for the two-node box


def test_the_true_damage_of_a_two_node_run_uses_the_payload_node(box):
    import dataclasses

    from simulator.scenario import load_all_scenarios
    from simulator.simulate import simulate

    result = simulate(
        load_all_scenarios()["reefer_failure"],
        dataclasses.replace(box, box_model="two_node"),
        seed=3,
    )
    sample = result.truth[40]
    assert sample.true_payload_temp_c is not None
    assert ev._damage_temp_c(sample) == sample.true_payload_temp_c
    single = simulate(load_all_scenarios()["reefer_failure"], box, seed=3)
    assert ev._damage_temp_c(single.truth[40]) == single.truth[40].true_temp_c


# ----------------------------------------------------------------- the false-alarm study


def test_the_false_alarm_replicate_agrees_with_the_monitor_at_the_current_setting(box, product):
    config = load_detector_config()
    twin = load_twin_params()
    monitor = TamperMonitor(
        twin, config, product.hard_limit_consecutive_samples, box.sensor_sigma_c
    )
    families = e3._families()
    for name in ev.CLEAN_NAMES:
        runs = [families[name].make(seed, box) for seed in ev.FALSE_ALARM_SEEDS[:6]]
        real, _ = ev._cusum_episodes(monitor, runs)
        sequences = []
        for run in runs:
            monitor.reset()
            sequences.append(
                [(s.residual_sigma, s.cusum_skipped) for s in map(monitor.update, run.readings)]
            )
        assert (
            e3.cusum_episodes(sequences, config.cusum_k, config.cusum_h, config.cusum_cap_factor)
            == real
        )


def test_the_false_alarm_study_uses_only_clean_families():
    assert set(e3.FA_FAMILIES) == set(ev.CLEAN_NAMES)
    assert "door_open_excursion" not in e3.FA_FAMILIES  # a real heat event is not a false alarm


# ----------------------------------------------------------------- parallel evaluation


def test_pmap_keeps_the_task_order():
    assert e3.pmap(abs, [-3, 2, -1], 1) == [3, 2, 1]


def _strip(study):
    study = json.loads(json.dumps(study, default=float))
    for key in ("runtime_s", "timings_s", "workers"):
        study.pop(key, None)
    return study


def test_the_quick_study_is_identical_in_serial_and_parallel_mode():
    serial = e3.run_study(quick=True, workers=1, log=lambda _m: None)
    parallel = e3.run_study(quick=True, workers=2, log=lambda _m: None)
    assert _strip(serial) == _strip(parallel)
    text = e3.render_markdown(serial)
    assert "Seed ledger" in text and "Not real-world evidence." in text
    assert all(seed not in set(ev.FINAL3C_SEEDS) for seed in ev.FINAL_SEEDS[:5])
