"""Lumped thermal model of the insulated box (master brief section 3.3).

C dT/dt = (T_amb - T) / R_th + Q, with tau = R_th * C. With inputs constant over one step the
exact update is T[n+1] = T_inf + (T[n] - T_inf) * exp(-dt / tau) and T_inf = T_amb + R_th * Q.
The cooling unit and the event handling live in simulator/engine.py.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


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


@dataclass(frozen=True)
class TwoNodeBox:
    """Air node and payload node (Phase 3C).

        C_a dT_a/dt = (T_amb - T_a) / R_wall + (T_p - T_a) / R_ap + Q
        C_p dT_p/dt = (T_a - T_p) / R_ap

    The sensor measures T_a; the potency depends on T_p. With the heat input Q constant over a
    step, both nodes settle at T_inf = T_amb + R_wall * Q, so  x(t+dt) = T_inf + E (x - T_inf)
    with E = exp(A dt), computed by an eigen-decomposition (numpy only).

    Parameters: R_wall is the single-node R_th. The payload holds `payload_fraction` of the total
    capacity C, and R_ap is set by the coupling time constant: tau_c = R_ap * C_a C_p / (C_a + C_p).
    C is then chosen so that the SLOW time constant of the whole box equals tau_h exactly (closed
    form below). With payload_fraction 0 there is no payload node (it equals the air node).
    """

    r_wall: float
    c_air: float
    c_payload: float
    r_ap: float
    slow_tau_s: float
    fast_tau_s: float

    @classmethod
    def build(
        cls, r_th: float, tau_s: float, payload_fraction: float, coupling_tau_s: float
    ) -> TwoNodeBox:
        if not 0.0 <= payload_fraction < 1.0:
            raise ValueError(f"payload fraction must be in [0, 1) (got {payload_fraction})")
        if payload_fraction == 0.0:
            c = tau_s / r_th
            return cls(r_th, c, 0.0, math.inf, tau_s, 0.0)
        f, lam = payload_fraction, 1.0 / tau_s
        c1, c2 = f / coupling_tau_s, (1.0 - f) / coupling_tau_s
        # det(A + lam I) = 0 solved for the wall rate w = 1 / (C_a R_wall)
        w = lam - c1 - c1 * c2 / (lam - c2)
        if not w > 0:
            raise ValueError("the two-node parameters give a non-physical wall rate")
        c_air = 1.0 / (w * r_th)
        c_total = c_air / (1.0 - f)
        c_payload = f * c_total
        c_eq = c_air * c_payload / (c_air + c_payload)
        r_ap = coupling_tau_s / c_eq
        box = cls(r_th, c_air, c_payload, r_ap, tau_s, 0.0)
        taus = sorted(float(-1.0 / v.real) for v in np.linalg.eigvals(box.matrix()))
        slow, fast = taus[-1], taus[0]
        return cls(r_th, c_air, c_payload, r_ap, slow, fast)

    def matrix(self) -> np.ndarray:
        a, p = self.c_air, self.c_payload
        return np.array(
            [
                [-(1.0 / (a * self.r_wall) + 1.0 / (a * self.r_ap)), 1.0 / (a * self.r_ap)],
                [1.0 / (p * self.r_ap), -1.0 / (p * self.r_ap)],
            ]
        )

    def transition(self, dt_s: float) -> np.ndarray:
        """E = exp(A dt) by eigen-decomposition (A has real, distinct eigenvalues)."""
        values, vectors = np.linalg.eig(self.matrix())
        return (vectors @ np.diag(np.exp(values.real * dt_s)) @ np.linalg.inv(vectors)).real


def two_node_for(box) -> TwoNodeBox | None:
    """The two-node parameters of a BoxConfig, or None for a single-node box."""
    if box.box_model != "two_node":
        return None
    return TwoNodeBox.build(
        box.box_R_th_k_per_w,
        box.box_tau_h * 3600.0,
        box.two_node_payload_fraction,
        box.two_node_coupling_tau_h * 3600.0,
    )
