"""The two product profiles (Phase 2D): the active default and the team-document reference."""

import json
from pathlib import Path

import pytest
import yaml

from edge.cli import analyse_recording
from edge.potency import (
    arrhenius_acceleration_factor,
    equivalent_reference_time_h,
    shelf_life_used_fraction,
)
from shared.config import load_product_config

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_YAML = ROOT / "config" / "product_default.yaml"
REFERENCE_YAML = ROOT / "config" / "product_team_document.yaml"
REFERENCE_VECTORS = json.loads(
    (ROOT / "shared" / "test-vectors" / "potency_vectors_team_document.json").read_text("utf-8")
)
STUDY_DOC = ROOT / "docs" / "02-phase-reports" / "phase-02c-constants-study.md"
KINETIC_KEYS = {"Ea_over_R", "tau_max_h"}

# Set C golden-recording numbers: (reported tau_eq h, true tau_eq h, reported used %, true used %).
# Re-derived by running the code in Phase 2D and cross-checked against the Set C table of the
# Phase 2C study document (see test_the_study_document_agrees_with_the_expected_numbers).
SET_C = {
    "baseline_ok": (48.099975241497134, 48.12149801527363, 0.5490864753595563, 0.5493321691241282),
    "door_open_excursion": (
        49.20335222740257,
        49.27820243845221,
        0.5616821030525407,
        0.5625365575165777,
    ),
    "freeze_event": (
        15.17720656004836,
        15.190436810345345,
        0.17325578264895386,
        0.17340681290348567,
    ),
    "heatwave_transit": (
        1666.3616881300354,
        1664.7898873830443,
        19.02239370011456,
        19.004450769212834,
    ),
    "reefer_failure": (
        14348.782850661075,
        14339.932554442847,
        163.7988909892817,
        163.69786021053477,
    ),
    "sensor_glitch": (
        24.07065079267376,
        24.021289465694426,
        0.27477911863782833,
        0.2742156331700277,
    ),
    "shock_drop": (24.004070789167223, 24.028481511495144, 0.2740190729356989, 0.27429773414948794),
    "spoof_attempt": (
        69.23151207904665,
        1262.1221551053814,
        0.7903140648292997,
        14.407787158737232,
    ),
    "hidden_spoilage": (
        155.9049252273094,
        18752.949982058977,
        1.7797365893528472,
        214.07477148469152,
    ),
}


def test_both_profiles_load():
    active = load_product_config(DEFAULT_YAML)
    reference = load_product_config(REFERENCE_YAML)
    assert (active.Ea_over_R, active.tau_max_h) == (15000, 8760)
    assert (reference.Ea_over_R, reference.tau_max_h) == (10000, 17520)
    assert active == load_product_config()  # the default loader returns the active profile


def test_the_profiles_differ_only_in_the_two_kinetic_constants():
    active = yaml.safe_load(DEFAULT_YAML.read_text(encoding="utf-8"))
    reference = yaml.safe_load(REFERENCE_YAML.read_text(encoding="utf-8"))
    assert set(reference) <= set(active)
    for key in reference:
        if key in KINETIC_KEYS:
            assert reference[key] != active[key], key
        else:
            assert reference[key] == active[key], f"{key} has drifted between the profiles"
    assert KINETIC_KEYS <= set(reference)


def test_both_files_label_the_constants_honestly():
    active_text = DEFAULT_YAML.read_text(encoding="utf-8")
    reference_text = REFERENCE_YAML.read_text(encoding="utf-8")
    assert "illustrative profile" in active_text and "[SOURCE NEEDED]" in active_text
    assert "replace with the manufacturer's stability data" in active_text
    assert "not independently verified by us [SOURCE NEEDED]" in reference_text
    assert "worked examples stay verifiable" in reference_text


@pytest.mark.parametrize(
    "check", REFERENCE_VECTORS["document_checks"], ids=lambda c: c["description"]
)
def test_the_reference_profile_reproduces_the_documents_worked_examples(check, reference_product):
    af = arrhenius_acceleration_factor(check["temp_c"], reference_product)
    tau_eq = equivalent_reference_time_h([check["temp_c"]], [check["hours"]], reference_product)
    computed = {
        "af": af,
        "tau_eq_h": tau_eq,
        "shelf_life_used_percent": shelf_life_used_fraction(tau_eq, reference_product) * 100,
    }[check["quantity"]]
    assert round(computed, check["rounding_decimals"]) == check["expected_rounded"]


def test_the_active_profile_does_not_reproduce_the_documents_numbers(product):
    # The point of keeping a reference profile: the document's numbers belong to its constants.
    assert round(arrhenius_acceleration_factor(12.0, product), 3) != 2.417


@pytest.fixture(scope="module")
def analyses(product):
    folder = ROOT / "data" / "recordings"
    return {
        path.name.removesuffix(".jsonl"): analyse_recording(path, product)
        for path in sorted(folder.glob("*.jsonl"))
    }


def test_the_active_profile_gives_the_set_c_numbers_for_every_golden_recording(analyses):
    assert set(analyses) == set(SET_C)
    for scenario_id, (rep_tau, true_tau, rep_used, true_used) in SET_C.items():
        reported, true = (
            analyses[scenario_id].reported_states[-1],
            analyses[scenario_id].true_states[-1],
        )
        assert reported.tau_eq_h == pytest.approx(rep_tau, rel=1e-9), scenario_id
        assert true.tau_eq_h == pytest.approx(true_tau, rel=1e-9), scenario_id
        assert reported.shelf_life_used_fraction * 100 == pytest.approx(rep_used, rel=1e-9)
        assert true.shelf_life_used_fraction * 100 == pytest.approx(true_used, rel=1e-9)


def test_the_study_document_agrees_with_the_expected_numbers():
    text = STUDY_DOC.read_text(encoding="utf-8")
    section = text.split("## Set C:")[1].split("## Set D:")[0]
    rows = {}
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 10 and cells[0] in SET_C:
            rows[cells[0]] = (float(cells[1]), float(cells[2]))
    assert set(rows) == set(SET_C)
    for scenario_id, (rep_used, true_used) in rows.items():
        assert rep_used == pytest.approx(SET_C[scenario_id][2], abs=0.0006)
        assert true_used == pytest.approx(SET_C[scenario_id][3], abs=0.0006)


def test_the_reefer_failure_and_hidden_spoilage_stories_under_the_active_profile(analyses):
    reefer = analyses["reefer_failure"]
    assert reefer.true_states[-1].below_min_potency and reefer.reported_states[-1].below_min_potency
    hidden = analyses["hidden_spoilage"]
    assert hidden.true_states[-1].below_min_potency
    assert not hidden.reported_states[-1].below_min_potency
    assert not any(s.below_min_potency for s in hidden.reported_states)
