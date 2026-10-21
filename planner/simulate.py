"""Scenario sampling and potency propagation for the planner (Phase 5).

All numbers come from config/planner.yaml (illustrative placeholders, not sourced
[SOURCE NEEDED]). Simulation results on a synthetic box, not real-world evidence. The planner
recommends; it never executes. Final authority stays with QA.

Common random numbers: ONE set of scenarios is drawn per call and every action uses the same
ambient path, so differences between actions come from the actions, not from sampling noise.
The generator is built from SeedSequence(seed) and spawned into four children (ambient noise,
heat wave, delays, cooling failures) in a fixed draw order: a fixed seed gives identical arrays.

Maths that already exists is reused, not rewritten: the acceleration factor is the function in
edge/potency.py (tabulated on a 0.01 degree grid and interpolated, for speed; a test compares the
table with the function), the potency at arrival is potency_from_tau_eq, and the box temperature
follows the single-node twin update of edge/thermal_twin.py (a test compares the vectorised step
with predict_next). A single-node twin does not represent a box with a payload (Phase 3C).
"""

from __future__ import annotations

import functools
import math
from dataclasses import dataclass

import numpy as np

from edge.potency import arrhenius_acceleration_factor, potency_from_tau_eq
from edge.thermal_twin import TwinParams
from planner.config import ACTIONS, ActionConfig, PlannerConfig
from shared.config import ProductConfig

AF_GRID_MIN_C = -60.0
AF_GRID_MAX_C = 120.0
AF_GRID_STEP_C = 0.01
SECONDS_PER_HOUR = 3600.0


@functools.lru_cache(maxsize=8)
def _af_table(product: ProductConfig) -> tuple[np.ndarray, np.ndarray]:
    n = round((AF_GRID_MAX_C - AF_GRID_MIN_C) / AF_GRID_STEP_C) + 1
    grid = AF_GRID_MIN_C + AF_GRID_STEP_C * np.arange(n)
    values = np.array([arrhenius_acceleration_factor(float(t), product) for t in grid])
    return grid, values


def acceleration_factor(temps_c: np.ndarray, product: ProductConfig) -> np.ndarray:
    """The acceleration factor of edge/potency.py, interpolated from its own values."""
    grid, values = _af_table(product)
    return np.interp(temps_c, grid, values)


def twin_step(
    temp_c: np.ndarray, ambient_c: np.ndarray, duty: np.ndarray, dt_h: float, twin: TwinParams
) -> np.ndarray:
    """The single-node twin update of edge/thermal_twin.py (predict_next), vectorised."""
    t_inf = ambient_c - twin.dT_cool_c * duty
    return t_inf + (temp_c - t_inf) * math.exp(-dt_h * SECONDS_PER_HOUR / twin.tau_s)


@dataclass(frozen=True)
class ScenarioSet:
    """The random draws of one planning call (the same for every action)."""

    n: int
    steps: int
    ambient_z: np.ndarray  # [n, steps]
    heatwave_occurs: np.ndarray  # [n] bool
    heatwave_start_fraction: np.ndarray  # [n] in [0, 1)
    delay_z: np.ndarray  # [n, actions]
    fail_u: np.ndarray  # [n, actions] uniform: the cooling fails if it is below the probability
    fail_fraction: np.ndarray  # [n, actions] uniform


def draw_scenarios(cfg: PlannerConfig) -> ScenarioSet:
    steps = math.ceil(cfg.max_horizon_h / cfg.dt_h)
    n, a = cfg.n_scenarios, len(ACTIONS)
    seeds = np.random.SeedSequence(cfg.seed).spawn(4)
    r_ambient, r_heat, r_delay, r_fail = (np.random.Generator(np.random.PCG64(s)) for s in seeds)
    ambient_z = r_ambient.standard_normal((n, steps))
    heat = r_heat.random((n, 2))
    delay_z = r_delay.standard_normal((n, a))
    fail = r_fail.random((n, a, 2))
    return ScenarioSet(
        n=n,
        steps=steps,
        ambient_z=ambient_z,
        heatwave_occurs=heat[:, 0] < cfg.ambient.heatwave_probability,
        heatwave_start_fraction=heat[:, 1],
        delay_z=delay_z,
        fail_u=fail[:, :, 0],
        fail_fraction=fail[:, :, 1],
    )


