"""Phase 6: the backend API, storage, key registry, audit log and the mock enterprise adapter.

No authentication in this phase. Signing protects records after signing and does not stop a lie at
the sensor (A18): these tests check that the backend recomputes the physics checks and plans from
the recomputed values. Simulation on a synthetic box.
"""

# ruff: noqa: E501
import hashlib
import io
import json
import sqlite3
import sys
import warnings
from pathlib import Path

import pytest

warnings.filterwarnings("ignore", message=".*starlette.testclient.*")
from fastapi.testclient import TestClient  # noqa: E402

from backend import cli as backend_cli  # noqa: E402
from backend.api import create_app  # noqa: E402
from backend.config import BackendConfig, load_backend_config  # noqa: E402
from backend.replay import entries_to_json  # noqa: E402
from backend.sap import (  # noqa: E402
    EVENT_DESCRIPTION,
    MockSapAdapter,
    SandboxSapAdapter,
    SapEvent,
    make_adapter,
)
from backend.service import apply_backend_rules, close_call  # noqa: E402
from backend.storage import TABLES, Store  # noqa: E402
from edge.chain import ChainWriter, Ledger, Signer, new_run_id  # noqa: E402
from edge.chain.canonical import parse_canonical as parse_device_record  # noqa: E402
from edge.runner import record_from_pipeline, run_recording  # noqa: E402
from planner.config import ACTIONS, load_planner_config  # noqa: E402
from planner.core import ActionResult, DecisionTable  # noqa: E402
from planner.records import parse_canonical as parse_decision_record  # noqa: E402
from shared.config import ConfigError  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RECORDINGS = ROOT / "data" / "recordings"
DEVICE = "pg-test-device-1"
CALLER = {"X-Caller": "pytest"}
sys.path.insert(0, str(ROOT / "scripts"))
import tamper_demo  # noqa: E402


def make_signer(label: bytes = b"potencyguard TEST ONLY backend seed") -> Signer:
    return Signer.from_seed(hashlib.sha256(label).digest())


SIGNER = make_signer()
OTHER = make_signer(b"potencyguard TEST ONLY other seed")


# ----------------------------------------------------------------- shared ledgers (made once)


@pytest.fixture(scope="module")
def ledgers(tmp_path_factory):
    from shared.config import load_box_config, load_product_config

    folder = tmp_path_factory.mktemp("ledgers")
    out = {}
    for name in (
        "baseline_ok",
        "hidden_spoilage",
        "spoof_attempt",
        "reefer_failure",
        "door_open_excursion",
    ):
        summary = run_recording(
            RECORDINGS / f"{name}.jsonl",
            load_product_config(),
            load_box_config(),
            SIGNER,
            DEVICE,
            folder,
            f"t_{name}",
        )
        with Ledger.open(summary.ledger_path) as ledger:
            out[name] = (summary.ledger_path, ledger.read_entries(), ledger.latest_anchor())
    return out


def t_h(entry) -> float:
    return parse_device_record(entry.record)["t_ms"] / 3_600_000


def prefix(entries, hours):
    return [e for e in entries if t_h(e) <= hours + 1e-9]


def duration_h(name):
    header = json.loads((RECORDINGS / f"{name}.jsonl").open(encoding="utf-8").readline())
    return (header["n_samples"] - 1) * header["sample_interval_s"] / 3600.0


