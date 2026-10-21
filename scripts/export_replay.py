"""Export replay files for the five featured scenarios (Phase F2): `dashboard/public/replay/`.

Read-only use of the existing pipeline: the recorded sensor feed goes through the trust assessor
(thermal twin, detectors, potency tracker), the planner decides at a fixed checkpoint, and the
signed ledger of the whole run is verified. Nothing here changes a recording or any existing
code. The output is deterministic: no clock, no randomness beyond the seeds recorded in each
file. The ledger is signed with a TEST-ONLY key derived from a public seed inside this script;
no key is written to disk.

    python scripts/export_replay.py [--out DIR]

All figures are model outputs for an imaginary product on synthetic data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from backend.replay import ReplaySummary, make_replay_app, replay_recording  # noqa: E402
from backend.service import SOFTWARE_VERSION  # noqa: E402
from edge.assessment import TrustAssessor  # noqa: E402
from edge.chain import Ledger, Signer, verify_chain  # noqa: E402
from edge.recorded_source import RecordedSource  # noqa: E402
from edge.runner import run_recording  # noqa: E402
from edge.tamper_monitor import TamperMonitor  # noqa: E402
from planner.config import load_planner_config  # noqa: E402
from shared.config import load_box_config, load_product_config  # noqa: E402

SCHEMA_VERSION = "1"
FRAME_STEP = 3  # keep every third sample (30 minutes) so the files stay small
DEVICE_ID = "pg-replay-demo"
DEFAULT_OUT = REPO / "dashboard" / "public" / "replay"

PRODUCT_LABEL = "Illustrative product, model output"
DATA_LABEL = "Synthetic data, simulated sensor feed"

# scenario code name -> (label, checkpoint in hours)
SCENARIOS: dict[str, tuple[str, float]] = {
    "baseline_ok": ("A normal journey", 24.0),
    "door_open_excursion": ("A door left open, a short excursion", 12.0),
    "reefer_failure": ("Cooling fails and stays failed", 20.0),
    "spoof_attempt": ("The sensor feed is falsified", 20.0),
    "hidden_spoilage": ("Falsified feed that hides real spoilage", 50.0),
}

ROUTE = {
    "origin": {"lat": 50.11, "lon": 8.68, "label": "Origin (illustrative)"},
    "destination": {"lat": 1.35, "lon": 103.82, "label": "Destination (illustrative)"},
    "alternative": [{"lat": 25.2, "lon": 55.3, "label": "Alternative stop (illustrative)"}],
}


def _round(value: float | None, digits: int = 4) -> float | None:
    return None if value is None else round(float(value), digits)


def _series(path: Path, product, box):  # noqa: ANN001
    """Run the recorded feed through the trust assessor; return frames, events and the header."""
    source = RecordedSource(path)
    source.start()
    assessor = TrustAssessor(product, TamperMonitor.from_defaults(product, box))
    frames: list[dict] = []
    events: list[dict] = []
    seen_flags: set[str] = set()
    last_verdict = ""
    index = 0
    try:
        while (reading := source.read()) is not None:
            assessment, potency, state = assessor.update(reading)
            t_s = float(reading.t_s)
            for name, flag in (
                ("cusum_neg", state.flag_cusum_neg),
                ("cusum_pos", state.flag_cusum_pos),
                ("impossible_step", state.flag_step),
                ("impossible_state", state.flag_state),
                ("flat_line", state.flag_flat),
            ):
                if flag and name not in seen_flags:
                    seen_flags.add(name)
                    events.append(
                        {"t_s": t_s, "type": "physics_check_fired", "payload": {"check": name}}
                    )
            if assessment.verdict != last_verdict:
                events.append(
                    {
                        "t_s": t_s,
                        "type": "verdict_changed",
                        "payload": {"from": last_verdict or None, "to": assessment.verdict},
                    }
                )
                last_verdict = assessment.verdict
            if index % FRAME_STEP == 0:
                frames.append(
                    {
                        "t_s": t_s,
                        "temp_c": _round(reading.temp_c),
                        "ambient_c": _round(reading.ambient_c),
                        "twin_c": _round(state.predicted_c),
                        "residual_c": _round(state.residual_c),
                        "cusum_neg": _round(state.cusum_neg),
                        "cusum_pos": _round(state.cusum_pos),
                        "potency": _round(potency.potency, 9),
                        "tau_eq_h": _round(potency.tau_eq_h, 6),
                        "shelf_life_used_fraction": _round(potency.shelf_life_used_fraction, 9),
                        "mkt_c": _round(potency.mkt_c),
                        "trust_level": assessment.trust_level,
                        "verdict": assessment.verdict,
                        "flags": {
                            "cusum": bool(state.flag_cusum_pos or state.flag_cusum_neg),
                            "step": bool(state.flag_step),
                            "state": bool(state.flag_state),
                            "flat": bool(state.flag_flat),
                        },
                    }
                )
            index += 1
    finally:
        source.close()
    return frames, events, index


def _cusum_h(product, box) -> float:  # noqa: ANN001
    return float(TamperMonitor.from_defaults(product, box).config.cusum_h)


def _header(path: Path) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.loads(handle.readline())


def _signer() -> Signer:
    return Signer.from_seed(hashlib.sha256(b"F2 replay demo key (TEST ONLY)").digest())


def backend_decision(name: str, checkpoint_h: float, tamper: str | None = None) -> ReplaySummary:
    """Drive the Phase 6 backend itself (in process, new database) for one recording.

    The decision is whatever `POST /shipments/{id}/decide` returns, so the exported route,
    table and reasons are the backend's own: nothing is recomputed or copied here.
    """
    from fastapi.testclient import TestClient  # noqa: PLC0415

    path = REPO / "data" / "recordings" / f"{name}.jsonl"
    with tempfile.TemporaryDirectory(prefix="pg_f3_") as tmp:
        app, store, _ = make_replay_app(db=Path(tmp) / "replay.sqlite")
        try:
            with TestClient(app) as client:
                summary = replay_recording(client, path, _signer(), Path(tmp), checkpoint_h, tamper)
                summary.view_json = client.get(f"/shipments/{name}").json()  # type: ignore[attr-defined]
                summary.provenance_json = client.get(f"/provenance/{name}").json()  # type: ignore[attr-defined]
                return summary
        finally:
            store.close()


def _worst_case(name: str, checkpoint_h: float, product, box) -> dict:  # noqa: ANN001
    """The planner's worst-case bound at the checkpoint: a bound, not an estimate."""
    from edge.potency import potency_from_tau_eq, shelf_life_used_fraction  # noqa: PLC0415
    from planner.pipeline import build_inputs  # noqa: PLC0415

    built = build_inputs(REPO / "data" / "recordings" / f"{name}.jsonl", checkpoint_h, product, box)
    tau = built.inputs.start_tau_eq_h
    return {
        "potency": _round(potency_from_tau_eq(tau, product), 9),
        "shelf_life_used_fraction": _round(shelf_life_used_fraction(tau, product), 9),
        "bound_used": bool(built.inputs.bound_used),
        "label": "worst-case bound, not an estimate",
    }


