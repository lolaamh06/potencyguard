"""The swappable sensor feed (master brief section 4: one edge program, swappable source)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from edge.sensor_reading import SensorReading


class SensorSource(ABC):
    """A feed of readings. Implementations: simulator, recorded file, later a Pi."""

    @abstractmethod
    def start(self) -> None:
        """Prepare the feed. Must be called before read()."""

    @abstractmethod
    def read(self) -> SensorReading | None:
        """Return the next reading, or None at the end of a recording."""

    @abstractmethod
    def close(self) -> None:
        """Release any resources."""
