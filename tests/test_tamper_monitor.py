"""Tamper monitor: each detector on hand-built sequences, the classification table, golden runs."""

import io
import math
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from edge.cli import main as edge_main
from edge.detector_config import DetectorConfig, load_detector_config
from edge.sensor_reading import SensorReading
from edge.tamper_monitor import (
    FALSIFICATION,
    GLITCH,
    OK,
    THERMAL_ANOMALY,
    TamperMonitor,
)
from edge.thermal_twin import TwinParams, load_twin_params, predict_next
from edge.twin_cli import analyse

ROOT = Path(__file__).resolve().parent.parent
PARAMS = load_twin_params()
CONFIG = load_detector_config()
DT = 600.0
SIGMA_SENSOR = 0.05


def make_monitor(config: DetectorConfig = CONFIG, confirm: int = 2) -> TamperMonitor:
    return TamperMonitor(PARAMS, config, confirm, SIGMA_SENSOR)


def reading(i, temp, amb=22.0, duty=0.5) -> SensorReading:
    return SensorReading(
        t_s=i * DT,
        temp_c=temp,
        rh_pct=45.0,
        shock_g=0.0,
        source="sim",
        ambient_c=amb,
        cooling_duty=duty,
    )


def series(n, *, amb=22.0, duty=0.5, t0=7.0, noise=SIGMA_SENSOR, seed=0, bias=0.0, bias_from=10**9):
    """Readings that follow the twin exactly, plus measurement noise and an optional drift."""
    rng = np.random.default_rng(seed)
    true = t0
    out = []
    for i in range(n):
        if i > 0:
            true = predict_next(true, amb, duty, DT, PARAMS) + (bias if i >= bias_from else 0.0)
        out.append(reading(i, true + float(rng.normal(0.0, noise)), amb, duty))
    return out


def run(monitor, readings):
    return [monitor.update(r) for r in readings]


# ----------------------------------------------------------------- CUSUM


def test_cusum_stays_quiet_on_pure_noise():
    for seed in range(5):
        monitor = make_monitor()
        states = run(monitor, series(2000, seed=seed))
        assert not any(s.flag_cusum_pos or s.flag_cusum_neg for s in states), seed
        assert all(s.verdict == OK for s in states)


@pytest.mark.parametrize(("bias", "flag"), [(0.2, "flag_cusum_pos"), (-0.2, "flag_cusum_neg")])
def test_cusum_fires_on_a_sustained_bias_within_the_expected_number_of_samples(bias, flag):
    onset = 100
    monitor = make_monitor()
    states = run(monitor, series(200, bias=bias, bias_from=onset, seed=3))
    shift_sigma = abs(bias) / PARAMS.sigma_r_c
    expected = math.ceil(CONFIG.cusum_h / (shift_sigma - CONFIG.cusum_k))
    first = next(i for i, s in enumerate(states) if getattr(s, flag))
    assert onset <= first <= onset + expected + 2
    assert not any(getattr(s, flag) for s in states[:onset])


def test_a_small_bias_takes_longer_than_a_large_one():
    onset = 100

    def first_alarm(bias):
        states = run(make_monitor(), series(400, bias=bias, bias_from=onset, seed=3))
        return next((i for i, s in enumerate(states) if s.flag_cusum_pos), None)

    large, small = first_alarm(0.2), first_alarm(0.05)
    assert large is not None and small is not None
    assert small - onset > 2 * (large - onset)


def _calm_after(last_temp, start_index, count):
    """Readings that follow the twin exactly (zero residual) from the given state."""
    out, temp = [], last_temp
    for i in range(count):
        temp = predict_next(temp, 22.0, 0.5, DT, PARAMS)
        out.append(reading(start_index + i, temp))
    return out


def test_the_cusum_statistic_is_capped_and_recovers():
    monitor = make_monitor()
    drift = series(120, bias=0.3, bias_from=50, seed=2)
    states = run(monitor, drift)
    cap = CONFIG.cusum_cap_factor * CONFIG.cusum_h
    assert max(s.cusum_pos for s in states) == pytest.approx(cap)
    calm = run(monitor, _calm_after(drift[-1].temp_c, 120, 60))
    assert calm[-1].cusum_pos < CONFIG.cusum_h and calm[-1].verdict == OK


