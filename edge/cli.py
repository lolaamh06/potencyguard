"""Command line for the edge package: python -m edge potency --recording FILE | --all."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from edge.potency import PotencyState, PotencyTracker
from edge.recorded_source import RecordedSource
from shared.config import REPO_ROOT, ProductConfig, load_product_config

DEFAULT_RECORDINGS_DIR = REPO_ROOT / "data" / "recordings"
PRINT_EVERY = 12
FOOTER = "Simulation result on a synthetic box. Not real-world evidence."


@dataclass(frozen=True)
class RecordingAnalysis:
    """The tracker run over one recording, from the reported readings and from the truth."""

    scenario_id: str
    seed: int
    reported_states: list[PotencyState]
    reported_temps_c: list[float]
    true_states: list[PotencyState]


def ground_truth_path(recording: Path) -> Path:
    return recording.with_name(recording.name.removesuffix(".jsonl") + ".ground_truth.json")


def analyse_recording(recording: Path | str, cfg: ProductConfig) -> RecordingAnalysis:
    """Replay a recording through the tracker.

    The reported series is what the edge program would see. The true series (from the
    ground-truth file) is fed to a second tracker only for this analysis.
    """
    path = Path(recording)
    source = RecordedSource(path)
    source.start()
    reported = PotencyTracker(cfg)
    reported_states, reported_temps = [], []
    while (reading := source.read()) is not None:
        reported_states.append(reported.update(reading))
        reported_temps.append(reading.temp_c)
    header = source.header
    source.close()

    truth = json.loads(ground_truth_path(path).read_text(encoding="utf-8"))
    true_tracker = PotencyTracker(cfg)
    true_states = [
        true_tracker.update_sample(t, temp)
        for t, temp in zip(truth["t_s"], truth["true_temp_c"], strict=True)
    ]
    return RecordingAnalysis(
        header["scenario_id"], header["seed"], reported_states, reported_temps, true_states
    )


def first_below_p_min_hour(states: Sequence[PotencyState]) -> float | None:
    """Simulated hour of the first sample at which potency was below P_min, or None."""
    return next((s.t_s / 3600.0 for s in states if s.below_min_potency), None)


def _row(label: str, states: Sequence[PotencyState]) -> str:
    state = states[-1]
    mkt = "n/a" if state.mkt_c is None else f"{state.mkt_c:.2f}"
    crossing = first_below_p_min_hour(states)
    below = "never" if crossing is None else f"{crossing:.1f} h"
    return (
        f"{label:<38}{state.tau_eq_h:>10.2f}{state.potency * 100:>10.3f}"
        f"{state.shelf_life_used_fraction * 100:>10.3f}{mkt:>9}{state.samples_excluded:>9}"
        f"{below:>16}"
    )


def summary_table(analysis: RecordingAnalysis) -> str:
    head = (
        f"{'':<38}{'tau_eq (h)':>10}{'potency %':>10}{'used %':>10}{'MKT (C)':>9}"
        f"{'excluded':>9}{'first < P_min':>16}"
    )
    return "\n".join(
        [
            head,
            _row("from reported readings", analysis.reported_states),
            _row("from true temperature (ground truth)", analysis.true_states),
        ]
    )


def _print_one(path: Path, cfg: ProductConfig, out, detail: bool) -> None:
    analysis = analyse_recording(path, cfg)
    print(f"Recording {path.name}: scenario {analysis.scenario_id}, seed {analysis.seed}", file=out)
    if detail:
        print("\n  sim hour   reported C   tau_eq (h)   potency %   status", file=out)
        for i, state in enumerate(analysis.reported_states):
            if i % PRINT_EVERY == 0:
                print(
                    f"  {state.t_s / 3600.0:8.2f}   {analysis.reported_temps_c[i]:10.2f}"
                    f"   {state.tau_eq_h:10.3f}   {state.potency * 100:9.4f}   {state.status}",
                    file=out,
                )
        print(file=out)
    print(summary_table(analysis), file=out)
    print(file=out)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m edge")
    sub = parser.add_subparsers(dest="command", required=True)
    potency = sub.add_parser("potency", help="replay recordings through the potency tracker")
    which = potency.add_mutually_exclusive_group(required=True)
    which.add_argument("--recording", metavar="FILE", help="one .jsonl recording")
    which.add_argument("--all", action="store_true", help="final summary for every recording")
    potency.add_argument("--recordings-dir", help="folder for --all (default data/recordings)")

    twin = sub.add_parser("twin", help="replay recordings through the thermal twin and detectors")
    which_twin = twin.add_mutually_exclusive_group(required=True)
    which_twin.add_argument("--recording", metavar="FILE", help="one .jsonl recording")
    which_twin.add_argument("--all", action="store_true", help="one line per recording")
    twin.add_argument("--verbose", action="store_true", help="print every sample")
    twin.add_argument("--recordings-dir", help="folder for --all (default data/recordings)")

    pre = sub.add_parser("precheck", help="pre-trip check: does the twin match this box?")
    pre.add_argument("--recording", metavar="FILE", required=True, help="one .jsonl recording")
    pre.add_argument("--hours", type=float, default=6.0, help="hours of data to use (default 6)")

    cal = sub.add_parser("calibrate", help="fit the twin from data/calibration/")
    cal.add_argument("--calibration-dir", help="folder (default data/calibration)")
    return parser


def main(argv: Sequence[str] | None = None, out=None) -> int:
    out = out or sys.stdout
    args = build_parser().parse_args(argv)
    cfg = load_product_config()
    if args.command == "precheck":
        return _precheck_command(args, out)
    if args.command in ("twin", "calibrate"):
        return _twin_commands(args, cfg, out)
    if args.all:
        folder = Path(args.recordings_dir) if args.recordings_dir else DEFAULT_RECORDINGS_DIR
        for path in sorted(folder.glob("*.jsonl")):
            _print_one(path, cfg, out, detail=False)
    else:
        path = Path(args.recording)
        if not path.exists():
            print(f"recording not found: {path}", file=sys.stderr)
            return 2
        _print_one(path, cfg, out, detail=True)
    print(FOOTER, file=out)
    return 0


def _precheck_command(args: argparse.Namespace, out) -> int:
    from edge.detector_config import load_detector_config
    from edge.precheck import precheck, window
    from edge.thermal_twin import load_twin_params

    path = Path(args.recording)
    if not path.exists():
        print(f"recording not found: {path}", file=sys.stderr)
        return 2
    source = RecordedSource(path)
    source.start()
    readings = []
    try:
        while (reading := source.read()) is not None:
            readings.append(reading)
    finally:
        source.close()
    try:
        result = precheck(window(readings, args.hours), load_twin_params(), load_detector_config())
    except ValueError as exc:
        print(f"cannot check {path.name}: {exc}", file=sys.stderr)
        return 2
    print(
        f"Pre-trip check of {path.name} (first {args.hours:g} hours, {result.n_pairs} intervals):",
        file=out,
    )
    print(f"  {result.message}", file=out)
    print(FOOTER, file=out)
    return 0


def _twin_commands(args: argparse.Namespace, cfg: ProductConfig, out) -> int:
    from edge import twin_cli
    from edge.thermal_twin import DEFAULT_TWIN_PATH
    from shared.config import load_box_config

    if args.command == "calibrate":
        folder = (
            Path(args.calibration_dir)
            if args.calibration_dir
            else (twin_cli.DEFAULT_CALIBRATION_DIR)
        )
        return twin_cli.run_calibrate(folder, DEFAULT_TWIN_PATH, out)
    box = load_box_config()
    if args.all:
        folder = (
            Path(args.recordings_dir) if args.recordings_dir else (twin_cli.DEFAULT_RECORDINGS_DIR)
        )
        twin_cli.print_all(folder, cfg, box, out)
        return 0
    path = Path(args.recording)
    if not path.exists():
        print(f"recording not found: {path}", file=sys.stderr)
        return 2
    try:
        analysis = twin_cli.analyse(path, cfg, box)
    except ValueError as exc:
        print(f"cannot analyse {path.name}: {exc}", file=sys.stderr)
        return 2
    twin_cli.print_recording(analysis, out, args.verbose)
    return 0
