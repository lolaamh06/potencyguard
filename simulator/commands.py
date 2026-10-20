"""Turn a typed line like "open_door 30" into an injection dict (used by the live-demo tool)."""

from __future__ import annotations

# Positional arguments for each command, in the order they are typed.
_POSITIONAL: dict[str, tuple[str, ...]] = {
    "kill_cooling": (),
    "derate_cooling": ("factor",),
    "restore_cooling": (),
    "open_door": ("duration_min", "power_w"),
    "heat_soak": ("delta_c", "duration_h", "ramp_h"),
    "cold_snap": ("delta_c", "duration_h", "ramp_h"),
    "stop_spoof": (),
    "glitch_spike": ("value_c",),
    "shock": ("peak_g",),
}
_SPOOF_ARGS: dict[str, tuple[str, ...]] = {
    "hold": ("reported_c", "duration_min"),
    "offset": ("delta_c", "duration_min"),
    "replay": ("replay_from_h", "replay_len_h", "duration_min"),
}
USAGE = (
    "kill_cooling | derate_cooling F | restore_cooling | open_door MIN [W] | "
    "heat_soak DELTA HOURS [RAMP] | cold_snap DELTA HOURS [RAMP] | "
    "spoof_sensor hold C [MIN] | spoof_sensor offset DELTA [MIN] | "
    "spoof_sensor replay FROM_H LEN_H [MIN] | stop_spoof | glitch_spike C | shock G"
)


def parse_command(text: str) -> dict:
    """Parse one command line. Raises ValueError with a readable message when it is malformed."""
    words = text.split()
    if not words:
        raise ValueError("empty command")
    name, args = words[0], words[1:]
    if name == "spoof_sensor":
        if not args or args[0] not in _SPOOF_ARGS:
            raise ValueError("spoof_sensor needs a mode: hold, offset or replay")
        mode, args = args[0], args[1:]
        names = _SPOOF_ARGS[mode]
        event: dict = {"type": name, "mode": mode}
    elif name in _POSITIONAL:
        names = _POSITIONAL[name]
        event = {"type": name}
    else:
        raise ValueError(f"unknown command {name!r}. Commands: {USAGE}")
    if len(args) > len(names):
        raise ValueError(f"{name} takes at most {len(names)} values (got {len(args)})")
    for key, word in zip(names, args, strict=False):
        try:
            event[key] = float(word)
        except ValueError as exc:
            raise ValueError(f"{key} must be a number (got {word!r})") from exc
    return event


def parse_scheduled(text: str) -> tuple[float, dict]:
    """Parse 'kill_cooling@2h' or 'open_door 30@1.5h' into (sim seconds, injection dict)."""
    if "@" not in text:
        raise ValueError(f"expected COMMAND@TIMEh, for example kill_cooling@2h (got {text!r})")
    command, when = text.rsplit("@", 1)
    when = when.strip().lower()
    if not when.endswith("h"):
        raise ValueError(f"time must end with h, for example 2h (got {when!r})")
    try:
        hours = float(when[:-1])
    except ValueError as exc:
        raise ValueError(f"time must be a number of hours (got {when!r})") from exc
    if hours < 0:
        raise ValueError("time must not be negative")
    return hours * 3600.0, parse_command(command)