# ----------------------------------------------------------------- impossible step


def test_impossible_step_fires_on_a_jump_beyond_the_bound_and_not_below_it():
    base = series(60, seed=1)
    big = base[:30] + [r.model_copy(update={"temp_c": r.temp_c + 10.0}) for r in base[30:]]
    states = run(make_monitor(), big)
    assert states[30].flag_step and not any(s.flag_step for s in states[:30])
    small = base[:30] + [r.model_copy(update={"temp_c": r.temp_c + 0.3}) for r in base[30:]]
    assert not any(s.flag_step for s in run(make_monitor(), small))


# ----------------------------------------------------------------- impossible state


def test_impossible_state_needs_consecutive_samples():
    # Ambient 60 C, so the coldest the box could be rises quickly; the reading stays at 5 C.
    flags = {}
    for m in (1, 3, 5):
        cfg = CONFIG.model_copy(update={"state_consecutive_samples": m})
        states = run(make_monitor(cfg), [reading(i, 5.0, amb=60.0, duty=1.0) for i in range(20)])
        flags[m] = next(i for i, s in enumerate(states) if s.flag_state)
    assert flags[3] - flags[1] == 2
    assert flags[5] - flags[1] == 4


def test_a_dip_shorter_than_the_run_does_not_fire_the_state_flag():
    cfg = CONFIG.model_copy(update={"state_consecutive_samples": 4})
    readings = [reading(i, 5.0, amb=60.0, duty=1.0) for i in range(3)]  # below for 3 samples...
    readings += [reading(3 + i, 30.0, amb=60.0, duty=1.0) for i in range(5)]  # ...then plausible
    assert not any(s.flag_state for s in run(make_monitor(cfg), readings))


def test_an_honest_box_that_lags_a_rising_ambient_is_not_impossible():
    # Colder than the steady floor for hours after the ambient rises: lawful, so no flag.
    amb = [10.0] * 10 + [40.0] * 60
    true, readings = 5.0, []
    for i, a in enumerate(amb):
        if i:
            true = predict_next(true, a, 1.0, DT, PARAMS)
        readings.append(reading(i, true, amb=a, duty=1.0))
    states = run(make_monitor(), readings)
    assert not any(s.flag_state for s in states)
    assert min(r.temp_c for r in readings[10:]) < 40.0 - PARAMS.dT_cool_c  # below the steady floor


# ----------------------------------------------------------------- flat line


def test_flat_line_fires_on_a_frozen_sensor_but_not_on_noisy_data():
    frozen = [reading(i, 5.0) for i in range(40)]
    states = run(make_monitor(), frozen)
    first = next(i for i, s in enumerate(states) if s.flag_flat)
    assert first == CONFIG.flat_window_samples - 1
    assert not any(s.flag_flat for s in run(make_monitor(), series(500, seed=7)))


# ----------------------------------------------------------------- classification table


def test_positive_drift_is_a_thermal_anomaly_not_a_falsification():
    states = run(make_monitor(), series(200, bias=0.2, bias_from=100, seed=5))
    verdicts = {s.verdict for s in states}
    assert THERMAL_ANOMALY in verdicts and FALSIFICATION not in verdicts


def test_negative_drift_is_a_suspected_falsification():
    states = run(make_monitor(), series(200, bias=-0.2, bias_from=100, seed=5))
    assert states[-1].verdict == FALSIFICATION
    first = next(i for i, s in enumerate(states) if s.verdict == FALSIFICATION)
    assert first >= 100


def test_a_lone_impossible_step_with_immediate_recovery_is_a_sensor_glitch():
    base = series(80, seed=6)
    spiked = base[:40] + [base[40].model_copy(update={"temp_c": 45.0})] + base[41:]
    monitor = make_monitor()
    states = run(monitor, spiked)
    assert states[40].verdict == GLITCH and states[41].verdict == GLITCH
    assert FALSIFICATION not in {s.verdict for s in states}
    assert states[-1].verdict == OK
    # the spike did not push the CUSUM around
    assert max(s.cusum_pos for s in states) < CONFIG.cusum_h


