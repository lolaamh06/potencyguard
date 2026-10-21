"""Tamper demo: change a COPY of a signed ledger and show what verify_chain reports (Phase 4).

    python scripts/tamper_demo.py LEDGER ACTION [--entry N] [--count N] [--public-key FILE]
                                                [--out-dir DIR]

Actions: edit, delete, reorder, replace-signature, resign, truncate, all.

The ledger itself is never changed: each action works on a copy (made with the SQLite backup API).
In the copy the append-only triggers are dropped first, to play someone who edits the file with
other tools. Then verify_chain runs on the copy with the real public key.

What this shows, honestly:
  * edits, deletions, reordering, a replaced signature and a re-signature with a DIFFERENT key
    (impersonation) are all reported, at the first broken entry;
  * removing entries from the END of the ledger is invisible without an anchor (the shorter chain
    is still valid) and is reported only when a signed anchor names an entry that is gone;
  * none of this stops a lie at the sensor before the device signs it: the device would sign it.
"""
# ruff: noqa: E501  (long literal lines in vectors and messages)

from __future__ import annotations

import argparse
import sqlite3
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from edge.chain import (  # noqa: E402
    Ledger,
    Signer,
    canonical_bytes,
    link_hash,
    parse_canonical,
    verify_chain,
)
from edge.chain.chain import genesis_hash  # noqa: E402

ACTIONS = ("edit", "delete", "reorder", "replace-signature", "resign", "truncate")
TRIGGERS = ("entries_no_update", "entries_no_delete", "anchors_no_update", "anchors_no_delete")


def make_copy(source: Path, out_dir: Path, name: str) -> Path:
    """Copy a ledger with the SQLite backup API (consistent even with a WAL file)."""
    target = out_dir / f"{source.stem}.{name}.sqlite"
    if target.exists():
        target.unlink()
    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        src.close()
        dst.close()
    return target


def _raw(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    for trigger in TRIGGERS:
        db.execute(f"DROP TRIGGER IF EXISTS {trigger}")
    return db


def apply_action(path: Path, action: str, entry: int | None, count: int) -> str:
    """Tamper with the copy at `path`. Returns a one-line description."""
    db = _raw(path)
    try:
        n = db.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        if n < 4:
            raise SystemExit("the ledger needs at least 4 entries for the demo")
        k = n // 2 if entry is None else entry
        if not 0 <= k < n - 1:
            raise SystemExit(f"--entry must be between 0 and {n - 2}")
        if action == "edit":
            (record,) = db.execute("SELECT record FROM entries WHERE seq=?", (k,)).fetchone()
            data = parse_canonical(bytes(record))
            old = data["temp"]
            data["temp"] = old + 10_000  # one degree
            db.execute("UPDATE entries SET record=? WHERE seq=?", (canonical_bytes(data), k))
            text = f"edited the temperature of entry {k} ({old / 1e4:.4f} -> {data['temp'] / 1e4:.4f} C)"
        elif action == "delete":
            db.execute("DELETE FROM entries WHERE seq=?", (k,))
            text = f"deleted entry {k}"
        elif action == "reorder":
            a = db.execute(
                "SELECT record, signature, hash, key_id FROM entries WHERE seq=?", (k,)
            ).fetchone()
            b = db.execute(
                "SELECT record, signature, hash, key_id FROM entries WHERE seq=?", (k + 1,)
            ).fetchone()
            sql = "UPDATE entries SET record=?, signature=?, hash=?, key_id=? WHERE seq=?"
            db.execute(sql, (*b, k))
            db.execute(sql, (*a, k + 1))
            text = f"swapped the contents of entries {k} and {k + 1}"
        elif action == "replace-signature":
            db.execute("UPDATE entries SET signature=? WHERE seq=?", (bytes(range(64)), k))
            text = f"replaced the signature of entry {k} with other bytes"
        elif action == "resign":
            rows = db.execute("SELECT seq, record FROM entries ORDER BY seq").fetchall()
            attacker = Signer.generate()
            device = parse_canonical(bytes(rows[0][1]))["device_id"]
            previous = genesis_hash(device)
            for seq, record in rows:
                signature = attacker.sign(bytes(record))
                digest = link_hash(previous, bytes(record), signature)
                db.execute(
                    "UPDATE entries SET signature=?, hash=?, key_id=? WHERE seq=?",
                    (signature, digest, attacker.key_id, seq),
                )
                previous = digest
            text = f"re-signed all {n} entries with a different key (id {attacker.key_id}) and rebuilt the chain"
        elif action == "truncate":
            if not 1 <= count < n:
                raise SystemExit(f"--count must be between 1 and {n - 1}")
            db.execute("DELETE FROM entries WHERE seq >= ?", (n - count,))
            text = f"removed the last {count} entries (now {n - count} remain)"
        else:
            raise SystemExit(f"unknown action {action!r}")
        db.commit()
        return text
    finally:
        db.close()


def _public_key(ledger: Path, option: str | None) -> bytes:
    file = Path(option) if option else ledger.with_suffix(".pubkey")
    if not file.exists():
        raise SystemExit(f"public key file not found: {file} (use --public-key)")
    return bytes.fromhex(file.read_text(encoding="utf-8").strip())


def run_action(
    source: Path, action: str, public_key: bytes, out_dir: Path, entry, count
) -> list[str]:
    copy = make_copy(source, out_dir, action)
    description = apply_action(copy, action, entry, count)
    with Ledger.open(copy) as ledger:
        entries, anchor = ledger.read_entries(), ledger.latest_anchor()
    lines = [f"[{action}] {description}"]
    if action == "truncate":
        lines.append(f"    without an anchor: {verify_chain(entries, public_key)}")
        lines.append(f"    with the anchor:   {verify_chain(entries, public_key, anchor)}")
    else:
        lines.append(f"    verify_chain:      {verify_chain(entries, public_key, anchor)}")
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tamper with a COPY of a ledger and verify it.")
    parser.add_argument("ledger", help="a ledger file written by python -m edge run")
    parser.add_argument("action", choices=(*ACTIONS, "all"))
    parser.add_argument("--entry", type=int, help="entry to change (default: the middle one)")
    parser.add_argument(
        "--count", type=int, default=5, help="entries to cut for truncate (default 5)"
    )
    parser.add_argument(
        "--public-key", help="file with the public key in hex (default LEDGER.pubkey)"
    )
    parser.add_argument("--out-dir", help="where the tampered copies go (default: a temp folder)")
    args = parser.parse_args(argv)
    source = Path(args.ledger)
    if not source.exists():
        print(f"ledger not found: {source}", file=sys.stderr)
        return 2
    public_key = _public_key(source, args.public_key)
    out_dir = Path(args.out_dir) if args.out_dir else Path(tempfile.mkdtemp(prefix="pg_tamper_"))
    out_dir.mkdir(parents=True, exist_ok=True)
    before = source.read_bytes()
    with Ledger.open(source) as ledger:
        entries, anchor = ledger.read_entries(), ledger.latest_anchor()
    print(f"Original: {verify_chain(entries, public_key, anchor)}")
    for action in ACTIONS if args.action == "all" else (args.action,):
        for line in run_action(source, action, public_key, out_dir, args.entry, args.count):
            print(line)
    print(f"Tampered copies are in {out_dir}; the original ledger was not changed.")
    print(
        "Note: signatures and the chain protect records AFTER signing. They do not stop a lie at the "
        "sensor before the device signs it."
    )
    if source.read_bytes() != before:  # pragma: no cover - sanity check
        print("WARNING: the original ledger file changed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
