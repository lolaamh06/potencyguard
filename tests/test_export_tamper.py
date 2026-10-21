"""Tests for the Phase F4 exports: real tamper results, worst-case bound, provenance."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import export_replay  # noqa: E402
import tamper_demo  # noqa: E402

from edge.chain import Ledger, verify_chain  # noqa: E402
from edge.runner import run_recording  # noqa: E402
from shared.config import load_box_config, load_product_config  # noqa: E402

NAME = "door_open_excursion"


@pytest.fixture(scope="module")
def exported(tmp_path_factory: pytest.TempPathFactory) -> dict:
    out = tmp_path_factory.mktemp("f4")
    path = export_replay.export_one(NAME, out)
    return json.loads(path.read_text(encoding="utf-8"))


def test_positions_are_inside_the_editable_range() -> None:
    for n in (145, 289, 577):
        pos = export_replay.tamper_positions(n)
        assert pos == sorted(set(pos)) and pos[0] == 0 and pos[-1] == n - 2
        assert all(0 <= k <= n - 2 for k in pos)


def test_exported_tamper_results_equal_a_fresh_verify_chain(exported: dict) -> None:
    product, box = load_product_config(), load_box_config()
    signer = export_replay._signer()
    tamper = exported["tamper"]
    assert tamper["label"] == "Result of a real edit on a ledger copy (recorded)"
    with tempfile.TemporaryDirectory() as tmp:
        run = run_recording(
            REPO / "data" / "recordings" / f"{NAME}.jsonl", product, box, signer,
            export_replay.DEVICE_ID, Path(tmp), "check",
        )  # fmt: skip
        with Ledger.open(run.ledger_path) as ledger:
            assert len(ledger.read_entries()) == tamper["ledger_length"]
        for item in tamper["edits"]:
            copy = tamper_demo.make_copy(run.ledger_path, Path(tmp), f"e{item['entry']}")
            tamper_demo.apply_action(copy, "edit", item["entry"], 1)
            with Ledger.open(copy) as ledger:
                entries, anchor = ledger.read_entries(), ledger.latest_anchor()
            fresh = verify_chain(entries, signer.public_key_bytes, anchor, export_replay.DEVICE_ID)
            assert not fresh.ok and not item["ok"]
            assert item["first_broken_index"] == fresh.index == item["entry"]
            assert item["reason"] == fresh.reason


def test_truncation_passes_without_an_anchor_and_is_caught_with_it(exported: dict) -> None:
    t = exported["tamper"]["truncation"]
    assert t["removed"] == export_replay.TRUNCATE_COUNT
    assert t["without_anchor"]["ok"] is True
    assert t["with_anchor"]["ok"] is False


def test_worst_case_is_labelled_a_bound_and_provenance_is_honest(exported: dict) -> None:
    wc = exported["decision"]["worst_case"]
    assert wc["label"] == "worst-case bound, not an estimate"
    assert 0 < wc["potency"] <= 1
    prov = exported["provenance"]
    assert (
        prov["source"] == "sim" and prov["sap_adapter_mode"] == "mock" and prov["simulated"] is True
    )
    assert "does not stop a false sensor value" in prov["note"]
    assert exported["meta"]["cusum_h"] > 0
    assert set(exported["decision"]["recomputed"]) >= {"potency", "tau_eq_h", "trust_level"}
