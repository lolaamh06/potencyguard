"""RecordedSource: replays a JSONL recording as a SensorSource (Phase 1)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import IO

from edge.sensor_reading import SensorReading
from edge.sensor_source import SensorSource

# 0.3 adds the ambient_c and cooling_duty channels. 0.2 files are still read; those two fields are
# then None (the thermal twin needs them and will say so).
SUPPORTED_SCHEMA_VERSIONS = ("0.2", "0.3")
SUPPORTED_SCHEMA_VERSION = SUPPORTED_SCHEMA_VERSIONS[-1]


class RecordedSource(SensorSource):
    """First line is a header; every later line is one reading."""

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._handle: IO[str] | None = None
        self.header: dict = {}

    def start(self) -> None:
        self._handle = open(self._path, encoding="utf-8")
        first = self._handle.readline()
        if not first:
            raise ValueError(f"recording {self._path} is empty")
        header = json.loads(first)
        if header.get("type") != "header":
            raise ValueError(f"recording {self._path} must start with a header line")
        if header.get("schema_version") not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(
                f"unsupported schema_version {header.get('schema_version')!r} in {self._path}; "
                f"this reader needs one of {SUPPORTED_SCHEMA_VERSIONS}. Regenerate the recording."
            )
        self.header = header

    def read(self) -> SensorReading | None:
        if self._handle is None:
            raise RuntimeError("RecordedSource.start() has not been called")
        line = self._handle.readline()
        if not line.strip():
            return None
        return SensorReading(**json.loads(line))

    def close(self) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None
