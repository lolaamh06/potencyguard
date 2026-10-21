"""The planning step: sample scenarios per action, compute loss, CVaR and the table (Phase 5).

The planner RECOMMENDS; it never executes. Final authority stays with QA. Illustrative
placeholder numbers (config/planner.yaml), not sourced [SOURCE NEEDED]; simulation results on a
synthetic box, not real-world evidence. A signed record is never treated as true just because it
is signed (A18): the starting state below depends on the trust level the physics checks produced.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from edge.thermal_twin import TwinParams
from planner.config import ACTIONS, PlannerConfig
from planner.cvar import choose_action, cvar_sample, var_sample
from planner.simulate import ambient_paths, draw_scenarios, simulate_action
from shared.config import ProductConfig

TRUSTED = "trusted"
THERMAL_ANOMALY = "thermal_anomaly"
# actions after which the shipment is still in the same box with the same cooling unit
SAME_BOX_ACTIONS = ("continue", "expedite", "reroute_to_depot")


class PlannerInputs(BaseModel):
    """Everything the planner needs about one shipment at one moment. Immutable."""

    model_config = ConfigDict(frozen=True)

    shipment_id: str = Field(min_length=1)
    t_s: float = Field(ge=0)
    remaining_h: float = Field(gt=0, description="Scheduled remaining transit time R")
    potency_now: float
    tau_eq_now_h: float = Field(ge=0, description="Point estimate from the potency tracker")
    start_tau_eq_h: float = Field(ge=0, description="Equivalent time the planner starts from")
    start_temp_c: float
    ambient_now_c: float
    bound_used: bool = Field(description="True when start_tau_eq_h is the HIGH worst-case bound")
    trust_level: str
    verdict: str
    chain_status: str = Field(description="ok, broken or not_checked")
    falsification_latched: bool = False


def conservative_start(
    trust_level: str,
    tau_eq_now_h: float,
    temp_now_c: float,
    bound_tau_eq_h: float | None,
    bound_temp_c: float | None,
) -> tuple[float, float, bool]:
    """(start tau_eq, start temperature, bound used) for the planner.

    Trusted data: the point estimate. low_confidence or untrusted: the HIGH bound and its
    worst-case temperature, never the point estimate (the readings or the twin are in doubt).
    """
    if trust_level == TRUSTED:
        return tau_eq_now_h, temp_now_c, False
    if bound_tau_eq_h is None or bound_temp_c is None:
        raise ValueError(f"trust level {trust_level!r} needs a high bound, but none was given")
    return max(bound_tau_eq_h, tau_eq_now_h), max(bound_temp_c, temp_now_c), True


@dataclass(frozen=True)
class ActionResult:
    action: str
    cost: float
    failure_probability: float
    expected_loss: float
    var: float
    cvar: float
    mean_delay_h: float
    potency_p05: float  # the 5th percentile of potency at arrival (a bad-case view)


@dataclass(frozen=True)
class DecisionTable:
    alpha: float
    seed: int
    n: int
    results: dict[str, ActionResult]
    cvar_optimal: str
    expected_optimal: str

    @property
    def disagree(self) -> bool:
        return self.cvar_optimal != self.expected_optimal


def plan(
    inputs: PlannerInputs,
    cfg: PlannerConfig,
    product: ProductConfig,
    twin: TwinParams,
    setpoint_c: float,
) -> DecisionTable:
    """Sample scenarios once and evaluate all five actions on the same scenarios."""
    sc = draw_scenarios(cfg)
    paths = ambient_paths(cfg, sc, inputs.ambient_now_c, inputs.remaining_h)
    results: dict[str, ActionResult] = {}
    for index, name in enumerate(ACTIONS):
        action = cfg.actions[name]
        sample = simulate_action(
            index, action, cfg, sc, paths, inputs.start_tau_eq_h, inputs.start_temp_c,
            inputs.remaining_h, twin, product, setpoint_c,
            cooling_already_suspect=(
                inputs.verdict == THERMAL_ANOMALY and name in SAME_BOX_ACTIONS
            ),
        )  # fmt: skip
        results[name] = ActionResult(
            action=name,
            cost=action.cost,
            failure_probability=float(sample.failed.mean()),
            expected_loss=float(sample.losses.mean()),
            var=var_sample(sample.losses, cfg.alpha),
            cvar=cvar_sample(sample.losses, cfg.alpha),
            mean_delay_h=float(sample.delay_h.mean()),
            potency_p05=float(np.percentile(sample.potency_arrival, 5)),
        )
    values = {
        a: {"cvar": r.cvar, "expected": r.expected_loss, "cost": r.cost} for a, r in results.items()
    }
    return DecisionTable(
        alpha=cfg.alpha,
        seed=cfg.seed,
        n=cfg.n_scenarios,
        results=results,
        cvar_optimal=choose_action(values, "cvar", ACTIONS),
        expected_optimal=choose_action(values, "expected", ACTIONS),
    )


def format_table(table: DecisionTable) -> list[str]:
    head = (
        f"{'action':<18}{'cost':>9}{'fail prob':>11}{'exp. loss':>12}{'VaR':>11}{'CVaR':>11}"
        f"{'delay h':>9}"
    )
    lines = [head]
    for name in ACTIONS:
        r = table.results[name]
        mark = ""
        if name == table.cvar_optimal:
            mark += "  <- CVaR-optimal"
        if name == table.expected_optimal:
            mark += "  <- expected-loss-optimal"
        lines.append(
            f"{name:<18}{r.cost:>9,.0f}{r.failure_probability * 100:>10.1f}%"
            f"{r.expected_loss:>12,.0f}{r.var:>11,.0f}{r.cvar:>11,.0f}{r.mean_delay_h:>9.1f}{mark}"
        )
    return lines
