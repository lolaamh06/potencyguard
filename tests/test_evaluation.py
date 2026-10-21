"""The evaluation harness: seeds, the selection rule, determinism and the committed result."""

import re
import sys
from pathlib import Path

import pytest

from edge.detector_config import load_detector_config
from edge.tamper_monitor import TamperMonitor
from edge.thermal_twin import load_twin_params
from simulator.calibration_set import CALIBRATION_SEEDS

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import evaluate_detectors as ev  # noqa: E402

DOC = ROOT / "docs" / "02-phase-reports" / "phase-03-evaluation.md"


@pytest.fixture(scope="module")
def quick():
    return ev.run_evaluation(quick=True)


def test_seed_blocks_are_disjoint():
    calibration, training, test = set(CALIBRATION_SEEDS), set(ev.TRAIN_SEEDS), set(ev.TEST_SEEDS)
    assert not calibration & training and not calibration & test and not training & test
    assert len(training) == 100 and len(test) == 200


def test_the_selection_rule_picks_the_smallest_delay_within_the_target():
    table = [
        {"k": 0.5, "h": 8.0, "false_alarms_per_1000h": 0.2, "cusum_neg_median_delay_min": 30.0},
        {"k": 0.25, "h": 4.0, "false_alarms_per_1000h": 3.0, "cusum_neg_median_delay_min": 10.0},
        {"k": 1.0, "h": 4.0, "false_alarms_per_1000h": 0.5, "cusum_neg_median_delay_min": 20.0},
        {"k": 1.0, "h": 8.0, "false_alarms_per_1000h": 0.0, "cusum_neg_median_delay_min": None},
    ]
    assert ev.select_setting(table, 1.0)["k"] == 1.0  # the 3.0 row is too noisy, None is skipped
    assert ev.select_setting(table, 1.0)["h"] == 4.0
    assert ev.select_setting(table, 5.0)["k"] == 0.25
    assert ev.select_setting(table, 0.01) is None


def test_ties_prefer_fewer_false_alarms_then_the_larger_h():
    table = [
        {"k": 0.5, "h": 4.0, "false_alarms_per_1000h": 0.5, "cusum_neg_median_delay_min": 20.0},
        {"k": 0.5, "h": 8.0, "false_alarms_per_1000h": 0.1, "cusum_neg_median_delay_min": 20.0},
        {"k": 1.0, "h": 12.0, "false_alarms_per_1000h": 0.1, "cusum_neg_median_delay_min": 20.0},
    ]
    assert ev.select_setting(table, 1.0)["h"] == 12.0


def test_quick_mode_reports_the_configured_cusum_settings(quick):
    config = load_detector_config()
    assert quick["config"] == {"cusum_k": config.cusum_k, "cusum_h": config.cusum_h}
    assert quick["quick"] is True
    assert quick["seeds"]["training"][2] == ev.QUICK_COUNT
    assert quick["seeds"]["test"][2] == ev.QUICK_COUNT


def test_quick_mode_covers_every_family_and_mismatch_box(quick):
    assert set(quick["final"]) == set(ev.build_families())
    assert set(quick["mismatch"]) == set(ev.mismatch_boxes(ev.load_box_config()))
    for e in quick["final"].values():
        assert e["runs"] == ev.QUICK_COUNT
    assert len(quick["sweep"]["table"]) == len(ev.SWEEP_K) * len(ev.SWEEP_H)


def test_the_evaluation_is_deterministic(box, product):
    families = ev.build_families()
    monitor = TamperMonitor(
        load_twin_params(), load_detector_config(), product.hard_limit_consecutive_samples,
        box.sensor_sigma_c,
    )  # fmt: skip
    for name in ("hidden_spoilage", "injected_replay", "door_open_excursion"):
        a = ev.evaluate_family(families[name], ev.TEST_SEEDS[:3], box, monitor)
        b = ev.evaluate_family(families[name], ev.TEST_SEEDS[:3], box, monitor)
        assert a == b


