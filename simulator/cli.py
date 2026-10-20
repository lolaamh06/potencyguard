"""Command line: python -m simulator generate --all | --scenario <id>."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from shared.config import load_box_config
from simulator.recording import write_recording
from simulator.scenario import load_all_scenarios


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m simulator")
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate", help="write scenario recordings")
    which = gen.add_mutually_exclusive_group(required=True)
    which.add_argument("--all", action="store_true", help="generate every scenario")
    which.add_argument("--scenario", metavar="ID", help="generate one scenario by id")
    gen.add_argument("--scenarios-dir", help="folder with scenario YAML files")
    gen.add_argument("--out-dir", help="folder for recordings (default data/recordings)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    scenarios = load_all_scenarios(args.scenarios_dir)
    if args.all:
        chosen = list(scenarios.values())
    elif args.scenario in scenarios:
        chosen = [scenarios[args.scenario]]
    else:
        print(f"unknown scenario {args.scenario!r}; known: {', '.join(scenarios)}", file=sys.stderr)
        return 2
    box = load_box_config()
    for scenario in chosen:
        recording, truth = write_recording(scenario, box, args.out_dir)
        print(f"wrote {recording} and {truth}")
    return 0