class World:
    """An app with its own database, a test client and a registered device."""

    def __init__(self, tmp_path, cfg_changes=None, planner_cfg=None, register=True, clock=None):
        cfg = load_backend_config().model_copy(
            update={"database": str(tmp_path / "backend.sqlite"), **(cfg_changes or {})}
        )
        self.cfg = cfg
        self.store = Store(cfg.database_path(), clock) if clock else Store(cfg.database_path())
        self.app = create_app(
            cfg, self.store, str(tmp_path / "planner-key"), planner_cfg=planner_cfg
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        if register:
            r = self.register(SIGNER)
            assert r.status_code == 201, r.text

    def register(self, signer, device=DEVICE, by="pytest-operator"):
        return self.client.post(
            "/devices/register",
            headers=CALLER,
            json={
                "device_id": device,
                "public_key_hex": signer.public_key_bytes.hex(),
                "registered_by": by,
            },
        )

    def shipment(self, sid, name, hours=None):
        body = {
            "shipment_id": sid,
            "label": name,
            "device_id": DEVICE,
            "origin": "replay",
            "scheduled_duration_h": duration_h(name),
        }
        r = self.client.post("/shipments", headers=CALLER, json=body)
        assert r.status_code == 201, r.text
        return r.json()

    def post_ledger(self, sid, entries, anchor=None, **extra):
        return self.client.post(
            f"/shipments/{sid}/ledger",
            headers=CALLER,
            json={**entries_to_json(entries, anchor), **extra},
        )

    def decide(self, sid, **body):
        return self.client.post(f"/shipments/{sid}/decide", headers=CALLER, json=body)

    def loaded(self, ledgers, name, hours, sid=None):
        sid = sid or name
        self.shipment(sid, name)
        entries, anchor = ledgers[name][1], ledgers[name][2]
        part = prefix(entries, hours)
        r = self.post_ledger(sid, part, None if len(part) < len(entries) else anchor)
        assert r.status_code == 200 and r.json()["chain_status"] == "verified", r.text
        return sid

    def close(self):
        self.client.close()
        self.store.close()


@pytest.fixture
def world(tmp_path):
    w = World(tmp_path)
    yield w
    w.close()


# ----------------------------------------------------------------- registry and revocation


def test_a_device_key_is_registered_listed_and_revoked_with_new_rows(world):
    devices = world.client.get("/devices").json()["items"]
    assert [(d["device_id"], d["status"]) for d in devices] == [(DEVICE, "active")]
    assert devices[0]["key_id"] == SIGNER.key_id
    assert world.register(SIGNER).status_code == 409  # already registered
    assert (
        world.register(SIGNER, device="another-device").status_code == 409
    )  # a key belongs to one device
    r = world.client.post(
        f"/devices/{DEVICE}/revoke",
        headers=CALLER,
        json={
            "key_id": SIGNER.key_id,
            "revoked_by": "pytest-operator",
            "reason": "test revocation",
        },
    )
    assert r.status_code == 200 and r.json()["status"] == "revoked"
    assert world.client.get("/devices").json()["items"][0]["status"] == "revoked"
    assert (
        world.client.post(
            f"/devices/{DEVICE}/revoke",
            headers=CALLER,
            json={"key_id": SIGNER.key_id, "revoked_by": "pytest-operator", "reason": "again"},
        ).status_code
        == 409
    )
    assert (
        world.client.post(
            f"/devices/{DEVICE}/revoke",
            headers=CALLER,
            json={"key_id": "0" * 16, "revoked_by": "pytest-operator", "reason": "unknown"},
        ).status_code
        == 404
    )
    rows = world.store.key_rows(DEVICE)
    assert [r["status"] for r in rows] == ["active", "revoked"]  # revocation is a new row


def test_a_ledger_received_after_revocation_is_rejected_and_old_data_are_marked(world, ledgers):
    sid = world.loaded(ledgers, "baseline_ok", 24.0)
    world.client.post(
        f"/devices/{DEVICE}/revoke",
        headers=CALLER,
        json={
            "key_id": SIGNER.key_id,
            "revoked_by": "pytest-operator",
            "reason": "test revocation",
        },
    )
    world.shipment("late", "baseline_ok")
    r = world.post_ledger("late", ledgers["baseline_ok"][1], ledgers["baseline_ok"][2]).json()
    assert (r["chain_status"], r["reason"]) == (
        "rejected",
        "key_revoked",
    ) and "device clock is not trusted" in r["detail"]
    verify = world.client.get(f"/shipments/{sid}/verify").json()
    assert (
        verify["ok"] is True
        and verify["key_status"] == "revoked"
        and "cannot tell" in verify["note"]
    )
    decision = world.decide(
        sid
    ).json()  # a decision on data from a revoked key always needs a person
    assert decision["route"] == "needs_human" and any(
        "revoked" in reason for reason in decision["reasons"]
    )


# ----------------------------------------------------------------- ingest and the trust model


def test_a_good_ledger_verifies_and_the_values_are_recomputed(world, ledgers):
    sid = world.loaded(ledgers, "baseline_ok", 48.0)
    view = world.client.get(f"/shipments/{sid}").json()
    assert (
        view["chain"]["status"] == "verified"
        and view["chain"]["entries"] == 289
        and view["chain"]["anchor_checked"]
    )
    assert view["status"] == "active" and view["latest"]["claims_consistent"] is True
    assert view["latest"]["trust_level"] == "trusted" and "recomputed" in view["latest"]["note"]
    last = parse_device_record(ledgers["baseline_ok"][1][-1].record)
    assert view["latest"]["potency"] == pytest.approx(last["potency"] / 1e9, abs=1e-9)
    assert [h["status"] for h in view["status_history"]] == ["created", "active"]


@pytest.mark.parametrize(
    "action,reason",
    [("edit", "bad_signature"), ("delete", "bad_sequence"), ("reorder", "bad_sequence")],
)
def test_each_tamper_action_is_rejected_at_the_right_entry(
    world, ledgers, tmp_path, action, reason
):
    path = ledgers["hidden_spoilage"][0]
    copy = tamper_demo.make_copy(path, tmp_path, action)
    tamper_demo.apply_action(copy, action, None, 5)
    with Ledger.open(copy) as ledger:
        entries, anchor = ledger.read_entries(), ledger.latest_anchor()
    world.shipment("tampered", "hidden_spoilage")
    r = world.post_ledger("tampered", entries, anchor).json()
    middle = len(ledgers["hidden_spoilage"][1]) // 2
    assert (r["chain_status"], r["reason"], r["first_bad_index"]) == ("rejected", reason, middle)
    view = world.client.get("/shipments/tampered").json()
    assert view["status"] == "quarantined_pending_review" and view["chain"]["status"] == "rejected"
    refused = world.decide("tampered")
    assert refused.status_code == 409 and refused.json()["error"] == "ledger_rejected"
    assert world.store.decision_index("tampered") == []  # nothing was produced from it


def test_a_ledger_re_signed_with_another_key_is_rejected_even_if_consistent(
    world, ledgers, tmp_path
):
    copy = tamper_demo.make_copy(ledgers["baseline_ok"][0], tmp_path, "resign")
    tamper_demo.apply_action(copy, "resign", None, 5)
    with Ledger.open(copy) as ledger:
        entries, anchor = ledger.read_entries(), ledger.latest_anchor()
    world.shipment("forged", "baseline_ok")
    r = world.post_ledger("forged", entries, anchor).json()
    assert (r["chain_status"], r["reason"], r["first_bad_index"]) == (
        "rejected",
        "unregistered_key",
        0,
    )
    from edge.chain import Signer as S

    attacker = S.generate()
    # a public key shipped with the ledger is ignored: the attacker's own key does not help
    r2 = world.post_ledger(
        "forged", entries, anchor, public_key_hex=attacker.public_key_bytes.hex()
    ).json()
    assert r2["reason"] == "unregistered_key" and r2["public_key_in_request"].startswith(
        "a public key in the request was ignored"
    )


def test_an_attacker_who_copies_the_registered_key_id_still_fails_the_signature(world, ledgers):
    from edge.chain import Entry, genesis_hash, link_hash

    attacker = OTHER
    previous, forged = genesis_hash(DEVICE), []
    for entry in ledgers["baseline_ok"][1][:30]:
        sig = attacker.sign(entry.record)
        previous = link_hash(previous, entry.record, sig)
        forged.append(
            Entry(entry.seq, entry.record, sig, previous, SIGNER.key_id)
        )  # claims the registered key id
    world.shipment("disguised", "baseline_ok")
    r = world.post_ledger("disguised", forged).json()
    assert (r["chain_status"], r["reason"], r["first_bad_index"]) == (
        "rejected",
        "bad_signature",
        0,
    )


def test_truncation_passes_without_an_anchor_and_is_caught_with_one(world, ledgers):
    entries, anchor = ledgers["baseline_ok"][1], ledgers["baseline_ok"][2]
    world.shipment("cut-a", "baseline_ok")
    assert (
        world.post_ledger("cut-a", entries[:200]).json()["chain_status"] == "verified"
    )  # the Phase 4 limit
    world.shipment("cut-b", "baseline_ok")
    r = world.post_ledger("cut-b", entries[:200], anchor).json()
    assert (r["chain_status"], r["reason"]) == ("rejected", "truncated")


def test_a_later_shorter_or_different_ledger_conflicts_with_the_stored_one(world, ledgers):
    entries = ledgers["baseline_ok"][1]
    world.shipment("grow", "baseline_ok")
    assert world.post_ledger("grow", entries[:100]).json()["chain_status"] == "verified"
    assert (
        world.post_ledger("grow", entries[:150]).json()["chain_status"] == "verified"
    )  # extending is fine
    r = world.post_ledger("grow", entries[:80]).json()
    assert (r["chain_status"], r["reason"]) == ("rejected", "history_conflict")
    assert world.client.get("/shipments/grow").json()["status"] == "quarantined_pending_review"


def test_signed_values_that_differ_from_the_recomputation_are_flagged(world, tmp_path):
    from edge.assessment import TrustAssessor
    from edge.recorded_source import RecordedSource
    from edge.tamper_monitor import TamperMonitor
    from shared.config import load_box_config, load_product_config

    product, box = load_product_config(), load_box_config()
    assessor = TrustAssessor(product, TamperMonitor.from_defaults(product, box))
    ledger = Ledger.create(new_run_id("lying"), tmp_path)
    writer = ChainWriter(DEVICE, SIGNER, ledger)
    source = RecordedSource(RECORDINGS / "reefer_failure.jsonl")
    source.start()
    while (reading := source.read()) is not None:
        assessment, potency, _ = assessor.update(reading)
        record = record_from_pipeline(DEVICE, writer.next_seq, reading, potency, assessment)
        record["potency"] = (
            1_000_000_000  # the device CLAIMS perfect potency (a signed lie about its own result)
        )
        record["trust_level"], record["verdict"] = "trusted", "ok"
        writer.append(record)
    source.close()
    entries = ledger.read_entries()
    ledger.close()
    world.shipment("claims", "reefer_failure")
    r = world.post_ledger("claims", prefix(entries, 20.0)).json()
    assert (
        r["chain_status"] == "verified"
        and r["claims_consistent"] is False
        and "differ from the recomputation" in r["claims_detail"]
    )
    assert world.client.get("/shipments/claims").json()["status"] == "quarantined_pending_review"
    d = world.decide("claims").json()
    assert d["route"] == "needs_human" and any(
        "differ from the backend's recomputation" in x for x in d["reasons"]
    )
    assert d["trust_level"] == "trusted" or d["trust_level"] in (
        "low_confidence",
        "untrusted",
    )  # planned from the recomputed values, not the claim


# ----------------------------------------------------------------- decisions


def test_trusted_recordings_are_auto_approved_where_phase_5_did(world, ledgers):
    sid = world.loaded(ledgers, "baseline_ok", 24.0)
    d = world.decide(sid).json()
    assert (d["chosen_action"], d["route"], d["close_call"]) == ("continue", "auto_approved", False)
    assert (
        len(d["sap_events"]) == 1
        and d["sap_events"][0]["provenance"] == "mock"
        and d["sap_events"][0]["description"] == EVENT_DESCRIPTION
    )
    sid2 = world.loaded(ledgers, "reefer_failure", 20.0)
    d2 = world.decide(sid2).json()
    assert (d2["chosen_action"], d2["route"]) == ("reroute_to_depot", "auto_approved")
    assert "recommendation, not an action" in d2["note"] or "recommendation" in d2["note"].lower()


def test_untrusted_data_never_auto_approve_whatever_the_thresholds(tmp_path, ledgers):
    planner = load_planner_config().model_copy(update={"v_thr": 1e12, "confidence_gap_thr": 1e12})
    w = World(tmp_path, planner_cfg=planner)
    try:
        for name, hour in (("spoof_attempt", 20.0), ("hidden_spoilage", 50.0)):
            sid = w.loaded(ledgers, name, hour)
            d = w.decide(sid).json()
            assert (
                d["route"] == "needs_human" and d["trust_level"] == "untrusted" and d["bound_used"]
            )
            assert d["shipment_status"] == "quarantined_pending_review" and d["sap_events"] == []
            assert d["approval_task"] == d["decision_seq"]
        assert w.store.count_sap_events() == 0
    finally:
        w.close()


def test_a_close_call_goes_to_a_person_even_when_the_three_rules_pass(tmp_path, ledgers):
    w = World(tmp_path, cfg_changes={"close_call_percent": 5000.0})
    try:
        sid = w.loaded(ledgers, "baseline_ok", 24.0)
        d = w.decide(sid).json()
        assert d["close_call"] and d["route"] == "needs_human" and d["sap_events"] == []
        assert any(r.startswith("close call:") for r in d["reasons"]) and not any(
            "all three rules hold" in r for r in d["reasons"]
        )
    finally:
        w.close()


def make_table(cvars):
    results = {
        a: ActionResult(a, 0.0, 0.0, c, c, c, 0.0, 0.99)
        for a, c in zip(ACTIONS, cvars, strict=True)
    }
    best = min(ACTIONS, key=lambda a: results[a].cvar)
    return DecisionTable(0.95, 1, 100, results, best, best)


def test_close_call_is_a_relative_difference_of_the_best_two():
    assert close_call(make_table([1000, 1049, 5000, 9000, 9000]), 5.0)[0] is True
    assert close_call(make_table([1000, 1051, 5000, 9000, 9000]), 5.0)[0] is False
    assert close_call(make_table([1000, 1000, 5000, 9000, 9000]), 5.0)[0] is True
    assert close_call(make_table([0, 0, 5000, 9000, 9000]), 5.0)[0] is True
    assert close_call(make_table([0, 10, 5000, 9000, 9000]), 5.0)[0] is False
    assert close_call(make_table([1000, 1049, 5000, 9000, 9000]), 0.0)[0] is False
    text = close_call(make_table([1000, 1049, 5000, 9000, 9000]), 5.0)[1]
    assert "less than 5 percent" in text


def test_backend_rules_only_make_a_decision_stricter(product, box):
    from planner.core import PlannerInputs
    from planner.governance import build_decision

    cfg = load_planner_config()
    table = make_table([1000, 9000, 9500, 9800, 9900])
    inputs = PlannerInputs(
        shipment_id="x",
        t_s=0.0,
        remaining_h=10.0,
        potency_now=0.99,
        tau_eq_now_h=1.0,
        start_tau_eq_h=1.0,
        start_temp_c=5.0,
        ambient_now_c=20.0,
        bound_used=False,
        trust_level="trusted",
        verdict="ok",
        chain_status="ok",
    )
    base = build_decision(table, inputs, cfg)
    same, flags = apply_backend_rules(base, table, 5.0, False, False)
    assert same == base and flags == {
        "close_call": False,
        "claims_inconsistent": False,
        "key_revoked": False,
    }
    for kwargs in (
        {"claims_inconsistent": True, "key_revoked": False},
        {"claims_inconsistent": False, "key_revoked": True},
    ):
        stricter, _ = apply_backend_rules(base, table, 5.0, **kwargs)
        assert stricter.route == "needs_human" and len(stricter.reasons) >= len(base.reasons)


# ----------------------------------------------------------------- human resolution


def open_task(world, ledgers, name="hidden_spoilage", hour=50.0):
    sid = world.loaded(ledgers, name, hour)
    d = world.decide(sid).json()
    assert d["route"] == "needs_human"
    return sid, d


def test_a_human_resolution_is_a_new_record_and_the_original_is_untouched(world, ledgers):
    sid, d = open_task(world, ledgers)
    task = world.client.get("/approvals").json()["items"][0]
    assert (
        task["task_id"] == d["decision_seq"]
        and task["shipment_id"] == sid
        and task["alternatives"]
        and task["potency_curve"]
        and task["chain_status"] == "ok"
    )
    before = {e.seq: e.record for e in world.store.decision_entries()}
    short = world.client.post(
        f"/approvals/{task['task_id']}/resolve",
        headers=CALLER,
        json={"who": "QA lead", "action": "approve", "reason": "too short"},
    )
    assert short.status_code == 422 and world.client.get("/approvals").json()["items"]  # still open
    no_final = world.client.post(
        f"/approvals/{task['task_id']}/resolve",
        headers=CALLER,
        json={"who": "QA lead", "action": "override", "reason": "hold it for the review"},
    )
    assert no_final.status_code == 422
    same = world.client.post(
        f"/approvals/{task['task_id']}/resolve",
        headers=CALLER,
        json={
            "who": "QA lead",
            "action": "override",
            "final_action": d["chosen_action"],
            "reason": "same as recommended",
        },
    )
    assert same.status_code == 422
    ok = world.client.post(
        f"/approvals/{task['task_id']}/resolve",
        headers=CALLER,
        json={
            "who": "QA lead",
            "action": "override",
            "final_action": "quarantine",
            "reason": "hold it for the review",
        },
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["final_action"] == "quarantine" and body["human_seq"] == d["decision_seq"] + 1
    assert len(body["sap_events"]) == 1 and body["sap_events"][0]["resolution"] == "human_override"
    after = {e.seq: e.record for e in world.store.decision_entries()}
    assert after[d["decision_seq"]] == before[d["decision_seq"]] and len(after) == len(before) + 1
    human = parse_decision_record(after[body["human_seq"]])
    assert (
        human["kind"] == "human_decision"
        and human["refers_to_seq"] == d["decision_seq"]
        and human["who"] == "QA lead"
    )
    assert world.client.get("/approvals").json()["items"] == []
    assert (
        world.client.post(
            f"/approvals/{task['task_id']}/resolve",
            headers=CALLER,
            json={"who": "QA lead", "action": "approve", "reason": "second attempt here"},
        ).status_code
        == 409
    )
    assert (
        world.client.post(
            "/approvals/9999/resolve",
            headers=CALLER,
            json={"who": "QA lead", "action": "approve", "reason": "no such task here"},
        ).status_code
        == 404
    )
    assert world.client.get(f"/shipments/{sid}").json()["status"] == "human_resolved"
    log = world.client.get(f"/shipments/{sid}/decisions").json()
    assert log["decision_log"]["ok"] and [i["kind"] for i in log["items"]] == [
        "decision",
        "human_decision",
    ]


def test_rejecting_and_approving_are_recorded(world, ledgers):
    sid, d = open_task(world, ledgers, "spoof_attempt", 20.0)
    r = world.client.post(
        f"/approvals/{d['decision_seq']}/resolve",
        headers=CALLER,
        json={"who": "QA lead", "action": "reject", "reason": "do not act on this"},
    ).json()
    assert (
        r["final_action"] is None
        and r["sap_events"][0]["action"] is None
        and r["sap_events"][0]["resolution"] == "human_reject"
    )
    sid2 = world.loaded(ledgers, "hidden_spoilage", 50.0, "second")
    d2 = world.decide(sid2).json()
    r2 = world.client.post(
        f"/approvals/{d2['decision_seq']}/resolve",
        headers=CALLER,
        json={"who": "QA lead", "action": "approve", "reason": "agree with the plan"},
    ).json()
    assert (
        r2["final_action"] == d2["chosen_action"]
        and r2["sap_events"][0]["resolution"] == "human_approve"
    )


def test_enterprise_events_are_dispatched_only_on_auto_approval_or_human_resolution(world, ledgers):
    assert world.store.count_sap_events() == 0
    sid = world.loaded(ledgers, "baseline_ok", 24.0)
    world.decide(sid)  # auto-approved
    assert world.store.count_sap_events() == 1
    sid2, d2 = open_task(world, ledgers)  # needs a person: no event
    assert world.store.count_sap_events() == 1
    world.client.post(
        f"/approvals/{d2['decision_seq']}/resolve",
        headers=CALLER,
        json={"who": "QA lead", "action": "approve", "reason": "agree with the plan"},
    )
    events = world.store.sap_events()
    assert len(events) == 2 and {e["adapter_mode"] for e in events} == {"mock"}
    payload = json.loads(events[1]["event_json"])
    assert (
        payload["description"] == "Event dispatched"
        and payload["reference"]["decision_seq"] == d2["decision_seq"]
        and len(payload["reference"]["decision_hash_hex"]) == 64
    )


# ----------------------------------------------------------------- storage


def test_the_storage_module_has_no_update_or_delete_function():
    names = [n for n in dir(Store) if not n.startswith("_")]
    assert not [
        n
        for n in names
        if n.split("_")[0]
        in {"update", "delete", "remove", "set", "replace", "clear", "truncate", "drop", "edit"}
    ]


@pytest.mark.parametrize("table", TABLES)
def test_the_database_refuses_update_and_delete_on_every_table(world, ledgers, table):
    # fill every table first: a trigger only fires for a row that exists
    full = "full"
    world.shipment(full, "baseline_ok")
    world.post_ledger(
        full, ledgers["baseline_ok"][1], ledgers["baseline_ok"][2]
    )  # entries and an anchor
    world.decide(full, remaining_hours=24.0)  # decision entries, anchors, an automatic event
    sid, d = open_task(world, ledgers)  # a decision that needs a person
    world.client.post(
        f"/approvals/{d['decision_seq']}/resolve",
        headers=CALLER,
        json={"who": "QA lead", "action": "approve", "reason": "agree with the plan"},
    )
    world.client.get("/health")
    db = sqlite3.connect(world.store.path)
    assert db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] > 0, table
    for verb in ("UPDATE {t} SET rowid = rowid", "DELETE FROM {t}"):
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            db.execute(verb.format(t=table))
    db.close()


def test_status_changes_are_new_rows_and_history_is_kept(world, ledgers):
    sid, d = open_task(world, ledgers)
    world.client.post(
        f"/approvals/{d['decision_seq']}/resolve",
        headers=CALLER,
        json={"who": "QA lead", "action": "approve", "reason": "agree with the plan"},
    )
    history = world.client.get(f"/shipments/{sid}").json()["status_history"]
    statuses = [h["status"] for h in history]
    assert (
        statuses[0] == "created"
        and "quarantined_pending_review" in statuses
        and statuses[-1] == "human_resolved"
    )
    assert [h["at_ms"] for h in history] == sorted(h["at_ms"] for h in history)


def test_stored_canonical_bytes_contain_no_float(world, ledgers):
    sid, d = open_task(world, ledgers)
    for entry in world.store.decision_entries():
        parse_decision_record(entry.record)  # rejects any float
    for sub in world.store.submissions(sid):
        for entry in world.store.submission_entries(sub["id"]):
            parse_device_record(entry.record)


# ----------------------------------------------------------------- the API surface


def test_the_audit_log_records_every_state_changing_call_including_failures(world, ledgers):
    base = world.client.get("/audit").json()["total"]
    calls = [
        world.client.post(
            "/shipments",
            headers=CALLER,
            json={"shipment_id": "a1", "label": "x", "device_id": DEVICE, "origin": "replay"},
        ),  # ok
        world.client.post(
            "/shipments",
            headers=CALLER,
            json={"shipment_id": "a1", "label": "x", "device_id": DEVICE, "origin": "replay"},
        ),  # 409
        world.client.post(
            "/shipments",
            headers=CALLER,
            json={"shipment_id": "bad id!", "label": "x", "device_id": DEVICE, "origin": "replay"},
        ),  # 422
        world.client.post("/shipments/none/decide", headers=CALLER, json={}),  # 404
        world.client.post("/shipments/a1/decide", headers=CALLER, json={}),  # 409 no ledger
        world.client.post(
            "/shipments/a1/ledger",
            headers=CALLER,
            content="not json",
        ),  # 422
        world.client.post(
            "/approvals/5/resolve",
            headers=CALLER,
            json={"who": "QA lead", "action": "approve", "reason": "no such task here"},
        ),  # 404
    ]
    assert [c.status_code for c in calls] == [201, 409, 422, 404, 409, 422, 404]
    world.client.get("/shipments")  # reads are not audited
    audit = world.client.get("/audit").json()
    assert audit["total"] == base + 7
    rows = audit["items"][base:]
    assert [r["status_code"] for r in rows] == [201, 409, 422, 404, 409, 422, 404]
    assert [r["outcome"] for r in rows] == [
        "ok",
        "refused",
        "refused",
        "refused",
        "refused",
        "refused",
        "refused",
    ]
    assert (
        rows[0]["caller"] == "pytest"
        and rows[0]["shipment_id"] == "a1"
        and rows[0]["method"] == "POST"
        and rows[0]["endpoint"] == "/shipments"
    )
    assert rows[4]["shipment_id"] == "a1" and rows[3]["shipment_id"] == "none"


def test_audit_outcomes_name_rejected_ledgers_and_decisions(world, ledgers):
    entries = ledgers["baseline_ok"][1]
    world.shipment("o1", "baseline_ok")
    world.post_ledger("o1", entries[:50])
    world.post_ledger("o1", entries[:20])  # history conflict
    world.decide("o1", remaining_hours=24.0)
    outcomes = [
        r["outcome"] for r in world.client.get("/audit").json()["items"] if r["shipment_id"] == "o1"
    ]
    assert outcomes == [
        "ok",
        "ok",
        "ledger_rejected",
        "refused",
    ]  # a rejected latest ledger blocks decisions


def test_bad_input_gives_clean_errors_without_stack_traces(world):
    cases = [
        ("post", "/devices/register", {"json": {"device_id": "x"}}),
        (
            "post",
            "/devices/register",
            {"json": {"device_id": "x", "public_key_hex": "zz", "registered_by": "operator"}},
        ),
        (
            "post",
            "/devices/register",
            {
                "json": {
                    "device_id": "x",
                    "public_key_hex": "a" * 64,
                    "registered_by": "op",
                    "extra": 1,
                }
            },
        ),
        (
            "post",
            "/devices/register",
            {"content": "{broken", "headers": {"content-type": "application/json"}},
        ),
        (
            "post",
            "/shipments",
            {"json": {"shipment_id": "s", "label": "l", "device_id": "d", "origin": "mars"}},
        ),
        (
            "post",
            "/shipments",
            {
                "json": {
                    "shipment_id": "s",
                    "label": "l",
                    "device_id": "d",
                    "origin": "live",
                    "scheduled_duration_h": -1,
                }
            },
        ),
        ("post", "/shipments/s/ledger", {"json": {"entries": []}}),
        ("get", "/shipments/s/readings?limit=0", {}),
        ("get", "/shipments/s/readings?limit=100000", {}),
        ("get", "/audit?offset=-1", {}),
        ("get", "/approvals/abc", {}),
        ("post", "/approvals/abc/resolve", {"json": {}}),
    ]
    for method, path, kwargs in cases:
        r = getattr(world.client, method)(path, **kwargs)
        assert r.status_code in (400, 404, 405, 422), (path, r.status_code)
        text = r.text
        assert "Traceback" not in text and 'File "' not in text
        assert r.json().get("error") or r.json().get("detail")
    assert world.client.get("/nothing-here").json()["error"] == "not_found"
    for path in (
        "/shipments/none",
        "/shipments/none/readings",
        "/shipments/none/verify",
        "/shipments/none/decisions",
        "/provenance/none",
    ):
        assert world.client.get(path).status_code == 404
    unexpected = world.client.get("/shipments/s/readings?limit=abc")
    assert unexpected.status_code == 422


def test_an_unexpected_failure_returns_a_plain_500_and_is_audited(world, monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(world.app.state.service, "list_devices", boom)
    r = world.client.get("/devices")
    assert r.status_code == 500 and r.json() == {
        "error": "internal_error",
        "message": "An internal error occurred.",
    }
    assert "secret" not in r.text
    monkeypatch.setattr(world.app.state.service, "register_device", boom)
    r = world.register(OTHER, device="boom-device")
    assert r.status_code == 500 and "secret" not in r.text
    assert world.client.get("/audit").json()["items"][-1]["outcome"] == "error"


def test_paging_of_readings_and_the_audit_log(world, ledgers):
    sid = world.loaded(ledgers, "baseline_ok", 24.0)
    page = world.client.get(f"/shipments/{sid}/readings?offset=10&limit=5").json()
    assert page["total"] == 145 and page["offset"] == 10 and len(page["items"]) == 5
    assert [i["seq"] for i in page["items"]] == [10, 11, 12, 13, 14]
    first = page["items"][0]
    assert (
        first["t_h"] == pytest.approx(10 * 600 / 3600)
        and first["source"] == "sim"
        and "device_reported" in first
    )
    last = world.client.get(f"/shipments/{sid}/readings?offset=140&limit=100").json()
    assert len(last["items"]) == 5
    assert world.client.get(f"/shipments/{sid}/readings?offset=1000").json()["items"] == []
    audit = world.client.get("/audit?limit=2").json()
    assert len(audit["items"]) == 2 and audit["total"] >= 3


def test_provenance_health_and_listing(world, ledgers):
    health = world.client.get("/health").json()
    assert (
        health["status"] == "ok"
        and health["authentication"] == "none"
        and health["sap_adapter_mode"] == "mock"
        and health["bound_host"] == "127.0.0.1"
    )
    world.shipment("p1", "baseline_ok")
    before = world.client.get("/provenance/p1").json()
    assert (
        before["source"] is None and before["from_replay"] is True and before["simulated"] is True
    )
    world.post_ledger("p1", prefix(ledgers["baseline_ok"][1], 12.0))
    after = world.client.get("/provenance/p1").json()
    assert (
        after["source"] == "sim"
        and after["sap_adapter_mode"] == "mock"
        and after["scenario_id"] == "baseline_ok"
        and after["software_version"].startswith("backend-")
    )
    assert [s["shipment_id"] for s in world.client.get("/shipments").json()["items"]] == ["p1"]
    assert "Connected" not in json.dumps(after) and "SAP" not in after["note"]


def test_replay_and_live_shipments_carry_their_origin(world):
    world.client.post(
        "/shipments",
        headers=CALLER,
        json={"shipment_id": "live-1", "label": "bench", "device_id": DEVICE, "origin": "live"},
    )
    assert world.client.get("/provenance/live-1").json()["from_replay"] is False


# ----------------------------------------------------------------- the enterprise adapter


def test_the_default_adapter_is_the_mock_and_is_chosen_by_configuration():
    cfg = load_backend_config()
    assert cfg.sap_adapter == "mock"
    adapter = make_adapter("mock", lambda e, a: None, lambda: 0)
    assert isinstance(adapter, MockSapAdapter) and adapter.mode == "mock"
    assert isinstance(make_adapter("sandbox", lambda e, a: None, lambda: 0), SandboxSapAdapter)
    with pytest.raises(ValueError):
        make_adapter("real", lambda e, a: None, lambda: 0)
    with pytest.raises(ValueError):
        BackendConfig.model_validate({**cfg.model_dump(), "sap_adapter": "real"})


def test_the_mock_marks_itself_and_the_sandbox_cannot_send_anything(tmp_path):
    from backend.sap import DecisionReference

    seen = []
    adapter = make_adapter("mock", lambda e, a: seen.append((e, a)), lambda: len(seen))
    event = SapEvent(
        shipment_id="s",
        action="continue",
        route="auto_approved",
        resolution="auto_approved",
        reference=DecisionReference(decision_seq=0, decision_hash_hex="0" * 64),
    )
    ack = adapter.dispatch(event)
    assert (
        ack.provenance == "mock"
        and ack.ack_id.startswith("mock-")
        and seen
        and adapter.lookup_acknowledgement(ack.ack_id) == ack
    )
    assert adapter.lookup_acknowledgement("nope") is None
    sandbox = SandboxSapAdapter()
    for call in (lambda: sandbox.dispatch(event), lambda: sandbox.lookup_acknowledgement("x")):
        with pytest.raises(NotImplementedError, match="not implemented"):
            call()


def test_the_sandbox_mode_answers_501_through_the_api(tmp_path, ledgers):
    w = World(tmp_path, cfg_changes={"sap_adapter": "sandbox"})
    try:
        sid = w.loaded(ledgers, "baseline_ok", 24.0)
        r = w.decide(sid)
        assert r.status_code == 501 and r.json()["error"] == "adapter_not_implemented"
    finally:
        w.close()


def test_the_adapter_source_contains_no_address_or_credential_and_no_false_wording():
    source = (ROOT / "backend" / "sap.py").read_text(encoding="utf-8").lower()
    for forbidden in (
        "http",
        "://",
        "api_key",
        "password",
        "token",
        "bearer",
        "secret",
        "localhost",
    ):
        assert forbidden not in source, forbidden
    for path in (ROOT / "backend").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for phrase in ("Connected to SAP", "connected to SAP", "unhackable", "tamper-proof"):
            assert phrase not in text, (path.name, phrase)


# ----------------------------------------------------------------- configuration, binding, repository hygiene


def test_the_server_binds_to_localhost_by_default_and_the_config_is_validated(tmp_path):
    import yaml

    cfg = load_backend_config()
    assert cfg.host == "127.0.0.1"
    parser = backend_cli.build_parser()
    args = parser.parse_args(["serve"])
    assert args.host is None  # no other default: the settings file (127.0.0.1) is used
    base = yaml.safe_load((ROOT / "config" / "backend.yaml").read_text(encoding="utf-8"))
    for change in (
        {"port": 0},
        {"port": 70000},
        {"sap_adapter": "x"},
        {"close_call_percent": -1},
        {"unknown": 1},
        {"default_page_size": 5000},
        {"database": ""},
    ):
        bad = tmp_path / "bad.yaml"
        bad.write_text(yaml.safe_dump({**base, **change}), encoding="utf-8")
        with pytest.raises(ConfigError):
            load_backend_config(bad)
    text = (ROOT / "config" / "backend.yaml").read_text(encoding="utf-8")
    assert "NO authentication" in text and "illustrative placeholder" in text


def test_unchanged_files_and_no_key_in_the_repository():
    expected = json.loads((ROOT / "shared" / "golden_sha256.json").read_text("utf-8"))["sha256"]
    for relative, digest in expected.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest().upper() == digest, (
            relative
        )
    import subprocess

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "make_chain_vectors.py"), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    marker = ("-----" + "BEGIN").encode()
    skip = {
        ".git",
        ".venv",
        "node_modules",
        "dist",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        "runs",
    }
    for path in ROOT.rglob("*"):
        if any(part in skip for part in path.relative_to(ROOT).parts) or not path.is_file():
            continue
        assert path.suffix not in {".key", ".pem", ".p8", ".pk8", ".priv"}, path
        if path.stat().st_size < 3_000_000:
            assert marker not in path.read_bytes(), path


# ----------------------------------------------------------------- replay and the command line


def test_replay_runs_end_to_end_for_three_recordings(tmp_path):
    out = io.StringIO()
    code = backend_cli.main(
        [
            "replay",
            "--recording",
            str(RECORDINGS / "baseline_ok.jsonl"),
            "--at-hour",
            "24",
            "--key-dir",
            str(tmp_path / "k"),
            "--db",
            str(tmp_path / "a.sqlite"),
        ],
        out,
    )
    text = out.getvalue()
    assert (
        code == 0
        and "chain status      verified" in text
        and "route             auto_approved" in text
        and "events dispatched 1 [mock-000001 mock]" in text
    )
    out = io.StringIO()
    backend_cli.main(
        [
            "replay",
            "--recording",
            str(RECORDINGS / "hidden_spoilage.jsonl"),
            "--at-hour",
            "50",
            "--key-dir",
            str(tmp_path / "k"),
            "--db",
            str(tmp_path / "b.sqlite"),
        ],
        out,
    )
    assert (
        "needs_human" in out.getvalue()
        and "trust level       untrusted" in out.getvalue()
        and "events dispatched 0" in out.getvalue()
    )
    out = io.StringIO()
    backend_cli.main(
        [
            "replay",
            "--recording",
            str(RECORDINGS / "reefer_failure.jsonl"),
            "--at-hour",
            "20",
            "--key-dir",
            str(tmp_path / "k"),
            "--db",
            str(tmp_path / "c.sqlite"),
        ],
        out,
    )
    assert "reroute_to_depot" in out.getvalue() and "auto_approved" in out.getvalue()
    assert out.getvalue().rstrip().endswith("Not real-world evidence.")


@pytest.mark.parametrize("action", ["edit", "delete", "reorder", "resign", "truncate"])
def test_replay_with_each_tamper_option_is_rejected_and_quarantined(tmp_path, action):
    out = io.StringIO()
    code = backend_cli.main(
        [
            "replay",
            "--recording",
            str(RECORDINGS / "baseline_ok.jsonl"),
            "--tamper",
            action,
            "--key-dir",
            str(tmp_path / "k"),
            "--db",
            str(tmp_path / f"{action}.sqlite"),
        ],
        out,
    )
    text = out.getvalue()
    assert code == 0
    if action == "truncate":
        assert "chain status      rejected (truncated" in text
    else:
        assert "chain status      rejected" in text
    assert (
        "quarantined_pending_review" in text and "REFUSED" in text and "events dispatched 0" in text
    )


def test_replay_all_and_the_export_command(tmp_path):
    out = io.StringIO()
    assert (
        backend_cli.main(
            [
                "replay",
                "--all",
                "--key-dir",
                str(tmp_path / "k"),
                "--db",
                str(tmp_path / "all.sqlite"),
            ],
            out,
        )
        == 0
    )
    text = out.getvalue()
    assert (
        text.count("Recording ") == 6
        and text.count("auto_approved") == 4
        and text.count("needs_human") == 2
    )
    assert "audit rows" in text and "no authentication" in text
    # export a ledger body and post it by hand
    from shared.config import load_box_config, load_product_config

    summary = run_recording(
        RECORDINGS / "baseline_ok.jsonl",
        load_product_config(),
        load_box_config(),
        SIGNER,
        DEVICE,
        tmp_path / "led",
        "export",
    )
    body_path = tmp_path / "body.json"
    assert (
        backend_cli.main(
            ["export-ledger", "--ledger", str(summary.ledger_path), "--out", str(body_path)],
            io.StringIO(),
        )
        == 0
    )
    w = World(tmp_path / "w")
    try:
        w.shipment("exp", "baseline_ok")
        r = w.client.post(
            "/shipments/exp/ledger",
            headers={**CALLER, "content-type": "application/json"},
            content=body_path.read_text(encoding="utf-8"),
        )
        assert (
            r.status_code == 200
            and r.json()["chain_status"] == "verified"
            and r.json()["anchor_checked"]
        )
    finally:
        w.close()


def test_reefer_failure_decision_is_stable_and_logged_in_one_verifiable_chain(world, ledgers):
    world.loaded(ledgers, "reefer_failure", 20.0)
    world.loaded(ledgers, "baseline_ok", 24.0)
    a, b = world.decide("reefer_failure").json(), world.decide("baseline_ok").json()
    assert b["decision_seq"] == a["decision_seq"] + 1
    assert world.decide("reefer_failure", seed=7).status_code == 201
    log = world.client.get("/shipments/reefer_failure/decisions").json()
    assert log["decision_log"]["ok"] and len(log["items"]) == 2
    assert world.decide("reefer_failure", remaining_hours=-1).status_code == 422
