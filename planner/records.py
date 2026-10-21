"""Signed, hash-chained decision log (Phase 5, schema pg-decision/1).

Decision records and human decisions are turned into canonical bytes with the same integer-only
rules as Phase 4 (edge/chain/canonical.py: shortest decimal, exact multiplication, round half away
from zero, sorted keys, no whitespace, integers/strings/null only), signed with Ed25519 and
appended to a SEPARATE append-only ledger (the Phase 4 Ledger) under data/runs/ (git-ignored). The
Phase 4 record schema and behaviour are untouched.

Units: money in 1e-2, probabilities and alpha in 1e-6, potency in 1e-9, tau_eq in 1e-6 hour,
temperature in 1e-4 degree C, time in milliseconds. Booleans are 0/1 integers.

Human decisions are appended as NEW entries that refer to the original decision's sequence number.

Signing protects records after signing; it does not stop a lie at the sensor before signing (A18).
The planner recommends; it never executes. Illustrative placeholder numbers.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from edge.chain import (
    Anchor,
    Entry,
    Ledger,
    Signer,
    VerifyResult,
    genesis_hash,
    link_hash,
    make_anchor,
    to_scaled_int,
)
from edge.chain import chain as chain_module
from edge.chain.canonical import _reject_constant, _reject_float
from edge.chain.crypto import key_id_of, verify_signature
from planner.config import ACTIONS
from planner.governance import DecisionRecord, HumanDecisionRecord

SCHEMA = "pg-decision/1"
KIND_DECISION = "decision"
KIND_HUMAN = "human_decision"
MAX_SAFE_INT = 2**53
REASON_BAD_REFERENCE = "bad_reference"

_COMMON = {"schema": "str", "kind": "str", "planner_id": "str", "seq": "int", "shipment_id": "str"}
DECISION_FIELDS: dict[str, str] = {
    **_COMMON,
    "t_ms": "int", "seed": "int", "alpha_e6": "int", "n_scenarios": "int",
    "potency_e9": "int", "tau_eq_now_e6": "int", "tau_eq_start_e6": "int",
    "start_temp_e4": "int", "bound_used": "int", "trust_level": "str", "verdict": "str",
    "chain_status": "str", "falsification_latched": "int", "shipment_status": "str",
    "chosen_action": "str", "expected_optimal_action": "str", "disagree": "int",
    "route": "str", "chosen_var_e2": "int", "chosen_gap_e2": "int", "v_thr_e2": "int",
    "confidence_gap_thr_e2": "int", "reasons": "str", "explanation": "str",
    **{
        f"{a}_{suffix}": "int"
        for a in ACTIONS
        for suffix in ("cost_e2", "fail_e6", "exp_e2", "var_e2", "cvar_e2")
    },
}  # fmt: skip
HUMAN_FIELDS: dict[str, str] = {
    **_COMMON,
    "refers_to_seq": "int", "who": "str", "when_ms": "int", "human_action": "str",
    "final_action": "str?", "reason": "str",
}  # fmt: skip
FIELDS_BY_KIND = {KIND_DECISION: DECISION_FIELDS, KIND_HUMAN: HUMAN_FIELDS}


def _validate(record: object) -> dict:
    if not isinstance(record, dict):
        raise ValueError("a record must be a JSON object")
    fields = FIELDS_BY_KIND.get(record.get("kind"))
    if fields is None:
        raise ValueError(f"unknown kind {record.get('kind')!r}")
    if set(record) != set(fields):
        raise ValueError(
            f"wrong fields (missing {sorted(set(fields) - set(record))}, "
            f"unexpected {sorted(set(record) - set(fields))})"
        )
    for name, kind in fields.items():
        value = record[name]
        if kind == "str?" and value is None:
            continue
        if kind == "int":
            if isinstance(value, bool) or not isinstance(value, int) or abs(value) > MAX_SAFE_INT:
                raise ValueError(f"{name} must be a safe integer (got {value!r})")
        elif not isinstance(value, str) or not value:
            raise ValueError(f"{name} must be a non-empty string (got {value!r})")
    if record["schema"] != SCHEMA:
        raise ValueError(f"unsupported schema {record['schema']!r}")
    if record["seq"] < 0:
        raise ValueError("seq must not be negative")
    return record


def canonical_bytes(record: dict) -> bytes:
    _validate(record)
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def parse_canonical(data: bytes) -> dict:
    """Read canonical bytes back; raises ValueError unless they are EXACTLY the canonical form."""
    try:
        record = json.loads(
            data.decode("utf-8"), parse_float=_reject_float, parse_constant=_reject_constant
        )
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, AttributeError) as exc:
        raise ValueError(f"not valid canonical JSON: {exc}") from exc
    _validate(record)
    if canonical_bytes(record) != data:
        raise ValueError("bytes are valid JSON but not in canonical form")
    return record


def _ms(seconds: float) -> int:
    return to_scaled_int(seconds, 1000)


def decision_record_dict(planner_id: str, seq: int, d: DecisionRecord) -> dict:
    i = d.inputs
    rec: dict = {
        "schema": SCHEMA, "kind": KIND_DECISION, "planner_id": planner_id, "seq": seq,
        "shipment_id": d.shipment_id, "t_ms": _ms(d.t_s), "seed": d.seed,
        "alpha_e6": to_scaled_int(d.alpha, 10**6), "n_scenarios": d.n_scenarios,
        "potency_e9": to_scaled_int(i.potency_now, 10**9),
        "tau_eq_now_e6": to_scaled_int(i.tau_eq_now_h, 10**6),
        "tau_eq_start_e6": to_scaled_int(i.start_tau_eq_h, 10**6),
        "start_temp_e4": to_scaled_int(i.start_temp_c, 10**4),
        "bound_used": int(i.bound_used), "trust_level": i.trust_level, "verdict": i.verdict,
        "chain_status": i.chain_status, "falsification_latched": int(i.falsification_latched),
        "shipment_status": d.shipment_status, "chosen_action": d.chosen_action,
        "expected_optimal_action": d.expected_optimal_action, "disagree": int(d.disagree),
        "route": d.route, "chosen_var_e2": to_scaled_int(d.chosen_var, 100),
        "chosen_gap_e2": to_scaled_int(d.chosen_gap, 100),
        "v_thr_e2": to_scaled_int(d.v_thr, 100),
        "confidence_gap_thr_e2": to_scaled_int(d.confidence_gap_thr, 100),
        "reasons": " | ".join(d.reasons) or "none", "explanation": d.explanation,
    }  # fmt: skip
    for row in d.table:
        rec[f"{row.action}_cost_e2"] = to_scaled_int(row.cost, 100)
        rec[f"{row.action}_fail_e6"] = to_scaled_int(row.failure_probability, 10**6)
        rec[f"{row.action}_exp_e2"] = to_scaled_int(row.expected_loss, 100)
        rec[f"{row.action}_var_e2"] = to_scaled_int(row.var, 100)
        rec[f"{row.action}_cvar_e2"] = to_scaled_int(row.cvar, 100)
    return rec


def human_record_dict(planner_id: str, seq: int, h: HumanDecisionRecord) -> dict:
    when = h.when
    if when.tzinfo is None:
        raise ValueError("the time of a human decision needs a time zone")
    return {
        "schema": SCHEMA, "kind": KIND_HUMAN, "planner_id": planner_id, "seq": seq,
        "shipment_id": h.shipment_id, "refers_to_seq": h.refers_to_seq, "who": h.who,
        "when_ms": int(round(when.timestamp() * 1000)), "human_action": h.human_action,
        "final_action": h.final_action, "reason": h.reason,
    }  # fmt: skip


def log_genesis_id(planner_id: str) -> str:
    return f"{planner_id}/decision-log"


class DecisionLog:
    """Append-only, signed, hash-chained log of decisions and human decisions."""

    def __init__(self, planner_id: str, signer: Signer, ledger: Ledger) -> None:
        self.planner_id = planner_id
        self._signer = signer
        self._ledger = ledger
        last = ledger.last_entry()
        self._next = 0 if last is None else last.seq + 1
        self._previous = genesis_hash(log_genesis_id(planner_id)) if last is None else last.hash

    @property
    def next_seq(self) -> int:
        return self._next

    def _append(self, record: dict) -> Entry:
        canonical = canonical_bytes(record)
        signature = self._signer.sign(canonical)
        digest = link_hash(self._previous, canonical, signature)
        entry = Entry(self._next, canonical, signature, digest, self._signer.key_id)
        self._ledger.append(entry)
        self._previous, self._next = digest, self._next + 1
        return entry

    def append_decision(self, decision: DecisionRecord) -> Entry:
        return self._append(decision_record_dict(self.planner_id, self._next, decision))

    def append_human(self, human: HumanDecisionRecord) -> Entry:
        """Append a person's decision as a NEW entry; it must refer to an earlier decision."""
        entries = {e.seq: e for e in self._ledger.read_entries()}
        target = entries.get(human.refers_to_seq)
        if target is None or parse_canonical(target.record)["kind"] != KIND_DECISION:
            raise ValueError(f"entry {human.refers_to_seq} is not a decision in this log")
        return self._append(human_record_dict(self.planner_id, self._next, human))

    def anchor(self) -> Anchor:
        if self._next == 0:
            raise ValueError("nothing to anchor: the log is empty")
        anchor = make_anchor(
            self._signer, log_genesis_id(self.planner_id), self._next - 1, self._previous
        )
        self._ledger.add_anchor(anchor)
        return anchor


