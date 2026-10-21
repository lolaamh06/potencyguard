"""PiSource: the sensor feed of a real Raspberry Pi (stub, Phase 4).

No hardware is attached and no hardware driver exists in this project yet, so this class only
marks the place where a real feed will plug in behind the SensorSource interface. It never
returns a reading.
"""

from __future__ import annotations

from edge.sensor_reading import SensorReading
from edge.sensor_source import SensorSource

NOT_IMPLEMENTED_MESSAGE = (
    "PiSource is a stub: no Raspberry Pi hardware or driver is attached to this project. "
    "Use RecordedSource (a recording) or the simulator instead."
)


class PiSource(SensorSource):
    def start(self) -> None:
        raise NotImplementedError(NOT_IMPLEMENTED_MESSAGE)

    def read(self) -> SensorReading | None:
        raise NotImplementedError(NOT_IMPLEMENTED_MESSAGE)

    def close(self) -> None:
        return None
