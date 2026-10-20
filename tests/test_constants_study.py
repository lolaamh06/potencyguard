"""Tests for the read-only constants study (Phase 2C). It must never change the real config."""

import hashlib
import importlib.util
import json
import math
from pathlib import Path

import pytest

from shared.config import load_product_config

ROOT = Path(__file__).resolve().parent.parent
YAML_PATH = ROOT / "config" / "product_default.yaml"
REPORT_2B = ROOT / "docs" / "02-phase-reports" / "phase-02b-potency-report.md"


def _load_study():
    spec = importlib.util.spec_from_file_location(
        "constants_study", ROOT / "scripts" / "constants_study.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


STUDY_MODULE = _load_study()


@pytest.fixture(scope="module")
def study():
    return STUDY_MODULE.run_study()


def _report_2b_rows() -> dict[str, list[float]]:
    """Section 10 table of the Phase 2B report: scenario -> 8 numbers."""
    text = REPORT_2B.read_text(encoding="utf-8")
    section = text.split("## 10.")[1].split("## 11.")[0]
    rows = {}
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 9 and cells[0] not in ("Scenario", "---"):
            try:
                rows[cells[0]] = [float(c) for c in cells[1:]]
            except ValueError:
                continue
    return rows


def test_set_a_reproduces_the_phase_2b_report(study):
    rows = _report_2b_rows()
    assert len(rows) == 8
    set_a = study["sets"]["A"]["scenarios"]
    for scenario_id, (r_tau, _r_p, r_used, _r_mkt, t_tau, _t_p, t_used, _t_mkt) in rows.items():
        assert set_a[scenario_id]["reported"]["tau_eq_h"] == pytest.approx(r_tau, abs=0.01)
        assert set_a[scenario_id]["true"]["tau_eq_h"] == pytest.approx(t_tau, abs=0.01)
        assert set_a[scenario_id]["reported"]["used_percent"] == pytest.approx(r_used, abs=0.001)
        assert set_a[scenario_id]["true"]["used_percent"] == pytest.approx(t_used, abs=0.001)


def test_every_set_yields_finite_numbers_for_all_recordings(study):
    assert set(study["sets"]) == {"A", "B", "C", "D", "E"}
    for name, data in study["sets"].items():
        assert len(data["scenarios"]) == 9, name  # eight originals plus hidden_spoilage
        for key in (
            "days_lost_per_day_at_25c",
            "days_lost_per_day_at_40c",
            "days_at_40c_to_use_all_shelf_life",
        ):
            assert math.isfinite(data[key]), (name, key)
        for item in data["scenarios"].values():
            for series in (item["reported"], item["true"]):
                for key, value in series.items():
                    if isinstance(value, float):
                        assert math.isfinite(value), (name, key)
        assert all(math.isfinite(v) for v in data["spoof_hidden_loss"].values())


def test_below_p_min_comes_with_an_hour_only_when_it_happened(study):
    for data in study["sets"].values():
        for item in data["scenarios"].values():
            for series in (item["reported"], item["true"]):
                assert series["below_p_min"] == (series["first_below_p_min_hour"] is not None)


def test_the_spoof_hides_damage_in_every_set(study):
    for name, data in study["sets"].items():
        assert data["spoof_hidden_loss"]["used_percent_points"] > 0, name
        assert data["spoof_hidden_loss"]["extra_days_lost"] > 0, name


def test_the_study_does_not_modify_the_loaded_config():
    cfg = load_product_config()
    snapshot = (cfg, cfg.k_ref_per_h)
    STUDY_MODULE.run_study(cfg)
    assert (cfg, cfg.k_ref_per_h) == snapshot
    assert load_product_config() == cfg
    variant = STUDY_MODULE.make_variant(cfg, {"Ea_over_R": 20000})
    assert variant.Ea_over_R == 20000 and cfg.Ea_over_R == 15000  # the active profile is untouched


def test_the_yaml_file_is_byte_identical_after_the_study(tmp_path):
    before = hashlib.sha256(YAML_PATH.read_bytes()).hexdigest()
    exit_code = STUDY_MODULE.main(
        ["--markdown", str(tmp_path / "study.md"), "--json", str(tmp_path / "study.json")]
    )
    assert exit_code == 0
    assert hashlib.sha256(YAML_PATH.read_bytes()).hexdigest() == before
    assert "Not real-world evidence." in (tmp_path / "study.md").read_text(encoding="utf-8")
    assert set(json.loads((tmp_path / "study.json").read_text(encoding="utf-8"))["sets"]) == set(
        "ABCDE"
    )


def test_the_committed_study_document_matches_a_fresh_run(study):
    committed = (ROOT / "docs" / "02-phase-reports" / "phase-02c-constants-study.md").read_text(
        encoding="utf-8"
    )
    assert committed == STUDY_MODULE.render_markdown(study) + "\n"


def test_the_active_default_equals_set_c(study):
    cfg = load_product_config()
    set_c = STUDY_MODULE.CANDIDATES["C"]
    assert (cfg.Ea_over_R, cfg.tau_max_h) == (set_c["Ea_over_R"], set_c["tau_max_h"])
    assert study["sets"]["C"]["Ea_over_R"] == cfg.Ea_over_R
    assert study["sets"]["C"]["tau_max_h"] == cfg.tau_max_h