def test_a_persistent_jump_is_a_suspected_falsification_after_the_confirmation_count():
    base = series(80, seed=6)
    jumped = base[:40] + [r.model_copy(update={"temp_c": r.temp_c + 12.0}) for r in base[40:]]
    states = run(make_monitor(confirm=2), jumped)
    assert [s.verdict for s in states[40:42]] == [GLITCH, FALSIFICATION]
    immediate = run(make_monitor(confirm=1), jumped)
    assert immediate[40].verdict == FALSIFICATION
    slow = run(make_monitor(confirm=3), jumped)
    assert [s.verdict for s in slow[40:43]] == [GLITCH, GLITCH, FALSIFICATION]


def test_proof_of_falsification_is_latched_until_reset():
    base = series(120, seed=6)
    jumped = base[:40] + [r.model_copy(update={"temp_c": r.temp_c + 12.0}) for r in base[40:]]
    monitor = make_monitor()
    states = run(monitor, jumped)
    assert states[-1].verdict == FALSIFICATION
    monitor.reset()
    assert monitor.snapshot().verdict == OK and monitor.verdict_history == []
    assert run(monitor, base)[-1].verdict == OK


def test_a_negative_cusum_alarm_alone_is_held_but_not_latched():
    onset = 60
    drift = series(onset + 10, bias=-0.2, bias_from=onset, seed=5)
    monitor = make_monitor()
    states = run(monitor, drift)
    assert states[-1].verdict == FALSIFICATION and not any(s.flag_step for s in states)
    calm = run(monitor, _calm_after(drift[-1].temp_c, onset + 10, 80))
    assert calm[-1].verdict == OK  # the statistic drained and the hold expired
    assert [v for _, v in monitor.verdict_history][-2:] == [FALSIFICATION, OK]


# ----------------------------------------------------------------- housekeeping


def test_first_state_has_no_prediction_and_no_residual_flags():
    state = make_monitor().update(reading(0, 5.0))
    assert state.predicted_c is None and state.residual_c is None
    assert not (state.flag_cusum_pos or state.flag_cusum_neg or state.flag_step or state.flag_flat)
    assert state.verdict == OK and state.samples_seen == 1


def test_missing_channels_and_time_going_backwards_are_errors():
    monitor = make_monitor()
    bare = SensorReading(t_s=0.0, temp_c=5.0, rh_pct=45.0, shock_g=0.0, source="sim")
    with pytest.raises(ValueError, match="ambient_c and cooling_duty"):
        monitor.update(bare)
    monitor.update(reading(1, 5.0))
    with pytest.raises(ValueError, match="time must increase"):
        monitor.update(reading(1, 5.0))
    with pytest.raises(ValueError):
        make_monitor(confirm=0)


def test_snapshot_returns_the_latest_state():
    monitor = make_monitor()
    assert monitor.snapshot().samples_seen == 0
    state = monitor.update(reading(0, 5.0))
    assert monitor.snapshot() == state


def test_from_defaults_builds_a_working_monitor(box, product):
    monitor = TamperMonitor.from_defaults(product, box)
    assert monitor.update(reading(0, 5.0)).verdict == OK