def test_quick_results_are_sensible(quick):
    final = quick["final"]
    for name in ("spoof_attempt", "hidden_spoilage", "injected_offset", "injected_replay"):
        assert final[name]["detection_rate"] == 1.0, name
    for name in ("baseline_ok", "shock_drop"):
        assert final[name]["runs_with_tamper_verdict"] == 0, name
    for name in ("reefer_failure", "door_open_excursion"):
        assert final[name]["detection_rate"] == 1.0 and final[name]["correct_class_rate"] == 1.0
    assert final["sensor_glitch"]["runs_with_glitch_verdict"] == ev.QUICK_COUNT


def test_the_markdown_has_every_section_and_the_footer(quick):
    text = ev.render_markdown(quick)
    for needle in (
        "## Seed blocks (disjoint)",
        "## CUSUM sweep (training seeds)",
        "## Final scoring (test seeds)",
        "## Mismatch: the real box differs from the calibration",
        "Selection rule:",
        "Simulation result on a synthetic box. Not real-world evidence.",
    ):
        assert needle in text


def test_the_committed_evaluation_names_the_configured_settings():
    text = DOC.read_text(encoding="utf-8")
    match = re.search(
        r"settings in config/detectors\.yaml are k = (\d+(?:\.\d+)?), h = (\d+(?:\.\d+)?)", text
    )
    assert match, "the committed evaluation does not state the configured settings"
    config = load_detector_config()
    assert float(match.group(1)) == config.cusum_k and float(match.group(2)) == config.cusum_h
    assert "The rule selects k = " in text
    assert "(100 per family; used only for the sweep below)" in text
    assert "(200 per family; final scoring)" in text
    assert text.rstrip().endswith("Not real-world evidence.*")


# ----------------------------------------------------------------- Phase 3B

DOC_3B = ROOT / "docs" / "02-phase-reports" / "phase-03b-evaluation.md"


def test_the_seed_sets_stay_disjoint_across_all_blocks():
    blocks = [
        set(CALIBRATION_SEEDS),
        set(ev.TRAIN_SEEDS),
        set(ev.DEVELOPMENT_SEEDS),
        set(ev.VALIDITY_DEV_SEEDS),
        set(ev.FINAL_SEEDS),
    ]
    for i, first in enumerate(blocks):
        for second in blocks[i + 1 :]:
            assert not first & second
    assert (min(ev.TRAIN_SEEDS), max(ev.TRAIN_SEEDS)) == (10001, 10100)
    assert (min(ev.DEVELOPMENT_SEEDS), max(ev.DEVELOPMENT_SEEDS)) == (20001, 20200)
    assert (min(ev.VALIDITY_DEV_SEEDS), max(ev.VALIDITY_DEV_SEEDS)) == (30001, 30200)
    assert (min(ev.FINAL_SEEDS), max(ev.FINAL_SEEDS)) == (40001, 40200)
    assert ev.TEST_SEEDS == ev.FINAL_SEEDS
    assert (min(CALIBRATION_SEEDS), max(CALIBRATION_SEEDS)) == (9001, 9010)


def test_the_ood_selection_rule_filters_then_minimises_the_runs_that_end_with_tamper():
    def row(window, margin, sustained, false, loss, ended_plus, ended_minus, plus, minus):
        return {
            "window": window,
            "margin": margin,
            "sustained": sustained,
            "nominal_false_ood_rate": false,
            "max_lie_loss": loss,
            "plus15_ended_tamper_rate": ended_plus,
            "minus15_ended_tamper_rate": ended_minus,
            "plus15_ood_rate": plus,
            "minus15_ood_rate": minus,
        }

    table = [
        row(36, 0.06, 6, 0.10, 0.0, 0.0, 0.0, 0.9, 0.9),  # too many nominal false alarms
        row(72, 0.06, 6, 0.00, 0.05, 0.0, 0.0, 0.9, 0.9),  # loses lie detection
        row(72, 0.08, 12, 0.00, 0.0, 0.20, 0.0, 0.7, 0.5),
        row(72, 0.08, 6, 0.00, 0.0, 0.20, 0.0, 0.8, 0.6),  # same ending, more coverage
        row(36, 0.10, 6, 0.01, 0.0, 0.34, 0.0, 0.9, 0.9),  # more coverage but ends with tamper more
        row(144, 0.08, 6, 0.00, 0.0, 0.20, 0.0, 0.8, 0.6),  # same as the chosen one, larger window
    ]
    chosen = ev.select_ood_setting(table, 0.02, 0.01)
    assert (chosen["window"], chosen["margin"], chosen["sustained"]) == (72, 0.08, 6)
    assert ev.select_ood_setting([table[0], table[1]], 0.02, 0.01) is None
    close = [
        row(72, 0.08, 6, 0.0, 0.0, 0.200, 0.0, 0.5, 0.5),
        row(72, 0.1, 6, 0.0, 0.0, 0.204, 0.0, 0.9, 0.9),
    ]
    assert ev.select_ood_setting(close, 0.02, 0.01)["margin"] == 0.1  # a tie to the nearest point


