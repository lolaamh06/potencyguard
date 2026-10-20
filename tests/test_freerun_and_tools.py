"""Tests for free-run trips, the command parser and the live-demo loop (Phase 2A)."""

import io
import queue
from pathlib import Path

import pytest

from shared.config import ConfigError
from simulator.commands import parse_command, parse_scheduled
from simulator.demo import run_live_demo
from simulator.freerun import FreeRun, load_freerun_config
from simulator.live import LiveSimulator
from simulator.simulate import run_to_end

DEFAULT_YAML = Path(__file__).resolve().parent.parent / "config" / "product_default.yaml"
CONFIG = load_freerun_config()
PHYSICAL = ("kill_cooling", "derate_cooling", "open_door", "heat_soak")


def _freerun(box, seed, hours=48.0):
    return run_to_end(LiveSimulator(FreeRun(CONFIG, hours), box, seed))


def test_freerun_is_deterministic_for_a_fixed_seed(box):
    a, b = _freerun(box, 21), _freerun(box, 21)
    assert a.readings == b.readings and a.truth == b.truth
    assert [e.as_dict() for e in a.events] == [e.as_dict() for e in b.events]
    assert _freerun(box, 22).readings != a.readings


def test_freerun_over_100_seeds(box):
    clean = faulty = 0
    for seed in range(100):
        run = _freerun(box, seed)
        assert len(run.readings) == round(48 * 3600 / CONFIG.sample_interval_s) + 1
        assert all(r.source == "sim" for r in run.readings)
        assert all(e.origin == "freerun" for e in run.events)
        if run.events:
            faulty += 1
        else:
            clean += 1
        spoofs = sorted(
            (e for e in run.events if e.type == "spoof_sensor"), key=lambda e: e.start_s
        )
        for first, second in zip(spoofs, spoofs[1:], strict=False):
            assert first.end_s <= second.start_s, f"seed {seed}: overlapping spoofs"
        if spoofs:
            physical = [e.start_s for e in run.events if e.type in PHYSICAL]
            assert physical, f"seed {seed}: spoof without a physical fault"
            assert spoofs[0].start_s >= min(physical)
    assert clean > 0 and faulty > 0


def test_a_spoof_only_affects_the_reported_series(box):
    for seed in range(100):
        run = _freerun(box, seed)
        if any(e.type == "spoof_sensor" for e in run.events):
            assert any(s.spoof_mode for s in run.truth)
            return
    pytest.fail("no free-run seed in 0..99 produced a spoof")


def test_endless_run_starts_like_the_finite_run(box):
    finite = _freerun(box, 8, hours=48.0)
    endless = run_to_end(LiveSimulator(FreeRun(CONFIG, None), box, 8), max_samples=400)
    assert len(endless.readings) == 400
    assert endless.readings[: len(finite.readings)] == finite.readings


def test_random_free_runs_differ(box):
    a = run_to_end(LiveSimulator(FreeRun(CONFIG, 24.0), box), 100)
    b = run_to_end(LiveSimulator(FreeRun(CONFIG, 24.0), box), 100)
    assert a.seed != b.seed and a.seed_mode == "random"
    assert a.readings != b.readings


def test_freerun_config_validation(tmp_path):
    text = DEFAULT_YAML.read_text(encoding="utf-8")
    bad = tmp_path / "bad.yaml"
    bad.write_text(text.replace("freerun_kill_cooling_prob: 0.010", "freerun_kill_cooling_prob: 2"))
    with pytest.raises(ConfigError, match="freerun"):
        load_freerun_config(bad)
    swapped = tmp_path / "swapped.yaml"
    swapped.write_text(
        text.replace("freerun_swing_min_c: 2", "freerun_swing_min_c: 20"), encoding="utf-8"
    )
    with pytest.raises(ConfigError, match="swing_min_c"):
        load_freerun_config(swapped)
    missing = tmp_path / "missing.yaml"
    missing.write_text("Ea_over_R: 1\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_freerun_config(missing)


# ----------------------------------------------------------------- commands


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("kill_cooling", {"type": "kill_cooling"}),
        ("derate_cooling 0.4", {"type": "derate_cooling", "factor": 0.4}),
        ("open_door 30", {"type": "open_door", "duration_min": 30.0}),
        ("open_door 30 150", {"type": "open_door", "duration_min": 30.0, "power_w": 150.0}),
        (
            "heat_soak 10 6 1",
            {"type": "heat_soak", "delta_c": 10.0, "duration_h": 6.0, "ramp_h": 1.0},
        ),
        (
            "spoof_sensor hold 5",
            {"type": "spoof_sensor", "mode": "hold", "reported_c": 5.0},
        ),
        (
            "spoof_sensor replay 1 2 30",
            {
                "type": "spoof_sensor",
                "mode": "replay",
                "replay_from_h": 1.0,
                "replay_len_h": 2.0,
                "duration_min": 30.0,
            },
        ),
        ("stop_spoof", {"type": "stop_spoof"}),
        ("shock 12", {"type": "shock", "peak_g": 12.0}),
    ],
)
def test_parse_command(text, expected):
    assert parse_command(text) == expected


@pytest.mark.parametrize(
    "text", ["", "fly", "derate_cooling abc", "kill_cooling 3", "spoof_sensor", "spoof_sensor x 1"]
)
def test_parse_command_rejects_bad_input(text):
    with pytest.raises(ValueError):
        parse_command(text)


def test_parse_scheduled():
    assert parse_scheduled("kill_cooling@2h") == (7200.0, {"type": "kill_cooling"})
    seconds, event = parse_scheduled("open_door 30@1.5h")
    assert seconds == 5400.0 and event["duration_min"] == 30.0
    for bad in ("kill_cooling", "kill_cooling@2", "kill_cooling@xh", "kill_cooling@-1h"):
        with pytest.raises(ValueError):
            parse_scheduled(bad)


# ----------------------------------------------------------------- live demo loop


def test_live_demo_runs_without_sleeping(box, make_scenario):
    sim = LiveSimulator(make_scenario(duration_h=48), box, seed=3)
    typed: queue.Queue[str] = queue.Queue()
    typed.put("kill_cooling")
    typed.put("not_a_command")
    waits: list[float] = []
    out = io.StringIO()
    printed = run_live_demo(
        sim,
        speed=3600.0,
        commands=typed,
        scheduled=[(3600.0, {"type": "open_door", "duration_min": 10})],
        out=out,
        sleep=waits.append,
        max_samples=20,
    )
    text = out.getvalue()
    assert printed == 20 and len(waits) == 20
    assert all(w == pytest.approx(600.0 / 3600.0) for w in waits)
    assert text.startswith("seed=3 (fixed)")
    assert "kill_cooling applied" in text and "cannot parse" in text
    assert "open_door applied" in text and "compressor=" in text


def test_live_demo_stops_at_the_end_of_the_scenario(box, make_scenario):
    sim = LiveSimulator(make_scenario(duration_h=1), box, seed=3)
    out = io.StringIO()
    printed = run_live_demo(sim, 60.0, queue.Queue(), [], out, sleep=lambda _s: None)
    assert printed == 7 and "end of scenario" in out.getvalue()
