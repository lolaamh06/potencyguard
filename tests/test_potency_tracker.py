"""Tests for the streaming PotencyTracker, the suspect-reading rule, recordings and the CLI."""

import dataclasses
import io
import json
from pathlib import Path

import pytest

from edge.cli import analyse_recording
from edge.cli import main as edge_main
from edge.potency import (
    PotencyTracker,
    arrhenius_acceleration_factor,
    equivalent_reference_time_h,
    time_weighted_mkt_c,
)
from edge.sensor_reading import SensorReading

ROOT = Path(__file__).resolve().parent.parent
VECTORS = json.loads((ROOT / "shared" / "test-vectors" / "potency_vectors.json").read_text("utf-8"))
RECORDINGS = ROOT / "data" / "recordings"
STEP_S = 600.0
STEP_H = STEP_S / 3600.0


def _run(cfg, temps, step_s=STEP_S):
    tracker = PotencyTracker(cfg)
    return tracker, [tracker.update_sample(i * step_s, t) for i, t in enumerate(temps)]


def _af(temp, cfg):
    return arrhenius_acceleration_factor(temp, cfg)


# ----------------------------------------------------------------- shared vectors


@pytest.mark.parametrize("case", VECTORS["tracker_cases"], ids=lambda c: c["name"])
def test_tracker_matches_the_shared_vectors(case, product):
    tracker = PotencyTracker(product)
    for reading, status, per in zip(
        case["readings"], case["expected_statuses"], case["expected_per_sample"], strict=True
    ):
        state = tracker.update_sample(reading["t_s"], reading["temp_c"])
        assert state.status == status
        assert state.tau_eq_h == pytest.approx(per["tau_eq_h"], rel=1e-12, abs=1e-300)
        assert state.samples_excluded == per["samples_excluded"]
    final = tracker.snapshot().model_dump()
    for key, expected in case["expected_final_state"].items():
        if isinstance(expected, float):
            assert final[key] == pytest.approx(expected, rel=1e-12), key
        else:
            assert final[key] == expected, key


# ----------------------------------------------------------------- the rule


def test_clean_run_matches_the_pure_functions(product):
    temps = [5.0, 6.5, 4.0, 12.0, 9.0, 5.5]
    tracker, states = _run(product, temps)
    dts = [STEP_H] * (len(temps) - 1)
    assert states[-1].tau_eq_h == pytest.approx(
        equivalent_reference_time_h(temps[1:], dts, product), rel=1e-12
    )
    assert states[-1].mkt_c == pytest.approx(
        time_weighted_mkt_c(temps[1:], dts, product), rel=1e-12
    )
    assert all(s.status == "ok" for s in states) and states[-1].samples_excluded == 0


def test_the_first_sample_has_no_interval(product):
    state = PotencyTracker(product).update_sample(0.0, 12.0)
    assert state.tau_eq_h == 0.0 and state.mkt_c is None and state.potency == 1.0
    assert state.current_af == pytest.approx(_af(12.0, product))


def test_lone_glitch_is_excluded_with_hold_last_valid(product):
    _, with_glitch = _run(product, [5.0, 7.0, 99.0, 5.0, 5.0])
    _, held = _run(product, [5.0, 7.0, 7.0, 5.0, 5.0])
    assert [s.status for s in with_glitch] == ["ok", "ok", "suspect", "ok", "ok"]
    assert with_glitch[-1].tau_eq_h == pytest.approx(held[-1].tau_eq_h, rel=1e-14)
    assert with_glitch[-1].mkt_c == pytest.approx(held[-1].mkt_c, rel=1e-12)
    assert with_glitch[2].samples_excluded == 1 and with_glitch[-1].samples_excluded == 1
    assert with_glitch[2].effective_temp_c == 7.0


def test_two_out_of_range_readings_confirm_and_count_the_earlier_one_once(product):
    _, states = _run(product, [5.0, 5.0, 45.0, 46.0])
    assert [s.status for s in states] == ["ok", "ok", "suspect", "excursion_confirmed"]
    # While the first reading is only suspect it is integrated with the held 5 C.
    assert states[2].tau_eq_h == pytest.approx((1.0 + 1.0) * STEP_H, rel=1e-12)
    assert states[2].samples_excluded == 1
    # After confirmation it is redone with its own temperature, exactly once.
    expected = (_af(5.0, product) + _af(45.0, product) + _af(46.0, product)) * STEP_H
    assert states[3].tau_eq_h == pytest.approx(expected, rel=1e-12)
    assert states[3].samples_excluded == 0


