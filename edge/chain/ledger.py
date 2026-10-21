"""Append-only SQLite ledger (Phase 4).

One file per run, under data/runs/ (git-ignored), named by run id. Two tables: `entries` and
`anchors`. This module offers NO function that updates, deletes or replaces a row, and the
database itself refuses UPDATE and DELETE through triggers. That is a guard against mistakes in
this program, not a defence against someone who edits the file with other tools; that is what the
signatures and the hash chain are for (a tampered copy fails verify_chain).

Signatures and the hash chain protect records AFTER they are signed. They do not stop a lie at the
sensor before the device signs it.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from edge.chain.chain import Anchor, Entry
from shared.config import REPO_ROOT

DEFAULT_RUNS_DIR = REPO_ROOT / "data" / "runs"
_RUN_ID = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    seq INTEGER PRIMARY KEY,
    record BLOB NOT NULL,
    signature BLOB NOT NULL,
    hash BLOB NOT NULL,
    key_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS anchors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seq INTEGER NOT NULL,
    head BLOB NOT NULL,
    statement BLOB NOT NULL,
    signature BLOB NOT NULL,
    key_id TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS entries_no_update BEFORE UPDATE ON entries
BEGIN SELECT RAISE(ABORT, 'ledger is append-only'); END;
CREATE TRIGGER IF NOT EXISTS entries_no_delete BEFORE DELETE ON entries
BEGIN SELECT RAISE(ABORT, 'ledger is append-only'); END;
CREATE TRIGGER IF NOT EXISTS anchors_no_update BEFORE UPDATE ON anchors
BEGIN SELECT RAISE(ABORT, 'ledger is append-only'); END;
CREATE TRIGGER IF NOT EXISTS anchors_no_delete BEFORE DELETE ON anchors
BEGIN SELECT RAISE(ABORT, 'ledger is append-only'); END;
"""


def new_run_id(label: str) -> str:
    """A run id like 20261021T101500Z_baseline_ok (label cleaned to safe characters)."""
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{stamp}_{re.sub(r'[^A-Za-z0-9_.-]', '_', label)[:40]}"


class Ledger:
    """The ledger of one run. Use Ledger.create(...) for a new run, Ledger.open(...) to read."""

    def __init__(self, path: Path, connection: sqlite3.Connection) -> None:
        self.path = path
        self._db = connection

    @classmethod
    def create(cls, run_id: str, runs_dir: Path | str | None = None) -> Ledger:
        """A fresh ledger file named by run id. Refuses to touch an existing file."""
        if not _RUN_ID.match(run_id):
            raise ValueError(f"run id {run_id!r} has characters that are not allowed")
        folder = Path(runs_dir) if runs_dir is not None else DEFAULT_RUNS_DIR
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{run_id}.sqlite"
        if path.exists():
            raise FileExistsError(f"ledger {path} already exists; every run needs a new run id")
        db = sqlite3.connect(path)
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript(_SCHEMA)
        db.commit()
        return cls(path, db)

    @classmethod
    def open(cls, path: Path | str) -> Ledger:
        """Open an existing ledger (read and append only)."""
        target = Path(path)
        if not target.exists():
            raise FileNotFoundError(f"no ledger at {target}")
        db = sqlite3.connect(target)
        db.executescript(_SCHEMA)
        return cls(target, db)

    # -- append only ---------------------------------------------------------------------------

    def append(self, entry: Entry) -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO entries (seq, record, signature, hash, key_id) VALUES (?, ?, ?, ?, ?)",
                (entry.seq, entry.record, entry.signature, entry.hash, entry.key_id),
            )

    def add_anchor(self, anchor: Anchor) -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO anchors (seq, head, statement, signature, key_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (anchor.seq, anchor.head, anchor.statement, anchor.signature, anchor.key_id),
            )

    # -- reading -------------------------------------------------------------------------------

    def read_entries(self) -> list[Entry]:
        rows = self._db.execute(
            "SELECT seq, record, signature, hash, key_id FROM entries ORDER BY seq"
        ).fetchall()
        return [Entry(r[0], bytes(r[1]), bytes(r[2]), bytes(r[3]), r[4]) for r in rows]

    def last_entry(self) -> Entry | None:
        row = self._db.execute(
            "SELECT seq, record, signature, hash, key_id FROM entries ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        return (
            None
            if row is None
            else Entry(row[0], bytes(row[1]), bytes(row[2]), bytes(row[3]), row[4])
        )

    def read_anchors(self) -> list[Anchor]:
        rows = self._db.execute(
            "SELECT seq, head, statement, signature, key_id FROM anchors ORDER BY id"
        ).fetchall()
        return [Anchor(r[0], bytes(r[1]), bytes(r[2]), bytes(r[3]), r[4]) for r in rows]

    def latest_anchor(self) -> Anchor | None:
        anchors = self.read_anchors()
        return anchors[-1] if anchors else None

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> Ledger:
        return self

    def __exit__(self, *exc) -> None:
        self.close()
