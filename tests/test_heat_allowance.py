"""Phase 3B: the step detector's heat allowance is derived from the box and the door limit."""

from pathlib import Path

from edge.detector_config import load_detector_config

MAX_RATIO = 1.5


def test_the_allowance_covers_the_largest_door_the_simulator_can_open(box):
    needed = box.box_R_th_k_per_w * box.door_max_power_w
    assert load_detector_config().heat_allowance_c >= needed


def test_the_allowance_stays_tied_to_the_simulator(box):
    needed = box.box_R_th_k_per_w * box.door_max_power_w
    assert load_detector_config().heat_allowance_c <= MAX_RATIO * needed


def test_the_derivation_is_stated_next_to_the_value():
    path = Path(__file__).resolve().parent.parent / "config" / "detectors.yaml"
    text = path.read_text(encoding="utf-8")
    assert "heat_allowance_c = box_R_th_k_per_w * door_max_power_w" in text
    assert "largest sudden warming of the box" in text
