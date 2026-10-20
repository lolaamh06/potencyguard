"""SimSource: the box simulator as a SensorSource (master brief section 4)."""

from __future__ import annotations

from edge.sensor_reading import SensorReading
from edge.sensor_source import SensorSource
from shared.config import BoxConfig
from simulator.engine import SOURCE_NAME
from simulator.events import InjectionResult
from simulator.freerun import FreeRun
from simulator.live import LiveSimulator
from simulator.scenario import Scenario
from simulator.truth import TruthSample

__all__ = ["SOURCE_NAME", "SimSource"]


class SimSource(SensorSource):
    """Streams a LiveSimulator one reading at a time, and passes injections through.

    For a scenario the default seed is the scenario's own (a fixed, reproducible run).
    Pass random_seed=True for a fresh random seed; the seed used is always in .seed.
    """

    def __init__(
        self,
        source: Scenario | FreeRun,
        box: BoxConfig,
        seed: int | None = None,
        random_seed: bool = False,
    ) -> None:
        self._source = source
        self._box = box
        if seed is None and not random_seed and isinstance(source, Scenario):
            seed = source.seed
        self._seed_arg = seed
        self._sim: LiveSimulator | None = None

    @property
    def simulator(self) -> LiveSimulator:
        if self._sim is None:
            raise RuntimeError("SimSource.start() has not been called")
        return self._sim

    @property
    def seed(self) -> int:
        return self.simulator.seed

    def start(self) -> None:
        self._sim = LiveSimulator(self._source, self._box, self._seed_arg)

    def read(self) -> SensorReading | None:
        return self.simulator.step()[0]

    def read_with_truth(self) -> tuple[SensorReading | None, TruthSample | None]:
        return self.simulator.step()

    def inject(self, event) -> InjectionResult:
        return self.simulator.inject(event)

    def close(self) -> None:
        self._sim = None
