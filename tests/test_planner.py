"""Phase 5: CVaR, the oracle, scenarios, governance, decision records and the decision log.

The planner recommends; it never executes. All money values, probabilities and thresholds are
illustrative placeholders, not sourced [SOURCE NEEDED]. Simulation results on a synthetic box.
"""

# ruff: noqa: E501
import hashlib
import io
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from edge.chain import Ledger, Signer, verify_chain
from edge.chain.chain import Entry
from edge.potency import arrhenius_acceleration_factor
from edge.thermal_twin import load_twin_params, predict_next
from planner import cli as planner_cli
from planner import governance as gov_module
from planner.config import ACTIONS, load_planner_config
from planner.core import (
    ActionResult,
    DecisionTable,
    PlannerInputs,
    conservative_start,
    format_table,
    plan,
)
from planner.cvar import (
    choose_action,
    cvar_by_minimisation,
    cvar_discrete,
    cvar_sample,
    cvar_tail_average,
    expected_discrete,
    var_discrete,
    var_sample,
)
from planner.governance import (
    AUTO,
    HUMAN,
    QUARANTINED,
    build_decision,
    build_task,
    govern,
    record_human_decision,
)
from planner.pipeline import build_inputs
from planner.records import (
    DecisionLog,
    canonical_bytes,
    decision_record_dict,
    parse_canonical,
    verify_decision_log,
)
from planner.simulate import (
    acceleration_factor,
    ambient_paths,
    draw_scenarios,
    twin_step,
)

ROOT = Path(__file__).resolve().parent.parent
RECORDINGS = ROOT / "data" / "recordings"
V, ALPHA = 50_000.0, 0.95


def make_test_signer():
    return Signer.from_seed(hashlib.sha256(b"potencyguard TEST ONLY planner seed").digest())


# ----------------------------------------------------------------- the oracle (master brief 3.5)


def oracle_outcomes(cost, p_fail):
    return [(cost, 1.0 - p_fail), (cost + V, p_fail)]


def test_the_oracle_table_is_reproduced_exactly():
    cont, reroute = oracle_outcomes(0.0, 0.08), oracle_outcomes(5_000.0, 0.005)
    assert expected_discrete(cont) == pytest.approx(4_000.0, abs=1e-9)
    assert cvar_discrete(cont, ALPHA) == pytest.approx(50_000.0, abs=1e-9)
    assert expected_discrete(reroute) == pytest.approx(5_250.0, abs=1e-9)
    assert cvar_discrete(reroute, ALPHA) == pytest.approx(10_000.0, abs=1e-9)
    table = {
        "continue": {"expected": 4_000.0, "cvar": cvar_discrete(cont, ALPHA), "cost": 0.0},
        "reroute": {"expected": 5_250.0, "cvar": cvar_discrete(reroute, ALPHA), "cost": 5_000.0},
    }
    assert choose_action(table, "expected", ["continue", "reroute"]) == "continue"
    assert choose_action(table, "cvar", ["continue", "reroute"]) == "reroute"
    assert var_discrete(cont, ALPHA) == 50_000.0 and var_discrete(reroute, ALPHA) == 5_000.0


def test_the_hand_check_from_the_brief():
    # the brief: reroute loses 5,000 w.p. 0.995 and 55,000 w.p. 0.005; the worst 5 percent average
    assert (0.005 * 55_000 + 0.045 * 5_000) / 0.05 == pytest.approx(10_000.0)
    assert (0.00555000 + 0.0455000) / 0.05 != 10_000  # the prompt's digits were garbled: not used


def test_a_monte_carlo_sample_matches_the_oracle_within_a_stated_tolerance():
    rng = np.random.default_rng(7)
    n = 400_000
    for cost, p_fail, expected_cvar, expected_mean in (
        (0.0, 0.08, 50_000.0, 4_000.0),
        (5_000.0, 0.005, 10_000.0, 5_250.0),
    ):
        losses = cost + V * (rng.random(n) < p_fail)
        assert float(losses.mean()) == pytest.approx(expected_mean, rel=0.03)
        assert cvar_sample(losses, ALPHA) == pytest.approx(
            expected_cvar, rel=0.05
        )  # tolerance 5 percent


# ----------------------------------------------------------------- CVaR properties


def test_cvar_equals_the_sorted_tail_average_and_the_definition():
    rng = np.random.default_rng(3)
    for n in (1, 2, 3, 7, 19, 20, 21, 30, 100, 333):
        losses = rng.gamma(2.0, 1000.0, size=n)
        for alpha in (0.0, 0.5, 0.9, 0.95, 0.99):
            ru = cvar_sample(losses, alpha)
            assert ru == pytest.approx(cvar_tail_average(losses, alpha), rel=1e-9), (n, alpha)
            assert ru == pytest.approx(cvar_by_minimisation(losses, alpha), rel=1e-9), (n, alpha)


