"""Headless end-to-end flow: a recording through the edge runner into the API (Phase 6).

`replay_recording` builds an in-process app with a NEW database, registers a device key, creates a
shipment, runs the recording through the real edge runner (signed ledger), posts the ledger through
the app with the test client, triggers a decision and prints what happened. Nothing is resolved
automatically. With a tamper action the ledger copy is changed first (scripts/tamper_demo.py) and the
backend is expected to reject it, quarantine the shipment and refuse to decide.

Signing protects records after signing and does not stop a lie at the sensor (A18). Simulation on a
synthetic box. No authentication in this phase.
"""
# ruff: noqa: E501, E402  (long literal lines; the warning filter must come before the import)

from __future__ import annotations

import sys
import tempfile
import warnings
from dataclasses import dataclass, field
from pathlib import Path

warnings.filterwarnings(
    "ignore", message=".*httpx.*starlette.testclient.*", category=DeprecationWarning
)
warnings.filterwarnings("ignore", message=".*starlette.testclient.*")

from fastapi.testclient import TestClient  # noqa: E402

from backend.api import create_app
from backend.config import BackendConfig, load_backend_config
from backend.storage import Store
from edge.chain import Anchor, Entry, Ledger, Signer, load_or_create_signer
from edge.runner import run_recording
from shared.config import REPO_ROOT, load_box_config, load_product_config

DEMO_CHECKPOINTS = (
    ("baseline_ok", 24.0),
    ("door_open_excursion", 12.0),
    ("reefer_failure", 20.0),
    ("heatwave_transit", 40.0),
    ("spoof_attempt", 20.0),
    ("hidden_spoilage", 50.0),
)
TAMPER_ACTIONS = ("edit", "delete", "reorder", "resign", "truncate")
REPLAY_DEVICE = "pg-replay-001"


def entries_to_json(entries: list[Entry], anchor: Anchor | None) -> dict:
    """The body of POST /shipments/{id}/ledger for these entries."""
    body: dict = {
        "entries": [
            {"seq": e.seq, "record_hex": e.record.hex(), "signature_hex": e.signature.hex(),
             "hash_hex": e.hash.hex(), "key_id": e.key_id}
            for e in entries
        ]
    }  # fmt: skip
    if anchor is not None:
        body["anchor"] = {
            "seq": anchor.seq, "head_hex": anchor.head.hex(), "statement_hex": anchor.statement.hex(),
            "signature_hex": anchor.signature.hex(), "key_id": anchor.key_id,
        }  # fmt: skip
    return body


@dataclass
class ReplaySummary:
    recording: str
    shipment_id: str
    entries: int = 0
    chain_status: str = ""
    chain_reason: str = ""
    first_bad_index: int | None = None
    trust_level: str | None = None
    verdict: str | None = None
    potency: float | None = None
    decision: dict | None = None
    decision_refused: str | None = None
    status: str | None = None
    sap_events: list = field(default_factory=list)
    notes: list = field(default_factory=list)

    def lines(self) -> list[str]:
        out = [f"Recording {self.recording} -> shipment {self.shipment_id}"]
        out.append(f"  entries ingested  {self.entries}")
        chain = self.chain_status + (
            ""
            if self.chain_reason in ("", "ok")
            else f" ({self.chain_reason} at entry {self.first_bad_index})"
        )
        out.append(f"  chain status      {chain}")
        out.append(f"  shipment status   {self.status}")
        if self.trust_level:
            out.append(
                f"  trust level       {self.trust_level} (verdict {self.verdict}, potency {self.potency * 100:.3f} percent, recomputed)"
            )
        if self.decision:
            d = self.decision
            flag = " (CLOSE CALL)" if d["close_call"] else ""
            out.append(
                f"  decision          {d['chosen_action']} (expected-loss-optimal {d['expected_loss_optimal_action']}){flag}"
            )
            out.append(f"  route             {d['route']}")
            for reason in d["reasons"]:
                out.append(f"    - {reason}")
        if self.decision_refused:
            out.append(f"  decision          REFUSED: {self.decision_refused}")
        out.append(
            f"  events dispatched {len(self.sap_events)}"
            + "".join(f" [{e['ack_id']} {e['provenance']}]" for e in self.sap_events)
        )
        out.extend(f"  note: {n}" for n in self.notes)
        return out


