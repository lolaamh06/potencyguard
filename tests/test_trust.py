"""Phase 3B: the twin-out-of-date self-check, the worst-case bound and the potency assessment."""

import io
import json
import math
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from edge.assessment import (
    PotencyAssessment,
    TrustAssessor,
    WorstCaseIntegrator,
    assess,
    worst_case_bound,
)
from edge.cli import main as edge_main
from edge.detector_config import DetectorConfig, load_detector_config
from edge.potency import PotencyTracker, arrhenius_acceleration_factor
from edge.sensor_reading import SensorReading
from edge.tamper_monitor import (
    FALSIFICATION,
    GLITCH,
    LOW_CONFIDENCE,
    OK,
    OUT_OF_DATE,
    THERMAL_ANOMALY,
    TRUSTED,
    UNTRUSTED,
    TamperMonitor,
    fit_gain,
)
from edge.thermal_twin import TwinParams, load_twin_params, predict_next

ROOT = Path(__file__).resolve().parent.parent
RECORDINGS = ROOT / "data" / "recordings"
PARAMS = load_twin_params()
CONFIG = load_detector_config()
DT = 600.0
SIGMA_SENSOR = 0.05


def ambient(i: int) -> float:
    return 22.0 + 6.0 * math.sin(2 * math.pi * i / 144)


