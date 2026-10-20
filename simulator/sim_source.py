"""SimSource: the box simulator as a SensorSource (master brief section 4)."""

from __future__ import annotations

from edge.sensor_reading import SensorReading
from edge.sensor_source import SensorSource
from shared.config import BoxConfig
from simulator.scenario import Scenario
from simulator.simulate import SimulationTrace, simulate

SOURCE_NAME = "sim"


class SimSource(SensorSource):
    """Replays a freshly simulated scenario one reading at a time."""

    def __init__(self, scenario: Scenario, box: BoxConfig) -> None:
        self.scenario = scenario
        self._box = box
        self._trace: SimulationTrace | None = None
        self._next = 0

    @property
    def trace(self) -> SimulationTrace:
        """The full simulation, including ground truth. Available after start()."""
        if self._trace is None:
            raise RuntimeError("SimSource.start() has not been called")
        return self._trace

    def start(self) -> None:
        self._trace = simulate(self.scenario, self._box)
        self._next = 0

    def read(self) -> SensorReading | None:
        trace = self.trace
        i = self._next
        if i >= len(trace.t_s):
            return None
        self._next += 1
        return SensorReading(
            t_s=float(trace.t_s[i]),
            temp_c=float(trace.reported_temp_c[i]),
            rh_pct=float(trace.rh_pct[i]),
            shock_g=float(trace.shock_g[i]),
            source=SOURCE_NAME,
        )

    def close(self) -> None:
        self._trace = None
        self._next = 0
