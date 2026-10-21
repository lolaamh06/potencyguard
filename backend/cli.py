"""python -m backend: serve, replay, export-ledger (Phase 6).

No authentication in this phase: the server binds to 127.0.0.1 by default and must not be exposed.
Simulation on a synthetic box. Signing does not stop a lie at the sensor (A18).
"""
# ruff: noqa: E501  (long literal lines)

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from backend.config import load_backend_config
from backend.replay import DEMO_CHECKPOINTS, TAMPER_ACTIONS, entries_to_json, run_replay
from edge.chain import Ledger
from shared.config import REPO_ROOT

RECORDINGS = REPO_ROOT / "data" / "recordings"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m backend")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser(
        "serve", help="run the API server (127.0.0.1 by default, NO authentication)"
    )
    serve.add_argument("--config", help="backend settings (default config/backend.yaml)")
    serve.add_argument("--host", help="override the bind address (keep 127.0.0.1)")
    serve.add_argument("--port", type=int)
    serve.add_argument("--db", help="database file (default from the settings)")
    serve.add_argument("--key-dir", help="folder of the backend planner key")
    replay = sub.add_parser(
        "replay", help="a recording through the edge runner into an in-process API"
    )
    which = replay.add_mutually_exclusive_group(required=True)
    which.add_argument("--recording", metavar="FILE")
    which.add_argument("--all", action="store_true", help="the six demo checkpoints")
    replay.add_argument("--at-hour", type=float, help="post only the first H hours")
    replay.add_argument(
        "--tamper", choices=TAMPER_ACTIONS, help="tamper with the ledger copy first"
    )
    replay.add_argument("--key-dir", help="folder of the device key (default outside the repo)")
    replay.add_argument(
        "--db", help="database file for this replay (default a new file under data/runs)"
    )
    export = sub.add_parser(
        "export-ledger", help="write the JSON body for POST /shipments/{id}/ledger"
    )
    export.add_argument("--ledger", required=True)
    export.add_argument("--out", required=True)
    export.add_argument("--no-anchor", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None, out=None) -> int:
    out = out or sys.stdout
    args = build_parser().parse_args(argv)
    if args.command == "serve":
        import uvicorn

        from backend.api import create_app
        from backend.storage import Store

        cfg = load_backend_config(args.config)
        if args.host:
            cfg = cfg.model_copy(update={"host": args.host})
        if args.port:
            cfg = cfg.model_copy(update={"port": args.port})
        if args.db:
            cfg = cfg.model_copy(update={"database": args.db})
        if cfg.host not in ("127.0.0.1", "localhost", "::1"):
            print(
                "WARNING: there is NO authentication; do not bind to a public address.",
                file=sys.stderr,
            )
        app = create_app(cfg, Store(cfg.database_path()), args.key_dir)
        print(
            f"Serving on http://{cfg.host}:{cfg.port} (no authentication; simulation only)",
            file=out,
        )
        uvicorn.run(app, host=cfg.host, port=cfg.port, log_level="warning")
        return 0
    if args.command == "export-ledger":
        with Ledger.open(args.ledger) as ledger:
            entries, anchor = (
                ledger.read_entries(),
                (None if args.no_anchor else ledger.latest_anchor()),
            )
        Path(args.out).write_text(
            json.dumps(entries_to_json(entries, anchor)), encoding="utf-8", newline="\n"
        )
        print(f"wrote {args.out} ({len(entries)} entries)", file=out)
        return 0
    if args.all:
        jobs = [(RECORDINGS / f"{name}.jsonl", hour) for name, hour in DEMO_CHECKPOINTS]
    else:
        path = Path(args.recording)
        if not path.exists():
            print(f"recording not found: {path}", file=sys.stderr)
            return 2
        jobs = [(path, args.at_hour)]
    db = Path(args.db) if args.db else None
    return run_replay(jobs, args.tamper, args.key_dir, db, out)
