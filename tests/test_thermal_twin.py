"""Thermal twin: prediction, bounds, the lag-aware floor and the stored parameters."""

import dataclasses
import math

import pytest
from pydantic import ValidationError

from edge.thermal_twin import (
    TwinParams,
    advance_floor,
    equilibrium_c,
    floor_bound,
    load_twin_params,
    max_step_bound,
    predict_next,
)
from shared.config import ConfigError
from simulator.simulate import simulate

PARAMS = TwinParams(tau_h=6.0, dT_cool_c=30.0, sigma_r_c=0.07)
DT = 600.0


def test_predict_next_matches_the_closed_form():
    t_inf = 22.0 - 30.0 * 0.4
    expected = t_inf + (5.0 - t_inf) * math.exp(-DT / (6.0 * 3600.0))
    assert predict_next(5.0, 22.0, 0.4, DT, PARAMS) == pytest.approx(expected, rel=1e-14)
    assert equilibrium_c(22.0, 0.4, PARAMS) == pytest.approx(10.0)


def test_predict_next_stays_put_at_equilibrium_and_moves_towards_it():
    assert predict_next(10.0, 22.0, 0.4, DT, PARAMS) == pytest.approx(10.0)
    assert 5.0 < predict_next(5.0, 22.0, 0.4, DT, PARAMS) < 10.0
    assert 10.0 < predict_next(20.0, 22.0, 0.4, DT, PARAMS) < 20.0


@pytest.mark.parametrize(
    "args",
    [
        (math.nan, 22.0, 0.5, DT),
        (5.0, math.inf, 0.5, DT),
        (5.0, 22.0, -0.1, DT),
        (5.0, 22.0, 1.1, DT),
        (5.0, 22.0, 0.5, 0.0),
        (5.0, 22.0, 0.5, -5.0),
        (5.0, 22.0, True, DT),
    ],
)
def test_inputs_are_validated(args):
    with pytest.raises(ValueError):
        predict_next(*args, PARAMS)


def test_params_are_validated_and_frozen():
    for bad in ({"tau_h": 0}, {"dT_cool_c": -1}, {"sigma_r_c": math.nan}):
        with pytest.raises(ValidationError):
            TwinParams(**{**PARAMS.model_dump(), **bad})
    with pytest.raises(ValidationError):
        PARAMS.tau_h = 1.0  # type: ignore[misc]
    assert PARAMS.tau_s == 21600.0


def test_clean_run_residuals_are_small_without_noise(box, make_scenario):
    quiet = dataclasses.replace(
        box,
        sensor_sigma_c=0.0,
        sensor_sigma_rh_pct=0.0,
        sensor_sigma_shock_g=0.0,
        sensor_sigma_ambient_c=0.0,
    )
    run = simulate(
        make_scenario(duration_h=48, ambient=[(0, 22), (24, 36), (48, 12)]), quiet, seed=1
    )
    params = TwinParams(
        tau_h=box.box_tau_h,
        dT_cool_c=box.box_R_th_k_per_w * box.box_cooling_capacity_w,
        sigma_r_c=0.07,
    )
    residuals = []
    for prev, cur in zip(run.readings, run.readings[1:], strict=False):
        amb = (prev.ambient_c + cur.ambient_c) / 2
        residuals.append(cur.temp_c - predict_next(prev.temp_c, amb, cur.cooling_duty, DT, params))
    # Only the within-interval timing of the compressor and the 4-decimal rounding remain.
    assert max(abs(r) for r in residuals) < 0.1
    assert sum(abs(r) for r in residuals) / len(residuals) < 0.03


def test_max_step_bound_is_smallest_between_the_two_equilibria():
    # The box is pulled towards ambient (no cooling) or ambient - dT_cool (full cooling), here
    # 22 C and -8 C. The farthest of the two sets the bound, so it is smallest halfway between.
    middle = max_step_bound(7.0, 22.0, DT, PARAMS)
    cold = max_step_bound(5.0, 22.0, DT, PARAMS)
    near = max_step_bound(21.5, 22.0, DT, PARAMS)
    assert middle < cold < near
    # Without a heat allowance the warm end is ambient: the farthest equilibrium from 21.5 C is
    # the fully cooled one (22 - 30), a distance of 29.5 K.
    expected = 29.5 * (1 - math.exp(-DT / PARAMS.tau_s)) + 5 * PARAMS.sigma_r_c
    assert near == pytest.approx(expected, rel=1e-12)


def test_max_step_bound_heat_allowance_and_tolerance():
    base = max_step_bound(5.0, 22.0, DT, PARAMS, heat_allowance_c=0.0, tolerance_sigma=0.0)
    widened = max_step_bound(5.0, 22.0, DT, PARAMS, heat_allowance_c=60.0, tolerance_sigma=0.0)
    assert widened > base
    assert max_step_bound(5.0, 22.0, DT, PARAMS, 0.0, 5.0) == pytest.approx(
        base + 5 * PARAMS.sigma_r_c
    )
    with pytest.raises(ValueError):
        max_step_bound(5.0, 22.0, DT, PARAMS, heat_allowance_c=-1.0)


def test_floor_bound_is_ambient_minus_the_cooling_depression():
    assert floor_bound(22.0, PARAMS) == -8.0
    assert floor_bound(40.0, PARAMS) == 10.0


def test_lag_aware_floor_follows_the_dynamics():
    # The ambient jumps from 0 to 40 C: the steady floor is 10 C, but a box starting at 5 C
    # can still lawfully be colder than 10 C for a while.
    floor = 5.0
    values = []
    for _ in range(50):
        floor = advance_floor(floor, 40.0, DT, PARAMS)
        values.append(floor)
    assert values == sorted(values)  # rising towards the steady floor
    assert values[0] < 5.5
    assert values[-1] < floor_bound(40.0, PARAMS)
    assert abs(advance_floor(10.0, 40.0, DT, PARAMS) - 10.0) < 1e-12


def test_the_stored_parameters_load_and_are_close_to_the_simulated_box(box):
    params = load_twin_params()
    assert params.tau_h == pytest.approx(box.box_tau_h, rel=0.03)
    assert params.dT_cool_c == pytest.approx(
        box.box_R_th_k_per_w * box.box_cooling_capacity_w, rel=0.03
    )
    assert 0.05 < params.sigma_r_c < 0.1


def test_a_broken_parameter_file_is_reported(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("tau_h: -1\ndT_cool_c: 30\nsigma_r_c: 0.1\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_twin_params(bad)
    with pytest.raises(ConfigError):
        load_twin_params(tmp_path / "missing.yaml")
