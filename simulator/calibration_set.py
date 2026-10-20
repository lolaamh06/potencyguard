"""The calibration recordings for the thermal twin (Phase 3): fixed seeds, kept apart from scoring.

Seed blocks used in this project (disjoint, asserted in the tests):
  calibration  9001 to 9010   fit the twin
  training    10001 to 10100  choose the detector settings
  test        20001 to 20200  the final scoring
"""

from __future__ import annotations

from pathlib import Path

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
