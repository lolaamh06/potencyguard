"""Tests for scripts/export_replay.py: the replay files the dashboard reads (Phase F2)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import export_replay  # noqa: E402

FRAME_KEYS = {
    "t_s", "temp_c", "ambient_c", "twin_c", "residual_c", "cusum_neg", "cusum_pos",
    "potency", "tau_eq_h", "shelf_life_used_fraction", "mkt_c", "trust_level", "verdict", "flags",
}  # fmt: skip


@pytest.fixture(scope="module")
def exported(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("replay")
    export_replay.export_all(out)
    return out


def _load(folder: Path, name: str) -> dict:
    return json.loads((folder / f"{name}.json").read_text(encoding="utf-8"))


def test_all_five_scenarios_and_an_index_are_written(exported: Path) -> None:
    names = sorted(export_replay.SCENARIOS)
    assert names == [
        "baseline_ok",
        "door_open_excursion",
        "hidden_spoilage",
        "reefer_failure",
        "spoof_attempt",
    ]
    index = _load(exported, "index")
    assert [s["scenario_id"] for s in index["scenarios"]] == list(export_replay.SCENARIOS)
    for name in names:
        assert (exported / f"{name}.json").is_file()


@pytest.mark.parametrize("name", list(export_replay.SCENARIOS))
def test_schema_of_each_file(exported: Path, name: str) -> None:
    doc = _load(exported, name)
    assert set(doc) == {"meta", "frames", "events", "decision", "chain", "tamper", "provenance"}
    meta = doc["meta"]
    assert meta["schema_version"] == export_replay.SCHEMA_VERSION
    assert meta["scenario_id"] == name
    assert meta["labels"]["product"] == "Illustrative product, model output"
    assert meta["labels"]["data"].startswith("Synthetic data")
    assert meta["source"] == "sim"
    assert meta["route"]["origin"]["label"].endswith("(illustrative)")
    assert doc["frames"], "no frames"
    for frame in doc["frames"]:
        assert set(frame) == FRAME_KEYS
        assert 0.0 <= frame["potency"] <= 1.0
    times = [f["t_s"] for f in doc["frames"]]
    assert times == sorted(times)
    decision = doc["decision"]
    assert decision["chosen_action"] in {a["name"] for a in decision["actions"]}
    assert isinstance(decision["needs_human"], bool)
    assert doc["chain"]["ok"] is True
    assert doc["chain"]["anchor"] is None


def test_untrusted_scenarios_are_never_auto_approved(exported: Path) -> None:
    for name in ("spoof_attempt", "hidden_spoilage"):
        decision = _load(exported, name)["decision"]
        assert decision["trust_level"] == "untrusted"
        assert decision["needs_human"] is True


def test_files_stay_small(exported: Path) -> None:
    for path in exported.glob("*.json"):
        assert path.stat().st_size < 120_000, path.name


def test_export_is_deterministic(tmp_path: Path) -> None:
    first = export_replay.export_one("door_open_excursion", tmp_path / "a")
    second = export_replay.export_one("door_open_excursion", tmp_path / "b")
    assert first.read_bytes() == second.read_bytes()


def test_no_key_or_clock_in_the_output(exported: Path) -> None:
    for path in exported.glob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert "BEGIN" not in text
        assert "private" not in text.lower()