def test_cvar_is_at_least_var_and_at_least_the_mean():
    rng = np.random.default_rng(11)
    for _ in range(20):
        losses = rng.lognormal(7.0, 1.0, size=int(rng.integers(5, 400)))
        for alpha in (0.0, 0.3, 0.95):
            assert cvar_sample(losses, alpha) >= float(losses.mean()) - 1e-9
            assert cvar_sample(losses, alpha) >= var_sample(losses, alpha) - 1e-9
    assert cvar_sample([4.0, 4.0, 4.0], 0.95) == 4.0


def test_alpha_edge_cases_and_bad_input():
    losses = [1.0, 2.0, 3.0, 10.0]
    assert cvar_sample(losses, 0.0) == pytest.approx(4.0)  # alpha 0 is the mean
    assert cvar_sample(losses, 0.999) == pytest.approx(10.0)
    assert cvar_sample([7.0], 0.95) == 7.0
    for bad in (1.0, 1.5, -0.1, float("nan"), "0.9", True):
        with pytest.raises(ValueError):
            cvar_sample(losses, bad)
    for bad_sample in ([], [1.0, float("nan")], [float("inf")]):
        with pytest.raises(ValueError):
            cvar_sample(bad_sample, 0.9)
    with pytest.raises(ValueError):
        cvar_discrete([(1.0, 0.5), (2.0, 0.4)], 0.9)  # probabilities do not sum to 1
    with pytest.raises(ValueError):
        cvar_discrete([], 0.9)


def test_ties_are_broken_by_expected_loss_then_cost_then_order():
    values = {
        "a": {"cvar": 100.0, "expected": 50.0, "cost": 10.0},
        "b": {"cvar": 100.0 + 1e-12, "expected": 40.0, "cost": 20.0},
        "c": {"cvar": 100.0, "expected": 40.0, "cost": 5.0},
        "d": {"cvar": 100.0, "expected": 40.0, "cost": 5.0},
    }
    assert choose_action(values, "cvar", ["a", "b", "c", "d"]) == "c"
    assert choose_action(values, "cvar", ["d", "c", "b", "a"]) == "d"


# ----------------------------------------------------------------- the pieces the planner reuses


def test_the_acceleration_factor_table_matches_the_real_function(product):
    rng = np.random.default_rng(5)
    temps = rng.uniform(-30.0, 90.0, size=500)
    table = acceleration_factor(temps, product)
    exact = np.array([arrhenius_acceleration_factor(float(t), product) for t in temps])
    assert np.max(np.abs(table / exact - 1.0)) < 2e-6


def test_the_vectorised_twin_step_matches_predict_next():
    twin = load_twin_params()
    rng = np.random.default_rng(9)
    temp, amb, duty = rng.uniform(0, 30, 50), rng.uniform(0, 40, 50), rng.random(50)
    new = twin_step(temp, amb, duty, 0.5, twin)
    for i in range(50):
        assert new[i] == pytest.approx(
            predict_next(temp[i], amb[i], duty[i], 1800.0, twin), abs=1e-9
        )


def test_scenarios_are_reproducible_and_depend_on_the_seed():
    cfg = load_planner_config()
    a, b = draw_scenarios(cfg), draw_scenarios(cfg)
    other = draw_scenarios(cfg.model_copy(update={"seed": cfg.seed + 1}))
    for name in ("ambient_z", "delay_z", "fail_u", "fail_fraction", "heatwave_start_fraction"):
        assert getattr(a, name).tobytes() == getattr(b, name).tobytes()
        assert getattr(a, name).tobytes() != getattr(other, name).tobytes()
    paths = ambient_paths(cfg, a, 25.0, 24.0)
    assert paths["route"].shape == (cfg.n_scenarios, a.steps + 1) and np.all(
        paths["route"][:, 0] == 25.0
    )
    again = ambient_paths(cfg, b, 25.0, 24.0)
    assert paths["route"].tobytes() == again["route"].tobytes()


def inputs_for(**changes):
    values = dict(
        shipment_id="s1", t_s=3600.0 * 12, remaining_h=24.0, potency_now=0.99,
        tau_eq_now_h=500.0, start_tau_eq_h=500.0, start_temp_c=6.0, ambient_now_c=25.0,
        bound_used=False, trust_level="trusted", verdict="ok", chain_status="ok",
    )  # fmt: skip
    values.update(changes)
    return PlannerInputs(**values)