def _decision(name: str, checkpoint_h: float, product=None, box=None) -> dict:  # noqa: ANN001
    summary = backend_decision(name, checkpoint_h)
    d = summary.decision
    if d is None:
        raise RuntimeError(f"the backend refused a decision for {name}: {summary.decision_refused}")
    actions = [
        {
            "name": row["action"],
            "cost": row["cost"],
            "failure_probability": row["failure_probability"],
            "expected_loss": row["expected_loss"],
            "cvar": row["cvar"],
        }
        for row in d["table"]
    ]
    cfg = load_planner_config()
    return {
        "checkpoint_h": checkpoint_h,
        "alpha": cfg.alpha,
        "n_scenarios": cfg.n_scenarios,
        "planner_seed": cfg.seed,
        "actions": actions,
        "chosen_action": d["chosen_action"],
        "route": d["route"],
        "shipment_status": d["shipment_status"],
        "reasons": list(d["reasons"]),
        "explanation": d["explanation"],
        "close_call": d["close_call"],
        "needs_human": d["route"] != "auto_approved",
        "trust_level": d["trust_level"],
        "verdict": d["verdict"],
        "approval_task": d["approval_task"],
        "recomputed": {
            k: summary.view_json["latest"][k]  # type: ignore[attr-defined]
            for k in ("t_h", "potency", "tau_eq_h", "trust_level", "verdict", "claims_consistent")
        },
        "worst_case": _worst_case(name, checkpoint_h, product, box),
        "source": "POST /shipments/{id}/decide of the Phase 6 backend (in process)",
    }


def _provenance(name: str, checkpoint_h: float) -> dict:
    return backend_decision(name, checkpoint_h).provenance_json  # type: ignore[attr-defined]