def test_detector_config_is_validated(tmp_path):
    from shared.config import ConfigError

    bad = tmp_path / "bad.yaml"
    bad.write_text("cusum_k: 0.5\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_detector_config(bad)
    assert CONFIG.flat_window_samples >= 2
    with pytest.raises(ValidationError):
        TwinParams(tau_h=1, dT_cool_c=1, sigma_r_c=0)


# ----------------------------------------------------------------- golden recordings


@pytest.fixture(scope="module")
def golden(box, product):
    folder = ROOT / "data" / "recordings"
    return {p.stem: analyse(p, product, box) for p in sorted(folder.glob("*.jsonl"))}


def _verdicts(analysis):
    return {s.verdict for s in analysis.states}


@pytest.mark.parametrize("name", ["baseline_ok", "shock_drop", "freeze_event"])
def test_clean_golden_runs_have_no_verdict_at_all(golden, name):
    assert _verdicts(golden[name]) == {OK}


def test_sensor_glitch_gives_one_glitch_and_no_tamper_verdict(golden):
    analysis = golden["sensor_glitch"]
    assert FALSIFICATION not in _verdicts(analysis)
    assert sum(1 for _, v in analysis.monitor.verdict_history if v == GLITCH) == 1


@pytest.mark.parametrize("name", ["reefer_failure", "door_open_excursion", "heatwave_transit"])
def test_physical_events_are_thermal_anomalies_and_never_falsifications(golden, name):
    verdicts = _verdicts(golden[name])
    assert THERMAL_ANOMALY in verdicts and FALSIFICATION not in verdicts


@pytest.mark.parametrize("name", ["spoof_attempt", "hidden_spoilage"])
def test_spoofs_are_caught_within_a_few_samples_of_the_divergence(golden, name):
    analysis = golden[name]
    assert analysis.first_divergence_s is not None
    delay = analysis.detection_delay_s()
    # Measured delay: 1 sample (the persistence wait of the lone-jump rule); the bound adds margin.
    assert delay is not None and delay <= 3 * analysis.interval_s
    assert analysis.states[-1].verdict == FALSIFICATION


def test_the_monitor_and_the_potency_tracker_agree_on_a_lone_glitch(golden):
    analysis = golden["sensor_glitch"]
    suspect = [p for p in analysis.potency if p.status == "suspect"]
    glitch = [s for s in analysis.states if s.verdict == GLITCH]
    assert len(suspect) == 1 and len(glitch) >= 1
    assert analysis.potency[-1].samples_excluded == 1


# ----------------------------------------------------------------- the commands


def test_twin_command_for_one_recording():
    out = io.StringIO()
    path = ROOT / "data" / "recordings" / "spoof_attempt.jsonl"
    assert edge_main(["twin", "--recording", str(path)], out) == 0
    text = out.getvalue()
    for needle in (
        "First alarm per detector:",
        "Verdict timeline:",
        "true divergence starts",
        "detection delay",
        "suspected_falsification",
        "potency %",
    ):
        assert needle in text
    assert text.rstrip().endswith("Simulation result on a synthetic box. Not real-world evidence.")


def test_twin_command_verbose_prints_every_sample():
    quiet, loud = io.StringIO(), io.StringIO()
    path = ROOT / "data" / "recordings" / "shock_drop.jsonl"
    edge_main(["twin", "--recording", str(path)], quiet)
    edge_main(["twin", "--recording", str(path), "--verbose"], loud)
    assert loud.getvalue().count("\n") > quiet.getvalue().count("\n") + 100


def test_twin_command_all_prints_one_line_per_recording():
    out = io.StringIO()
    assert edge_main(["twin", "--all"], out) == 0
    lines = [
        ln for ln in out.getvalue().splitlines() if ln and not ln.startswith(("recording", "Sim"))
    ]
    assert len(lines) == 9
    assert any("suspected_falsification" in ln for ln in lines)
    assert out.getvalue().rstrip().endswith("Not real-world evidence.")


def test_twin_command_rejects_a_missing_file_and_old_schema_files(tmp_path):
    assert edge_main(["twin", "--recording", str(tmp_path / "nope.jsonl")], io.StringIO()) == 2
    old = tmp_path / "old.jsonl"
    old.write_text(
        '{"type":"header","schema_version":"0.2","scenario_id":"x","seed":1,"sample_interval_s":600}\n'
        '{"t_s":0.0,"temp_c":5.0,"rh_pct":45.0,"shock_g":0.0,"source":"sim"}\n',
        encoding="utf-8",
    )
    assert edge_main(["twin", "--recording", str(old)], io.StringIO()) == 2


def test_calibrate_command_reproduces_the_stored_parameters(tmp_path, monkeypatch):
    from edge import thermal_twin, twin_cli

    target = tmp_path / "twin.yaml"
    out = io.StringIO()
    assert twin_cli.run_calibrate(twin_cli.DEFAULT_CALIBRATION_DIR, target, out) == 0
    assert "fitted from 10 runs" in out.getvalue()
    refit = thermal_twin.load_twin_params(target)
    assert refit.tau_h == pytest.approx(load_twin_params().tau_h, rel=1e-12)