def run_plan(inputs, product, box, **cfg_changes):
    cfg = load_planner_config().model_copy(update=cfg_changes)
    return plan(inputs, cfg, product, load_twin_params(), box.box_setpoint_c), cfg


def test_the_plan_is_reproducible_byte_for_byte_and_changes_with_the_seed(product, box):
    inputs = inputs_for()
    a, cfg = run_plan(inputs, product, box)
    b, _ = run_plan(inputs, product, box)
    assert [
        (r.action, r.expected_loss, r.var, r.cvar, r.failure_probability)
        for r in a.results.values()
    ] == [
        (r.action, r.expected_loss, r.var, r.cvar, r.failure_probability)
        for r in b.results.values()
    ]
    da = canonical_bytes(decision_record_dict("p", 0, build_decision(a, inputs, cfg)))
    db = canonical_bytes(decision_record_dict("p", 0, build_decision(b, inputs, cfg)))
    assert da == db
    hot = inputs_for(start_tau_eq_h=8500.0, tau_eq_now_h=8500.0, ambient_now_c=40.0)
    c1, _ = run_plan(hot, product, box, seed=1)
    c2, _ = run_plan(hot, product, box, seed=2)
    assert [r.cvar for r in c1.results.values()] != [r.cvar for r in c2.results.values()]


def test_tables_have_all_five_actions_and_cvar_is_at_least_the_expected_loss(product, box):
    for inputs in (inputs_for(), inputs_for(start_tau_eq_h=8400.0, ambient_now_c=38.0)):
        table, _ = run_plan(inputs, product, box)
        assert list(table.results) == list(ACTIONS)
        for r in table.results.values():
            assert r.cvar >= r.expected_loss - 1e-6 and r.var <= r.cvar + 1e-6
            assert 0.0 <= r.failure_probability <= 1.0 and r.cost >= 0
        assert any("<- CVaR-optimal" in line for line in format_table(table))


def test_a_start_near_the_limit_fails_more_often_than_a_fresh_start(product, box):
    fresh, _ = run_plan(inputs_for(start_tau_eq_h=0.0, tau_eq_now_h=0.0), product, box)
    worn, _ = run_plan(inputs_for(start_tau_eq_h=8700.0), product, box)
    assert (
        worn.results["continue"].failure_probability > fresh.results["continue"].failure_probability
    )
    assert (
        worn.results["re_source"].failure_probability
        == fresh.results["re_source"].failure_probability
    )  # a new shipment starts fresh


def test_a_cooling_anomaly_makes_staying_in_the_box_riskier(product, box):
    hot = dict(ambient_now_c=40.0, start_tau_eq_h=8000.0, start_temp_c=8.0)
    calm, _ = run_plan(inputs_for(**hot), product, box)
    faulty, _ = run_plan(inputs_for(verdict="thermal_anomaly", **hot), product, box)
    assert (
        faulty.results["continue"].failure_probability
        > calm.results["continue"].failure_probability
    )
    assert (
        faulty.results["re_source"].failure_probability
        == calm.results["re_source"].failure_probability
    )
    off, _ = run_plan(
        inputs_for(verdict="thermal_anomaly", **hot),
        product,
        box,
        anomaly_cooling_fail_probability=0.0,
    )
    assert (
        off.results["continue"].failure_probability
        <= faulty.results["continue"].failure_probability
    )


# ----------------------------------------------------------------- the conservative start


def test_the_high_bound_is_used_when_trust_is_low_or_untrusted():
    assert conservative_start("trusted", 100.0, 6.0, None, None) == (100.0, 6.0, False)
    assert conservative_start("trusted", 100.0, 6.0, 9999.0, 50.0) == (100.0, 6.0, False)
    for level in ("low_confidence", "untrusted"):
        assert conservative_start(level, 100.0, 6.0, 900.0, 30.0) == (900.0, 30.0, True)
        # never below the point estimate, even if a bound looks smaller
        assert conservative_start(level, 100.0, 6.0, 50.0, 2.0) == (100.0, 6.0, True)
        with pytest.raises(ValueError):
            conservative_start(level, 100.0, 6.0, None, None)


def test_the_pipeline_starts_from_the_bound_for_a_falsified_recording_and_not_for_a_clean_one(
    product, box
):
    clean = build_inputs(RECORDINGS / "baseline_ok.jsonl", 24.0, product, box)
    assert clean.inputs.trust_level == "trusted" and not clean.inputs.bound_used
    assert clean.inputs.start_tau_eq_h == clean.inputs.tau_eq_now_h
    for name, hour in (("hidden_spoilage", 50.0), ("spoof_attempt", 20.0)):
        bad = build_inputs(RECORDINGS / f"{name}.jsonl", hour, product, box)
        assert bad.inputs.trust_level == "untrusted" and bad.inputs.bound_used
        assert bad.inputs.start_tau_eq_h > bad.inputs.tau_eq_now_h
        assert bad.inputs.falsification_latched


