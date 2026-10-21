"""Append-only SQLite storage for the backend (Phase 6).

One database file (under data/runs/, git-ignored), standard `sqlite3`, no ORM. This module has NO
function that updates, deletes or replaces a row, and a trigger on every table aborts UPDATE and
DELETE. That guards against mistakes in this program; against someone who edits the file with other
tools the protection is the signatures and the hash chains (a tampered copy fails verification).
Status changes and revocations are NEW rows.

Signed entries and anchors are stored in the Phase 4 format and the decision log in the Phase 5
format, unchanged. Signing protects records after signing and does not stop a lie at the sensor.
"""
# ruff: noqa: E501  (long literal lines)

from __future__ import annotations

import sqlite3
import threading
import time
from collections.abc import Callable
from pathlib import Path

from edge.chain import Anchor, Entry

TABLES = (
    "shipments",
    "shipment_status_history",
    "device_keys",
    "ledger_submissions",
    "entries",
    "anchors",
    "decision_entries",
    "decision_anchors",
    "decisions",
    "approval_tasks",
    "approval_resolutions",
    "sap_events",
    "api_audit",
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS shipments (
    id TEXT PRIMARY KEY, label TEXT NOT NULL, device_id TEXT NOT NULL, origin TEXT NOT NULL,
    scheduled_duration_h REAL, created_ms INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS shipment_status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT, shipment_id TEXT NOT NULL, status TEXT NOT NULL,
    reason TEXT NOT NULL, at_ms INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS device_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT NOT NULL, key_id TEXT NOT NULL,
    public_key BLOB NOT NULL, status TEXT NOT NULL, at_ms INTEGER NOT NULL,
    by_whom TEXT NOT NULL, note TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ledger_submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, shipment_id TEXT NOT NULL, device_id TEXT NOT NULL,
    key_id TEXT NOT NULL, submitted_ms INTEGER NOT NULL, entry_count INTEGER NOT NULL,
    result TEXT NOT NULL, first_bad_index INTEGER, reason TEXT NOT NULL, detail TEXT NOT NULL,
    anchor_present INTEGER NOT NULL, anchor_checked INTEGER NOT NULL,
    last_t_ms INTEGER, potency_e9 INTEGER, tau_eq_e6 INTEGER, trust_level TEXT, verdict TEXT,
    claims_consistent INTEGER, claims_detail TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS entries (
    submission_id INTEGER NOT NULL, shipment_id TEXT NOT NULL, position INTEGER NOT NULL,
    seq INTEGER NOT NULL, record BLOB NOT NULL, signature BLOB NOT NULL, hash BLOB NOT NULL,
    key_id TEXT NOT NULL, PRIMARY KEY (submission_id, position)
);
CREATE TABLE IF NOT EXISTS anchors (
    id INTEGER PRIMARY KEY AUTOINCREMENT, submission_id INTEGER NOT NULL, shipment_id TEXT NOT NULL,
    seq INTEGER NOT NULL, head BLOB NOT NULL, statement BLOB NOT NULL, signature BLOB NOT NULL,
    key_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decision_entries (
    seq INTEGER PRIMARY KEY, record BLOB NOT NULL, signature BLOB NOT NULL, hash BLOB NOT NULL,
    key_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decision_anchors (
    id INTEGER PRIMARY KEY AUTOINCREMENT, seq INTEGER NOT NULL, head BLOB NOT NULL,
    statement BLOB NOT NULL, signature BLOB NOT NULL, key_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decisions (
    seq INTEGER PRIMARY KEY, shipment_id TEXT NOT NULL, submission_id INTEGER NOT NULL,
    at_ms INTEGER NOT NULL, kind TEXT NOT NULL, chosen_action TEXT, route TEXT, close_call INTEGER,
    shipment_status TEXT, refers_to_seq INTEGER
);
CREATE TABLE IF NOT EXISTS approval_tasks (
    task_id INTEGER PRIMARY KEY, shipment_id TEXT NOT NULL, created_ms INTEGER NOT NULL,
    task_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS approval_resolutions (
    task_id INTEGER PRIMARY KEY, shipment_id TEXT NOT NULL, resolved_ms INTEGER NOT NULL,
    who TEXT NOT NULL, human_action TEXT NOT NULL, final_action TEXT, reason TEXT NOT NULL,
    human_seq INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS sap_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, shipment_id TEXT NOT NULL, decision_seq INTEGER NOT NULL,
    human_seq INTEGER, resolution TEXT NOT NULL, event_json TEXT NOT NULL, adapter_mode TEXT NOT NULL,
    ack_id TEXT NOT NULL, ack_json TEXT NOT NULL, at_ms INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS api_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT, at_ms INTEGER NOT NULL, method TEXT NOT NULL,
    endpoint TEXT NOT NULL, caller TEXT NOT NULL, shipment_id TEXT, outcome TEXT NOT NULL,
    status_code INTEGER NOT NULL, detail TEXT NOT NULL
);
"""


def _triggers() -> str:
    parts = []
    for table in TABLES:
        for verb in ("UPDATE", "DELETE"):
            parts.append(
                f"CREATE TRIGGER IF NOT EXISTS {table}_no_{verb.lower()} BEFORE {verb} ON {table} "
                "BEGIN SELECT RAISE(ABORT, 'storage is append-only'); END;"
            )
    return "\n".join(parts)


def system_clock_ms() -> int:
    return int(time.time() * 1000)


class Store:
    """The backend database. Thread-safe through one lock; use `store.lock` around compound steps."""

    def __init__(self, path: Path | str, clock: Callable[[], int] = system_clock_ms) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self.clock = clock
        self.lock = threading.RLock()
        with self.lock:
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.executescript(_SCHEMA + _triggers())
            self._db.commit()

    def close(self) -> None:
        with self.lock:
            self._db.close()

    # ---------------------------------------------------------------- helpers

    def _insert(self, sql: str, params: tuple) -> int:
        with self.lock, self._db:
            cursor = self._db.execute(sql, params)
            return int(cursor.lastrowid or 0)

    def _rows(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self.lock:
            return self._db.execute(sql, params).fetchall()

    def _row(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        with self.lock:
            return self._db.execute(sql, params).fetchone()

    # ---------------------------------------------------------------- shipments

    def add_shipment(
        self, shipment_id: str, label: str, device_id: str, origin: str, duration_h: float | None
    ) -> None:
        self._insert(
            "INSERT INTO shipments (id, label, device_id, origin, scheduled_duration_h, created_ms)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (shipment_id, label, device_id, origin, duration_h, self.clock()),
        )

    def get_shipment(self, shipment_id: str) -> sqlite3.Row | None:
        return self._row("SELECT * FROM shipments WHERE id = ?", (shipment_id,))

    def list_shipments(self) -> list[sqlite3.Row]:
        return self._rows("SELECT * FROM shipments ORDER BY created_ms, id")

    def add_status(self, shipment_id: str, status: str, reason: str) -> None:
        self._insert(
            "INSERT INTO shipment_status_history (shipment_id, status, reason, at_ms)"
            " VALUES (?, ?, ?, ?)",
            (shipment_id, status, reason, self.clock()),
        )

    def status_history(self, shipment_id: str) -> list[sqlite3.Row]:
        return self._rows(
            "SELECT status, reason, at_ms FROM shipment_status_history WHERE shipment_id = ?"
            " ORDER BY id",
            (shipment_id,),
        )

    def current_status(self, shipment_id: str) -> str | None:
        row = self._row(
            "SELECT status FROM shipment_status_history WHERE shipment_id = ? ORDER BY id DESC"
            " LIMIT 1",
            (shipment_id,),
        )
        return None if row is None else row["status"]

    # ---------------------------------------------------------------- device keys

    def add_device_key(
        self, device_id: str, key_id: str, public_key: bytes, status: str, by_whom: str, note: str
    ) -> None:
        self._insert(
            "INSERT INTO device_keys (device_id, key_id, public_key, status, at_ms, by_whom, note)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (device_id, key_id, public_key, status, self.clock(), by_whom, note),
        )

    def key_rows(self, device_id: str | None = None) -> list[sqlite3.Row]:
        if device_id is None:
            return self._rows("SELECT * FROM device_keys ORDER BY id")
        return self._rows("SELECT * FROM device_keys WHERE device_id = ? ORDER BY id", (device_id,))

    def key_state(self, device_id: str, key_id: str) -> dict | None:
        """The registered public key and its CURRENT status (the latest row wins), or None."""
        rows = [r for r in self.key_rows(device_id) if r["key_id"] == key_id]
        if not rows:
            return None
        registered = next((r for r in rows if r["status"] == "active"), None)
        if registered is None:
            return None
        latest = rows[-1]
        revoked = next((r for r in reversed(rows) if r["status"] == "revoked"), None)
        return {
            "public_key": bytes(registered["public_key"]),
            "status": latest["status"],
            "registered_ms": registered["at_ms"],
            "revoked_ms": None if revoked is None else revoked["at_ms"],
        }

    # ---------------------------------------------------------------- ledger submissions

    def add_submission(self, values: dict, entries: list[Entry], anchor: Anchor | None) -> int:
        columns = (
            "shipment_id", "device_id", "key_id", "submitted_ms", "entry_count", "result",
            "first_bad_index", "reason", "detail", "anchor_present", "anchor_checked",
            "last_t_ms", "potency_e9", "tau_eq_e6", "trust_level", "verdict",
            "claims_consistent", "claims_detail",
        )  # fmt: skip
        with self.lock, self._db:
            cursor = self._db.execute(
                f"INSERT INTO ledger_submissions ({', '.join(columns)}) VALUES "
                f"({', '.join('?' for _ in columns)})",
                tuple(values.get(c) for c in columns),
            )
            sid = int(cursor.lastrowid or 0)
            self._db.executemany(
                "INSERT INTO entries (submission_id, shipment_id, position, seq, record, signature,"
                " hash, key_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (sid, values["shipment_id"], i, e.seq, e.record, e.signature, e.hash, e.key_id)
                    for i, e in enumerate(entries)
                ],
            )
            if anchor is not None:
                self._db.execute(
                    "INSERT INTO anchors (submission_id, shipment_id, seq, head, statement,"
                    " signature, key_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (sid, values["shipment_id"], anchor.seq, anchor.head, anchor.statement,
                     anchor.signature, anchor.key_id),
                )  # fmt: skip
        return sid

    def submissions(self, shipment_id: str) -> list[sqlite3.Row]:
        return self._rows(
            "SELECT * FROM ledger_submissions WHERE shipment_id = ? ORDER BY id", (shipment_id,)
        )

    def latest_submission(self, shipment_id: str) -> sqlite3.Row | None:
        return self._row(
            "SELECT * FROM ledger_submissions WHERE shipment_id = ? ORDER BY id DESC LIMIT 1",
            (shipment_id,),
        )

    def latest_verified_submission(self, shipment_id: str) -> sqlite3.Row | None:
        return self._row(
            "SELECT * FROM ledger_submissions WHERE shipment_id = ? AND result = 'verified'"
            " ORDER BY id DESC LIMIT 1",
            (shipment_id,),
        )

    def submission_entries(self, submission_id: int) -> list[Entry]:
        rows = self._rows(
            "SELECT seq, record, signature, hash, key_id FROM entries WHERE submission_id = ?"
            " ORDER BY position",
            (submission_id,),
        )
        return [
            Entry(
                r["seq"], bytes(r["record"]), bytes(r["signature"]), bytes(r["hash"]), r["key_id"]
            )
            for r in rows
        ]

    def submission_anchor(self, submission_id: int) -> Anchor | None:
        r = self._row(
            "SELECT * FROM anchors WHERE submission_id = ? ORDER BY id DESC LIMIT 1",
            (submission_id,),
        )
        if r is None:
            return None
        return Anchor(
            r["seq"], bytes(r["head"]), bytes(r["statement"]), bytes(r["signature"]), r["key_id"]
        )

    # ---------------------------------------------------------------- decision log (Phase 5 format)

    def last_decision_entry(self) -> Entry | None:
        r = self._row("SELECT * FROM decision_entries ORDER BY seq DESC LIMIT 1")
        return None if r is None else _entry(r)

    def append_decision_entry(self, entry: Entry) -> None:
        self._insert(
            "INSERT INTO decision_entries (seq, record, signature, hash, key_id) VALUES (?, ?, ?, ?, ?)",
            (entry.seq, entry.record, entry.signature, entry.hash, entry.key_id),
        )

    def decision_entries(self) -> list[Entry]:
        return [_entry(r) for r in self._rows("SELECT * FROM decision_entries ORDER BY seq")]

    def add_decision_anchor(self, anchor: Anchor) -> None:
        self._insert(
            "INSERT INTO decision_anchors (seq, head, statement, signature, key_id)"
            " VALUES (?, ?, ?, ?, ?)",
            (anchor.seq, anchor.head, anchor.statement, anchor.signature, anchor.key_id),
        )

    def latest_decision_anchor(self) -> Anchor | None:
        r = self._row("SELECT * FROM decision_anchors ORDER BY id DESC LIMIT 1")
        if r is None:
            return None
        return Anchor(
            r["seq"], bytes(r["head"]), bytes(r["statement"]), bytes(r["signature"]), r["key_id"]
        )

    def add_decision_index(self, values: dict) -> None:
        columns = ("seq", "shipment_id", "submission_id", "kind", "chosen_action", "route",
                   "close_call", "shipment_status", "refers_to_seq")  # fmt: skip
        self._insert(
            f"INSERT INTO decisions (at_ms, {', '.join(columns)}) VALUES (?, "
            f"{', '.join('?' for _ in columns)})",
            (self.clock(), *(values.get(c) for c in columns)),
        )

    def decision_index(self, shipment_id: str) -> list[sqlite3.Row]:
        return self._rows(
            "SELECT * FROM decisions WHERE shipment_id = ? ORDER BY seq", (shipment_id,)
        )

    def decision_index_row(self, seq: int) -> sqlite3.Row | None:
        return self._row("SELECT * FROM decisions WHERE seq = ?", (seq,))

    # ---------------------------------------------------------------- approvals

    def add_task(self, task_id: int, shipment_id: str, task_json: str) -> None:
        self._insert(
            "INSERT INTO approval_tasks (task_id, shipment_id, created_ms, task_json) VALUES (?, ?, ?, ?)",
            (task_id, shipment_id, self.clock(), task_json),
        )

    def get_task(self, task_id: int) -> sqlite3.Row | None:
        return self._row("SELECT * FROM approval_tasks WHERE task_id = ?", (task_id,))

    def open_tasks(self) -> list[sqlite3.Row]:
        return self._rows(
            "SELECT t.* FROM approval_tasks t LEFT JOIN approval_resolutions r ON r.task_id = t.task_id"
            " WHERE r.task_id IS NULL ORDER BY t.task_id"
        )

    def add_resolution(self, values: dict) -> None:
        self._insert(
            "INSERT INTO approval_resolutions (task_id, shipment_id, resolved_ms, who, human_action,"
            " final_action, reason, human_seq) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (values["task_id"], values["shipment_id"], self.clock(), values["who"],
             values["human_action"], values["final_action"], values["reason"], values["human_seq"]),
        )  # fmt: skip

    def get_resolution(self, task_id: int) -> sqlite3.Row | None:
        return self._row("SELECT * FROM approval_resolutions WHERE task_id = ?", (task_id,))

    # ---------------------------------------------------------------- enterprise events

    def add_sap_event(self, values: dict) -> int:
        return self._insert(
            "INSERT INTO sap_events (shipment_id, decision_seq, human_seq, resolution, event_json,"
            " adapter_mode, ack_id, ack_json, at_ms) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (values["shipment_id"], values["decision_seq"], values.get("human_seq"),
             values["resolution"], values["event_json"], values["adapter_mode"], values["ack_id"],
             values["ack_json"], self.clock()),
        )  # fmt: skip

    def sap_events(self, shipment_id: str | None = None) -> list[sqlite3.Row]:
        if shipment_id is None:
            return self._rows("SELECT * FROM sap_events ORDER BY id")
        return self._rows(
            "SELECT * FROM sap_events WHERE shipment_id = ? ORDER BY id", (shipment_id,)
        )

    def sap_event_by_ack(self, ack_id: str) -> sqlite3.Row | None:
        return self._row("SELECT * FROM sap_events WHERE ack_id = ?", (ack_id,))

    def count_sap_events(self) -> int:
        return int(self._row("SELECT COUNT(*) AS n FROM sap_events")["n"])  # type: ignore[index]

    # ---------------------------------------------------------------- API audit

    def add_audit(
        self, method: str, endpoint: str, caller: str, shipment_id: str | None, outcome: str,
        status_code: int, detail: str,
    ) -> None:  # fmt: skip
        self._insert(
            "INSERT INTO api_audit (at_ms, method, endpoint, caller, shipment_id, outcome,"
            " status_code, detail) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (self.clock(), method, endpoint, caller, shipment_id, outcome, status_code, detail),
        )

    def audit_page(self, offset: int, limit: int) -> tuple[int, list[sqlite3.Row]]:
        total = int(self._row("SELECT COUNT(*) AS n FROM api_audit")["n"])  # type: ignore[index]
        rows = self._rows("SELECT * FROM api_audit ORDER BY id LIMIT ? OFFSET ?", (limit, offset))
        return total, rows


def _entry(r: sqlite3.Row) -> Entry:
    return Entry(r["seq"], bytes(r["record"]), bytes(r["signature"]), bytes(r["hash"]), r["key_id"])


class DecisionStoreLedger:
    """Adapter that lets the unchanged Phase 5 DecisionLog write into the backend database."""

    def __init__(self, store: Store) -> None:
        self._store = store

    def last_entry(self) -> Entry | None:
        return self._store.last_decision_entry()

    def append(self, entry: Entry) -> None:
        self._store.append_decision_entry(entry)

    def add_anchor(self, anchor: Anchor) -> None:
        self._store.add_decision_anchor(anchor)

    def read_entries(self) -> list[Entry]:
        return self._store.decision_entries()

    def latest_anchor(self) -> Anchor | None:
        return self._store.latest_decision_anchor()
