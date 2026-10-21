"""Hash chain over signed records, and its verification (Phase 4).

    genesis = SHA-256(b"potencyguard/genesis/v1" || device_id bytes)
    h_n     = SHA-256(h_{n-1} || canonical_bytes_n || signature_n)        (h_{-1} = genesis)
    signature_n = Ed25519 signature over canonical_bytes_n

WHAT THIS PROTECTS, AND WHAT IT DOES NOT. Signatures and the hash chain protect records AFTER they
are signed. They detect edits, deletions, reordering and impersonation by someone without the key.
They do NOT stop a lie at the sensor before the device signs it: if the sensor input is false,
the device signs the false value. A sensor-level mimic liar needs attested or redundant sensors,
or out-of-band data (GPS, carrier records).

TAIL TRUNCATION. Removing entries from the END of a ledger leaves a shorter chain that is still
valid. Without an anchor this cannot be detected. An anchor is a small signed statement
(device id, seq, head hash h_seq); if one exists, a ledger that no longer contains that entry with
that hash is reported. An anchor only protects up to the entry it names.

verify_chain never raises on corrupt input: it reports the index of the FIRST broken entry and why.
The public key must reach the verifier from somewhere other than the ledger it is checking.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass

from edge.chain.canonical import canonical_bytes, parse_canonical
from edge.chain.crypto import Signer, key_id_of, verify_signature

GENESIS_PREFIX = b"potencyguard/genesis/v1"
ANCHOR_SCHEMA = "pg-anchor/1"

# reasons reported by verify_chain
OK = "ok"
MALFORMED = "malformed"
BAD_SEQUENCE = "bad_sequence"
WRONG_DEVICE = "wrong_device"
BAD_SIGNATURE = "bad_signature"
BAD_HASH_LINK = "bad_hash_link"
TRUNCATED = "truncated"
BAD_ANCHOR = "bad_anchor"
ANCHOR_MISMATCH = "anchor_mismatch"


def genesis_hash(device_id: str) -> bytes:
    return hashlib.sha256(GENESIS_PREFIX + device_id.encode("utf-8")).digest()


def link_hash(previous: bytes, canonical: bytes, signature: bytes) -> bytes:
    return hashlib.sha256(previous + canonical + signature).digest()


@dataclass(frozen=True)
class Entry:
    """One stored ledger entry."""

    seq: int
    record: bytes  # canonical bytes
    signature: bytes
    hash: bytes
    key_id: str


@dataclass(frozen=True)
class Anchor:
    """A signed statement of the chain head at some seq."""

    seq: int
    head: bytes
    statement: bytes  # canonical bytes of the statement that was signed
    signature: bytes
    key_id: str


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    index: int | None  # first broken entry (None when ok)
    reason: str
    detail: str
    entries_checked: int
    anchor_checked: bool

    def __str__(self) -> str:
        if self.ok:
            tail = (
                "; anchor checked"
                if self.anchor_checked
                else "; no anchor (tail truncation cannot be detected)"
            )
            return f"chain OK: {self.entries_checked} entries verified{tail}"
        return f"chain BROKEN at entry {self.index}: {self.reason} ({self.detail})"


def anchor_statement(device_id: str, seq: int, head: bytes) -> bytes:
    body = {"device_id": device_id, "head": head.hex(), "schema": ANCHOR_SCHEMA, "seq": seq}
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")


def make_anchor(signer: Signer, device_id: str, seq: int, head: bytes) -> Anchor:
    statement = anchor_statement(device_id, seq, head)
    return Anchor(seq, head, statement, signer.sign(statement), signer.key_id)


class ChainWriter:
    """Signs records and links them into the chain, writing each entry to a ledger.

    `ledger` needs: last_entry() -> Entry | None, append(Entry), add_anchor(Anchor).
    """

    def __init__(self, device_id: str, signer: Signer, ledger) -> None:
        self.device_id = device_id
        self._signer = signer
        self._ledger = ledger
        last = ledger.last_entry()
        self._next_seq = 0 if last is None else last.seq + 1
        self._previous = genesis_hash(device_id) if last is None else last.hash

    @property
    def next_seq(self) -> int:
        return self._next_seq

    @property
    def head(self) -> bytes:
        return self._previous

    def append(self, record: dict) -> Entry:
        if record.get("seq") != self._next_seq:
            raise ValueError(f"record seq {record.get('seq')} but the next seq is {self._next_seq}")
        if record.get("device_id") != self.device_id:
            raise ValueError("record device_id does not match the writer's device_id")
        canonical = canonical_bytes(record)
        signature = self._signer.sign(canonical)
        digest = link_hash(self._previous, canonical, signature)
        entry = Entry(self._next_seq, canonical, signature, digest, self._signer.key_id)
        self._ledger.append(entry)
        self._previous = digest
        self._next_seq += 1
        return entry

    def anchor(self) -> Anchor:
        """Sign and store the current head. Needs at least one entry."""
        if self._next_seq == 0:
            raise ValueError("nothing to anchor: the ledger is empty")
        anchor = make_anchor(self._signer, self.device_id, self._next_seq - 1, self._previous)
        self._ledger.add_anchor(anchor)
        return anchor


def verify_chain(
    entries: Sequence[Entry],
    public_key: bytes,
    anchor: Anchor | None = None,
    device_id: str | None = None,
) -> VerifyResult:
    """Check every entry in order; report the FIRST broken one. Never raises."""
    index = 0
    try:
        return _verify(entries, public_key, anchor, device_id)
    except Exception as exc:  # corrupt input must be reported, never raised
        return VerifyResult(False, index, MALFORMED, f"unexpected {type(exc).__name__}", 0, False)


def _fail(index: int, reason: str, detail: str, checked: int) -> VerifyResult:
    return VerifyResult(False, index, reason, detail, checked, False)


def _verify(entries, public_key, anchor, device_id) -> VerifyResult:
    expected_key_id = key_id_of(public_key) if isinstance(public_key, bytes) else ""
    previous: bytes | None = None
    device = device_id
    for i, entry in enumerate(entries):
        if not (
            isinstance(entry, Entry)
            and isinstance(entry.record, bytes)
            and isinstance(entry.signature, bytes)
            and isinstance(entry.hash, bytes)
            and isinstance(entry.key_id, str)
            and isinstance(entry.seq, int)
        ):
            return _fail(i, MALFORMED, "entry fields have the wrong types", i)
        try:
            record = parse_canonical(entry.record)
        except ValueError as exc:
            return _fail(i, MALFORMED, str(exc), i)
        if record["seq"] != i or entry.seq != i:
            return _fail(i, BAD_SEQUENCE, f"expected seq {i}, record says {record['seq']}", i)
        if device is None:
            device = record["device_id"]
        if record["device_id"] != device:
            return _fail(i, WRONG_DEVICE, "device_id differs from the chain's device", i)
        if previous is None:
            previous = genesis_hash(device)
        if entry.key_id != expected_key_id:
            return _fail(i, BAD_SIGNATURE, "signed with a different key (key id differs)", i)
        if not verify_signature(public_key, entry.signature, entry.record):
            return _fail(i, BAD_SIGNATURE, "signature does not verify", i)
        expected = link_hash(previous, entry.record, entry.signature)
        if entry.hash != expected:
            return _fail(i, BAD_HASH_LINK, "stored hash does not match the chain", i)
        previous = expected
    n = len(entries)
    if anchor is None:
        return VerifyResult(True, None, OK, "no anchor given", n, False)
    return _check_anchor(entries, public_key, anchor, device, n)


def _check_anchor(entries, public_key, anchor, device, n) -> VerifyResult:
    if not (
        isinstance(anchor, Anchor)
        and isinstance(anchor.statement, bytes)
        and isinstance(anchor.signature, bytes)
        and isinstance(anchor.head, bytes)
        and isinstance(anchor.seq, int)
    ):
        return _fail(n, BAD_ANCHOR, "anchor fields have the wrong types", n)
    if not verify_signature(public_key, anchor.signature, anchor.statement):
        return _fail(n, BAD_ANCHOR, "anchor signature does not verify", n)
    try:
        body = json.loads(anchor.statement.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _fail(n, BAD_ANCHOR, "anchor statement is not valid JSON", n)
    if (
        not isinstance(body, dict)
        or body.get("schema") != ANCHOR_SCHEMA
        or body.get("seq") != anchor.seq
        or body.get("head") != anchor.head.hex()
        or (device is not None and body.get("device_id") != device)
    ):
        return _fail(n, BAD_ANCHOR, "anchor statement does not match its fields or device", n)
    if n <= anchor.seq:
        return _fail(
            n,
            TRUNCATED,
            f"anchor names entry {anchor.seq} but the ledger ends at entry {n - 1}",
            n,
        )
    if entries[anchor.seq].hash != anchor.head:
        return _fail(anchor.seq, ANCHOR_MISMATCH, "entry hash differs from the anchored head", n)
    return VerifyResult(True, None, OK, "anchor matches", n, True)