def test_the_pipeline_builds_a_bound_for_a_low_confidence_trip(product, box, tmp_path):
    from simulator.calibration_set import scaled_box
    from simulator.recording import write_run
    from simulator.scenario import load_all_scenarios
    from simulator.simulate import simulate

    run = simulate(load_all_scenarios()["baseline_ok"], scaled_box(box, 1.15), seed=11)
    path, _ = write_run(run, tmp_path, "mismatch")
    built = build_inputs(path, 40.0, product, box)
    assert built.inputs.trust_level in ("low_confidence", "untrusted")
    assert built.inputs.bound_used and built.inputs.start_tau_eq_h >= built.inputs.tau_eq_now_h
    assert built.inputs.chain_status == "ok"


def test_a_real_ledger_is_verified_and_a_broken_one_is_reported(product, box, tmp_path):
    from edge.runner import run_recording

    signer = make_test_signer()
    summary = run_recording(
        RECORDINGS / "baseline_ok.jsonl", product, box, signer, runs_dir=tmp_path
    )
    key = summary.ledger_path.with_suffix(".pubkey")
    good = build_inputs(
        RECORDINGS / "baseline_ok.jsonl",
        10.0,
        product,
        box,
        ledger_path=summary.ledger_path,
        public_key_path=key,
    )
    assert good.inputs.chain_status == "ok" and "real ledger" in good.chain_detail
    import sqlite3

    db = sqlite3.connect(summary.ledger_path)
    for trigger in (
        "entries_no_update",
        "entries_no_delete",
        "anchors_no_update",
        "anchors_no_delete",
    ):
        db.execute(f"DROP TRIGGER {trigger}")
    db.execute("UPDATE entries SET signature=? WHERE seq=5", (bytes(64),))
    db.commit()
    db.close()
    bad = build_inputs(
        RECORDINGS / "baseline_ok.jsonl",
        10.0,
        product,
        box,
        ledger_path=summary.ledger_path,
        public_key_path=key,
    )
    assert bad.inputs.chain_status == "broken"
    with pytest.raises(ValueError):
        build_inputs(
            RECORDINGS / "baseline_ok.jsonl", 10.0, product, box, ledger_path=summary.ledger_path
        )


# ----------------------------------------------------------------- governance


def make_table(chosen_var=1_000.0, chosen_cvar=2_000.0, chosen_expected=500.0):
    results = {a: ActionResult(a, 0.0, 0.0, 9e9, 9e9, 9e9, 0.0, 0.99) for a in ACTIONS}
    results["continue"] = ActionResult(
        "continue", 0.0, 0.01, chosen_expected, chosen_var, chosen_cvar, 1.0, 0.95
    )
    return DecisionTable(ALPHA, 1, 100, results, "continue", "continue")


CFG = load_planner_config()


def test_all_three_rules_satisfied_gives_auto_approval():
    g = govern(make_table(), inputs_for(), CFG)
    assert (
        (g.route, g.shipment_status) == (AUTO, "active")
        and g.rule_var
        and g.rule_gap
        and g.rule_audit
    )
    assert "all three rules hold" in g.reasons[-1]


def test_each_rule_alone_forces_a_human():
    high_var = govern(make_table(chosen_var=CFG.v_thr + 1), inputs_for(), CFG)
    assert (
        high_var.route == HUMAN
        and not high_var.rule_var
        and any("rule 1" in r for r in high_var.reasons)
    )
    wide_gap = govern(make_table(chosen_cvar=CFG.confidence_gap_thr + 10_000.0), inputs_for(), CFG)
    assert (
        wide_gap.route == HUMAN
        and not wide_gap.rule_gap
        and any("rule 2" in r for r in wide_gap.reasons)
    )
    for level in ("low_confidence", "untrusted"):
        audit = govern(make_table(), inputs_for(trust_level=level, bound_used=True), CFG)
        assert (
            audit.route == HUMAN
            and not audit.rule_audit
            and any("rule 3" in r for r in audit.reasons)
        )
    latched = govern(make_table(), inputs_for(falsification_latched=True), CFG)
    assert latched.route == HUMAN and not latched.rule_audit


def test_values_exactly_at_the_thresholds_are_not_below_them():
    assert govern(make_table(chosen_var=CFG.v_thr), inputs_for(), CFG).route == HUMAN
    gap_table = make_table(chosen_cvar=500.0 + CFG.confidence_gap_thr)
    assert govern(gap_table, inputs_for(), CFG).route == HUMAN


