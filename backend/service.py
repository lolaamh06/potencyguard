"""Backend logic: key registry, ledger ingest, decisions, approvals, enterprise events (Phase 6).

No authentication in this phase (decision 0010, section 4): caller names and QA identities are plain
strings. Signing protects records after signing and does not stop a lie at the sensor (A18), so the
backend recomputes the physics checks from the signed readings and plans from the recomputed values.
All money values, probabilities and thresholds are illustrative placeholders. Simulation only.
The planner recommends; a person (QA) decides what happens next.
"""
# ruff: noqa: E501  (long literal lines)

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

from backend.config import BackendConfig
from backend.sap import (
    DecisionReference,
    SapAcknowledgement,
    SapAdapter,
    SapEvent,
    make_adapter,
)
from backend.storage import DecisionStoreLedger, Store
from edge.assessment import TrustAssessor
from edge.chain import Anchor, Entry, Signer, verify_chain
from edge.chain.canonical import parse_canonical as parse_device_record
from edge.chain.crypto import key_id_of
from edge.sensor_reading import SensorReading
from edge.tamper_monitor import TamperMonitor
from planner.config import PlannerConfig
from planner.core import DecisionTable, plan
from planner.governance import (
    AUTO,
    HUMAN,
    QUARANTINED,
    DecisionRecord,
    build_decision,
    build_task,
    record_human_decision,
)
from planner.pipeline import build_inputs
from planner.records import (
    DecisionLog,
    parse_canonical,
    verify_decision_log,
)
from shared.config import BoxConfig, ProductConfig

SOFTWARE_VERSION = "backend-0.6.0 (Phase 6)"
UNITS = {"temp": 10**4, "rh": 10**4, "shock": 10**4, "ambient_c": 10**4, "cooling_duty": 10**4}

# shipment statuses (every change is a new row in the status history)
CREATED, ACTIVE, QUARANTINE, HUMAN_RESOLVED = (
    "created", "active", QUARANTINED, "human_resolved"
)  # fmt: skip

# extra reasons a ledger can be rejected for (besides those of verify_chain)
UNREGISTERED_KEY, KEY_REVOKED, MIXED_KEYS = "unregistered_key", "key_revoked", "mixed_keys"
HISTORY_CONFLICT, UNUSABLE_READINGS = "history_conflict", "unusable_readings"


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


@dataclass(frozen=True)
class IngestResult:
    submission_id: int
    result: str  # verified or rejected
    reason: str
    first_bad_index: int | None
    detail: str
    entry_count: int
    anchor_present: bool
    anchor_checked: bool
    claims_consistent: bool | None
    claims_detail: str
    public_key_in_request: str


def _hex(value: str, name: str) -> bytes:
    try:
        return bytes.fromhex(value)
    except ValueError as exc:
        raise ApiError(422, "invalid_request", f"{name} is not valid hex") from exc


