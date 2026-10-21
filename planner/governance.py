"""Governance: auto-approve or send to a human, and the records that result (Phase 5).

The planner RECOMMENDS; it never executes. Final authority stays with QA. Thresholds are
illustrative placeholders, not sourced [SOURCE NEEDED] (config/planner.yaml). Simulation results on
a synthetic box, not real-world evidence.

A recommendation is AUTO-APPROVED only if ALL hold:
  1. the value at risk (VaR at alpha) of the chosen action is below v_thr;
  2. the gap between its CVaR and its expected loss is below confidence_gap_thr;
  3. the tamper audit is clean: trust level is "trusted" and no falsification has latched.
Otherwise a human approval task is created. Overriding rules: a reading that fails the hash or the
physics check is excluded from decisions and the shipment is set to quarantined_pending_review; a
latched falsification or an untrusted trust level means NO auto-approval, for any thresholds.

A signed record is never treated as true just because it is signed: signing protects records after
signing and does not stop a lie at the sensor (A18).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from planner.config import ACTIONS, PlannerConfig
from planner.core import TRUSTED, DecisionTable, PlannerInputs

AUTO = "auto_approved"
HUMAN = "needs_human"
ACTIVE = "active"
QUARANTINED = "quarantined_pending_review"
PHYSICS_FAIL_VERDICTS = ("suspected_falsification", "sensor_glitch")

APPROVE, OVERRIDE, REJECT = "approve", "override", "reject"
HUMAN_ACTIONS = (APPROVE, OVERRIDE, REJECT)

ACTION_WORDS = {
    "continue": "keep going on the current plan",
    "expedite": "speed the shipment up",
    "reroute_to_depot": "divert the shipment to the nearest depot",
    "re_source": "replace the shipment with a new one",
    "quarantine": "hold the shipment in a cooled depot",
}


class ActionRow(BaseModel):
    """One line of the table of alternatives."""

    model_config = ConfigDict(frozen=True)

    action: str
    cost: float
    failure_probability: float
    expected_loss: float
    var: float
    cvar: float


class DecisionRecord(BaseModel):
    """What the planner recommended and why. Immutable. A recommendation, not an action."""

    model_config = ConfigDict(frozen=True)

    shipment_id: str
    t_s: float
    inputs: PlannerInputs
    table: tuple[ActionRow, ...]
    chosen_action: str
    expected_optimal_action: str
    disagree: bool
    route: str
    shipment_status: str
    chosen_var: float
    chosen_gap: float
    v_thr: float
    confidence_gap_thr: float
    reasons: tuple[str, ...]
    explanation: str
    seed: int
    alpha: float
    n_scenarios: int


class HumanApprovalTask(BaseModel):
    """What a person needs to decide. Immutable."""

    model_config = ConfigDict(frozen=True)

    shipment_id: str
    decision_seq: int | None
    potency_curve: tuple[tuple[float, float], ...]  # (hours, potency) of the readings so far
    alternatives: tuple[ActionRow, ...]
    chosen_action: str
    chain_status: str
    reason: str
    explanation: str


class HumanDecisionRecord(BaseModel):
    """A person's decision, recorded as a NEW record that refers to the original. Immutable."""

    model_config = ConfigDict(frozen=True)

    refers_to_seq: int = Field(ge=0)
    shipment_id: str
    who: str = Field(min_length=1)
    when: datetime
    human_action: str
    final_action: str | None
    reason: str = Field(min_length=1)


@dataclass(frozen=True)
class Governance:
    route: str
    shipment_status: str
    reasons: tuple[str, ...]
    rule_var: bool
    rule_gap: bool
    rule_audit: bool


def govern(table: DecisionTable, inputs: PlannerInputs, cfg: PlannerConfig) -> Governance:
    chosen = table.results[table.cvar_optimal]
    gap = chosen.cvar - chosen.expected_loss
    rule_var = chosen.var < cfg.v_thr
    rule_gap = gap < cfg.confidence_gap_thr
    audit_clean = inputs.trust_level == TRUSTED and not inputs.falsification_latched
    reasons: list[str] = []
    hash_fail = inputs.chain_status == "broken"
    physics_fail = (
        inputs.trust_level != TRUSTED
        or inputs.verdict in PHYSICS_FAIL_VERDICTS
        or inputs.falsification_latched
    )
    quarantined = hash_fail or physics_fail
    if hash_fail:
        reasons.append(
            "the record chain does not verify: the affected readings are excluded and the "
            "shipment is quarantined pending review"
        )
    if physics_fail:
        reasons.append(
            f"the physics checks do not trust the readings (trust level {inputs.trust_level}, "
            f"verdict {inputs.verdict}): they are excluded, the shipment is quarantined pending "
            "review and the plan starts from the worst-case bound"
            if inputs.bound_used
            else f"the physics checks do not trust the readings (trust level {inputs.trust_level}, "
            f"verdict {inputs.verdict}): the shipment is quarantined pending review"
        )
    if inputs.falsification_latched or inputs.trust_level == "untrusted":
        reasons.append("a falsification is latched or the data are untrusted: never auto-approved")
    if not rule_var:
        reasons.append(
            f"rule 1: the value at risk of the chosen action ({chosen.var:,.0f}) is not below "
            f"the limit ({cfg.v_thr:,.0f})"
        )
    if not rule_gap:
        reasons.append(
            f"rule 2: the gap between the bad-case loss (CVaR) and the average loss is "
            f"{gap:,.0f}, not below {cfg.confidence_gap_thr:,.0f}, so the estimate is not "
            "reliable enough to act on alone"
        )
    if not audit_clean:
        reasons.append(
            f"rule 3: the tamper audit is not clean (trust level {inputs.trust_level}"
            f"{', falsification latched' if inputs.falsification_latched else ''})"
        )
    if inputs.chain_status == "not_checked":
        reasons.append("note: the record chain was not checked against a real ledger")
    auto = rule_var and rule_gap and audit_clean and not quarantined and not hash_fail
    if auto:
        reasons.append("all three rules hold: value at risk, estimate gap and a clean tamper audit")
    return Governance(
        AUTO if auto else HUMAN,
        QUARANTINED if quarantined else ACTIVE,
        tuple(reasons),
        rule_var,
        rule_gap,
        audit_clean,
    )