def test_the_phase3_behaviour_is_the_same_code_with_the_self_check_off(box, product):
    families = ev.build_families()
    twin = load_twin_params()
    off = TamperMonitor(
        twin, ev.phase3_config(load_detector_config()), product.hard_limit_consecutive_samples,
        box.sensor_sigma_c,
    )  # fmt: skip
    for name in ("baseline_ok", "reefer_failure", "hidden_spoilage"):
        result = ev.evaluate_family(families[name], ev.TEST_SEEDS[:2], box, off)
        assert result["runs_with_ood_verdict"] == 0


def test_the_lie_families_are_deterministic_and_use_the_new_modes(box, product):
    lies = ev.build_lie_families()
    assert len(lies) == 2 * len(ev.DRIFT_RATES) + 2
    monitor = TamperMonitor.from_defaults(product, box)
    for name in ("injected_drift_1_clean", "injected_mimic_at_failure"):
        a = ev.evaluate_family(lies[name], ev.TEST_SEEDS[:3], box, monitor)
        b = ev.evaluate_family(lies[name], ev.TEST_SEEDS[:3], box, monitor)
        assert a == b
    run = lies["injected_drift_1_clean"].make(ev.TEST_SEEDS[0], box)
    assert {s.spoof_mode for s in run.truth} == {None, "drift"}
    run = lies["injected_mimic_at_failure"].make(ev.TEST_SEEDS[0], box)
    assert {s.spoof_mode for s in run.truth} == {None, "mimic"}


def test_quick_mode_has_the_phase_3b_tables(quick):
    assert set(quick["lies"]) == set(ev.build_lie_families())
    assert set(quick["before_final"]) == set(ev.build_families())
    assert set(quick["before_mismatch"]) == set(quick["mismatch"])
    config = load_detector_config()
    assert quick["ood_config"]["window"] == config.ood_window_samples
    assert len(quick["ood_sweep"]["table"]) == 1  # quick mode checks the configured setting only
    row = quick["ood_sweep"]["table"][0]
    assert (row["window"], row["margin"], row["sustained"]) == (
        config.ood_window_samples,
        config.ood_gain_margin,
        config.ood_sustained_samples,
    )
    for e in quick["lies"].values():
        assert e["runs"] == ev.QUICK_COUNT and "bound" in e


def test_quick_phase_3b_markdown_has_every_new_section(quick):
    text = ev.render_markdown(quick)
    for needle in (
        "## Phase 3B: the twin-out-of-date self-check, threshold sweep (training seeds)",
        "## Phase 3B: lie families (test seeds)",
        "## Phase 3B: mismatch, with the new verdict space",
        "## Phase 3B: before and after (same test seeds)",
        "## Phase 3B: the worst-case bound",
        "Simulation result on a synthetic box. Not real-world evidence.",
    ):
        assert needle in text


def test_the_committed_3b_evaluation_names_the_configured_settings():
    text = DOC_3B.read_text(encoding="utf-8")
    config = load_detector_config()
    needle = (
        f"The settings in config/detectors.yaml are window = {config.ood_window_samples}, "
        f"margin = {config.ood_gain_margin}, sustained = {config.ood_sustained_samples}."
    )
    assert needle in text
    match = re.search(
        r"The rule selects window = (\d+), margin = ([\d.]+), sustained = (\d+)", text
    )
    assert match, "the committed evaluation does not state the selected setting"
    assert int(match.group(1)) == config.ood_window_samples
    assert float(match.group(2)) == config.ood_gain_margin
    assert int(match.group(3)) == config.ood_sustained_samples
    assert "(100 per family; used only for the sweep below)" in text
    assert "(200 per family; final scoring)" in text
    assert text.rstrip().endswith("Not real-world evidence.*")