def test_a_failed_hash_or_physics_check_quarantines_and_excludes():
    broken = govern(make_table(), inputs_for(chain_status="broken"), CFG)
    assert broken.route == HUMAN and broken.shipment_status == QUARANTINED
    assert any("does not verify" in r and "quarantined" in r for r in broken.reasons)
    for verdict in ("suspected_falsification", "sensor_glitch"):
        g = govern(make_table(), inputs_for(verdict=verdict), CFG)
        assert g.route == HUMAN and g.shipment_status == QUARANTINED
    g = govern(make_table(), inputs_for(chain_status="not_checked"), CFG)
    assert g.route == AUTO and any(
        "not checked" in r for r in g.reasons
    )  # shown, not blocking (decision 0009, P4)


def test_untrusted_or_latched_never_auto_approves_for_any_threshold():
    tables = [
        make_table(chosen_var=v, chosen_cvar=c, chosen_expected=e)
        for v, c, e in ((0.0, 0.0, 0.0), (1.0, 2.0, 1.0), (500.0, 600.0, 550.0))
    ]
    for v_thr in (1e-6, 1.0, 1e3, 1e6, 1e12):
        for gap_thr in (1e-6, 1.0, 1e6, 1e12):
            cfg = CFG.model_copy(update={"v_thr": v_thr, "confidence_gap_thr": gap_thr})
            for table in tables:
                for changes in (
                    {"trust_level": "untrusted"},
                    {"falsification_latched": True},
                    {"trust_level": "low_confidence"},
                ):
                    assert govern(table, inputs_for(**changes), cfg).route == HUMAN
                assert govern(table, inputs_for(chain_status="broken"), cfg).route == HUMAN


def test_decisions_carry_the_required_content_and_are_immutable(product, box):
    inputs = inputs_for()
    table, cfg = run_plan(inputs, product, box)
    decision = build_decision(table, inputs, cfg)
    assert (
        decision.shipment_id == "s1" and decision.seed == cfg.seed and decision.alpha == cfg.alpha
    )
    assert [row.action for row in decision.table] == list(ACTIONS)
    assert (
        decision.inputs.chain_status == "ok"
        and decision.reasons
        and "recommendation, not an action" in decision.explanation
    )
    with pytest.raises(ValidationError):
        decision.route = HUMAN  # type: ignore[misc]
    assert (build_task(decision, [(0.0, 1.0)]) is None) == (decision.route == AUTO)
    forced = build_decision(
        table,
        inputs_for(trust_level="untrusted", bound_used=True),
        cfg,
    )
    task = build_task(forced, [(h / 10, 1.0 - h / 1000) for h in range(1000)], 3)
    assert task is not None and task.decision_seq == 3 and len(task.potency_curve) <= 200
    assert (
        task.alternatives == forced.table
        and "untrusted" in task.reason
        and task.chain_status == "ok"
    )


def test_the_planner_recommends_and_never_executes():
    for module in (gov_module, planner_cli):
        assert "never executes" in module.__doc__
    names = " ".join(n for m in (gov_module, planner_cli) for n in dir(m)).lower()
    assert "execute_action" not in names and "dispatch" not in names


# ----------------------------------------------------------------- human decisions and the decision log


def two_decisions(product, box, tmp_path):
    cfg = load_planner_config()
    signer = make_test_signer()
    ledger = Ledger.create("planner_test", tmp_path)
    log = DecisionLog(cfg.planner_id, signer, ledger)
    decisions = []
    for kwargs in ({}, {"trust_level": "untrusted", "bound_used": True, "start_tau_eq_h": 9000.0}):
        inputs = inputs_for(**kwargs)
        table = plan(inputs, cfg, product, load_twin_params(), box.box_setpoint_c)
        decision = build_decision(table, inputs, cfg)
        log.append_decision(decision)
        decisions.append(decision)
    return cfg, signer, ledger, log, decisions


def test_the_decision_log_verifies_and_a_human_decision_is_a_new_entry(product, box, tmp_path):
    cfg, signer, ledger, log, decisions = two_decisions(product, box, tmp_path)
    before = ledger.read_entries()
    human = record_human_decision(
        "s1",
        decisions[1].chosen_action,
        1,
        "A. Tester",
        "override",
        "I prefer to hold it",
        "quarantine",
        datetime(2026, 10, 21, 12, 0, tzinfo=UTC),
    )
    entry = log.append_human(human)
    after = ledger.read_entries()
    assert entry.seq == 2 and len(after) == 3
    assert [e.record for e in after[:2]] == [
        e.record for e in before
    ]  # the originals are untouched
    record = parse_canonical(after[2].record)
    assert (
        record["kind"] == "human_decision"
        and record["refers_to_seq"] == 1
        and record["final_action"] == "quarantine"
    )
    assert record["who"] == "A. Tester" and record["when_ms"] == int(
        datetime(2026, 10, 21, 12, 0, tzinfo=UTC).timestamp() * 1000
    )
    log.anchor()
    assert verify_decision_log(after, signer.public_key_bytes, ledger.latest_anchor()).ok
    ledger.close()


