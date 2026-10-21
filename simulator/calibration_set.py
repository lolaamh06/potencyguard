"""The calibration recordings for the thermal twin (Phase 3): fixed seeds, kept apart from scoring.

Seed blocks used in this project (disjoint, asserted in the tests; the full ledger is in
docs/02-phase-reports/phase-03c-evaluation.md):
  calibration  9001 to 9010   fit the nominal twin
  per-box      9101 to 9110   fit the twin of the +15 percent box (Phase 3C)
               9201 to 9210   fit the twin of the -15 percent box
               9301 to 9310   fit the twin of the two-node box
  training    10001 to 10100  choose the detector settings
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from edge.calibration import CalibrationResult, calibrate
from shared.config import REPO_ROOT, BoxConfig
from simulator.recording import write_run
from simulator.scenario import load_all_scenarios
from simulator.simulate import simulate

CALIBRATION_SCENARIOS_DIR = REPO_ROOT / "simulator" / "calibration_scenarios"
DEFAULT_CALIBRATION_DIR = REPO_ROOT / "data" / "calibration"
# scenario id -> seeds
CALIBRATION_PLAN: dict[str, range] = {
    "calibration_baseline": range(9001, 9006),
    "calibration_wide": range(9006, 9011),
}
CALIBRATION_SEEDS = [seed for seeds in CALIBRATION_PLAN.values() for seed in seeds]


def generate_calibration(box: BoxConfig, out_dir: Path | str | None = None) -> list[Path]:
    """Write every calibration recording and return the recording paths (not the sidecars)."""
    scenarios = load_all_scenarios(CALIBRATION_SCENARIOS_DIR)
    folder = Path(out_dir) if out_dir is not None else DEFAULT_CALIBRATION_DIR
    written = []
    for scenario_id, seeds in CALIBRATION_PLAN.items():
        for seed in seeds:
            result = simulate(scenarios[scenario_id], box, seed=seed)
            recording, _ = write_run(result, folder, f"{scenario_id}_{seed}")
            written.append(recording)
    return written


# Phase 3C: one clean calibration set per box variant, same two scenarios as the nominal set.
VARIANT_SEED_STARTS = {"plus15": 9101, "minus15": 9201, "two_node": 9301}
VARIANT_LABELS = {
    "plus15": "tau, R_th and capacity +15%",
    "minus15": "tau, R_th and capacity -15%",
    "two_node": "two-node box (air and payload nodes)",
}


def variant_seed_plan(variant: str) -> dict[str, range]:
    start = VARIANT_SEED_STARTS[variant]
    return {
        "calibration_baseline": range(start, start + 5),
        "calibration_wide": range(start + 5, start + 10),
    }


VARIANT_SEEDS = {
    name: [seed for seeds in variant_seed_plan(name).values() for seed in seeds]
    for name in VARIANT_SEED_STARTS
}


def scaled_box(box: BoxConfig, factor: float) -> BoxConfig:
    """A box whose time constant, wall resistance and cooling capacity are scaled together."""
    return dataclasses.replace(
        box,
        box_tau_h=box.box_tau_h * factor,
        box_R_th_k_per_w=box.box_R_th_k_per_w * factor,
        box_cooling_capacity_w=box.box_cooling_capacity_w * factor,
    )


def variant_boxes(box: BoxConfig) -> dict[str, BoxConfig]:
    """The three boxes that differ from the nominal one (built in memory, no file written)."""
    return {
        "plus15": scaled_box(box, 1.15),
        "minus15": scaled_box(box, 0.85),
        "two_node": dataclasses.replace(box, box_model="two_node"),
    }


def calibrate_for_box(box: BoxConfig, seeds: dict[str, range] | None = None) -> CalibrationResult:
    """Generate the clean calibration set for THIS box with the simulator and fit the twin.

    Same two clean scenarios and the same restricted regression as the nominal calibration; only
    the box (and so the seeds) differ. Nothing is written; readings stay in memory.
    """
    plan = seeds if seeds is not None else CALIBRATION_PLAN
    scenarios = load_all_scenarios(CALIBRATION_SCENARIOS_DIR)
    runs = [
        simulate(scenarios[scenario_id], box, seed=seed).readings
        for scenario_id, seed_range in plan.items()
        for seed in seed_range
    ]
    return calibrate(runs)
