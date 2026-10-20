"""Developer tool: watch a live run in the terminal and type faults into it (Phase 2A)."""

from __future__ import annotations

import queue
import sys
import threading
import time
from collections.abc import Callable
from typing import TextIO

from edge.sim_clock import SimClock
from simulator.commands import parse_command
from simulator.live import LiveSimulator


def format_sample(reading, truth, event_types: dict[str, str]) -> str:
    """One readable line for one sample."""
    active = ", ".join(event_types.get(i, i) for i in truth.active_event_ids) or "-"
    return (
        f"t={truth.t_s / 3600.0:7.2f} h  reported={reading.temp_c:7.2f}"
        f"  true={truth.true_temp_c:7.2f}"
        f"  compressor={'ON ' if truth.compressor_on else 'off'}  events=[{active}]"
    )


def run_live_demo(
    sim: LiveSimulator,
    speed: float,
    commands: queue.Queue[str],
    scheduled: list[tuple[float, dict]],
    out: TextIO,
    sleep: Callable[[float], None] = time.sleep,
    max_samples: int | None = None,
) -> int:
    """Print one line per sample, paced by SimClock; apply typed and scheduled injections.

    The pacing waits interval/speed wall seconds per sample through the injectable `sleep`, so
    tests pass a function that does not wait. Returns the number of samples printed.
    """
    clock = SimClock(speed_factor=speed)
    wall_per_sample_s = sim.sample_interval_s / speed
    pending = sorted(scheduled, key=lambda item: item[0])
    printed = 0
    print(
        f"seed={sim.seed} ({sim.seed_mode})  scenario={sim.scenario_id}  speed={speed:g}x", file=out
    )
    while max_samples is None or printed < max_samples:
        while pending and pending[0][0] <= sim.engine.next_sample_s:
            _, event = pending.pop(0)
            result = sim.inject(event)
            print(f"  >> {result.message or result.error}", file=out)
        while True:
            try:
                line = commands.get_nowait()
            except queue.Empty:
                break
            try:
                result = sim.inject(parse_command(line))
            except ValueError as exc:
                print(f"  >> cannot parse {line!r}: {exc}", file=out)
                continue
            print(f"  >> {result.message or result.error}", file=out)
        reading, truth = sim.step()
        if reading is None or truth is None:
            print("end of scenario", file=out)
            break
        types = {e.id: e.type for e in sim.events()}
        print(format_sample(reading, truth, types), file=out)
        printed += 1
        sleep(wall_per_sample_s)
        clock.tick(wall_per_sample_s)
    return printed


def stdin_commands() -> queue.Queue[str]:
    """Collect typed lines from stdin in a background thread."""
    lines: queue.Queue[str] = queue.Queue()

    def reader() -> None:
        for line in sys.stdin:
            if line.strip():
                lines.put(line.strip())

    threading.Thread(target=reader, daemon=True).start()
    return lines