def ambient_paths(
    cfg: PlannerConfig, sc: ScenarioSet, ambient_now_c: float, remaining_h: float
) -> dict[str, np.ndarray]:
    """Sampled ambient temperature at times 0, dt, 2dt, ... for the route and for the depot."""
    amb, dt = cfg.ambient, cfg.dt_h
    out = {}
    for mode, mean, theta, sigma, start in (
        (
            "route",
            ambient_now_c if amb.route_mean_mode == "persistence" else amb.route_mean_c,
            amb.route_theta_per_h,
            amb.route_sigma_c,
            ambient_now_c,
        ),
        ("depot", amb.depot_mean_c, amb.depot_theta_per_h, amb.depot_sigma_c, amb.depot_mean_c),
    ):
        decay = math.exp(-theta * dt)
        noise_sd = sigma * math.sqrt((1.0 - math.exp(-2.0 * theta * dt)) / (2.0 * theta))
        path = np.empty((sc.n, sc.steps + 1))
        path[:, 0] = start
        for k in range(sc.steps):
            path[:, k + 1] = mean + (path[:, k] - mean) * decay + noise_sd * sc.ambient_z[:, k]
        if mode == "route" and amb.heatwave_probability > 0:
            t = dt * np.arange(sc.steps + 1)[None, :]
            begin = (sc.heatwave_start_fraction * max(remaining_h, dt))[:, None]
            inside = (t >= begin) & (t < begin + amb.heatwave_duration_h)
            path += amb.heatwave_offset_c * (sc.heatwave_occurs[:, None] & inside)
        out[mode] = path
    return out


@dataclass(frozen=True)
class ActionSample:
    """Per-scenario results of one action."""

    losses: np.ndarray
    potency_arrival: np.ndarray
    delay_h: np.ndarray
    failed: np.ndarray  # bool: P_arr < P_min


def simulate_action(
    index: int,
    action: ActionConfig,
    cfg: PlannerConfig,
    sc: ScenarioSet,
    paths: dict[str, np.ndarray],
    start_tau_eq_h: float,
    start_temp_c: float,
    remaining_h: float,
    twin: TwinParams,
    product: ProductConfig,
    setpoint_c: float,
    cooling_already_suspect: bool = False,
) -> ActionSample:
    dt = cfg.dt_h
    delay_draw = np.maximum(0.0, action.delay_mean_h + action.delay_sd_h * sc.delay_z[:, index])
    raw_horizon = action.time_factor * remaining_h + action.time_offset_h + delay_draw
    horizon = np.clip(raw_horizon, 0.0, cfg.max_horizon_h)
    steps_n = np.rint(horizon / dt).astype(int)
    if cooling_already_suspect:
        # the monitor sees a cooling shortfall now: the unit is assumed to be off from the start
        fails = sc.fail_u[:, index] < cfg.anomaly_cooling_fail_probability
        fail_time = np.where(fails, 0.0, np.inf)
    else:
        fails = sc.fail_u[:, index] < action.cooling_fail_probability
        fail_time = np.where(fails, sc.fail_fraction[:, index] * horizon, np.inf)

    tau = np.full(sc.n, 0.0 if action.fresh_start else float(start_tau_eq_h))
    temp = np.full(sc.n, setpoint_c if action.fresh_start else float(start_temp_c))
    path = paths[action.ambient_mode]
    for k in range(int(steps_n.max(initial=0))):
        active = k < steps_n
        amb = 0.5 * (path[:, k] + path[:, k + 1])
        needed = np.clip((amb - setpoint_c) / twin.dT_cool_c, 0.0, 1.0)  # thermostat proxy
        duty = np.where(dt * k < fail_time, needed, 0.0)
        new_temp = twin_step(temp, amb, duty, dt, twin)
        tau = tau + np.where(active, acceleration_factor(new_temp, product) * dt, 0.0)
        temp = np.where(active, new_temp, temp)
    potency = np.array([potency_from_tau_eq(float(t), product) for t in tau])
    failed = potency < product.P_min
    delay_h = action.extra_delay_h + np.maximum(0.0, raw_horizon - remaining_h)
    losses = action.cost + cfg.V * failed + cfg.beta * delay_h
    return ActionSample(losses, potency, delay_h, failed)
