"""Phase 3 simulator extension: ambient and cooling-duty channels, last-sample fix, independence."""

import dataclasses
import json
import math
from pathlib import Path

import pytest
from pydantic import ValidationError

from edge.recorded_source import RecordedSource
from edge.sensor_reading import SensorReading
from simulator.live import LiveSimulator
from simulator.recording import SCHEMA_VERSION, write_recording
from simulator.scenario import load_all_scenarios
from simulator.simulate import simulate

ROOT = Path(__file__).resolve().parent.parent
RECORDINGS = ROOT / "data" / "recordings"
SCENARIOS = load_all_scenarios()


def _reading(**overrides):
    values = {"t_s": 0.0, "temp_c": 5.0, "rh_pct": 45.0, "shock_g": 0.0, "source": "sim"}
    values.update(overrides)
    return SensorReading(**values)


# ----------------------------------------------------------------- the model


def test_new_fields_default_to_none_and_validate():
    reading = _reading()
    assert reading.ambient_c is None and reading.cooling_duty is None
    ok = _reading(ambient_c=22.0, cooling_duty=0.5)
    assert (ok.ambient_c, ok.cooling_duty) == (22.0, 0.5)


@pytest.mark.parametrize(
    "overrides",
    [
        {"ambient_c": -61.0},
        {"ambient_c": 81.0},
        {"ambient_c": math.nan},
        {"cooling_duty": -0.01},
        {"cooling_duty": 1.01},
        {"cooling_duty": math.inf},
    ],
)
def test_new_fields_reject_bad_values(overrides):
    with pytest.raises(ValidationError):
        _reading(**overrides)


# ----------------------------------------------------------------- the engine


def test_duty_is_the_exact_substep_fraction(box, make_scenario):
    # A tiny scenario: ambient 22 C, 10 minute samples, 60 s substeps: duty is a multiple of 0.1.
    run = simulate(make_scenario(duration_h=2), box, seed=3)
    duties = [r.cooling_duty for r in run.readings]
    assert duties[0] == 0.0  # no interval has elapsed before the first sample
    assert all(0.0 <= d <= 1.0 for d in duties)
    assert all(abs(d * 10 - round(d * 10)) < 1e-9 for d in duties)
    assert [s.cooling_duty for s in run.truth] == duties


def test_duty_matches_a_hand_count_of_compressor_state(box, make_scenario):
    # Re-run the physics by hand for one interval and count the substeps with the compressor on.
    scenario = make_scenario(duration_h=1, ambient=[(0, 40), (1, 40)])
    sim = LiveSimulator(scenario, box, seed=5)
    sim.step()
    engine = sim.engine
    temp = engine.true_temp_c
    tau_s = box.box_tau_h * 3600.0
    on = engine.compressor_on
    count = 0
    half = box.box_deadband_c / 2
    dt = engine._dt_s
    for _ in range(engine._n_sub):
        if temp > box.box_setpoint_c + half:
            on = True
        elif temp < box.box_setpoint_c - half:
            on = False
        count += on
        cooling = -box.box_cooling_capacity_w if on else 0.0
        t_inf = 40.0 + box.box_R_th_k_per_w * cooling
        temp = t_inf + (temp - t_inf) * math.exp(-dt / tau_s)
    reading, _ = sim.step()
    assert reading.cooling_duty == pytest.approx(round(count / engine._n_sub, 4))


def test_ambient_channel_is_the_true_ambient_plus_noise(box, make_scenario):
    run = simulate(make_scenario(duration_h=500, ambient=[(0, 22), (500, 22)]), box, seed=2)
    noise = [r.ambient_c - s.ambient_c for r, s in zip(run.readings, run.truth, strict=True)]
    mean = sum(noise) / len(noise)
    std = math.sqrt(sum((x - mean) ** 2 for x in noise) / len(noise))
    assert std == pytest.approx(box.sensor_sigma_ambient_c, rel=0.06)
    assert abs(mean) < 0.01


def test_a_spoof_changes_only_the_temperature_channel(box, make_scenario):
    spoof = [{"type": "spoof", "start_h": 2, "end_h": 10, "mode": "hold", "reported_c": 3.0}]
    plain = simulate(make_scenario(duration_h=12), box, seed=4)
    lied = simulate(make_scenario(duration_h=12, events=spoof), box, seed=4)
    for a, b in zip(plain.readings, lied.readings, strict=True):
        assert (a.ambient_c, a.cooling_duty, a.rh_pct, a.shock_g) == (
            b.ambient_c,
            b.cooling_duty,
            b.rh_pct,
            b.shock_g,
        )
    assert plain.readings[20].temp_c != lied.readings[20].temp_c


def test_ambient_noise_has_its_own_stream(box, make_scenario):
    # Changing the ambient noise level must not change temperature, humidity or shock noise.
    quiet = dataclasses.replace(box, sensor_sigma_ambient_c=0.0)
    loud = dataclasses.replace(box, sensor_sigma_ambient_c=1.0)
    a = simulate(make_scenario(), quiet, seed=9)
    b = simulate(make_scenario(), loud, seed=9)
    for x, y in zip(a.readings, b.readings, strict=True):
        assert (x.temp_c, x.rh_pct, x.shock_g) == (y.temp_c, y.rh_pct, y.shock_g)
    assert any(x.ambient_c != y.ambient_c for x, y in zip(a.readings, b.readings, strict=True))