def box_series(
    n,
    *,
    tau_scale=1.0,
    dT_scale=1.0,
    switch_back_at=10**9,
    seed=0,
    ramp_per_h=0.0,
    ramp_from=10**9,
    jump=None,
):
    """Readings from a box whose real dynamics differ from the twin's by the given scales.

    The compressor duty alternates (nine samples on, nine off) and the ambient swings, so the
    predicted change varies enough for the gain to be measurable. A ramp lie lowers the reported
    value linearly; `jump` is a (from_index, to_index, offset_c) offset on the reported value.
    """
    rng = np.random.default_rng(seed)
    out, temp = [], 7.0
    for i in range(n):
        scale = tau_scale if i < switch_back_at else 1.0
        real = TwinParams(
            tau_h=PARAMS.tau_h * scale,
            dT_cool_c=PARAMS.dT_cool_c * (dT_scale if i < switch_back_at else 1.0),
            sigma_r_c=PARAMS.sigma_r_c,
        )
        duty = 1.0 if (i // 9) % 2 == 0 else 0.0
        if i > 0:
            temp = predict_next(temp, (ambient(i - 1) + ambient(i)) / 2, duty, DT, real)
        lie = ramp_per_h * max(0, i - ramp_from) * DT / 3600.0
        if jump and jump[0] <= i < jump[1]:
            lie += jump[2]
        out.append(
            SensorReading(
                t_s=i * DT,
                temp_c=temp - lie + float(rng.normal(0.0, SIGMA_SENSOR)),
                rh_pct=45.0,
                shock_g=0.0,
                source="sim",
                ambient_c=ambient(i),
                cooling_duty=duty,
            )
        )
    return out


def pairs(readings):
    out = []
    for a, b in zip(readings, readings[1:], strict=False):
        pred = predict_next(a.temp_c, (a.ambient_c + b.ambient_c) / 2, b.cooling_duty, DT, PARAMS)
        out.append((pred - a.temp_c, b.temp_c - a.temp_c, DT / 3600.0))
    return out


def make_monitor(config: DetectorConfig = CONFIG) -> TamperMonitor:
    return TamperMonitor(PARAMS, config, 2, SIGMA_SENSOR)


def run(monitor, readings):
    return [monitor.update(r) for r in readings]


# ----------------------------------------------------------------- the rolling regression


def test_a_pure_gain_error_gives_a_gain_away_from_one_and_no_drift():
    # The real box responds 1.43 times faster than the twin says: g about 1.4, b about 0.
    g, b, se = fit_gain(pairs(box_series(300, tau_scale=0.7))[-72:])
    assert 1.25 < g < 1.6 and abs(b) < 0.1 and se < 0.04


def test_the_nominal_box_gives_a_gain_of_one():
    g, b, _ = fit_gain(pairs(box_series(300))[-72:])
    assert g == pytest.approx(1.0, abs=0.06) and abs(b) < 0.1


def test_a_ramp_drift_gives_a_negative_drift_slope_and_a_gain_near_one():
    g, b, _ = fit_gain(pairs(box_series(300, ramp_per_h=0.5, ramp_from=100))[-72:])
    assert g == pytest.approx(1.0, abs=0.1) and b < -0.3


def test_a_jump_is_caught_by_the_impossible_step_flag_not_by_the_gain():
    monitor = make_monitor()
    states = run(monitor, box_series(120, jump=(60, 10**9, -6.0)))
    assert any(s.flag_step for s in states)
    assert states[-1].verdict == FALSIFICATION


def test_fit_gain_needs_variation_and_enough_pairs():
    assert fit_gain([(0.1, 0.1, 0.17)] * 2) is None
    assert fit_gain([(0.0, 0.0, 0.1667)] * 10) is None  # x carries no information
    g, b, se = fit_gain([(float(i), 2.0 * i + 0.3, 1.0) for i in range(10)])
    assert (g, b) == pytest.approx((2.0, 0.3)) and se == pytest.approx(0.0, abs=1e-9)


# ----------------------------------------------------------------- the verdict


def test_the_nominal_box_never_goes_out_of_date():
    for seed in range(4):
        states = run(make_monitor(), box_series(600, seed=seed))
        assert not any(s.twin_out_of_date for s in states), seed
        assert OUT_OF_DATE not in {s.verdict for s in states}


def test_a_mismatched_box_is_reported_out_of_date_and_flagged_from_the_start():
    monitor = make_monitor()
    states = run(monitor, box_series(400, tau_scale=1.4))
    ood = [s for s in states if s.verdict == OUT_OF_DATE]
    assert ood and states[-1].twin_out_of_date
    assert monitor.out_of_date_from_start and states[-1].out_of_date_from_start
    first = next(s for s in states if s.twin_out_of_date)
    assert first.samples_seen == CONFIG.ood_window_samples + CONFIG.ood_sustained_samples
    assert states[-1].untrusted_since_s is not None and states[-1].untrusted_reason == OUT_OF_DATE


def test_out_of_date_suppresses_the_cusum_tamper_verdict_but_still_reports_the_cusum():
    states = run(make_monitor(), box_series(400, tau_scale=1.4))
    suppressed = [s for s in states if s.twin_out_of_date and s.flag_cusum_neg]
    assert suppressed, "the mismatch should push the negative CUSUM up while out of date"
    assert all(s.verdict == OUT_OF_DATE for s in suppressed)
    assert all(s.cusum_neg > CONFIG.cusum_h for s in suppressed)


def test_a_cusum_alarm_on_a_nominal_box_is_still_a_falsification():
    states = run(make_monitor(), box_series(400, ramp_per_h=0.5, ramp_from=150))
    assert any(s.verdict == FALSIFICATION for s in states[150:])


def test_hard_proofs_are_not_suppressed_while_out_of_date():
    readings = box_series(400, tau_scale=1.4, jump=(300, 10**9, -8.0))
    monitor = make_monitor()
    states = run(monitor, readings)
    assert states[299].twin_out_of_date and states[299].verdict == OUT_OF_DATE
    assert states[-1].verdict == FALSIFICATION  # the persistent impossible step won
    assert not states[-1].twin_out_of_date and monitor.self_check_off


def test_the_impossible_state_is_not_suppressed_while_out_of_date():
    base = box_series(400, tau_scale=1.4)
    # a long stretch far below the lag-aware floor: physically impossible for any cooling
    lied = [
        r.model_copy(update={"temp_c": -20.0}) if 330 <= i < 345 else r for i, r in enumerate(base)
    ]
    states = run(make_monitor(), lied)
    assert states[329].twin_out_of_date
    assert any(s.flag_state for s in states[330:350])
    assert states[-1].verdict == FALSIFICATION


def test_once_a_proof_has_fired_the_self_check_is_off_for_the_rest_of_the_trip():
    readings = box_series(500, jump=(50, 10**9, -6.0))  # a hold-like jump, then nominal dynamics
    monitor = make_monitor()
    states = run(monitor, readings)
    assert monitor.self_check_off
    assert not any(s.twin_out_of_date for s in states)
    assert states[-1].verdict == FALSIFICATION


def test_a_lone_glitch_does_not_switch_the_self_check_off():
    readings = box_series(400, tau_scale=1.4)
    readings[250] = readings[250].model_copy(update={"temp_c": 60.0})  # after it went out of date
    monitor = make_monitor()
    states = run(monitor, readings)
    assert states[249].twin_out_of_date
    assert GLITCH in {s.verdict for s in states[250:254]}
    assert not monitor.self_check_off
    assert states[-1].twin_out_of_date and states[-1].verdict == OUT_OF_DATE


def test_the_gain_band_keeps_implausible_gains_from_being_called_a_mismatch():
    narrow = CONFIG.model_copy(update={"ood_gain_band_low": 0.9, "ood_gain_band_high": 1.2})
    states = run(make_monitor(narrow), box_series(400, tau_scale=0.7))  # g about 1.4: outside
    assert not any(s.twin_out_of_date for s in states)


def test_the_gain_is_not_judged_when_it_cannot_be_measured():
    picky = CONFIG.model_copy(update={"ood_max_gain_se": 1e-9})
    states = run(make_monitor(picky), box_series(400, tau_scale=1.4))
    assert not any(s.twin_out_of_date for s in states)


def test_out_of_date_clears_when_the_box_matches_the_twin_again():
    readings = box_series(700, tau_scale=1.4, switch_back_at=300)
    states = run(make_monitor(), readings)
    assert any(s.twin_out_of_date for s in states[:300])
    assert not states[-1].twin_out_of_date
    assert states[-1].untrusted_since_s is not None  # the doubt about the earlier data stays


def test_the_detector_config_validates_the_new_values():
    raw = CONFIG.model_dump()
    for bad in (
        {"ood_window_samples": 3},
        {"ood_gain_margin": 0.0},
        {"ood_gain_band_low": 1.2},
        {"ood_gain_band_high": 0.9},
        {"ood_sustained_samples": 0},
        {"ood_max_gain_se": float("nan")},
        {"trust_lookback_samples": -1},
    ):
        with pytest.raises(ValidationError):
            DetectorConfig(**{**raw, **bad})


# ----------------------------------------------------------------- the worst-case bound


def _flat_readings(n, *, temp=6.0, amb=30.0, duty=1.0):
    return [
        SensorReading(
            t_s=i * DT,
            temp_c=temp,
            rh_pct=45.0,
            shock_g=0.0,
            source="sim",
            ambient_c=amb,
            cooling_duty=duty,
        )
        for i in range(n)
    ]


def test_the_bound_matches_a_hand_integration(product):
    readings = _flat_readings(30)
    allowance = 12.0
    bound = worst_case_bound(readings, 5 * DT, 1.5, product, PARAMS, allowance)
    temp, added = 6.0, 0.0
    for k in range(6, 30):
        t_inf = 30.0 + (allowance if k == 6 else 0.0)
        temp = t_inf + (temp - t_inf) * math.exp(-DT / PARAMS.tau_s)
        added += arrhenius_acceleration_factor(temp, product) * DT / 3600.0
    assert bound.tau_eq_from_t0_h == pytest.approx(added)
    assert bound.tau_eq_total_h == pytest.approx(1.5 + added)
    assert bound.t0_h == pytest.approx(5 * DT / 3600.0) and bound.samples_after_t0 == 24
    assert bound.worst_case_temp_c == pytest.approx(temp)
    assert 0.0 < bound.potency < 1.0 and bound.shelf_life_used_fraction > 0.0


def test_the_bound_never_looks_at_the_duty_or_at_temperatures_after_t0(product):
    base = _flat_readings(30)
    changed = [
        r if i <= 5 else r.model_copy(update={"temp_c": 1.0 + (i % 3), "cooling_duty": 0.0})
        for i, r in enumerate(base)
    ]
    a = worst_case_bound(base, 5 * DT, 0.0, product, PARAMS, 10.0)
    b = worst_case_bound(changed, 5 * DT, 0.0, product, PARAMS, 10.0)
    assert a == b


def test_the_bound_grows_with_the_heat_allowance_and_a_warmer_ambient(product):
    low = worst_case_bound(_flat_readings(30), 0.0, 0.0, product, PARAMS, 0.0)
    high = worst_case_bound(_flat_readings(30), 0.0, 0.0, product, PARAMS, 20.0)
    warm = worst_case_bound(_flat_readings(30, amb=40.0), 0.0, 0.0, product, PARAMS, 0.0)
    assert high.tau_eq_from_t0_h > low.tau_eq_from_t0_h
    assert warm.tau_eq_from_t0_h > low.tau_eq_from_t0_h


def test_the_bound_needs_a_reading_at_t0_and_the_ambient_channel(product):
    with pytest.raises(ValueError, match="no reading at t0"):
        worst_case_bound(_flat_readings(5), 123.0, 0.0, product, PARAMS, 0.0)
    bare = SensorReading(t_s=0.0, temp_c=5.0, rh_pct=45.0, shock_g=0.0, source="sim")
    with pytest.raises(ValueError, match="ambient"):
        WorstCaseIntegrator(product, PARAMS, 0.0, bare, 0.0)


def _true_tau_after(truth_temps, index, product):
    return sum(
        arrhenius_acceleration_factor(t, product) * DT / 3600.0 for t in truth_temps[index + 1 :]
    )


@pytest.mark.parametrize("name", ["spoof_attempt", "hidden_spoilage"])
def test_the_bound_holds_on_the_golden_recordings(name, product, box):
    from edge.twin_cli import analyse

    analysis = analyse(RECORDINGS / f"{name}.jsonl", product, box)
    truth = json.loads((RECORDINGS / f"{name}.ground_truth.json").read_text("utf-8"))
    bound = analysis.bound
    assert bound is not None
    index = round(bound.t0_s / DT)
    assert bound.tau_eq_from_t0_h >= _true_tau_after(truth["true_temp_c"], index, product)
    assert bound.t0_s < analysis.first_divergence_s  # it starts before the lie began


def test_the_bound_holds_on_fresh_seeds_of_every_lie_family(product, box):
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    import evaluate_detectors as ev

    families = {**ev.build_families(), **ev.build_lie_families()}
    names = [
        "spoof_attempt",
        "hidden_spoilage",
        "injected_offset",
        "injected_replay",
        "injected_drift_0.5_clean",
        "injected_drift_2_fault",
        "injected_mimic_at_failure",
    ]
    monitor = TamperMonitor.from_defaults(product, box)
    computed = 0
    for name in names:
        for seed in range(30001, 30005):
            row = ev.score_run(families[name].make(seed, box), families[name], monitor)
            if row["bound_computed"]:
                computed += 1
                assert row["bound_valid"], (name, seed, row["bound_ratio"])
    assert computed >= 20


# ----------------------------------------------------------------- the assessment


def _states_for(readings, product):
    assessor = TrustAssessor(product, make_monitor())
    return assessor, [assessor.update(r) for r in readings]


def test_trusted_data_have_no_worst_case_and_a_plain_reason(product):
    _, results = _states_for(box_series(100), product)
    assessment, potency, monitor_state = results[-1]
    assert assessment.trusted and assessment.worst_case_potency is None
    assert assessment.untrusted_since_s is None and assessment.verdict == OK
    assert assessment.reported_potency == potency.potency
    assert "no evidence" in assessment.trust_reason


def test_the_assessment_turns_untrusted_when_a_lie_is_found_and_stays_so(product):
    readings = box_series(200, jump=(80, 10**9, -6.0))
    assessor, results = _states_for(readings, product)
    flags = [a.trusted for a, _, _ in results]
    first_untrusted = flags.index(False)
    assert 80 <= first_untrusted <= 83 and not any(flags[first_untrusted:])
    final = results[-1][0]
    assert final.untrusted_since_s is not None and final.untrusted_since_s <= 80 * DT
    assert (
        final.worst_case_potency is not None and final.worst_case_potency <= final.reported_potency
    )
    assert final.worst_case_shelf_life_used_fraction >= final.reported_shelf_life_used_fraction
    assert final.verdict == FALSIFICATION and "inconsistent" in final.trust_reason


def test_an_out_of_date_twin_makes_the_data_untrusted_with_its_own_reason(product):
    _, results = _states_for(box_series(300, tau_scale=1.4), product)
    final = results[-1][0]
    assert not final.trusted and "out of date" in final.trust_reason
    assert final.untrusted_since_s == 0.0 or final.untrusted_since_s < 3 * DT


def test_assess_checks_that_the_bound_matches_the_monitor(product):
    readings = box_series(200, jump=(80, 10**9, -6.0))
    assessor, results = _states_for(readings, product)
    _, potency, state = results[-1]
    bound = assessor.last_bound
    assert assess(potency, state, bound).trusted is False
    other = worst_case_bound(readings, 0.0, 0.0, product, PARAMS, 10.0)
    with pytest.raises(ValueError, match="starts at"):
        assess(potency, state, other)
    _, _, early = _states_for(box_series(50), product)[1][-1]
    with pytest.raises(ValueError, match="still trusts"):
        assess(potency, early, bound)


def test_assess_is_pure_and_frozen(product):
    readings = box_series(200, jump=(80, 10**9, -6.0))
    assessor, results = _states_for(readings, product)
    _, potency, state = results[-1]
    a = assess(potency, state, assessor.last_bound)
    b = assess(potency, state, assessor.last_bound)
    assert a == b and isinstance(a, PotencyAssessment)
    with pytest.raises(ValidationError):
        a.trusted = True


def test_the_assessment_ignores_the_ground_truth_by_construction():
    import inspect

    from edge import assessment

    source = inspect.getsource(assessment)
    for forbidden in ("true_temp", "ground_truth", "TruthSample", "simulator"):
        assert forbidden not in source


def test_the_streaming_bound_equals_the_batch_bound(product):
    readings = box_series(200, jump=(80, 10**9, -6.0))
    assessor, _ = _states_for(readings, product)
    bound = assessor.last_bound
    tracker = PotencyTracker(product)
    taus = [tracker.update(r).tau_eq_h for r in readings]
    index = round(bound.t0_s / DT)
    batch = worst_case_bound(
        readings, bound.t0_s, taus[index], product, PARAMS, CONFIG.heat_allowance_c
    )
    assert batch == bound


# ----------------------------------------------------------------- the commands


def _twin(path):
    out = io.StringIO()
    assert edge_main(["twin", "--recording", str(path)], out) == 0
    return out.getvalue()


def test_twin_command_shows_trust_and_the_bound_for_a_falsified_recording():
    text = _twin(RECORDINGS / "hidden_spoilage.jsonl")
    assert "Trust:" in text and "NOT trusted since hour" in text
    assert "reported (untrusted):" in text
    assert "worst case from hour" in text and "percent of shelf life used" in text
    assert "upper bound, not an estimate" in text
    assert text.rstrip().endswith("Not real-world evidence.")


def test_twin_command_shows_a_plain_trusted_line_for_an_honest_recording():
    text = _twin(RECORDINGS / "baseline_ok.jsonl")
    assert "reported data   trusted" in text and "worst case" not in text


def test_twin_command_names_the_switched_off_self_check():
    assert "self-check switched off" in _twin(RECORDINGS / "spoof_attempt.jsonl")


def test_twin_all_has_a_trust_column():
    out = io.StringIO()
    assert edge_main(["twin", "--all"], out) == 0
    lines = out.getvalue().splitlines()
    assert lines[0].rstrip().endswith("trust")
    body = {ln.split()[0]: ln for ln in lines[1:] if ln and not ln.startswith("Sim")}
    assert body["baseline_ok"].rstrip().endswith("trusted")
    assert "untrusted from" in body["hidden_spoilage"] and "untrusted from" in body["spoof_attempt"]
    assert body["reefer_failure"].rstrip().endswith("trusted")
    assert THERMAL_ANOMALY in body["reefer_failure"]


# ----------------------------------------------------------------- the episode-latched bound start


def biased_series(biases, *, jump_at=None, jump_c=0.0):
    """Readings that follow the twin exactly, plus a per-step bias on the reported value.

    With bias 0 the residual is exactly zero, so both CUSUM statistics stay at exactly 0. A
    positive bias pushes the positive statistic up, a negative one the negative statistic.
    """
    out, temp = [], 7.0
    for i, bias in enumerate(biases):
        duty = 1.0 if (i // 9) % 2 == 0 else 0.0
        if i > 0:
            temp = predict_next(temp, (ambient(i - 1) + ambient(i)) / 2, duty, DT, PARAMS)
            temp += bias
        shown = temp + (jump_c if jump_at is not None and i >= jump_at else 0.0)
        out.append(
            SensorReading(
                t_s=i * DT,
                temp_c=shown,
                rh_pct=45.0,
                shock_g=0.0,
                source="sim",
                ambient_c=ambient(i),
                cooling_duty=duty,
            )
        )
    return out


def test_the_episode_start_is_latched_when_a_spike_goes_quiet_and_a_lie_starts_later():
    # the mimic failure: a fault spikes the statistic, it returns to exactly zero, then a lie starts
    spike = 0.15  # about 2.2 residual sigmas per step
    biases = [0.0] * 20 + [spike] * 6 + [0.0] * 80 + [-spike] * 40
    monitor = make_monitor()
    states = run(monitor, biased_series(biases))
    first_alarm = monitor.first_alarm_s["cusum_pos"]
    a0 = monitor.episode_start_s
    assert a0 is not None and a0 < first_alarm and a0 <= 20 * DT
    quiet_again = next(s for s in states[40:] if s.cusum_pos == 0.0 and s.cusum_neg == 0.0)
    assert quiet_again.t_s > a0  # the old "last quiet time" rule would have moved here
    assert states[-1].verdict == FALSIFICATION
    assert states[-1].untrusted_since_s <= a0
    assert monitor.episode_start_s == a0  # latched: it did not move


def test_a_jump_out_of_a_quiet_state_starts_at_the_last_good_reading():
    monitor = make_monitor()
    states = run(monitor, biased_series([0.0] * 120, jump_at=60, jump_c=-6.0))
    assert monitor.episode_start_s == 59 * DT
    assert states[-1].verdict == FALSIFICATION
    assert states[-1].untrusted_since_s <= 59 * DT


def test_the_episode_start_and_the_untrusted_time_never_move_later_as_samples_are_added():
    for seed in range(12):
        rng = np.random.default_rng(seed)
        biases = [float(b) for b in rng.choice([0.0, 0.0, 0.15, -0.15], size=260)]
        jump_at = int(rng.integers(40, 220)) if seed % 3 == 0 else None
        monitor = make_monitor()
        last_a0 = last_t0 = None
        for r in biased_series(biases, jump_at=jump_at, jump_c=-5.0):
            state = monitor.update(r)
            a0, t0 = monitor.episode_start_s, state.untrusted_since_s
            if last_a0 is not None:
                assert a0 == last_a0, seed
            if last_t0 is not None:
                assert t0 is not None and t0 <= last_t0, seed
            last_a0 = a0 if a0 is not None else last_a0
            last_t0 = t0 if t0 is not None else last_t0


def test_the_old_diagnosis_case_seed_20090_of_the_late_mimic_now_has_a_valid_bound(product, box):
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    import evaluate_detectors as ev

    family = ev.build_lie_families()["injected_mimic_late"]
    monitor = TamperMonitor.from_defaults(product, box)
    row = ev.score_run(family.make(20090, box), family, monitor)
    assert row["bound_computed"] and row["bound_valid"] and row["bound_ratio"] >= 1.0


# ----------------------------------------------------------------- the three trust levels


def test_a_clean_trip_is_trusted_and_has_no_message(product):
    _, results = _states_for(box_series(150), product)
    final = results[-1][0]
    assert final.trust_level == TRUSTED and final.trusted and final.operator_message is None


def test_an_out_of_date_trip_is_low_confidence_with_no_bound_and_an_operator_message(product):
    assessor, results = _states_for(box_series(400, tau_scale=1.4), product)
    final = results[-1][0]
    assert final.trust_level == LOW_CONFIDENCE and not final.trusted
    assert final.worst_case_potency is None and assessor.last_bound is None
    assert "operator review recommended" in final.operator_message
    assert "twin may not match this box" in final.operator_message


def test_a_hard_proof_makes_the_trip_untrusted_with_a_bound(product):
    _, results = _states_for(box_series(200, jump=(80, 10**9, -6.0)), product)
    final = results[-1][0]
    assert final.trust_level == UNTRUSTED and not final.trusted
    assert final.worst_case_potency is not None and final.operator_message is None


def test_the_levels_change_in_order_trusted_low_confidence_untrusted(product):
    # out of date well before sample 300, then a persistent jump (a hard proof) at sample 300
    readings = box_series(400, tau_scale=1.4, jump=(300, 10**9, -8.0))
    assessor, results = _states_for(readings, product)
    levels = [a.trust_level for a, _, _ in results]
    assert levels[0] == TRUSTED
    # A mismatched box first raises CUSUM-only alarms (untrusted); once the self-check has
    # explained them (sample ~77) the level is low_confidence, and it stays so until a hard proof.
    first_low = levels.index(LOW_CONFIDENCE)
    assert first_low < 100
    assert all(level == LOW_CONFIDENCE for level in levels[first_low:300])
    assert levels[-1] == UNTRUSTED and assessor.last_bound is not None
    first_hard = 300
    assert all(
        level == UNTRUSTED for level in levels[first_hard + 3 :]
    )  # a hard proof never clears


def test_the_trusted_flag_follows_the_trust_level(product):
    _, results = _states_for(box_series(400, tau_scale=1.4, jump=(300, 10**9, -8.0)), product)
    assert all(a.trusted == (a.trust_level == TRUSTED) for a, _, _ in results)


def test_assess_refuses_a_bound_for_a_low_confidence_trip(product):
    readings = box_series(400, tau_scale=1.4)
    _, results = _states_for(readings, product)
    _, potency, state = results[-1]
    other = worst_case_bound(
        readings, state.untrusted_since_s, 0.0, product, PARAMS, CONFIG.heat_allowance_c
    )
    with pytest.raises(ValueError, match="low_confidence"):
        assess(potency, state, other)


def test_twin_command_prints_the_trust_level():
    assert "trust level     trusted" in _twin(RECORDINGS / "baseline_ok.jsonl")
    assert "trust level     untrusted" in _twin(RECORDINGS / "hidden_spoilage.jsonl")


def test_twin_command_prints_the_operator_review_message_for_low_confidence(product):
    from types import SimpleNamespace

    from edge.twin_cli import print_trust

    assessor = TrustAssessor(product, make_monitor())
    results = [assessor.update(r) for r in box_series(400, tau_scale=1.4)]
    analysis = SimpleNamespace(
        assessments=[a for a, _, _ in results],
        states=[s for _, _, s in results],
        monitor=assessor.monitor,
        bound=None,
    )
    out = io.StringIO()
    print_trust(analysis, out)
    text = out.getvalue()
    assert "trust level     low_confidence" in text
    assert "operator review recommended: the twin may not match this box" in text
    assert "worst case from hour" not in text
