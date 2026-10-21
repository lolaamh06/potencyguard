# ruff: noqa: E501
"""Export the data the Story chapters need (Phase F3): `dashboard/public/story/` and the bundled
Chapter 1 figures in `dashboard/src/data/bundled/`.

Read-only use of the existing engine, planner and backend. Deterministic: seeds are recorded in
each file. The front end only displays these numbers (the one exception is the tested potency
mirror for the Chapter 1 scrub). Everything is for an imaginary product on synthetic data.

    python scripts/export_story.py [--out DIR]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import export_replay  # noqa: E402

from backend.replay import make_replay_app, replay_recording  # noqa: E402
from planner.cvar import cvar_discrete, cvar_sample, expected_discrete, var_sample  # noqa: E402

LABEL = "Illustrative product, model output"
OUT = REPO / "dashboard" / "public" / "story"
BUNDLED = REPO / "dashboard" / "src" / "data" / "bundled"
SEED = 20261021
ALPHAS = [round(i / 100, 2) for i in range(0, 100)]  # 0.00 to 0.99
N_POINTS = 5000
V = 50_000.0
ACTIONS = {"continue": (0.0, 0.08), "reroute": (5_000.0, 0.005)}  # cost, failure probability


def _generate_data():  # the Phase F1 generator, reused for Chapter 1 and the chain ribbon
    path = REPO / "docs" / "01-architecture" / "style-frames" / "generate_data.py"
    spec = importlib.util.spec_from_file_location("f1_generate_data", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["f1_generate_data"] = module
    spec.loader.exec_module(module)
    return module


def _write(path: Path, obj: dict, indent: int | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(
            obj, handle, indent=indent, sort_keys=True, separators=None if indent else (",", ":")
        )
        handle.write("\n")
    return path


def chapter1() -> dict:
    data = _generate_data().chapter1()
    data["label"] = LABEL
    data["provenance_note"] = (
        "Figures for the active profile are shown on the page; the reference-profile figures "
        "are kept for the Provenance drawer."
    )
    return data


def chapter5() -> dict:
    rng = np.random.default_rng(SEED)
    actions: dict = {}
    losses_by_action = {}
    for name, (cost, p_fail) in ACTIONS.items():
        failed = rng.random(N_POINTS) < p_fail
        losses = cost + V * failed
        order = np.argsort(-losses, kind="stable")
        rank = np.empty(N_POINTS, dtype=int)
        rank[order] = np.arange(N_POINTS)
        losses_by_action[name] = losses
        actions[name] = {
            "cost": cost,
            "failure_probability": p_fail,
            "failed": [int(f) for f in failed],
            "rank": [int(r) for r in rank],
        }
    rows = []
    for alpha in ALPHAS:
        row: dict = {
            "alpha": alpha,
            "tail_points": int(np.ceil((1 - alpha) * N_POINTS - 1e-9)),
            "actions": {},
        }
        for name, (cost, p_fail) in ACTIONS.items():
            outcomes = [(cost, 1.0 - p_fail), (cost + V, p_fail)]
            row["actions"][name] = {
                "expected_loss": expected_discrete(outcomes),
                "cvar": cvar_discrete(outcomes, alpha),
                "var_sample": var_sample(losses_by_action[name], alpha),
                "cvar_sample": cvar_sample(losses_by_action[name], alpha),
            }
        row["recommended"] = min(row["actions"], key=lambda n: row["actions"][n]["cvar"])
        rows.append(row)
    return {
        "label": LABEL,
        "note": "Textbook example from the master brief (illustrative placeholders), seeded draws from its two actions. The page only selects rows.",
        "seed": SEED, "n_points": N_POINTS, "V": V, "alpha_grid": "0.00 to 0.99, step 0.01",
        "actions": actions, "rows": rows,
        "source": "planner.cvar (exact discrete functions and the sample functions); numpy default_rng(seed)",
    }  # fmt: skip


def chapter6() -> dict:
    gen = _generate_data()
    chain = gen.control_room()["chain"]
    with tempfile.TemporaryDirectory(prefix="pg_f3_") as tmp:
        app, store, _ = make_replay_app(db=Path(tmp) / "story.sqlite")
        from fastapi.testclient import TestClient  # noqa: PLC0415

        try:
            with TestClient(app) as client:
                path = REPO / "data" / "recordings" / "hidden_spoilage.jsonl"
                summary = replay_recording(client, path, export_replay._signer(), Path(tmp), 50.0)
                task = client.get("/approvals").json()["items"][0]
                tampered = replay_recording(
                    client,
                    path,
                    export_replay._signer(),
                    Path(tmp),
                    50.0,
                    "edit",
                    "hidden_spoilage_edited",
                    False,
                )
        finally:
            store.close()
    curve = task["potency_curve"][::6]
    return {
        "label": LABEL,
        "scenario_id": "hidden_spoilage",
        "checkpoint_h": 50.0,
        "card": {
            "potency_curve": curve,
            "alternatives": [
                {
                    k: a[k]
                    for k in ("action", "cost", "failure_probability", "expected_loss", "cvar")
                }
                for a in task["alternatives"]
            ],
            "chosen_action": task["chosen_action"],
            "chain_status": task["chain_status"],
            "reason": task["reason"],
            "explanation": task["explanation"],
            "trust_level": summary.decision["trust_level"],
            "verdict": summary.decision["verdict"],
            "route": summary.decision["route"],
        },
        "chain": {
            "device_id": chain["device_id"],
            "key_id": chain["key_id"],
            "entries_total": chain["entries_total"],
            "intact_result": chain["intact_result"],
            "tampered_result": chain["tampered_result"],
            "tamper": chain["tamper"],
            "first_broken_index": chain["first_broken_index"],
            "reason": chain["reason"],
            "ribbon": chain["ribbon"],
        },
        "backend_check": {
            "chain_status": tampered.chain_status,
            "reason": tampered.chain_reason,
            "first_bad_index": tampered.first_bad_index,
            "decision_refused": tampered.decision_refused,
            "notes": tampered.notes,
        },
        "limit": "The signature shows the record has not changed since it was signed. It does not show the sensor told the truth.",
    }


def export_all(out_dir: Path = OUT, bundled_dir: Path = BUNDLED) -> list[Path]:
    return [
        _write(bundled_dir / "chapter1.json", chapter1(), indent=1),
        _write(out_dir / "chapter5.json", chapter5()),
        _write(out_dir / "chapter6.json", chapter6(), indent=None),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    for path in export_all(args.out):
        print(f"wrote {path} ({path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
