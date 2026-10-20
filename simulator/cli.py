"""Command line: python -m simulator generate | freerun | live-demo."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from shared.config import load_box_config
from simulator.commands import parse_scheduled
from simulator.demo import run_live_demo, stdin_commands
from simulator.freerun import FreeRun, load_freerun_config
from simulator.live import LiveSimulator
from simulator.recording import DEFAULT_RUNS_DIR, write_recording
from simulator.scenario import load_all_scenarios

DEFAULT_DEMO_SPEED = 3600.0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m simulator")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="write scenario recordings")
    which = gen.add_mutually_exclusive_group(required=True)
    which.add_argument("--all", action="store_true", help="every scenario, fixed seeds (golden)")
    which.add_argument("--scenario", metavar="ID", help="one scenario by id")
    seed = gen.add_mutually_exclusive_group()
    seed.add_argument("--seed", type=int, help="use this seed instead of the scenario's own")
    seed.add_argument("--random-seed", action="store_true", help="draw a fresh seed and print it")
    gen.add_argument("--scenarios-dir", help="folder with scenario YAML files")
    gen.add_argument("--out-dir", help="folder for recordings (default data/recordings)")

    free = sub.add_parser("freerun", help="write a recording of a random free-run trip")
    free.add_argument("--seed", type=int, help="fixed seed (default: random, printed)")
    free.add_argument("--hours", type=float, help="trip length (default from config)")
    free.add_argument("--out-dir", help="folder for the recording (default data/runs)")

    demo = sub.add_parser("live-demo", help="watch a live run and type faults into it")
    target = demo.add_mutually_exclusive_group(required=True)
    target.add_argument("--scenario", metavar="ID", help="run one scenario live")
    target.add_argument("--freerun", action="store_true", help="run an endless free-run trip")
    demo.add_argument("--seed", type=int, help="fixed seed (default: random, printed)")
    demo.add_argument(
        "--speed", type=float, default=DEFAULT_DEMO_SPEED, help="sim seconds per second"
    )
    demo.add_argument("--hours", type=float, help="stop a free run after this many hours")
    demo.add_argument("--inject", action="append", default=[], metavar="CMD@Nh")
    demo.add_argument("--scenarios-dir", help="folder with scenario YAML files")
    return parser


def _generate(args: argparse.Namespace) -> int:
    scenarios = load_all_scenarios(args.scenarios_dir)
    if args.all:
        if args.seed is not None or args.random_seed:
            print("--all always uses each scenario's own seed", file=sys.stderr)
            return 2
        chosen = list(scenarios.values())
    elif args.scenario in scenarios:
        chosen = [scenarios[args.scenario]]
    else:
        print(f"unknown scenario {args.scenario!r}; known: {', '.join(scenarios)}", file=sys.stderr)
        return 2
    custom_seed = args.seed is not None or args.random_seed
    out_dir = args.out_dir or (DEFAULT_RUNS_DIR if custom_seed else None)
    box = load_box_config()
    for scenario in chosen:
        recording, truth = write_recording(
            scenario, box, out_dir, seed=args.seed, random_seed=args.random_seed
        )
        if args.random_seed:
            print(f"seed used: {_seed_of(recording)}")
        print(f"wrote {recording} and {truth}")
    return 0


def _seed_of(recording_path) -> int:
    import json

    with open(recording_path, encoding="utf-8") as handle:
        return json.loads(handle.readline())["seed"]


def _freerun(args: argparse.Namespace) -> int:
    config = load_freerun_config()
    hours = args.hours if args.hours is not None else config.default_hours
    recording, truth = write_recording(
        FreeRun(config, hours),
        load_box_config(),
        args.out_dir or DEFAULT_RUNS_DIR,
        seed=args.seed,
        random_seed=args.seed is None,
    )
    print(f"seed used: {_seed_of(recording)}")
    print(f"wrote {recording} and {truth}")
    return 0


def _live_demo(args: argparse.Namespace) -> int:
    box = load_box_config()
    if args.freerun:
        source = FreeRun(load_freerun_config(), args.hours)
    else:
        scenarios = load_all_scenarios(args.scenarios_dir)
        if args.scenario not in scenarios:
            print(
                f"unknown scenario {args.scenario!r}; known: {', '.join(scenarios)}",
                file=sys.stderr,
            )
            return 2
        source = scenarios[args.scenario]
    try:
        scheduled = [parse_scheduled(text) for text in args.inject]
    except ValueError as exc:
        print(f"bad --inject: {exc}", file=sys.stderr)
        return 2
    sim = LiveSimulator(source, box, args.seed)
    try:
        run_live_demo(sim, args.speed, stdin_commands(), scheduled, sys.stdout)
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handlers = {"generate": _generate, "freerun": _freerun, "live-demo": _live_demo}
    return handlers[args.command](args)
