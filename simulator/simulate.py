"""Batch run: a thin loop over LiveSimulator.step(). There is exactly one physics path."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from edge.sensor_reading import SensorReading
from shared.config import BoxConfig
from simulator.events import EventRecord
from simulator.freerun import FreeRun
from simulator.live import LiveSimulator
from simulator.scenario import ResolvedScenario, Scenario
from simulator.truth import TruthSample

# Safety stop for endless free runs started through the batch helper.
DEFAULT_MAX_SAMPLES = 100_000


@dataclass(frozen=True)
class RunResult:
    """A finished run: what the sensor reported and what was really true."""

    scenario_id: str
    seed: int
    seed_mode: str
    sample_interval_s: float
    readings: list[SensorReading]
    truth: list[TruthSample]
    events: list[EventRecord]
    resolved: ResolvedScenario | None
    detect_divergence_c: float = 1.0

    def _series(self, name: str) -> np.ndarray:
        return np.array([getattr(s, name) for s in self.truth])

    @property
    def t_s(self) -> np.ndarray:
        return self._series("t_s")

    @property
    def true_temp_c(self) -> np.ndarray:
        return self._series("true_temp_c")

    @property
    def reported_temp_c(self) -> np.ndarray:
        return np.array([r.temp_c for r in self.readings])

    @property
    def ambient_c(self) -> np.ndarray:
        return self._series("ambient_c")

    @property
    def rh_pct(self) -> np.ndarray:
        return np.array([r.rh_pct for r in self.readings])

    @property
    def shock_g(self) -> np.ndarray:
        return np.array([r.shock_g for r in self.readings])

    @property
    def compressor_on(self) -> np.ndarray:
        return self._series("compressor_on")

    @property
    def cooling_factor(self) -> np.ndarray:
        return self._series("cooling_factor")


def run_to_end(sim: LiveSimulator, max_samples: int = DEFAULT_MAX_SAMPLES) -> RunResult:
    """Step a simulator until it ends (or max_samples) and collect everything."""
    readings: list[SensorReading] = []
    truth: list[TruthSample] = []
    while len(readings) < max_samples:
        reading, sample = sim.step()
        if reading is None or sample is None:
            break
        readings.append(reading)
        truth.append(sample)
    return RunResult(
        sim.scenario_id,
        sim.seed,
        sim.seed_mode,
        sim.sample_interval_s,
        readings,
        truth,
        sim.events(),
        sim.resolved,
        sim.detect_divergence_c,
    )


def simulate(
    source: Scenario | FreeRun,
    box: BoxConfig,
    seed: int | None = None,
    random_seed: bool = False,
) -> RunResult:
    """Run a scenario to the end. The scenario's own seed is used unless told otherwise."""
    if seed is None and not random_seed and isinstance(source, Scenario):
        seed = source.seed
    return run_to_end(LiveSimulator(source, box, seed))