def verify_decision_log(
    entries: Sequence[Entry],
    public_key: bytes,
    anchor: Anchor | None = None,
    planner_id: str | None = None,
) -> VerifyResult:
    """Check every entry in order and report the FIRST broken one. Never raises."""
    try:
        return _verify(entries, public_key, anchor, planner_id)
    except Exception as exc:  # corrupt input is reported, not raised
        return VerifyResult(False, 0, chain_module.MALFORMED, type(exc).__name__, 0, False)


def _fail(i: int, reason: str, detail: str) -> VerifyResult:
    return VerifyResult(False, i, reason, detail, i, False)


def _verify(entries, public_key, anchor, planner_id) -> VerifyResult:
    expected_key = key_id_of(public_key) if isinstance(public_key, bytes) else ""
    previous: bytes | None = None
    planner = planner_id
    kinds: dict[int, str] = {}
    for i, entry in enumerate(entries):
        if not (
            isinstance(entry, Entry)
            and isinstance(entry.record, bytes)
            and isinstance(entry.signature, bytes)
            and isinstance(entry.hash, bytes)
            and isinstance(entry.key_id, str)
            and isinstance(entry.seq, int)
        ):
            return _fail(i, chain_module.MALFORMED, "entry fields have the wrong types")
        try:
            record = parse_canonical(entry.record)
        except ValueError as exc:
            return _fail(i, chain_module.MALFORMED, str(exc))
        if record["seq"] != i or entry.seq != i:
            return _fail(
                i, chain_module.BAD_SEQUENCE, f"expected seq {i}, record says {record['seq']}"
            )
        planner = planner or record["planner_id"]
        if record["planner_id"] != planner:
            return _fail(i, chain_module.WRONG_DEVICE, "planner_id differs from the log's planner")
        if previous is None:
            previous = genesis_hash(log_genesis_id(planner))
        if entry.key_id != expected_key:
            return _fail(i, chain_module.BAD_SIGNATURE, "signed with a different key")
        if not verify_signature(public_key, entry.signature, entry.record):
            return _fail(i, chain_module.BAD_SIGNATURE, "signature does not verify")
        digest = link_hash(previous, entry.record, entry.signature)
        if entry.hash != digest:
            return _fail(i, chain_module.BAD_HASH_LINK, "stored hash does not match the chain")
        if record["kind"] == KIND_HUMAN:
            target = record["refers_to_seq"]
            if not (0 <= target < i and kinds.get(target) == KIND_DECISION):
                return _fail(
                    i, REASON_BAD_REFERENCE, f"refers to {target}, which is not an earlier decision"
                )
        kinds[i] = record["kind"]
        previous = digest
    n = len(entries)
    if anchor is None:
        return VerifyResult(True, None, chain_module.OK, "no anchor given", n, False)
    return chain_module._check_anchor(
        entries, public_key, anchor, log_genesis_id(planner) if planner else None, n
    )
