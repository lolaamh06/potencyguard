"""Phase 6 check (part of scripts/run_checks.py): the backend end to end, in process.

1. A device key is registered, a recording is run through the edge runner and posted through the
   API; the chain verifies and a decision is auto-approved (mock enterprise event).
2. A tampered copy of the ledger is rejected, the shipment is quarantined and no decision is made.
3. The database refuses UPDATE and DELETE; the sandbox adapter is an unimplemented stub.
4. The golden recordings and shared hashes are unchanged.

No authentication in this phase. Simulation on a synthetic box.
"""

# ruff: noqa: E501, E402

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
import warnings
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
for p in (str(REPO_ROOT), str(REPO_ROOT / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

warnings.filterwarnings("ignore", message=".*starlette.testclient.*")
import tamper_demo
from fastapi.testclient import TestClient

from backend.api import create_app
from backend.config import load_backend_config
from backend.replay import entries_to_json
from backend.sap import SandboxSapAdapter
from backend.storage import Store
from edge.chain import Ledger, Signer
from edge.runner import run_recording
from shared.config import load_box_config, load_product_config


def main() -> int:
    problems: list[str] = []
    device = "pg-check-device"
    with tempfile.TemporaryDirectory(prefix="pg_phase6_") as tmp:
        tmp_path = Path(tmp)
        cfg = load_backend_config().model_copy(
            update={"database": str(tmp_path / "backend.sqlite")}
        )
        store = Store(cfg.database_path())
        client = TestClient(
            create_app(cfg, store, str(tmp_path / "planner-key")), raise_server_exceptions=False
        )
        signer = Signer.generate()  # throw-away, never stored
        r = client.post(
            "/devices/register",
            json={
                "device_id": device,
                "public_key_hex": signer.public_key_bytes.hex(),
                "registered_by": "phase-6-check",
            },
        )
        if r.status_code != 201:
            problems.append(f"registration failed: {r.status_code}")
        product, box = load_product_config(), load_box_config()
        run = run_recording(
            REPO_ROOT / "data" / "recordings" / "baseline_ok.jsonl",
            product,
            box,
            signer,
            device,
            tmp_path,
            "check",
        )
        with Ledger.open(run.ledger_path) as ledger:
            entries, anchor = ledger.read_entries(), ledger.latest_anchor()
        header = json.loads(
            (REPO_ROOT / "data" / "recordings" / "baseline_ok.jsonl")
            .open(encoding="utf-8")
            .readline()
        )
        duration = (header["n_samples"] - 1) * header["sample_interval_s"] / 3600.0
        for sid, copy_action in (("good", None), ("bad", "edit")):
            client.post(
                "/shipments",
                json={
                    "shipment_id": sid,
                    "label": "baseline_ok",
                    "device_id": device,
                    "origin": "replay",
                    "scheduled_duration_h": duration,
                },
            )
            use, use_anchor = entries, anchor
            if copy_action:
                copy = tamper_demo.make_copy(run.ledger_path, tmp_path, copy_action)
                tamper_demo.apply_action(copy, copy_action, None, 5)
                with Ledger.open(copy) as ledger:
                    use, use_anchor = ledger.read_entries(), ledger.latest_anchor()
            else:
                use, use_anchor = entries[:145], None  # the first 24 hours
            ingest = client.post(
                f"/shipments/{sid}/ledger", json=entries_to_json(use, use_anchor)
            ).json()
            decide = client.post(f"/shipments/{sid}/decide", json={})
            if sid == "good":
                if ingest.get("chain_status") != "verified":
                    problems.append(f"good ledger not verified: {ingest}")
                body = decide.json()
                if (
                    decide.status_code != 201
                    or body.get("route") != "auto_approved"
                    or len(body.get("sap_events", [])) != 1
                ):
                    problems.append(f"good shipment not auto-approved: {decide.status_code} {body}")
            else:
                if ingest.get("chain_status") != "rejected" or decide.status_code != 409:
                    problems.append("tampered ledger not rejected and refused")
                if client.get(f"/shipments/{sid}").json()["status"] != "quarantined_pending_review":
                    problems.append("tampered shipment not quarantined")
        db = sqlite3.connect(store.path)
        try:
            db.execute("DELETE FROM api_audit")
            problems.append("the database allowed a DELETE")
        except sqlite3.DatabaseError:
            pass
        db.close()
        try:
            SandboxSapAdapter().lookup_acknowledgement("x")
            problems.append("the sandbox adapter did not raise")
        except NotImplementedError:
            pass
        client.close()
        store.close()
    expected = json.loads(
        (REPO_ROOT / "shared" / "golden_sha256.json").read_text(encoding="utf-8")
    )["sha256"]
    for relative, digest in expected.items():
        if hashlib.sha256((REPO_ROOT / relative).read_bytes()).hexdigest().upper() != digest:
            problems.append(f"{relative} changed")
    for problem in problems:
        print(f"FAIL: {problem}")
    if not problems:
        print(
            "phase 6 check: registered key, good ledger decided, tampered ledger rejected and quarantined, storage append-only"
        )
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
