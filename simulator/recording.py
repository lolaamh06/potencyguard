"""Write scenario recordings: a JSONL feed plus a ground-truth sidecar (Phase 1)."""

from __future__ import annotations

import json
from pathlib import Path

from shared.config import REPO_ROOT, BoxConfig
from simulator.scenario import Scenario
from simulator.sim_source import SOURCE_NAME, SimSource

SCHEMA_VERSION = "0.1"
DEFAULT_RECORDINGS_DIR = REPO_ROOT / "data" / "recordings"


def _dumps(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def write_recording(scenario: Scenario, box: BoxConfig, out_dir: Path | str | None = None):
    """Generate one scenario and write <id>.jsonl and <id>.ground_truth.json.

    Returns (recording_path, ground_truth_path). Output is byte-identical for the same seed.
    """
    folder = Path(out_dir) if out_dir is not None else DEFAULT_RECORDINGS_DIR
    folder.mkdir(parents=True, exist_ok=True)

    source = SimSource(scenario, box)
    source.start()
    header = {
        "type": "header",
        "scenario_id": scenario.id,
        "seed": scenario.seed,
        "sample_interval_s": scenario.sample_interval_s,
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE_NAME,
        "n_samples": scenario.n_samples,
    }
    lines = [_dumps(header)]
    while (reading := source.read()) is not None:
        lines.append(_dumps(reading.model_dump()))

    trace = source.trace
    ground_truth = {
        "scenario_id": scenario.id,
        "seed": scenario.seed,
        "sample_interval_s": scenario.sample_interval_s,
        "schema_version": SCHEMA_VERSION,
        "t_s": trace.t_s.tolist(),
        "true_temp_c": trace.true_temp_c.tolist(),
        "reported_temp_c": trace.reported_temp_c.tolist(),
        "ambient_c": trace.ambient_c.tolist(),
        "heat_input_w": trace.heat_input_w.tolist(),
        "labels": trace.labels,
    }
    source.close()

    recording_path = folder / f"{scenario.id}.jsonl"
    truth_path = folder / f"{scenario.id}.ground_truth.json"
    with open(recording_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")
    with open(truth_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(_dumps(ground_truth) + "\n")
    return recording_path, truth_path
