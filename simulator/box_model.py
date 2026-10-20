"""Lumped thermal model of the insulated box (master brief section 3.3).

C dT/dt = (T_amb - T) / R_th + Q, with tau = R_th * C. With inputs constant over one sample the
exact step is T[n+1] = T_inf + (T[n] - T_inf) * exp(-dt / tau) and T_inf = T_amb + R_th * Q.
"""

from __future__ import annotations

import math


def steady_state_temp_c(t_amb_c: float, r_th_k_per_w: float, q_w: float) -> float:
    """T_inf: where the box temperature settles for constant ambient and heat input Q."""
    return t_amb_c + r_th_k_per_w * q_w


def step_box_temp_c(t_c: float, t_inf_c: float, dt_s: float, tau_s: float) -> float:
    """Exact one-sample update of the box temperature."""
    if dt_s < 0 or tau_s <= 0:
        raise ValueError(f"need dt_s >= 0 and tau_s > 0 (got {dt_s}, {tau_s})")
    return t_inf_c + (t_c - t_inf_c) * math.exp(-dt_s / tau_s)


def cooling_power_w(
    t_amb_c: float, setpoint_c: float, r_th_k_per_w: float, capacity_w: float
) -> float:
    """Control heat input Q (negative = cooling) that would hold the setpoint if capacity allows.

    ASSUMPTION: simple proportional-free control that only cools, never heats, and saturates at
    the available capacity. This is a demonstration controller, not a model of a real unit.
    """
    wanted_w = (setpoint_c - t_amb_c) / r_th_k_per_w
    return min(0.0, max(-capacity_w, wanted_w))
