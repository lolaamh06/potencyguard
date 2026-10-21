"""Write scenario recordings: a JSONL feed plus a ground-truth sidecar (schema 0.3)."""

from __future__ import annotations

import json
from pathlib import Path

from shared.config import REPO_ROOT, BoxConfig
from simulator.divergence import first_divergence_s
from simulator.engine import SOURCE_NAME
from simulator.events import EventRecord
from simulator.freerun import FreeRun
from simulator.scenario import Scenario
from simulator.simulate import RunResult, simulate

SCHEMA_VERSION = "0.3"
DEFAULT_RECORDINGS_DIR = REPO_ROOT / "data" / "recordings"
DEFAULT_RUNS_DIR = REPO_ROOT / "data" / "runs"


def _dumps(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _sample_range(event: EventRecord, interval_s: float, n: int) -> tuple[int | None, int | None]:
    """First and last sample index at which the event is active (None, None if never)."""
    indices = [i for i in range(n) if event.active_at(i * interval_s)]
    return (indices[0], indices[-1]) if indices else (None, None)


def recording_text(result: RunResult) -> tuple[str, str]:
    """Return (jsonl text, ground-truth json text) for a finished run. Pure and deterministic."""
    header = {
        "type": "header",
        "scenario_id": result.scenario_id,
        "seed": result.seed,
        "seed_mode": result.seed_mode,
        "sample_interval_s": result.sample_interval_s,
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE_NAME,
        "n_samples": len(result.readings),
    }
    lines = [_dumps(header)] + [_dumps(r.model_dump()) for r in result.readings]

    n = len(result.truth)
    events = []
    for event in result.events:
        first, last = _sample_range(event, result.sample_interval_s, n)
        events.append({**event.as_dict(), "first_sample_index": first, "last_sample_index": last})
    truth = {
        "scenario_id": result.scenario_id,
        "seed": result.seed,
        "seed_mode": result.seed_mode,
        "sample_interval_s": result.sample_interval_s,
        "schema_version": SCHEMA_VERSION,
        "t_s": [s.t_s for s in result.truth],
        "true_temp_c": [s.true_temp_c for s in result.truth],
        "reported_temp_c": [s.reported_temp_c for s in result.truth],
        "ambient_c": [s.ambient_c for s in result.truth],
        "measured_ambient_c": [s.measured_ambient_c for s in result.truth],
        "cooling_duty": [s.cooling_duty for s in result.truth],
        "detect_divergence_c": result.detect_divergence_c,
        "first_divergence_s": first_divergence_s(result.truth, result.detect_divergence_c),
        "compressor_on": [s.compressor_on for s in result.truth],
        "cooling_factor": [s.cooling_factor for s in result.truth],
        "spoof_mode": [s.spoof_mode for s in result.truth],
        "active_event_ids": [s.active_event_ids for s in result.truth],
        "resolved_parameters": None if result.resolved is None else result.resolved.parameters(),
        "events": events,
    }
    if any(s.true_payload_temp_c is not None for s in result.truth):
        truth["true_payload_temp_c"] = [s.true_payload_temp_c for s in result.truth]
    return "\n".join(lines) + "\n", _dumps(truth) + "\n"


def write_run(result: RunResult, out_dir: Path | str, name: str | None = None):
    """Write <name>.jsonl and <name>.ground_truth.json. Returns the two paths."""
    folder = Path(out_dir)
    folder.mkdir(parents=True, exist_ok=True)
    stem = name or result.scenario_id
    recording_text_, truth_text = recording_text(result)
    recording_path = folder / f"{stem}.jsonl"
    truth_path = folder / f"{stem}.ground_truth.json"
    with open(recording_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(recording_text_)
    with open(truth_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(truth_text)
    return recording_path, truth_path


def write_recording(
    source: Scenario | FreeRun,
    box: BoxConfig,
    out_dir: Path | str | None = None,
    seed: int | None = None,
    random_seed: bool = False,
):
    """Generate one run and write it. Default seed is the scenario's own (the golden recording).

    Returns (recording_path, ground_truth_path). Output is byte-identical for the same seed.
    """
    result = simulate(source, box, seed=seed, random_seed=random_seed)
    folder = out_dir if out_dir is not None else DEFAULT_RECORDINGS_DIR
    name = result.scenario_id
    if isinstance(source, FreeRun):
        name = f"freerun_{result.seed}"
    return write_run(result, folder, name)
