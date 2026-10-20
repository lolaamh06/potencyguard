"""Deterministic, seeded simulation of one box through one scenario (Phase 1)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from shared.config import BoxConfig
from simulator.box_model import cooling_power_w, steady_state_temp_c, step_box_temp_c
from simulator.scenario import (
    CoolingFactorEvent,
    GlitchEvent,
    HeatLoadEvent,
    Scenario,
    ShockEvent,
    SpoofEvent,
)

# Values are rounded so that the simulator and the recording files agree exactly.
DECIMALS = 4


@dataclass(frozen=True)
class SimulationTrace:
    """All per-sample series plus labels of injected events (ground truth)."""

    t_s: np.ndarray
    ambient_c: np.ndarray
    heat_input_w: np.ndarray
    true_temp_c: np.ndarray
    reported_temp_c: np.ndarray
    rh_pct: np.ndarray
    shock_g: np.ndarray
    labels: list[dict]


def _sample_index(time_s: float, interval_s: float, n: int) -> int:
    return min(max(round(time_s / interval_s), 0), n - 1)


def _window(t_s: np.ndarray, start_h: float, end_h: float) -> np.ndarray:
    return (t_s >= start_h * 3600.0) & (t_s < end_h * 3600.0)


def simulate(scenario: Scenario, box: BoxConfig) -> SimulationTrace:
    """Run the box physics, then add noise and injected events. Same seed gives the same trace."""
    n = scenario.n_samples
    dt_s = scenario.sample_interval_s
    t_s = np.arange(n) * dt_s
    key_t = np.array([t for t, _ in scenario.ambient]) * 3600.0
    key_c = np.array([c for _, c in scenario.ambient])
    ambient = np.interp(t_s, key_t, key_c)

    capacity_factor = np.ones(n)
    extra_heat_w = np.zeros(n)
    rh_delta = np.zeros(n)
    for event in scenario.events:
        if isinstance(event, CoolingFactorEvent):
            capacity_factor[_window(t_s, event.start_h, event.end_h)] *= event.factor
        elif isinstance(event, HeatLoadEvent):
            active = _window(t_s, event.start_h, event.end_h)
            extra_heat_w[active] += event.power_w
            rh_delta[active] += event.rh_delta_pct

    q_w = np.empty(n)
    true_temp = np.empty(n)
    true_temp[0] = box.box_setpoint_c
    tau_s = box.box_tau_h * 3600.0
    for i in range(n):
        q_w[i] = (
            cooling_power_w(
                ambient[i],
                box.box_setpoint_c,
                box.box_R_th_k_per_w,
                box.box_cooling_capacity_w * capacity_factor[i],
            )
            + extra_heat_w[i]
        )
        if i + 1 < n:
            t_inf = steady_state_temp_c(ambient[i], box.box_R_th_k_per_w, q_w[i])
            true_temp[i + 1] = step_box_temp_c(true_temp[i], t_inf, dt_s, tau_s)

    # Noise is drawn in a fixed order so the seed fully determines the output.
    rng = np.random.default_rng(scenario.seed)
    temp_noise = rng.normal(0.0, box.sensor_sigma_c, n)
    rh_noise = rng.normal(0.0, box.sensor_sigma_rh_pct, n)
    shock_noise = np.abs(rng.normal(0.0, box.sensor_sigma_shock_g, n))

    reported = true_temp + temp_noise
    rh = np.clip(scenario.rh_base_pct + rh_delta + rh_noise, 0.0, 100.0)
    shock = shock_noise.copy()

    labels: list[dict] = []
    for event in scenario.events:
        label: dict = event.model_dump()
        if isinstance(event, SpoofEvent):
            active = _window(t_s, event.start_h, event.end_h)
            reported[active] = event.reported_c + temp_noise[active]
        elif isinstance(event, GlitchEvent):
            idx = _sample_index(event.at_h * 3600.0, dt_s, n)
            reported[idx] = event.value_c
            label["sample_index"] = idx
        elif isinstance(event, ShockEvent):
            idx = _sample_index(event.at_h * 3600.0, dt_s, n)
            shock[idx] += event.peak_g
            label["sample_index"] = idx
        if hasattr(event, "start_h"):
            active_idx = np.flatnonzero(_window(t_s, event.start_h, event.end_h))
            label["first_sample_index"] = int(active_idx[0]) if len(active_idx) else None
            label["last_sample_index"] = int(active_idx[-1]) if len(active_idx) else None
        labels.append(label)

    def rounded(values: np.ndarray) -> np.ndarray:
        return np.round(values, DECIMALS)

    return SimulationTrace(
        t_s=rounded(t_s),
        ambient_c=rounded(ambient),
        heat_input_w=rounded(q_w),
        true_temp_c=rounded(true_temp),
        reported_temp_c=rounded(reported),
        rh_pct=rounded(rh),
        shock_g=rounded(shock),
        labels=labels,
    )