def test_human_decisions_follow_the_rules(product, box, tmp_path):
    cfg, signer, ledger, log, decisions = two_decisions(product, box, tmp_path)
    chosen = decisions[0].chosen_action
    approve = record_human_decision("s1", chosen, 0, "QA", "approve", "ok")
    assert approve.final_action == chosen
    reject = record_human_decision("s1", chosen, 0, "QA", "reject", "no")
    assert reject.final_action is None
    for bad in (
        dict(human_action="override", final_action=None),
        dict(human_action="override", final_action=chosen),
        dict(human_action="override", final_action="teleport"),
        dict(human_action="maybe", final_action=None),
        dict(human_action="approve", who=" "),
        dict(human_action="approve", reason=""),
    ):
        kwargs = dict(
            shipment_id="s1", recommended_action=chosen, decision_seq=0, who="QA", reason="because"
        )
        kwargs.update(bad)
        with pytest.raises(ValueError):
            record_human_decision(**kwargs)
    with pytest.raises(ValueError):
        log.append_human(approve.model_copy(update={"refers_to_seq": 7}))
    human_entry = log.append_human(approve)
    with pytest.raises(ValueError):  # a human decision may not refer to another human decision
        log.append_human(approve.model_copy(update={"refers_to_seq": human_entry.seq}))
    with pytest.raises(ValidationError):
        approve.who = "someone else"  # type: ignore[misc]
    ledger.close()


def entries_with_human(product, box, tmp_path):
    cfg, signer, ledger, log, decisions = two_decisions(product, box, tmp_path)
    log.append_human(
        record_human_decision("s1", decisions[0].chosen_action, 0, "QA", "approve", "fine")
    )
    log.anchor()
    entries, anchor = ledger.read_entries(), ledger.latest_anchor()
    ledger.close()
    return entries, anchor, signer


def swap(entries, index, **changes):
    e = entries[index]
    values = dict(seq=e.seq, record=e.record, signature=e.signature, hash=e.hash, key_id=e.key_id)
    values.update(changes)
    return [*entries[:index], Entry(**values), *entries[index + 1 :]]


def test_tampering_with_a_decision_log_copy_is_detected(product, box, tmp_path):
    entries, anchor, signer = entries_with_human(product, box, tmp_path)
    key = signer.public_key_bytes
    assert verify_decision_log(entries, key, anchor).ok
    record = parse_canonical(entries[0].record)
    record["route"] = "auto_approved" if record["route"] == "needs_human" else "needs_human"
    edited = swap(entries, 0, record=canonical_bytes(record))
    assert (
        verify_decision_log(edited, key, anchor).index,
        verify_decision_log(edited, key, anchor).reason,
    ) == (0, "bad_signature")
    assert verify_decision_log(entries[:1] + entries[2:], key, anchor).reason == "bad_sequence"
    swapped = [entries[1], entries[0], entries[2]]
    assert verify_decision_log(swapped, key, anchor).reason == "bad_sequence"
    assert (
        verify_decision_log(swap(entries, 1, hash=b"\x01" * 32), key, anchor).reason
        == "bad_hash_link"
    )
    assert (
        verify_decision_log(swap(entries, 1, signature=bytes(64)), key, anchor).reason
        == "bad_signature"
    )
    other = Signer.generate()
    assert verify_decision_log(entries, other.public_key_bytes, anchor).reason == "bad_signature"
    cut = verify_decision_log(entries[:2], key, anchor)
    assert (cut.ok, cut.reason) == (False, "truncated")
    assert verify_decision_log(entries[:2], key).ok  # no anchor: the cut is not detected


def test_a_human_entry_that_points_at_nothing_is_reported(product, box, tmp_path):
    from edge.chain import genesis_hash, link_hash
    from planner.records import human_record_dict, log_genesis_id

    entries, _, signer = entries_with_human(product, box, tmp_path)
    human = record_human_decision(
        "s1", "continue", 0, "QA", "approve", "fine", when=datetime(2026, 1, 1, tzinfo=UTC)
    )
    record = human_record_dict("pg-planner-001", 0, human.model_copy(update={"refers_to_seq": 5}))
    canonical = canonical_bytes(record)
    sig = signer.sign(canonical)
    digest = link_hash(genesis_hash(log_genesis_id("pg-planner-001")), canonical, sig)
    forged = [Entry(0, canonical, sig, digest, signer.key_id)]
    assert verify_decision_log(forged, signer.public_key_bytes).reason == "bad_reference"