def _import_tamper_demo():
    scripts = str(REPO_ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import tamper_demo

    return tamper_demo


def replay_recording(
    client: TestClient,
    recording: Path,
    signer: Signer,
    work_dir: Path,
    at_hour: float | None = None,
    tamper: str | None = None,
    shipment_id: str | None = None,
    register: bool = True,
) -> ReplaySummary:
    product, box = load_product_config(), load_box_config()
    name = shipment_id or recording.stem
    summary = ReplaySummary(recording.name, name)
    caller = {"X-Caller": "replay-driver"}
    if register:
        client.post("/devices/register", headers=caller, json={
            "device_id": REPLAY_DEVICE, "public_key_hex": signer.public_key_bytes.hex(),
            "registered_by": "replay-operator", "note": "demo registration"})  # fmt: skip
    duration_h = _duration_h(recording)
    r = client.post("/shipments", headers=caller, json={
        "shipment_id": name, "label": recording.stem, "device_id": REPLAY_DEVICE,
        "origin": "replay", "scheduled_duration_h": duration_h})  # fmt: skip
    r.raise_for_status()
    run = run_recording(recording, product, box, signer, REPLAY_DEVICE, work_dir, f"replay_{name}")
    ledger_path = run.ledger_path
    if tamper:
        demo = _import_tamper_demo()
        copy = demo.make_copy(ledger_path, work_dir, f"tampered_{tamper}")
        summary.notes.append(
            f"the ledger copy was tampered with ({demo.apply_action(copy, tamper, None, 5)})"
        )
        ledger_path = copy
    with Ledger.open(ledger_path) as ledger:
        entries, anchor = ledger.read_entries(), ledger.latest_anchor()
    if at_hour is not None:
        keep = [e for e in entries if _t_h(e) <= at_hour + 1e-9]
        if len(keep) < len(entries):
            entries, anchor = keep, None
            summary.notes.append(
                f"only the first {at_hour:g} hours were posted (no anchor: it names the last entry)"
            )
    r = client.post(
        f"/shipments/{name}/ledger", headers=caller, json=entries_to_json(entries, anchor)
    )
    r.raise_for_status()
    ingest = r.json()
    summary.entries = ingest["entries"]
    summary.chain_status, summary.chain_reason = ingest["chain_status"], ingest["reason"]
    summary.first_bad_index = ingest["first_bad_index"]
    d = client.post(f"/shipments/{name}/decide", headers=caller, json={})
    if d.status_code == 201:
        summary.decision = d.json()
        summary.sap_events = summary.decision["sap_events"]
    else:
        summary.decision_refused = d.json().get("message", d.text)
    view = client.get(f"/shipments/{name}").json()
    summary.status = view["status"]
    if view["latest"]:
        summary.trust_level, summary.verdict = (
            view["latest"]["trust_level"],
            view["latest"]["verdict"],
        )
        summary.potency = view["latest"]["potency"]
    return summary


def _duration_h(recording: Path) -> float:
    import json

    header = json.loads(recording.open(encoding="utf-8").readline())
    return (header["n_samples"] - 1) * header["sample_interval_s"] / 3600.0


def _t_h(entry: Entry) -> float:
    from edge.chain.canonical import parse_canonical

    return parse_canonical(entry.record)["t_ms"] / 3_600_000


def make_replay_app(
    cfg: BackendConfig | None = None, key_dir: str | None = None, db: Path | None = None
):
    """An in-process app with a NEW database file (never the long-running server's)."""
    cfg = cfg or load_backend_config()
    path = db or cfg.database_path().with_name(f"backend_replay_{_stamp()}.sqlite")
    store = Store(path)
    app = create_app(cfg, store, key_dir)
    return app, store, path


def _stamp() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")


def run_replay(
    recordings: list[tuple[Path, float | None]],
    tamper: str | None,
    key_dir: str | None,
    db: Path | None,
    out,
) -> int:
    signer = load_or_create_signer(key_dir)
    app, store, path = make_replay_app(key_dir=None, db=db)
    work = Path(tempfile.mkdtemp(prefix="pg_replay_"))
    problems = 0
    with TestClient(app) as client:
        first = True
        for recording, hour in recordings:
            summary = replay_recording(
                client, recording, signer, work, hour, tamper, register=first
            )
            first = False
            for line in summary.lines():
                print(line, file=out)
            problems += summary.chain_status != "verified" and not tamper
        audit = client.get("/audit").json()["total"]
        provenance = client.get(f"/provenance/{recordings[0][0].stem}").json()
    print(
        f"Database {path}; {audit} audit rows; enterprise adapter mode {provenance['sap_adapter_mode']}; "
        "no authentication in this phase.",
        file=out,
    )
    print("Simulation result on a synthetic box. Not real-world evidence.", file=out)
    store.close()
    return 1 if problems else 0