def test_a_confirmed_excursion_stays_in_tau_eq_and_status_recovers(product):
    _, states = _run(product, [5.0, 45.0, 46.0, 47.0, 5.0, 5.0])
    assert [s.status for s in states] == [
        "ok", "suspect", "excursion_confirmed", "excursion_confirmed", "ok", "ok",
    ]  # fmt: skip
    expected = sum(_af(t, product) for t in (45.0, 46.0, 47.0, 5.0, 5.0)) * STEP_H
    assert states[-1].tau_eq_h == pytest.approx(expected, rel=1e-12)
    assert states[-1].samples_excluded == 0


def test_the_low_limit_works_the_same_way(product):
    _, states = _run(product, [5.0, -2.0, -3.0, 5.0])
    assert [s.status for s in states] == ["ok", "suspect", "excursion_confirmed", "ok"]


def test_a_reading_exactly_on_a_limit_is_valid(product):
    _, states = _run(product, [5.0, product.hard_limit_low_c, product.hard_limit_high_c])
    assert all(s.status == "ok" for s in states)


def test_confirmation_count_comes_from_the_config(product):
    three = dataclasses.replace(product, hard_limit_consecutive_samples=3)
    _, states = _run(three, [5.0, 45.0, 46.0, 47.0])
    assert [s.status for s in states] == ["ok", "suspect", "suspect", "excursion_confirmed"]
    assert states[2].samples_excluded == 2 and states[3].samples_excluded == 0
    _, short = _run(three, [5.0, 45.0, 46.0, 5.0])
    assert [s.status for s in short] == ["ok", "suspect", "suspect", "ok"]
    assert short[-1].samples_excluded == 2
    assert short[-1].tau_eq_h == pytest.approx(3 * _af(5.0, three) * STEP_H, rel=1e-12)
    one = dataclasses.replace(product, hard_limit_consecutive_samples=1)
    _, now = _run(one, [5.0, 45.0])
    assert now[-1].status == "excursion_confirmed"


def test_glitch_as_the_very_first_or_last_sample(product):
    _, first = _run(product, [99.0, 5.0, 5.0])
    assert [s.status for s in first] == ["suspect", "ok", "ok"]
    assert first[-1].samples_excluded == 1
    assert first[-1].tau_eq_h == pytest.approx(2 * STEP_H * _af(5.0, product), rel=1e-12)
    _, last = _run(product, [5.0, 5.0, 99.0])
    assert last[-1].status == "suspect" and last[-1].samples_excluded == 1


def test_zero_dt_is_allowed_and_time_backwards_raises(product):
    tracker = PotencyTracker(product)
    tracker.update_sample(100.0, 5.0)
    same = tracker.update_sample(100.0, 30.0)
    assert same.tau_eq_h == 0.0
    with pytest.raises(ValueError, match="backwards"):
        tracker.update_sample(99.0, 5.0)


def test_reset_and_snapshot(product):
    tracker, _ = _run(product, [5.0, 30.0, 30.0])
    snap = tracker.snapshot()
    assert snap == tracker.snapshot() and snap.samples_seen == 3
    tracker.reset()
    fresh = tracker.snapshot()
    assert fresh.samples_seen == 0 and fresh.tau_eq_h == 0.0 and fresh.status == "ok"
    assert fresh.potency == 1.0 and fresh.mkt_c is None and fresh.current_af is None


def test_update_accepts_a_sensor_reading_and_rejects_bad_numbers(product):
    tracker = PotencyTracker(product)
    reading = SensorReading(t_s=0.0, temp_c=5.0, rh_pct=45.0, shock_g=0.0, source="sim")
    assert tracker.update(reading).samples_seen == 1
    with pytest.raises(ValueError):
        tracker.update_sample(10.0, float("nan"))