class Service:
    def __init__(
        self,
        store: Store,
        cfg: BackendConfig,
        planner_cfg: PlannerConfig,
        product: ProductConfig,
        box: BoxConfig,
        planner_signer: Signer,
    ) -> None:
        self.store, self.cfg, self.planner_cfg = store, cfg, planner_cfg
        self.product, self.box, self.signer = product, box, planner_signer
        self.adapter: SapAdapter = make_adapter(
            cfg.sap_adapter, self._log_event, store.count_sap_events
        )
        self._pending_event_context: dict = {}

    # ------------------------------------------------------------------ devices

    def register_device(self, device_id: str, public_key_hex: str, by: str, note: str) -> dict:
        public_key = _hex(public_key_hex, "public_key_hex")
        key_id = key_id_of(public_key)
        with self.store.lock:
            state = self.store.key_state(device_id, key_id)
            if state is not None:
                raise ApiError(
                    409, "already_registered", "this key is already registered for the device"
                )
            for row in self.store.key_rows():
                if row["key_id"] == key_id and row["device_id"] != device_id:
                    raise ApiError(409, "key_in_use", "this key is registered for another device")
            self.store.add_device_key(device_id, key_id, public_key, "active", by, note)
        return {"device_id": device_id, "key_id": key_id, "status": "active"}

    def revoke_key(self, device_id: str, key_id: str, by: str, reason: str) -> dict:
        with self.store.lock:
            state = self.store.key_state(device_id, key_id)
            if state is None:
                raise ApiError(404, "unknown_key", "no such registered key for this device")
            if state["status"] == "revoked":
                raise ApiError(409, "already_revoked", "this key is already revoked")
            self.store.add_device_key(device_id, key_id, state["public_key"], "revoked", by, reason)
        return {"device_id": device_id, "key_id": key_id, "status": "revoked"}

    def list_devices(self) -> list[dict]:
        seen: dict[tuple[str, str], dict] = {}
        for row in self.store.key_rows():
            key = (row["device_id"], row["key_id"])
            entry = seen.setdefault(
                key,
                {
                    "device_id": row["device_id"],
                    "key_id": row["key_id"],
                    "public_key_hex": bytes(row["public_key"]).hex(),
                    "registered_ms": row["at_ms"],
                    "registered_by": row["by_whom"],
                    "revoked_ms": None,
                    "status": "active",
                },
            )
            if row["status"] == "revoked":
                entry["status"], entry["revoked_ms"] = "revoked", row["at_ms"]
        return list(seen.values())

    # ------------------------------------------------------------------ shipments

    def create_shipment(
        self, shipment_id: str, label: str, device_id: str, origin: str, duration_h: float | None
    ) -> dict:
        with self.store.lock:
            if self.store.get_shipment(shipment_id) is not None:
                raise ApiError(409, "already_exists", "a shipment with this id already exists")
            self.store.add_shipment(shipment_id, label, device_id, origin, duration_h)
            self.store.add_status(shipment_id, CREATED, "shipment created")
        return self.shipment_view(shipment_id)

    def _shipment(self, shipment_id: str):
        row = self.store.get_shipment(shipment_id)
        if row is None:
            raise ApiError(404, "unknown_shipment", "no such shipment")
        return row

    def shipment_view(self, shipment_id: str) -> dict:
        s = self._shipment(shipment_id)
        latest = self.store.latest_submission(shipment_id)
        chain = {"status": "no_ledger"}
        recomputed = None
        if latest is not None:
            chain = {
                "status": latest["result"],
                "reason": latest["reason"],
                "first_bad_index": latest["first_bad_index"],
                "detail": latest["detail"],
                "entries": latest["entry_count"],
                "anchor_checked": bool(latest["anchor_checked"]),
                "submission_id": latest["id"],
            }
            if latest["result"] == "verified":
                recomputed = {
                    "t_h": latest["last_t_ms"] / 3_600_000,
                    "potency": latest["potency_e9"] / 1e9,
                    "tau_eq_h": latest["tau_eq_e6"] / 1e6,
                    "trust_level": latest["trust_level"],
                    "verdict": latest["verdict"],
                    "claims_consistent": bool(latest["claims_consistent"]),
                    "note": "recomputed by the backend from the verified readings",
                }
        decisions = [d for d in self.store.decision_index(shipment_id) if d["kind"] == "decision"]
        latest_decision = None
        if decisions:
            d = decisions[-1]
            latest_decision = {
                "decision_seq": d["seq"],
                "chosen_action": d["chosen_action"],
                "route": d["route"],
                "close_call": bool(d["close_call"]),
                "shipment_status": d["shipment_status"],
            }
        return {
            "shipment_id": s["id"],
            "label": s["label"],
            "device_id": s["device_id"],
            "origin": s["origin"],
            "scheduled_duration_h": s["scheduled_duration_h"],
            "created_ms": s["created_ms"],
            "status": self.store.current_status(shipment_id),
            "chain": chain,
            "latest": recomputed,
            "latest_decision": latest_decision,
            "status_history": [dict(r) for r in self.store.status_history(shipment_id)],
        }

    def list_shipments(self) -> list[dict]:
        return [
            {"shipment_id": s["id"], "label": s["label"], "device_id": s["device_id"],
             "origin": s["origin"], "status": self.store.current_status(s["id"])}
            for s in self.store.list_shipments()
        ]  # fmt: skip

    # ------------------------------------------------------------------ ingest

    def ingest(
        self,
        shipment_id: str,
        entries: list[Entry],
        anchor: Anchor | None,
        ignored_public_key: bool,
    ) -> IngestResult:
        with self.store.lock:
            shipment = self._shipment(shipment_id)
            device_id = shipment["device_id"]
            note = (
                "a public key in the request was ignored" if ignored_public_key else "none supplied"
            )
            key_id = entries[0].key_id

            def reject(reason: str, detail: str, index: int | None) -> IngestResult:
                return self._store_submission(
                    shipment_id, device_id, key_id, entries, anchor, "rejected", reason, detail,
                    index, False, None, "", note,
                )  # fmt: skip

            if any(e.key_id != key_id for e in entries):
                return reject(MIXED_KEYS, "entries are signed with more than one key id", None)
            state = self.store.key_state(device_id, key_id)
            if state is None:
                return reject(
                    UNREGISTERED_KEY, f"key {key_id} is not registered for this device", 0
                )
            if state["status"] == "revoked":
                return reject(
                    KEY_REVOKED,
                    "the key was revoked before this ledger was received (the device clock is not "
                    "trusted; the backend's own receipt time is used)",
                    0,
                )
            result = verify_chain(entries, state["public_key"], anchor, device_id)
            if not result.ok:
                return reject(result.reason, result.detail, result.index)
            previous = self.store.latest_verified_submission(shipment_id)
            if previous is not None:
                old = self.store.submission_entries(previous["id"])
                if len(entries) < len(old):
                    return reject(
                        HISTORY_CONFLICT,
                        f"{len(entries)} entries but {len(old)} were already stored and verified",
                        len(entries),
                    )
                for i, e in enumerate(old):
                    if entries[i].hash != e.hash:
                        return reject(HISTORY_CONFLICT, "differs from the stored ledger", i)
            try:
                summary = recompute(entries, self.product, self.box)
            except ValueError as exc:
                return reject(UNUSABLE_READINGS, str(exc), None)
            out = self._store_submission(
                shipment_id, device_id, key_id, entries, anchor, "verified", "ok", result.detail,
                None, result.anchor_checked, summary, "", note,
            )  # fmt: skip
            current = self.store.current_status(shipment_id)
            if not summary["claims_consistent"]:
                self.store.add_status(
                    shipment_id,
                    QUARANTINE,
                    "signed values differ from the recomputation: " + summary["claims_detail"],
                )
            elif current == CREATED:
                self.store.add_status(shipment_id, ACTIVE, "verified ledger ingested")
            return out

    def _store_submission(
        self, shipment_id, device_id, key_id, entries, anchor, result, reason, detail, index,
        anchor_checked, summary, _unused, note,
    ) -> IngestResult:  # fmt: skip
        values = {
            "shipment_id": shipment_id, "device_id": device_id, "key_id": key_id,
            "submitted_ms": self.store.clock(), "entry_count": len(entries), "result": result,
            "first_bad_index": index, "reason": reason, "detail": detail[:500],
            "anchor_present": int(anchor is not None), "anchor_checked": int(bool(anchor_checked)),
            "claims_detail": "" if summary is None else summary["claims_detail"],
        }  # fmt: skip
        if summary is not None:
            values.update(
                last_t_ms=summary["last_t_ms"], potency_e9=summary["potency_e9"],
                tau_eq_e6=summary["tau_eq_e6"], trust_level=summary["trust_level"],
                verdict=summary["verdict"], claims_consistent=int(summary["claims_consistent"]),
            )  # fmt: skip
        sid = self.store.add_submission(values, entries, anchor)
        if result == "rejected":
            self.store.add_status(
                shipment_id,
                QUARANTINE,
                f"ledger rejected ({reason}"
                + ("" if index is None else f" at entry {index}")
                + ")",
            )
        return IngestResult(
            sid, result, reason, index, detail[:500], len(entries), anchor is not None,
            bool(anchor_checked), None if summary is None else summary["claims_consistent"],
            "" if summary is None else summary["claims_detail"], note,
        )  # fmt: skip

    def verify_now(self, shipment_id: str) -> dict:
        shipment = self._shipment(shipment_id)
        latest = self.store.latest_submission(shipment_id)
        if latest is None:
            raise ApiError(409, "no_ledger", "no ledger has been ingested for this shipment")
        entries = self.store.submission_entries(latest["id"])
        state = self.store.key_state(shipment["device_id"], latest["key_id"])
        if state is None:
            return {
                "ok": False,
                "reason": UNREGISTERED_KEY,
                "index": 0,
                "detail": "key is not registered",
                "key_status": "unknown",
            }
        anchor = self.store.submission_anchor(latest["id"])
        result = verify_chain(entries, state["public_key"], anchor, shipment["device_id"])
        return {
            "ok": result.ok, "reason": result.reason, "index": result.index,
            "detail": result.detail, "entries_checked": result.entries_checked,
            "anchor_checked": result.anchor_checked, "key_status": state["status"],
            "key_revoked_ms": state["revoked_ms"],
            "stored_result": latest["result"],
            "note": (
                "the signing key has since been revoked: this data were stored before the revocation, "
                "and the backend cannot tell whether they were signed before any compromise"
                if state["status"] == "revoked" else ""
            ),
        }  # fmt: skip

    def readings_page(self, shipment_id: str, offset: int, limit: int) -> dict:
        self._shipment(shipment_id)
        sub = self.store.latest_verified_submission(shipment_id)
        if sub is None:
            raise ApiError(409, "no_verified_ledger", "no verified ledger for this shipment")
        entries = self.store.submission_entries(sub["id"])
        items = []
        for e in entries[offset : offset + limit]:
            r = parse_device_record(e.record)
            items.append(
                {
                    "seq": r["seq"], "t_h": r["t_ms"] / 3_600_000, "source": r["source"],
                    "temp_c": r["temp"] / UNITS["temp"], "rh_pct": r["rh"] / UNITS["rh"],
                    "shock_g": r["shock"] / UNITS["shock"],
                    "ambient_c": None if r["ambient_c"] is None else r["ambient_c"] / UNITS["ambient_c"],
                    "cooling_duty": None if r["cooling_duty"] is None else r["cooling_duty"] / UNITS["cooling_duty"],
                    "device_reported": {
                        "potency": r["potency"] / 1e9, "verdict": r["verdict"],
                        "trust_level": r["trust_level"], "tau_eq_h": r["tau_eq_h"] / 1e6,
                    },
                }
            )  # fmt: skip
        return {"total": len(entries), "offset": offset, "limit": limit, "items": items}

    # ------------------------------------------------------------------ decide

    def decide(self, shipment_id: str, remaining_hours: float | None, seed: int | None) -> dict:
        with self.store.lock:
            shipment = self._shipment(shipment_id)
            latest = self.store.latest_submission(shipment_id)
            if latest is None:
                raise ApiError(
                    409, "no_ledger", "no ledger has been ingested: nothing to decide on"
                )
            if latest["result"] != "verified":
                raise ApiError(
                    409, "ledger_rejected",
                    f"the latest ledger was rejected ({latest['reason']}): it is excluded from decisions",
                )  # fmt: skip
            entries = self.store.submission_entries(latest["id"])
            last_h = latest["last_t_ms"] / 3_600_000
            remaining = remaining_hours
            if remaining is None and shipment["scheduled_duration_h"] is not None:
                remaining = shipment["scheduled_duration_h"] - last_h
            if remaining is None or remaining <= 0:
                raise ApiError(
                    422,
                    "missing_schedule",
                    "give remaining_hours (>0) or create the shipment with a scheduled duration longer than the data so far",
                )
            cfg = (
                self.planner_cfg
                if seed is None
                else self.planner_cfg.model_copy(update={"seed": seed})
            )
            built = _inputs_from_entries(
                entries, self.product, self.box, remaining, shipment_id, last_h
            )
            inputs = built.inputs.model_copy(update={"chain_status": "ok"})
            table = plan(inputs, cfg, self.product, built.twin, built.setpoint_c)
            base = build_decision(table, inputs, cfg)
            state = self.store.key_state(shipment["device_id"], latest["key_id"])
            decision, flags = apply_backend_rules(
                base, table, self.cfg.close_call_percent,
                claims_inconsistent=not bool(latest["claims_consistent"]),
                key_revoked=bool(state and state["status"] == "revoked"),
            )  # fmt: skip
            log = DecisionLog(cfg.planner_id, self.signer, DecisionStoreLedger(self.store))
            seq = log.next_seq
            entry = log.append_decision(decision)
            log.anchor()
            self.store.add_decision_index(
                {"seq": seq, "shipment_id": shipment_id, "submission_id": latest["id"], "kind": "decision",
                 "chosen_action": decision.chosen_action, "route": decision.route,
                 "close_call": int(flags["close_call"]), "shipment_status": decision.shipment_status}
            )  # fmt: skip
            if (
                decision.shipment_status == QUARANTINED
                and self.store.current_status(shipment_id) != QUARANTINE
            ):
                self.store.add_status(
                    shipment_id,
                    QUARANTINE,
                    "the decision found the data not trusted: " + decision.reasons[0][:200],
                )
            events: list[dict] = []
            task_id = None
            if decision.route == AUTO:
                events.append(
                    self._dispatch(
                        shipment_id, decision.chosen_action, "auto_approved", seq, entry.hash, None
                    )
                )
            else:
                task = build_task(decision, built.potency_curve, seq)
                assert task is not None
                self.store.add_task(seq, shipment_id, task.model_dump_json())
                task_id = seq
            return {
                "decision_seq": seq, "shipment_id": shipment_id, "chosen_action": decision.chosen_action,
                "expected_loss_optimal_action": decision.expected_optimal_action,
                "disagree": decision.disagree, "route": decision.route,
                "close_call": flags["close_call"], "shipment_status": decision.shipment_status,
                "reasons": list(decision.reasons), "explanation": decision.explanation,
                "table": [row.model_dump() for row in decision.table],
                "trust_level": inputs.trust_level, "verdict": inputs.verdict,
                "bound_used": inputs.bound_used, "approval_task": task_id, "sap_events": events,
                "note": "A recommendation, not an action: final authority stays with QA.",
            }  # fmt: skip

    def decisions_view(self, shipment_id: str) -> dict:
        self._shipment(shipment_id)
        entries = self.store.decision_entries()
        by_seq = {e.seq: e for e in entries}
        out = []
        for row in self.store.decision_index(shipment_id):
            record = parse_canonical(by_seq[row["seq"]].record)
            item = {"seq": row["seq"], "kind": row["kind"], "at_ms": row["at_ms"], "route": row["route"],
                    "chosen_action": row["chosen_action"], "close_call": bool(row["close_call"]),
                    "shipment_status": row["shipment_status"], "refers_to_seq": row["refers_to_seq"]}  # fmt: skip
            if row["kind"] == "decision":
                item["reasons"] = record["reasons"].split(" | ")
                item["explanation"] = record["explanation"]
                item["seed"] = record["seed"]
            else:
                item.update(who=record["who"], human_action=record["human_action"],
                            final_action=record["final_action"], reason=record["reason"])  # fmt: skip
            out.append(item)
        verified = verify_decision_log(
            entries,
            self.signer.public_key_bytes,
            self.store.latest_decision_anchor(),
            self.planner_cfg.planner_id,
        )
        return {
            "items": out,
            "decision_log": {
                "ok": verified.ok,
                "text": str(verified),
                "signer_key_id": self.signer.key_id,
            },
        }

    # ------------------------------------------------------------------ approvals

    def open_approvals(self) -> list[dict]:
        out = []
        for row in self.store.open_tasks():
            task = json.loads(row["task_json"])
            task["task_id"] = row["task_id"]
            task["created_ms"] = row["created_ms"]
            out.append(task)
        return out

    def resolve(
        self, task_id: int, who: str, action: str, final_action: str | None, reason: str
    ) -> dict:
        with self.store.lock:
            task = self.store.get_task(task_id)
            if task is None:
                raise ApiError(404, "unknown_task", "no such approval task")
            if self.store.get_resolution(task_id) is not None:
                raise ApiError(409, "already_resolved", "this task was already resolved")
            entries = {e.seq: e for e in self.store.decision_entries()}
            decision_entry = entries[task_id]
            record = parse_canonical(decision_entry.record)
            try:
                human = record_human_decision(
                    record["shipment_id"], record["chosen_action"], task_id, who, action, reason,
                    final_action, _now(self.store),
                )  # fmt: skip
            except ValueError as exc:
                raise ApiError(422, "invalid_request", _first_line(exc)) from exc
            log = DecisionLog(
                self.planner_cfg.planner_id, self.signer, DecisionStoreLedger(self.store)
            )
            human_entry = log.append_human(human)
            log.anchor()
            shipment_id = record["shipment_id"]
            self.store.add_decision_index(
                {"seq": human_entry.seq, "shipment_id": shipment_id, "submission_id": 0, "kind": "human_decision",
                 "chosen_action": human.final_action, "route": "human_resolved", "close_call": 0,
                 "shipment_status": None, "refers_to_seq": task_id}
            )  # fmt: skip
            self.store.add_resolution(
                {"task_id": task_id, "shipment_id": shipment_id, "who": human.who, "human_action": action,
                 "final_action": human.final_action, "reason": human.reason, "human_seq": human_entry.seq}
            )  # fmt: skip
            self.store.add_status(shipment_id, HUMAN_RESOLVED, f"{action} recorded by {human.who}")
            event = self._dispatch(
                shipment_id,
                human.final_action,
                f"human_{action}",
                task_id,
                decision_entry.hash,
                human_entry.seq,
            )
            return {
                "task_id": task_id, "shipment_id": shipment_id, "human_action": action,
                "final_action": human.final_action, "human_seq": human_entry.seq,
                "sap_events": [event], "note": "recorded as a new entry; the original decision is unchanged",
            }  # fmt: skip

    # ------------------------------------------------------------------ enterprise events

    def _dispatch(
        self, shipment_id, action, resolution, decision_seq, decision_hash, human_seq
    ) -> dict:
        event = SapEvent(
            shipment_id=shipment_id, action=action,
            route="auto_approved" if resolution == "auto_approved" else "human_resolved",
            resolution=resolution,
            reference=DecisionReference(decision_seq=decision_seq, decision_hash_hex=decision_hash.hex(), human_seq=human_seq),
        )  # fmt: skip
        self._pending_event_context = {
            "shipment_id": shipment_id,
            "decision_seq": decision_seq,
            "human_seq": human_seq,
            "resolution": resolution,
        }
        try:
            ack = self.adapter.dispatch(event)
        except NotImplementedError as exc:
            raise ApiError(501, "adapter_not_implemented", str(exc)) from exc
        return {
            "ack_id": ack.ack_id,
            "provenance": ack.provenance,
            "description": event.description,
            "action": action,
            "resolution": resolution,
        }

    def _log_event(self, event: SapEvent, ack: SapAcknowledgement) -> None:
        ctx = self._pending_event_context
        self.store.add_sap_event(
            {"shipment_id": event.shipment_id, "decision_seq": ctx["decision_seq"], "human_seq": ctx["human_seq"],
             "resolution": ctx["resolution"], "event_json": event.model_dump_json(), "adapter_mode": self.adapter.mode,
             "ack_id": ack.ack_id, "ack_json": ack.model_dump_json()}
        )  # fmt: skip

    # ------------------------------------------------------------------ provenance and audit

    def provenance(self, shipment_id: str) -> dict:
        s = self._shipment(shipment_id)
        sub = self.store.latest_verified_submission(shipment_id)
        source = None
        if sub is not None:
            source = parse_device_record(self.store.submission_entries(sub["id"])[0].record)[
                "source"
            ]
        return {
            "shipment_id": shipment_id, "source": source, "scenario_id": s["label"],
            "from_replay": s["origin"] == "replay", "origin": s["origin"],
            "sap_adapter_mode": self.adapter.mode, "software_version": SOFTWARE_VERSION,
            "device_id": s["device_id"], "signing_key_id": None if sub is None else sub["key_id"],
            "simulated": True,
            "note": "Simulation on a synthetic box. Signing protects records after signing; it does not stop a false sensor value.",
        }  # fmt: skip

    def audit_page(self, offset: int, limit: int) -> dict:
        total, rows = self.store.audit_page(offset, limit)
        return {"total": total, "offset": offset, "limit": limit, "items": [dict(r) for r in rows]}


