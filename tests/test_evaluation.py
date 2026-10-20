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