def explain(table: DecisionTable, inputs: PlannerInputs, gov: Governance) -> str:
    chosen = table.cvar_optimal
    r = table.results[chosen]
    text = (
        f"Recommended: {chosen} ({ACTION_WORDS[chosen]}). It has the smallest bad-case loss "
        f"(CVaR {r.cvar:,.0f}) of the five actions; the failure chance is "
        f"{r.failure_probability * 100:.1f} percent and the average loss {r.expected_loss:,.0f}."
    )
    if table.disagree:
        e = table.expected_optimal
        text += (
            f" The action with the smallest average loss would be {e}; the two differ because "
            "the bad-case view weighs rare, large losses more."
        )
    if inputs.bound_used:
        text += (
            " Because the readings are not fully trusted, the plan starts from the worst-case "
            "bound on the damage so far, not from the best estimate."
        )
    text += (
        " This is a recommendation, not an action; the final decision rests with quality "
        f"assurance. Route: {'automatic approval' if gov.route == AUTO else 'a person decides'}."
    )
    return text


def build_decision(
    table: DecisionTable, inputs: PlannerInputs, cfg: PlannerConfig
) -> DecisionRecord:
    gov = govern(table, inputs, cfg)
    chosen = table.results[table.cvar_optimal]
    rows = tuple(
        ActionRow(
            action=a,
            cost=table.results[a].cost,
            failure_probability=table.results[a].failure_probability,
            expected_loss=table.results[a].expected_loss,
            var=table.results[a].var,
            cvar=table.results[a].cvar,
        )
        for a in ACTIONS
    )
    return DecisionRecord(
        shipment_id=inputs.shipment_id,
        t_s=inputs.t_s,
        inputs=inputs,
        table=rows,
        chosen_action=table.cvar_optimal,
        expected_optimal_action=table.expected_optimal,
        disagree=table.disagree,
        route=gov.route,
        shipment_status=gov.shipment_status,
        chosen_var=chosen.var,
        chosen_gap=chosen.cvar - chosen.expected_loss,
        v_thr=cfg.v_thr,
        confidence_gap_thr=cfg.confidence_gap_thr,
        reasons=gov.reasons,
        explanation=explain(table, inputs, gov),
        seed=table.seed,
        alpha=table.alpha,
        n_scenarios=table.n,
    )


def build_task(
    decision: DecisionRecord,
    potency_curve: list[tuple[float, float]],
    decision_seq: int | None = None,
) -> HumanApprovalTask | None:
    """A human approval task, or None when the decision was auto-approved."""
    if decision.route == AUTO:
        return None
    step = max(1, len(potency_curve) // 200)
    return HumanApprovalTask(
        shipment_id=decision.shipment_id,
        decision_seq=decision_seq,
        potency_curve=tuple(potency_curve[::step]),
        alternatives=decision.table,
        chosen_action=decision.chosen_action,
        chain_status=decision.inputs.chain_status,
        reason="; ".join(decision.reasons),
        explanation=decision.explanation,
    )


def record_human_decision(
    shipment_id: str,
    recommended_action: str,
    decision_seq: int,
    who: str,
    human_action: str,
    reason: str,
    final_action: str | None = None,
    when: datetime | None = None,
) -> HumanDecisionRecord:
    """Record a person's decision as a NEW immutable record that refers to the original.

    approve: the recommended action stands. override: another action, which must be named.
    reject: no action is taken (final_action stays None). The original record is never edited.
    """
    if human_action not in HUMAN_ACTIONS:
        raise ValueError(f"human_action must be one of {HUMAN_ACTIONS} (got {human_action!r})")
    if human_action == APPROVE:
        final = recommended_action
    elif human_action == OVERRIDE:
        if final_action not in ACTIONS:
            raise ValueError(f"override needs final_action from {ACTIONS} (got {final_action!r})")
        if final_action == recommended_action:
            raise ValueError("override must name a different action than the recommendation")
        final = final_action
    else:
        final = None
    return HumanDecisionRecord(
        refers_to_seq=decision_seq,
        shipment_id=shipment_id,
        who=who.strip(),
        when=when or datetime.now(UTC),
        human_action=human_action,
        final_action=final,
        reason=reason.strip(),
    )