# ---------------------------------------------------------------------- helpers


def _now(store: Store):
    from datetime import UTC, datetime

    return datetime.fromtimestamp(store.clock() / 1000.0, tz=UTC)


def _first_line(exc: Exception) -> str:
    return str(exc).splitlines()[0][:300]


def readings_from_entries(entries: list[Entry]) -> list[tuple[dict, SensorReading]]:
    out = []
    for e in entries:
        r = parse_device_record(e.record)
        try:
            reading = SensorReading(
                t_s=r["t_ms"] / 1000.0, temp_c=r["temp"] / 1e4, rh_pct=r["rh"] / 1e4,
                shock_g=r["shock"] / 1e4, source=r["source"],
                ambient_c=None if r["ambient_c"] is None else r["ambient_c"] / 1e4,
                cooling_duty=None if r["cooling_duty"] is None else r["cooling_duty"] / 1e4,
            )  # fmt: skip
        except ValueError as exc:
            raise ValueError(
                f"entry {r['seq']} holds a reading outside the allowed ranges"
            ) from exc
        out.append((r, reading))
    return out


def recompute(entries: list[Entry], product: ProductConfig, box: BoxConfig) -> dict:
    """Re-run the existing potency and tamper checks on the signed readings; compare with the claims."""
    from edge.chain.canonical import UNIT_E6, UNIT_E9, to_scaled_int

    pairs = readings_from_entries(entries)
    assessor = TrustAssessor(product, TamperMonitor.from_defaults(product, box))
    mismatches: list[str] = []
    last = None
    try:
        for record, reading in pairs:
            assessment, potency, _ = assessor.update(reading)
            last = (reading, assessment, potency)
            checks = (
                ("potency", record["potency"], to_scaled_int(potency.potency, UNIT_E9)),
                ("tau_eq_h", record["tau_eq_h"], to_scaled_int(potency.tau_eq_h, UNIT_E6)),
                ("verdict", record["verdict"], assessment.verdict),
                ("trust_level", record["trust_level"], assessment.trust_level),
            )
            for name, claimed, computed in checks:
                if claimed != computed:
                    mismatches.append(f"entry {record['seq']}: {name}")
    except ValueError as exc:
        raise ValueError(f"cannot recompute the physics checks: {exc}") from exc
    assert last is not None
    reading, assessment, potency = last
    detail = (
        ""
        if not mismatches
        else f"{len(mismatches)} signed values differ from the recomputation (first: {mismatches[0]})"
    )
    return {
        "last_t_ms": round(reading.t_s * 1000), "potency_e9": to_scaled_int(potency.potency, UNIT_E9),
        "tau_eq_e6": to_scaled_int(potency.tau_eq_h, UNIT_E6), "trust_level": assessment.trust_level,
        "verdict": assessment.verdict, "claims_consistent": not mismatches, "claims_detail": detail,
    }  # fmt: skip


