"""Simulated clock with a speed factor (master brief section 3.7). Never sleeps."""

from __future__ import annotations

import math
from dataclasses import dataclass

# Speed presets: 1 wall second equals this many simulated seconds.
SPEED_PRESETS: tuple[float, ...] = (1.0, 60.0, 3600.0)


def advance_sim_time(sim_time_s: float, wall_dt_s: float, speed_factor: float) -> float:
    """Pure function: simulated time after wall_dt_s real seconds at the given speed."""
    if not all(math.isfinite(v) for v in (sim_time_s, wall_dt_s, speed_factor)):
        raise ValueError("clock values must be finite numbers")
    if sim_time_s < 0:
        raise ValueError(f"simulated time must not be negative (got {sim_time_s})")
    if wall_dt_s < 0:
        raise ValueError(f"wall time step must not be negative (got {wall_dt_s})")
    if speed_factor <= 0:
        raise ValueError(f"speed factor must be positive (got {speed_factor})")
    return sim_time_s + wall_dt_s * speed_factor


@dataclass
class SimClock:
    """Holds simulated time. The caller supplies wall-time steps, so tests run instantly."""

    speed_factor: float = 1.0
    now_s: float = 0.0

    def __post_init__(self) -> None:
        advance_sim_time(self.now_s, 0.0, self.speed_factor)  # validates both fields

    def tick(self, wall_dt_s: float) -> float:
        """Advance by wall_dt_s real seconds and return the new simulated time."""
        self.now_s = advance_sim_time(self.now_s, wall_dt_s, self.speed_factor)
        return self.now_s

    def set_speed(self, speed_factor: float) -> None:
        """Change speed without changing the current simulated time."""
        advance_sim_time(self.now_s, 0.0, speed_factor)
        self.speed_factor = speed_factor

    def reset(self) -> None:
        self.now_s = 0.0
