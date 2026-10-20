"""Lumped thermal model of the insulated box (master brief section 3.3).

C dT/dt = (T_amb - T) / R_th + Q, with tau = R_th * C. With inputs constant over one step the
exact update is T[n+1] = T_inf + (T[n] - T_inf) * exp(-dt / tau) and T_inf = T_amb + R_th * Q.
The cooling unit and the event handling live in simulator/engine.py.
"""

from __future__ import annotations

import math


def steady_state_temp_c(t_amb_c: float, r_th_k_per_w: float, q_w: float) -> float:
    """T_inf: where the box temperature settles for constant ambient and heat input Q."""
    return t_amb_c + r_th_k_per_w * q_w


def decay_factor(dt_s: float, tau_s: float) -> float:
    """exp(-dt / tau), computed once per step size."""
    if dt_s < 0 or tau_s <= 0:
        raise ValueError(f"need dt_s >= 0 and tau_s > 0 (got {dt_s}, {tau_s})")
    return math.exp(-dt_s / tau_s)


def step_with_decay(t_c: float, t_inf_c: float, decay: float) -> float:
    """Exact update given a precomputed decay factor."""
    return t_inf_c + (t_c - t_inf_c) * decay


def step_box_temp_c(t_c: float, t_inf_c: float, dt_s: float, tau_s: float) -> float:
    """Exact one-step update of the box temperature."""
    return step_with_decay(t_c, t_inf_c, decay_factor(dt_s, tau_s))