def test_malformed_input_is_reported_and_never_raises(product, box, tmp_path):
    entries, anchor, signer = entries_with_human(product, box, tmp_path)
    key = signer.public_key_bytes
    for garbage in (
        [None],
        ["x"],
        [123],
        [Entry(0, b"", b"", b"", "")],
        [Entry(0, b"{}", b"x", b"y", "k")],
        [Entry("0", entries[0].record, entries[0].signature, entries[0].hash, "k")],
    ):  # type: ignore[arg-type]
        result = verify_decision_log(garbage, key, anchor)
        assert result.ok is False
    for bad_key in (b"", None, "text"):
        assert verify_decision_log(entries, bad_key).ok is False  # type: ignore[arg-type]
    assert verify_decision_log(None, key).ok is False  # type: ignore[arg-type]
    assert verify_decision_log(entries, key, "anchor").ok is False  # type: ignore[arg-type]


def test_no_float_leaks_into_the_canonical_decision_bytes(product, box):
    inputs = inputs_for()
    table, cfg = run_plan(inputs, product, box)
    record = decision_record_dict("pg-planner-001", 0, build_decision(table, inputs, cfg))
    for name, value in record.items():
        assert value is None or isinstance(value, int | str) and not isinstance(value, bool), name
    data = canonical_bytes(record)
    assert parse_canonical(data) == record
    text = data.decode()
    assert b" " not in data.replace(record["explanation"].encode(), b"").replace(
        record["reasons"].encode(), b""
    )
    with pytest.raises(ValueError):
        parse_canonical(
            text.replace(f'"seed":{record["seed"]}', f'"seed":{record["seed"]}.0').encode()
        )
    with pytest.raises(ValueError):
        canonical_bytes({**record, "alpha_e6": 950000.5})
    with pytest.raises(ValueError):
        canonical_bytes({**record, "extra": 1})
    assert record["alpha_e6"] == 950_000 and record["schema"] == "pg-decision/1"


# ----------------------------------------------------------------- configuration


def test_the_shipped_config_is_valid_and_labelled():
    cfg = load_planner_config()
    assert cfg.alpha == 0.95 and cfg.n_scenarios == 5000 and set(cfg.actions) == set(ACTIONS)
    text = (ROOT / "config" / "planner.yaml").read_text(encoding="utf-8")
    assert "illustrative placeholder" in text and "[SOURCE NEEDED]" in text


def test_bad_planner_settings_are_rejected(tmp_path):
    import yaml

    from shared.config import ConfigError

    base = yaml.safe_load((ROOT / "config" / "planner.yaml").read_text(encoding="utf-8"))

    def write(mutate):
        raw = json.loads(json.dumps(base))
        mutate(raw)
        path = tmp_path / "bad.yaml"
        path.write_text(yaml.safe_dump(raw), encoding="utf-8")
        return path

    mutations = [
        lambda r: r.update(alpha=1.0), lambda r: r.update(alpha=-0.1), lambda r: r.update(n_scenarios=10),
        lambda r: r.update(V=0), lambda r: r.update(beta=-1), lambda r: r.update(dt_h=0), lambda r: r.update(v_thr=0),
        lambda r: r.update(confidence_gap_thr=-5), lambda r: r.update(unknown=1), lambda r: r.update(seed=-1),
        lambda r: r["actions"].pop("quarantine"), lambda r: r["actions"].update(teleport=r["actions"]["continue"]),
        lambda r: r["actions"]["continue"].update(cost=-1), lambda r: r["actions"]["continue"].update(cooling_fail_probability=1.5),
        lambda r: r["actions"]["continue"].update(ambient_mode="sea"), lambda r: r["ambient"].update(route_theta_per_h=0),
        lambda r: r["ambient"].update(heatwave_probability=2), lambda r: r.update(anomaly_cooling_fail_probability=-0.1),
        lambda r: r.update(max_horizon_h=0.1), lambda r: r.update(planner_id="bad id"),
    ]  # fmt: skip
    for mutate in mutations:
        with pytest.raises(ConfigError):
            load_planner_config(write(mutate))
    with pytest.raises(ConfigError):
        load_planner_config(tmp_path / "missing.yaml")


# ----------------------------------------------------------------- files that must not change


def test_golden_recordings_and_chain_vectors_are_unchanged():
    expected = json.loads((ROOT / "shared" / "golden_sha256.json").read_text("utf-8"))["sha256"]
    for relative, digest in expected.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest().upper() == digest, (
            relative
        )
    import subprocess

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "make_chain_vectors.py"), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0


