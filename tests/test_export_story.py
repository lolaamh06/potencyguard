# ruff: noqa: E501
"""Tests for the Phase F3 exports: route equals the backend, and the Story data files."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import export_replay  # noqa: E402
import export_story  # noqa: E402

from backend.replay import DEMO_CHECKPOINTS, make_replay_app, replay_recording  # noqa: E402
from edge.chain import Signer  # noqa: E402

pytest.importorskip("fastapi")


@pytest.fixture(scope="module")
def replay_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("replay_f3")
    export_replay.export_all(out)
    return out


def test_checkpoints_are_the_backends_demo_checkpoints() -> None:
    backend = dict(DEMO_CHECKPOINTS)
    for name, (_, hours) in export_replay.SCENARIOS.items():
        assert backend[name] == hours


def test_exported_route_equals_the_backends_for_all_five(replay_dir: Path) -> None:
    from fastapi.testclient import TestClient

    other_key = Signer.from_seed(hashlib.sha256(b"a different test-only key").digest())
    with tempfile.TemporaryDirectory() as tmp:
        app, store, _ = make_replay_app(db=Path(tmp) / "check.sqlite")
        with TestClient(app) as client:
            for i, (name, hours) in enumerate(DEMO_CHECKPOINTS):
                if name not in export_replay.SCENARIOS:
                    continue
                summary = replay_recording(
                    client, REPO / "data" / "recordings" / f"{name}.jsonl", other_key, Path(tmp), hours,
                    register=(i == 0),
                )  # fmt: skip
                exported = json.loads((replay_dir / f"{name}.json").read_text(encoding="utf-8"))[
                    "decision"
                ]
                assert exported["route"] == summary.decision["route"], name
                assert exported["chosen_action"] == summary.decision["chosen_action"], name
                assert exported["needs_human"] == (summary.decision["route"] != "auto_approved"), (
                    name
                )
        store.close()


def test_the_untrusted_scenarios_need_a_person(replay_dir: Path) -> None:
    for name in ("spoof_attempt", "hidden_spoilage"):
        assert json.loads((replay_dir / f"{name}.json").read_text(encoding="utf-8"))["decision"][
            "needs_human"
        ]
    assert not json.loads((replay_dir / "baseline_ok.json").read_text(encoding="utf-8"))[
        "decision"
    ]["needs_human"]


@pytest.fixture(scope="module")
def story_files(tmp_path_factory: pytest.TempPathFactory) -> dict:
    root = tmp_path_factory.mktemp("story")
    paths = export_story.export_all(root / "story", root / "bundled")
    return {p.name: json.loads(p.read_text(encoding="utf-8")) for p in paths}


def test_chapter1_has_both_profiles_and_the_label(story_files: dict) -> None:
    c1 = story_files["chapter1.json"]
    assert c1["label"] == "Illustrative product, model output"
    assert set(c1["profiles"]) == {"active", "reference"}
    for profile in c1["profiles"].values():
        assert set(profile["journeys"]) == {"A", "B"}
        assert (
            profile["journeys"]["B"]["shelf_life_used_percent"]
            > profile["journeys"]["A"]["shelf_life_used_percent"]
        )


def test_chapter5_table_selects_rows_and_flips(story_files: dict) -> None:
    c5 = story_files["chapter5.json"]
    assert c5["n_points"] == 5000 and c5["seed"] == export_story.SEED
    rows = {r["alpha"]: r for r in c5["rows"]}
    assert len(rows) == 100
    # the textbook numbers at alpha 0.95
    assert rows[0.95]["actions"]["continue"]["expected_loss"] == pytest.approx(4000.0)
    assert rows[0.95]["actions"]["continue"]["cvar"] == pytest.approx(50000.0)
    assert rows[0.95]["actions"]["reroute"]["expected_loss"] == pytest.approx(5250.0)
    assert rows[0.95]["actions"]["reroute"]["cvar"] == pytest.approx(10000.0)
    assert rows[0.95]["recommended"] == "reroute"
    assert rows[0.0]["recommended"] == "continue"  # at alpha 0 the CVaR is the average
    for name, action in c5["actions"].items():
        assert len(action["failed"]) == 5000
        assert sorted(action["rank"]) == list(range(5000)), name
    assert rows[0.95]["tail_points"] == 250


def test_chapter6_has_a_real_edit_and_verify(story_files: dict) -> None:
    c6 = story_files["chapter6.json"]
    assert c6["card"]["trust_level"] == "untrusted"
    assert c6["card"]["route"] == "needs_human"
    chain = c6["chain"]
    assert "BROKEN" in chain["tampered_result"]
    assert chain["first_broken_index"] >= 0
    statuses = [t["status"] for t in chain["ribbon"]]
    assert "verified" in statuses and "broken" in statuses and "after_break" in statuses
    assert c6["backend_check"]["chain_status"] == "rejected"
    assert "does not show the sensor told the truth" in c6["limit"]


def test_story_files_stay_small(story_files: dict) -> None:
    assert len(json.dumps(story_files["chapter5.json"])) < 150_000
    assert len(json.dumps(story_files["chapter6.json"])) < 20_000