def test_the_state_reports_the_projection_and_the_min_potency_flag(product):
    _, states = _run(product, [5.0] * 4)
    assert states[-1].hours_to_min_potency_at_current_temp == pytest.approx(
        product.tau_max_h - states[-1].tau_eq_h, rel=1e-12
    )
    assert states[-1].below_min_potency is False
    tracker = PotencyTracker(product)
    tracker.update_sample(0.0, 5.0)
    huge = tracker.update_sample(product.tau_max_h * 3600.0 * 1.5, 5.0)
    assert huge.below_min_potency is True


# ----------------------------------------------------------------- recordings


@pytest.fixture(scope="module")
def analyses(product):
    return {
        path.name.removesuffix(".jsonl"): analyse_recording(path, product)
        for path in sorted(RECORDINGS.glob("*.jsonl"))
    }


def _final(analyses, scenario_id, which):
    series = (
        analyses[scenario_id].reported_states
        if which == "reported"
        else (analyses[scenario_id].true_states)
    )
    return series[-1]


def test_all_eight_recordings_were_analysed(analyses):
    assert len(analyses) == 8


def test_baseline_potency_stays_high(analyses, product):
    state = _final(analyses, "baseline_ok", "reported")
    assert state.potency > product.P_min and not state.below_min_potency
    assert state.tau_eq_h < 0.01 * product.tau_max_h


def test_reefer_failure_uses_far_more_shelf_life_than_the_baseline(analyses, product):
    # With these constants potency equals P_min only when 100 percent of the shelf life is used,
    # so a 36 hour failure cannot push potency below P_min; it spends a lot more of the shelf life.
    failure = _final(analyses, "reefer_failure", "true")
    baseline = _final(analyses, "baseline_ok", "true")
    assert failure.shelf_life_used_fraction > 10 * baseline.shelf_life_used_fraction
    assert failure.potency < baseline.potency
    assert not failure.below_min_potency


def test_spoof_hides_damage_from_the_reported_series(analyses):
    reported = _final(analyses, "spoof_attempt", "reported")
    true = _final(analyses, "spoof_attempt", "true")
    assert true.potency < reported.potency - 1e-4
    assert true.tau_eq_h > 3 * reported.tau_eq_h


def test_sensor_glitch_is_suspect_exactly_once_and_never_confirmed(analyses):
    states = analyses["sensor_glitch"].reported_states
    statuses = [s.status for s in states]
    assert statuses.count("suspect") == 1
    assert "excursion_confirmed" not in statuses
    assert states[-1].samples_excluded == 1
    assert _final(analyses, "sensor_glitch", "true").samples_excluded == 0


def test_freeze_event_reaches_a_confirmed_excursion(analyses):
    assert any(s.status == "excursion_confirmed" for s in analyses["freeze_event"].reported_states)


def test_reefer_failure_reaches_a_confirmed_excursion(analyses):
    assert any(
        s.status == "excursion_confirmed" for s in analyses["reefer_failure"].reported_states
    )


def test_reported_and_true_agree_when_nothing_is_falsified(analyses):
    for scenario_id in ("baseline_ok", "door_open_excursion", "shock_drop", "heatwave_transit"):
        reported = _final(analyses, scenario_id, "reported").tau_eq_h
        true = _final(analyses, scenario_id, "true").tau_eq_h
        assert reported == pytest.approx(true, rel=0.01), scenario_id


# ----------------------------------------------------------------- command line


def test_potency_command_for_one_recording():
    out = io.StringIO()
    assert edge_main(["potency", "--recording", str(RECORDINGS / "spoof_attempt.jsonl")], out) == 0
    text = out.getvalue()
    assert "from reported readings" in text and "from true temperature (ground truth)" in text
    assert text.rstrip().endswith("Simulation result on a synthetic box. Not real-world evidence.")
    assert "sim hour" in text


def test_potency_command_all_prints_a_two_row_summary_per_recording():
    out = io.StringIO()
    assert edge_main(["potency", "--all"], out) == 0
    text = out.getvalue()
    assert text.count("from reported readings") == 8
    assert text.count("from true temperature") == 8
    assert "sim hour" not in text


def test_potency_command_rejects_a_missing_file(tmp_path):
    assert edge_main(["potency", "--recording", str(tmp_path / "nope.jsonl")], io.StringIO()) == 2