# ----------------------------------------------------------------- the command line


def test_decide_prints_the_table_the_route_and_writes_a_verifying_log(tmp_path):
    out = io.StringIO()
    code = planner_cli.main(
        [
            "decide",
            "--recording",
            str(RECORDINGS / "hidden_spoilage.jsonl"),
            "--at-hour",
            "50",
            "--key-dir",
            str(tmp_path / "k"),
            "--log-dir",
            str(tmp_path / "l"),
        ],
        out,
    )
    text = out.getvalue()
    assert code == 0
    for needle in (
        "CVaR-optimal",
        "expected-loss-optimal",
        "needs_human",
        "quarantined_pending_review",
        "HIGH bound",
        "decision log: chain OK",
        "A human approval task",
        "final authority stays with QA",
    ):
        assert needle in text
    assert text.rstrip().endswith("Not real-world evidence.")
    assert (
        planner_cli.main(
            [
                "decide",
                "--recording",
                str(tmp_path / "no.jsonl"),
                "--at-hour",
                "5",
                "--key-dir",
                str(tmp_path / "k"),
            ],
            io.StringIO(),
        )
        == 2
    )
    assert (
        planner_cli.main(
            [
                "decide",
                "--recording",
                str(RECORDINGS / "baseline_ok.jsonl"),
                "--at-hour",
                "500",
                "--key-dir",
                str(tmp_path / "k"),
                "--log-dir",
                str(tmp_path / "l"),
            ],
            io.StringIO(),
        )
        == 2
    )


def test_demo_covers_six_scenarios_and_the_log_verifies(tmp_path):
    out = io.StringIO()
    assert (
        planner_cli.main(
            ["demo", "--key-dir", str(tmp_path / "k"), "--log-dir", str(tmp_path / "l")], out
        )
        == 0
    )
    text = out.getvalue()
    for name, _ in planner_cli.DEMO_CHECKPOINTS:
        assert name in text
    assert "chain OK: 6 entries verified; anchor checked" in text
    lines = {
        ln.split()[0]: ln
        for ln in text.splitlines()
        if ln and ln.split()[0] in dict(planner_cli.DEMO_CHECKPOINTS)
    }
    assert lines["baseline_ok"].rstrip().endswith("auto_approved")
    assert lines["spoof_attempt"].rstrip().endswith("needs_human") and lines[
        "hidden_spoilage"
    ].rstrip().endswith("needs_human")


def test_human_command_appends_a_new_entry(tmp_path):
    out = io.StringIO()
    planner_cli.main(
        [
            "decide",
            "--recording",
            str(RECORDINGS / "spoof_attempt.jsonl"),
            "--at-hour",
            "20",
            "--key-dir",
            str(tmp_path / "k"),
            "--log-dir",
            str(tmp_path / "l"),
        ],
        out,
    )
    log_path = next(Path(tmp_path / "l").glob("*.sqlite"))
    out = io.StringIO()
    code = planner_cli.main(
        [
            "human",
            "--log",
            str(log_path),
            "--seq",
            "0",
            "--who",
            "QA lead",
            "--action",
            "override",
            "--final-action",
            "quarantine",
            "--reason",
            "hold for review",
            "--key-dir",
            str(tmp_path / "k"),
        ],
        out,
    )
    assert code == 0 and "new entry 1" in out.getvalue() and "chain OK" in out.getvalue()
    bad = io.StringIO()
    assert (
        planner_cli.main(
            [
                "human",
                "--log",
                str(log_path),
                "--seq",
                "0",
                "--who",
                "x",
                "--action",
                "override",
                "--reason",
                "r",
                "--key-dir",
                str(tmp_path / "k"),
            ],
            bad,
        )
        == 2
    )


def test_the_key_is_never_printed_and_verify_chain_phase4_is_untouched(tmp_path):
    out = io.StringIO()
    planner_cli.main(
        ["demo", "--key-dir", str(tmp_path / "k"), "--log-dir", str(tmp_path / "l")], out
    )
    assert "BEGIN" not in out.getvalue() and "PRIVATE" not in out.getvalue()
    # the Phase 4 verifier still rejects a decision-schema record as malformed (the schemas are separate)
    ledger_path = next(Path(tmp_path / "l").glob("*.sqlite"))
    with Ledger.open(ledger_path) as ledger:
        entries = ledger.read_entries()
    signer_key = bytes.fromhex(ledger_path.with_suffix(".pubkey").read_text().strip())
    assert verify_chain(entries, signer_key).reason == "malformed"
    assert math.isfinite(1.0)
