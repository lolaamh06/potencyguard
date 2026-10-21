"""python -m planner: decide, demo and human (Phase 5).

The planner recommends; it never executes. Final authority stays with QA. Illustrative placeholder
numbers, not sourced [SOURCE NEEDED]. Simulation results on a synthetic box, not real-world
evidence. Signing protects records after signing and does not stop a lie at the sensor.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from edge.chain import Ledger, load_or_create_signer, new_run_id
from planner.config import PlannerConfig, load_planner_config
from planner.core import format_table, plan
from planner.governance import build_decision, build_task, record_human_decision
from planner.pipeline import BuiltInputs, build_inputs
from planner.records import DecisionLog, parse_canonical, verify_decision_log
from shared.config import REPO_ROOT, ProductConfig, load_box_config, load_product_config

FOOTER = "Simulation result on a synthetic box. Not real-world evidence."
NOTE = (
    "Illustrative placeholder numbers (config/planner.yaml), not sourced [SOURCE NEEDED]. "
    "A recommendation only: final authority stays with QA."
)
RECORDINGS = REPO_ROOT / "data" / "recordings"
DEMO_CHECKPOINTS = (
    ("baseline_ok", 24.0),
    ("door_open_excursion", 12.0),
    ("reefer_failure", 20.0),
    ("heatwave_transit", 40.0),
    ("spoof_attempt", 20.0),
    ("hidden_spoilage", 50.0),
)


def decide_one(
    built: BuiltInputs, cfg: PlannerConfig, product: ProductConfig, log: DecisionLog | None
):
    table = plan(built.inputs, cfg, product, built.twin, built.setpoint_c)
    decision = build_decision(table, built.inputs, cfg)
    seq = None
    if log is not None:
        seq = log.next_seq
        log.append_decision(decision)
    return table, decision, seq


def _print_decision(built: BuiltInputs, table, decision, seq, out) -> None:
    i = decision.inputs
    print(
        f"Shipment {i.shipment_id} at hour {i.t_s / 3600.0:.1f} (remaining {i.remaining_h:.1f} h)",
        file=out,
    )
    print(
        f"  potency now {i.potency_now * 100:.3f} percent, tau_eq {i.tau_eq_now_h:.1f} h, "
        f"trust {i.trust_level}, verdict {i.verdict}",
        file=out,
    )
    if i.bound_used:
        print(
            f"  planning starts from the HIGH bound: tau_eq {i.start_tau_eq_h:.1f} h at "
            f"{i.start_temp_c:.1f} C (not the point estimate)",
            file=out,
        )
    print(f"  chain: {i.chain_status} ({built.chain_detail})", file=out)
    print("", file=out)
    for line in format_table(table):
        print("  " + line, file=out)
    print("", file=out)
    agree = "they DISAGREE" if decision.disagree else "they agree"
    print(
        f"  CVaR-optimal {decision.chosen_action}; expected-loss-optimal "
        f"{decision.expected_optimal_action} ({agree})",
        file=out,
    )
    print(
        f"  route: {decision.route}; shipment status: {decision.shipment_status}"
        + ("" if seq is None else f"; log entry {seq}"),
        file=out,
    )
    for reason in decision.reasons:
        print(f"    - {reason}", file=out)
    print(f"  {decision.explanation}", file=out)


def _open_log(cfg: PlannerConfig, args, label: str):
    signer = load_or_create_signer(args.key_dir)
    ledger = Ledger.create(new_run_id(label), args.log_dir)
    return signer, ledger, DecisionLog(cfg.planner_id, signer, ledger)


def cmd_decide(args, out) -> int:
    cfg = load_planner_config(args.config)
    if args.seed is not None:
        cfg = cfg.model_copy(update={"seed": args.seed})
    product, box = load_product_config(), load_box_config()
    path = Path(args.recording)
    if not path.exists():
        print(f"recording not found: {path}", file=sys.stderr)
        return 2
    try:
        built = build_inputs(
            path, args.at_hour, product, box, args.remaining_hours, args.shipment_id,
            args.ledger, args.public_key,
        )  # fmt: skip
    except (ValueError, OSError) as exc:
        print(f"cannot plan: {exc}", file=sys.stderr)
        return 2
    signer, ledger, log = _open_log(cfg, args, f"decision_{path.stem}")
    try:
        table, decision, seq = decide_one(built, cfg, product, log)
        log.anchor()
        _print_decision(built, table, decision, seq, out)
        task = build_task(decision, built.potency_curve, seq)
        if task is not None:
            print(
                f"  A human approval task was created ({len(task.potency_curve)} curve points, "
                "alternatives, chain status, reason).",
                file=out,
            )
        entries = ledger.read_entries()
        result = verify_decision_log(entries, signer.public_key_bytes, ledger.latest_anchor())
        ledger.path.with_suffix(".pubkey").write_text(
            signer.public_key_bytes.hex() + "\n", encoding="utf-8", newline="\n"
        )
        print(f"  decision log: {result}", file=out)
        print(f"  decision log file: {ledger.path}", file=out)
    finally:
        ledger.close()
    print(NOTE, file=out)
    print(FOOTER, file=out)
    return 0


def cmd_demo(args, out) -> int:
    cfg = load_planner_config(args.config)
    if args.seed is not None:
        cfg = cfg.model_copy(update={"seed": args.seed})
    product, box = load_product_config(), load_box_config()
    signer, ledger, log = _open_log(cfg, args, "planner_demo")
    rows = []
    try:
        for name, hour in DEMO_CHECKPOINTS:
            built = build_inputs(RECORDINGS / f"{name}.jsonl", hour, product, box)
            table, decision, _ = decide_one(built, cfg, product, log)
            rows.append((name, hour, built.inputs, table, decision))
        log.anchor()
        result = verify_decision_log(
            ledger.read_entries(), signer.public_key_bytes, ledger.latest_anchor()
        )
        ledger.path.with_suffix(".pubkey").write_text(
            signer.public_key_bytes.hex() + "\n", encoding="utf-8", newline="\n"
        )
        path = ledger.path
    finally:
        ledger.close()
    for line in demo_table(rows):
        print(line, file=out)
    print(f"\ndecision log: {result}; file {path}", file=out)
    print(NOTE, file=out)
    print(FOOTER, file=out)
    return 0


def demo_table(rows) -> list[str]:
    head = (
        f"{'scenario':<20}{'hour':>5}{'trust':>16}{'status':>28}{'CVaR-optimal':>18}"
        f"{'expected-optimal':>18}{'disagree':>9}  route"
    )
    lines = [head]
    for name, hour, inputs, _table, decision in rows:
        lines.append(
            f"{name:<20}{hour:>5.0f}{inputs.trust_level:>16}{decision.shipment_status:>28}"
            f"{decision.chosen_action:>18}{decision.expected_optimal_action:>18}"
            f"{'yes' if decision.disagree else 'no':>9}  {decision.route}"
        )
    return lines


def cmd_human(args, out) -> int:
    """Record a person's decision on an existing decision log, as a new entry."""
    cfg = load_planner_config(args.config)
    signer = load_or_create_signer(args.key_dir)
    with Ledger.open(args.log) as ledger:
        entries = ledger.read_entries()
        if not 0 <= args.seq < len(entries):
            print(f"no entry {args.seq} in {args.log}", file=sys.stderr)
            return 2
        record = parse_canonical(entries[args.seq].record)
        if record["kind"] != "decision":
            print(f"entry {args.seq} is not a decision", file=sys.stderr)
            return 2
        log = DecisionLog(cfg.planner_id, signer, ledger)
        try:
            human = record_human_decision(
                record["shipment_id"], record["chosen_action"], args.seq, args.who, args.action,
                args.reason, args.final_action, datetime.now(UTC),
            )  # fmt: skip
            entry = log.append_human(human)
        except ValueError as exc:
            print(f"cannot record: {exc}", file=sys.stderr)
            return 2
        result = verify_decision_log(ledger.read_entries(), signer.public_key_bytes)
    print(
        f"Recorded {human.human_action} by {human.who} as new entry {entry.seq} "
        f"(refers to {human.refers_to_seq}); final action {human.final_action}. Log: {result}",
        file=out,
    )
    print(FOOTER, file=out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m planner")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p):
        p.add_argument("--config", help="planner settings (default config/planner.yaml)")
        p.add_argument("--seed", type=int, help="override the scenario seed")
        p.add_argument("--key-dir", help="folder of the planner key (default outside the repo)")
        p.add_argument("--log-dir", help="where decision logs go (default data/runs)")

    decide = sub.add_parser("decide", help="plan one shipment at one hour of a recording")
    decide.add_argument("--recording", required=True, metavar="FILE")
    decide.add_argument("--at-hour", required=True, type=float)
    decide.add_argument("--remaining-hours", type=float, help="scheduled remaining hours R")
    decide.add_argument("--shipment-id")
    decide.add_argument("--ledger", help="a real ledger to verify (with --public-key)")
    decide.add_argument("--public-key", help="file with the public key in hex")
    common(decide)
    demo = sub.add_parser("demo", help="plan six golden recordings at fixed checkpoints")
    common(demo)
    human = sub.add_parser("human", help="record a person's decision on a decision log")
    human.add_argument("--log", required=True, help="the decision log file")
    human.add_argument("--seq", required=True, type=int, help="entry number of the decision")
    human.add_argument("--who", required=True)
    human.add_argument("--action", required=True, choices=("approve", "override", "reject"))
    human.add_argument("--final-action", help="the action chosen when overriding")
    human.add_argument("--reason", required=True)
    human.add_argument("--config")
    human.add_argument("--key-dir")
    return parser


def main(argv: Sequence[str] | None = None, out=None) -> int:
    out = out or sys.stdout
    args = build_parser().parse_args(argv)
    return {"decide": cmd_decide, "demo": cmd_demo, "human": cmd_human}[args.command](args, out)