def tamper_positions(n: int) -> list[int]:
    """Edit positions offered in the Control Room (first, quarters, last editable)."""
    return sorted({0, n // 4, n // 2, (3 * n) // 4, n - 2})


TRUNCATE_COUNT = 5


def _tamper(path: Path, product, box) -> dict:  # noqa: ANN001
    """REAL results of edits and a truncation on COPIES of the run's ledger, from verify_chain."""
    import tamper_demo  # noqa: PLC0415

    signer = _signer()
    with tempfile.TemporaryDirectory(prefix="pg_f4_") as tmp:
        run = run_recording(path, product, box, signer, DEVICE_ID, Path(tmp), "f4")
        with Ledger.open(run.ledger_path) as ledger:
            n = len(ledger.read_entries())
        edits = []
        for k in tamper_positions(n):
            copy = tamper_demo.make_copy(run.ledger_path, Path(tmp), f"edit{k}")
            note = tamper_demo.apply_action(copy, "edit", k, 1)
            with Ledger.open(copy) as ledger:
                entries, anchor = ledger.read_entries(), ledger.latest_anchor()
            result = verify_chain(entries, signer.public_key_bytes, anchor, DEVICE_ID)
            edits.append(
                {
                    "entry": k,
                    "ok": bool(result.ok),
                    "first_broken_index": result.index,
                    "reason": result.reason,
                    "text": str(result),
                    "action": note,
                }
            )
        copy = tamper_demo.make_copy(run.ledger_path, Path(tmp), "truncate")
        note = tamper_demo.apply_action(copy, "truncate", None, TRUNCATE_COUNT)
        with Ledger.open(copy) as ledger:
            entries, anchor = ledger.read_entries(), ledger.latest_anchor()
        without = verify_chain(entries, signer.public_key_bytes, None, DEVICE_ID)
        with_anchor = verify_chain(entries, signer.public_key_bytes, anchor, DEVICE_ID)
    return {
        "label": "Result of a real edit on a ledger copy (recorded)",
        "ledger_length": n,
        "edits": edits,
        "truncation": {
            "removed": TRUNCATE_COUNT,
            "action": note,
            "without_anchor": {"ok": bool(without.ok), "text": str(without)},
            "with_anchor": {
                "ok": bool(with_anchor.ok),
                "text": str(with_anchor),
                "reason": with_anchor.reason,
            },
        },
    }


def _chain(path: Path, product, box):  # noqa: ANN001
    signer = _signer()
    with tempfile.TemporaryDirectory(prefix="pg_f2_") as tmp:
        run = run_recording(path, product, box, signer, DEVICE_ID, Path(tmp), "f2")
        with Ledger.open(run.ledger_path) as ledger:
            entries = ledger.read_entries()
        result = verify_chain(entries, signer.public_key_bytes, None, DEVICE_ID)
    return {
        "device_id": DEVICE_ID,
        "key_id": signer.key_id,
        "entries_total": len(entries),
        "ok": bool(result.ok),
        "result": str(result),
        "last_hash_prefix": entries[-1].hash.hex()[:8] if entries else None,
        "anchor": None,
        "note": "No anchor: removing entries from the end of a ledger cannot be detected.",
    }


def export_one(name: str, out_dir: Path) -> Path:
    """Write one replay file and return its path."""
    label, checkpoint_h = SCENARIOS[name]
    product, box = load_product_config(), load_box_config()
    path = REPO / "data" / "recordings" / f"{name}.jsonl"
    header = _header(path)
    frames, events, n_samples = _series(path, product, box)
    decision = _decision(name, checkpoint_h, product, box)
    prov = _provenance(name, checkpoint_h)
    events.append(
        {
            "t_s": checkpoint_h * 3600.0,
            "type": "decision_proposed",
            "payload": {
                "chosen_action": decision["chosen_action"],
                "shipment_status": decision["shipment_status"],
            },
        }
    )
    events.sort(key=lambda e: (e["t_s"], e["type"]))
    document = {
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "scenario_id": name,
            "label": label,
            "source": header.get("source", "sim"),
            "recording": f"data/recordings/{name}.jsonl",
            "recording_seed": header.get("seed"),
            "sample_interval_s": header.get("sample_interval_s"),
            "frame_step": FRAME_STEP,
            "samples_in_recording": n_samples,
            "duration_h": (n_samples - 1) * float(header.get("sample_interval_s", 600.0)) / 3600.0,
            "checkpoint_h": checkpoint_h,
            "profile": "active",
            "product": {
                "Ea_over_R": product.Ea_over_R,
                "T_ref_c": product.T_ref_c,
                "tau_max_h": product.tau_max_h,
                "P_min": product.P_min,
            },
            "route": ROUTE,
            "labels": {"product": PRODUCT_LABEL, "data": DATA_LABEL},
            "cusum_h": _cusum_h(product, box),
            "software_version": SOFTWARE_VERSION,
            "generated_by": "scripts/export_replay.py",
        },
        "frames": frames,
        "events": events,
        "decision": decision,
        "chain": _chain(path, product, box),
        "tamper": _tamper(path, product, box),
        "provenance": {
            **{
                k: prov[k]
                for k in (
                    "source",
                    "scenario_id",
                    "from_replay",
                    "sap_adapter_mode",
                    "software_version",
                    "signing_key_id",
                    "simulated",
                    "note",
                )
            },
            "recording_seed": header.get("seed"),
            "planner_seed": decision["planner_seed"],
        },
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{name}.json"
    with open(target, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, indent=None, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
    return target


def export_all(out_dir: Path) -> list[Path]:
    """Write the five scenario files and an index; return every path written."""
    written = [export_one(name, out_dir) for name in SCENARIOS]
    index = {
        "schema_version": SCHEMA_VERSION,
        "scenarios": [
            {"scenario_id": name, "label": label, "file": f"{name}.json", "checkpoint_h": hours}
            for name, (label, hours) in SCENARIOS.items()
        ],
    }
    target = out_dir / "index.json"
    with open(target, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(index, handle, indent=1, sort_keys=True)
        handle.write("\n")
    written.append(target)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    for path in export_all(args.out):
        print(f"wrote {path} ({path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
