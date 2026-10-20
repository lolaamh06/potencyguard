"""Tests for SensorReading, SensorSource and SimClock."""

import math

import pytest
from pydantic import ValidationError

from edge.sensor_reading import SensorReading
from edge.sensor_source import SensorSource
from edge.sim_clock import SPEED_PRESETS, SimClock, advance_sim_time


def _reading(**overrides) -> SensorReading:
    values = {"t_s": 0.0, "temp_c": 5.0, "rh_pct": 45.0, "shock_g": 0.02, "source": "sim"}
    values.update(overrides)
    return SensorReading(**values)


def test_valid_reading():
    r = _reading(t_s=600.0)
    assert (r.t_s, r.temp_c, r.source) == (600.0, 5.0, "sim")


@pytest.mark.parametrize("field", ["t_s", "temp_c", "rh_pct", "shock_g"])
@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_rejects_nan_and_infinity(field, bad):
    with pytest.raises(ValidationError):
        _reading(**{field: bad})


def test_rejects_negative_time():
    with pytest.raises(ValidationError):
        _reading(t_s=-1.0)


@pytest.mark.parametrize(
    "overrides", [{"rh_pct": -1.0}, {"rh_pct": 100.5}, {"shock_g": -0.1}, {"temp_c": 500.0}]
)
def test_rejects_out_of_range(overrides):
    with pytest.raises(ValidationError):
        _reading(**overrides)


def test_rejects_empty_source():
    with pytest.raises(ValidationError):
        _reading(source="")


def test_reading_is_immutable():
    with pytest.raises(ValidationError):
        _reading().temp_c = 9.0  # type: ignore[misc]


def test_sensor_source_is_abstract():
    with pytest.raises(TypeError):
        SensorSource()  # type: ignore[abstract]


@pytest.mark.parametrize("speed", SPEED_PRESETS)
def test_clock_advances_by_speed(speed):
    clock = SimClock(speed_factor=speed)
    assert clock.tick(2.0) == pytest.approx(2.0 * speed)
    assert clock.tick(1.0) == pytest.approx(3.0 * speed)


def test_advance_is_pure():
    assert advance_sim_time(100.0, 0.5, 60.0) == 130.0
    assert advance_sim_time(100.0, 0.5, 60.0) == 130.0


def test_clock_reset_and_speed_change():
    clock = SimClock(speed_factor=60.0)
    clock.tick(1.0)
    clock.set_speed(3600.0)
    assert clock.now_s == 60.0
    clock.tick(1.0)
    assert clock.now_s == 3660.0
    clock.reset()
    assert clock.now_s == 0.0


@pytest.mark.parametrize(
    "args",
    [(-1.0, 1.0, 1.0), (0.0, -1.0, 1.0), (0.0, 1.0, 0.0), (0.0, 1.0, -5.0), (0.0, math.nan, 1.0)],
)
def test_clock_rejects_bad_input(args):
    with pytest.raises(ValueError):
        advance_sim_time(*args)


def test_clock_rejects_bad_construction():
    with pytest.raises(ValueError):
        SimClock(speed_factor=0.0)
    with pytest.raises(ValueError):
        SimClock(now_s=-1.0)
