"""Phase 5 check (part of scripts/run_checks.py): the planner's oracle, determinism and decision log.

1. The oracle of master brief section 3.5 is reproduced exactly (continue: expected 4,000 and CVaR
   50,000; reroute: expected 5,250 and CVaR 10,000; expected-loss-optimal continue, CVaR-optimal
   reroute).
2. One plan is run twice with the same seed (identical numbers) and the decision is written to a
   signed decision log, which verifies; an edited copy is detected.
3. An untrusted shipment is never auto-approved.

The planner recommends; it never executes. Numbers are illustrative placeholders.
"""
# ruff: noqa: E501  (long literal lines)

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from edge.chain import Entry, Ledger, Signer  # noqa: E402
from planner.config import load_planner_config  # noqa: E402
from planner.core import plan  # noqa: E402
from planner.cvar import choose_action, cvar_discrete, expected_discrete  # noqa: E402
from planner.governance import HUMAN, build_decision  # noqa: E402
from planner.pipeline import build_inputs  # noqa: E402
from planner.records import DecisionLog, canonical_bytes, parse_canonical, verify_decision_log  # noqa: E402
from shared.config import load_box_config, load_product_config  # noqa: E402


def main() -> int:
    problems: list[str] = []
    cont, reroute = [(0.0, 0.92), (50_000.0, 0.08)], [(5_000.0, 0.995), (55_000.0, 0.005)]
    got = (
        expected_discrete(cont), cvar_discrete(cont, 0.95),
        expected_discrete(reroute), cvar_discrete(reroute, 0.95),
    )  # fmt: skip
    if any(
        abs(a - b) > 1e-6 for a, b in zip(got, (4_000.0, 50_000.0, 5_250.0, 10_000.0), strict=True)
    ):
        problems.append(f"oracle not reproduced: {got}")
    table = {
        "continue": {"expected": got[0], "cvar": got[1], "cost": 0.0},
        "reroute": {"expected": got[2], "cvar": got[3], "cost": 5_000.0},
    }
    if (
        choose_action(table, "expected", ["continue", "reroute"]),
        choose_action(table, "cvar", ["continue", "reroute"]),
    ) != ("continue", "reroute"):
        problems.append("oracle optimal actions differ")

    cfg, product, box = load_planner_config(), load_product_config(), load_box_config()
    recordings = REPO_ROOT / "data" / "recordings"
    clean = build_inputs(recordings / "baseline_ok.jsonl", 24.0, product, box)
    bad = build_inputs(recordings / "hidden_spoilage.jsonl", 50.0, product, box)
    results = []
    for _ in range(2):
        t = plan(clean.inputs, cfg, product, clean.twin, clean.setpoint_c)
        results.append([(r.expected_loss, r.var, r.cvar) for r in t.results.values()])
    if results[0] != results[1]:
        problems.append("the same seed gave different results")
    decision_bad = build_decision(
        plan(bad.inputs, cfg, product, bad.twin, bad.setpoint_c), bad.inputs, cfg
    )
    if decision_bad.route != HUMAN:
        problems.append("an untrusted shipment was auto-approved")
    with tempfile.TemporaryDirectory(prefix="pg_phase5_") as tmp:
        signer = Signer.generate()  # throw-away, never stored
        ledger = Ledger.create("check", tmp)
        log = DecisionLog(cfg.planner_id, signer, ledger)
        log.append_decision(
            build_decision(
                plan(clean.inputs, cfg, product, clean.twin, clean.setpoint_c), clean.inputs, cfg
            )
        )
        log.append_decision(decision_bad)
        log.anchor()
        entries, anchor = ledger.read_entries(), ledger.latest_anchor()
        ledger.close()
        if not verify_decision_log(entries, signer.public_key_bytes, anchor).ok:
            problems.append("the decision log does not verify")
        record = parse_canonical(entries[1].record)
        record["route"] = "auto_approved"
        e = entries[1]
        forged = [entries[0], Entry(e.seq, canonical_bytes(record), e.signature, e.hash, e.key_id)]
        if verify_decision_log(forged, signer.public_key_bytes, anchor).ok:
            problems.append("an edited decision was not detected")
    for problem in problems:
        print(f"FAIL: {problem}")
    if not problems:
        print(
            "phase 5 check: oracle exact, same seed same numbers, untrusted never auto-approved, log verifies"
        )
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