def _inputs_from_entries(entries, product, box, remaining_h, shipment_id, last_h):
    """Build planner inputs with the existing pipeline from the verified readings (via a temp file)."""
    pairs = readings_from_entries(entries)
    readings = [p[1] for p in pairs]
    interval = readings[1].t_s - readings[0].t_s if len(readings) > 1 else 600.0
    header = {
        "type": "header", "scenario_id": shipment_id, "seed": 0, "seed_mode": "fixed",
        "sample_interval_s": interval, "schema_version": "0.3", "source": readings[0].source,
        "n_samples": len(readings),
    }  # fmt: skip
    with tempfile.TemporaryDirectory(prefix="pg_backend_") as tmp:
        path = Path(tmp) / "verified.jsonl"
        lines = [json.dumps(header)] + [json.dumps(r.model_dump()) for r in readings]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        return build_inputs(path, last_h + 1e-6, product, box, remaining_h, shipment_id)


def close_call(table: DecisionTable, percent: float) -> tuple[bool, str]:
    """True when the best two actions' CVaR differ by less than `percent` of the best CVaR."""
    ordered = sorted(table.results.values(), key=lambda r: r.cvar)
    best, second = ordered[0], ordered[1]
    if best.cvar <= 0:
        is_close = second.cvar <= 0
    else:
        is_close = (second.cvar - best.cvar) / best.cvar * 100.0 < percent
    text = (
        f"close call: {best.action} and {second.action} differ by "
        f"{(second.cvar - best.cvar):,.0f} in bad-case loss (CVaR), less than {percent:g} percent of "
        f"the best ({best.cvar:,.0f})"
    )
    return is_close, text