def test_same_seed_is_still_deterministic(box):
    a = simulate(SCENARIOS["door_open_excursion"], box, seed=77)
    b = simulate(SCENARIOS["door_open_excursion"], box, seed=77)
    assert a.readings == b.readings and a.truth == b.truth


# ----------------------------------------------------------------- golden recordings


@pytest.mark.parametrize("scenario_id", sorted(SCENARIOS))
def test_golden_recordings_carry_the_new_channels(scenario_id):
    source = RecordedSource(RECORDINGS / f"{scenario_id}.jsonl")
    source.start()
    assert source.header["schema_version"] == SCHEMA_VERSION == "0.3"
    count = 0
    while (reading := source.read()) is not None:
        assert reading.ambient_c is not None and reading.cooling_duty is not None
        count += 1
    source.close()
    assert count == SCENARIOS[scenario_id].n_samples
    truth = json.loads((RECORDINGS / f"{scenario_id}.ground_truth.json").read_text("utf-8"))
    for key in ("measured_ambient_c", "cooling_duty", "first_divergence_s", "detect_divergence_c"):
        assert key in truth


def test_first_divergence_is_set_only_for_spoof_scenarios():
    def divergence(name):
        truth = json.loads((RECORDINGS / f"{name}.ground_truth.json").read_text("utf-8"))
        return truth["first_divergence_s"]

    assert divergence("baseline_ok") is None
    assert divergence("sensor_glitch") is None  # a glitch is not a spoof
    assert divergence("spoof_attempt") is not None
    assert divergence("hidden_spoilage") is not None


def test_old_schema_files_are_still_read_without_the_channels(tmp_path):
    old = tmp_path / "old.jsonl"
    old.write_text(
        '{"type":"header","schema_version":"0.2"}\n'
        '{"t_s":0.0,"temp_c":5.0,"rh_pct":45.0,"shock_g":0.0,"source":"sim"}\n',
        encoding="utf-8",
    )
    source = RecordedSource(old)
    source.start()
    reading = source.read()
    source.close()
    assert reading.ambient_c is None and reading.cooling_duty is None


# ----------------------------------------------------------------- last-sample fix


def test_an_event_ending_at_the_trip_end_covers_the_final_sample(box, make_scenario):
    spoof = [{"type": "spoof", "start_h": 1, "end_h": 6, "mode": "hold", "reported_c": 9.0}]
    run = simulate(make_scenario(duration_h=6, events=spoof), box, seed=1)
    assert run.truth[-1].spoof_mode == "hold"
    assert abs(run.readings[-1].temp_c - 9.0) < 0.5
    event = run.events[0]
    assert event.covers_final_sample and event.end_s == 6 * 3600


def test_an_event_ending_earlier_does_not_cover_the_final_sample(box, make_scenario):
    spoof = [{"type": "spoof", "start_h": 1, "end_h": 5, "mode": "hold", "reported_c": 9.0}]
    run = simulate(make_scenario(duration_h=6, events=spoof), box, seed=1)
    assert run.truth[-1].spoof_mode is None
    assert not run.events[0].covers_final_sample
    # and it is still closed at its end sample
    assert run.truth[5 * 6].spoof_mode is None and run.truth[5 * 6 - 1].spoof_mode == "hold"


def test_open_ended_injections_cover_every_later_sample(box, make_scenario):
    sim = LiveSimulator(make_scenario(duration_h=3), box, seed=1)
    for _ in range(4):
        sim.step()
    assert sim.inject({"type": "spoof_sensor", "mode": "hold", "reported_c": 9.0}).accepted
    modes = []
    while (pair := sim.step())[0] is not None:
        modes.append(pair[1].spoof_mode)
    assert modes and all(m == "hold" for m in modes)


def test_an_injection_ending_exactly_at_the_trip_end_covers_the_final_sample(box, make_scenario):
    sim = LiveSimulator(make_scenario(duration_h=2), box, seed=1)
    for _ in range(6):  # samples 0..5 are emitted; the last emitted time is 50 minutes
        sim.step()
    assert sim.inject(
        {"type": "spoof_sensor", "mode": "hold", "reported_c": 9.0, "duration_min": 70}
    ).accepted
    last = None
    while (pair := sim.step())[0] is not None:
        last = pair[1]
    assert last.t_s == 7200.0 and last.spoof_mode == "hold"


def test_the_golden_spoof_recordings_end_falsified(box):
    for name in ("spoof_attempt", "hidden_spoilage"):
        truth = json.loads((RECORDINGS / f"{name}.ground_truth.json").read_text("utf-8"))
        assert truth["spoof_mode"][-1] == "hold", name
        assert abs(truth["reported_temp_c"][-1] - truth["true_temp_c"][-1]) > 1.0


def test_write_recording_reports_the_schema(box, tmp_path):
    recording, _ = write_recording(SCENARIOS["baseline_ok"], box, tmp_path)
    header = json.loads(recording.read_text(encoding="utf-8").splitlines()[0])
    assert header["schema_version"] == "0.3"