def apply_backend_rules(
    decision: DecisionRecord, table: DecisionTable, percent: float,
    claims_inconsistent: bool, key_revoked: bool,
) -> tuple[DecisionRecord, dict]:  # fmt: skip
    """Rules the backend adds ON TOP of the planner's: they can only make a decision stricter."""
    reasons = list(decision.reasons)
    extra = []
    is_close, text = close_call(table, percent)
    if is_close:
        extra.append(text)
    if claims_inconsistent:
        extra.append(
            "the values signed by the device differ from the backend's recomputation of the physics checks"
        )
    if key_revoked:
        extra.append(
            "the signing key was revoked after this data were stored: a person must look at it"
        )
    flags = {
        "close_call": is_close,
        "claims_inconsistent": claims_inconsistent,
        "key_revoked": key_revoked,
    }
    if not extra:
        return decision, flags
    status = QUARANTINED if claims_inconsistent else decision.shipment_status
    reasons = [r for r in reasons if not r.startswith("all three rules hold")] + extra
    explanation = decision.explanation + " Extra checks by the backend: " + "; ".join(extra) + "."
    return (
        decision.model_copy(update={"route": HUMAN, "reasons": tuple(reasons), "explanation": explanation, "shipment_status": status}),
        flags,
    )  # fmt: skip
