"""Generate the JSON files that the Phase F1 style frames read (read-only use of the project code).

Run from the repository root with the project's Python:
    python docs/01-architecture/style-frames/generate_data.py

Nothing in the repository is changed except the JSON files written next to this script, under data/.
Every number shown on a style frame comes from one of these files (the pages contain none typed by
hand). Everything is a simulation on a synthetic product and box. The planner numbers are
illustrative placeholders, not sourced [SOURCE NEEDED].

Files:
  data/chapter1.json      the two journeys of Chapter 1, computed for both product profiles
  data/futures.json       the Chapter 5 cloud: seeded draws from the oracle's two actions, plus the
                          exact (analytic) oracle numbers and the sample's CVaR
  data/control_room.json  one golden recording (hidden_spoilage) at the planner demo checkpoint:
                          series, planner table, decision, chain ribbon with one broken link, provenance
  data/contrast.json      WCAG contrast ratios of the design tokens
"""
# ruff: noqa: E501  (long literal lines)

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from backend.service import (  # noqa: E402
    SOFTWARE_VERSION,  # noqa: E402
    apply_backend_rules,
    close_call,
)
from edge.assessment import TrustAssessor  # noqa: E402
from edge.chain import Ledger, Signer, verify_chain  # noqa: E402
from edge.chain.canonical import parse_canonical  # noqa: E402
from edge.potency import (  # noqa: E402
    arrhenius_acceleration_factor,
    potency_from_tau_eq,
    shelf_life_used_fraction,
)
from edge.recorded_source import RecordedSource  # noqa: E402
from edge.runner import run_recording  # noqa: E402
from edge.tamper_monitor import TamperMonitor  # noqa: E402
from planner.config import ACTIONS, load_planner_config  # noqa: E402
from planner.core import plan  # noqa: E402
from planner.cvar import cvar_discrete, cvar_sample, expected_discrete, var_sample  # noqa: E402
from planner.governance import build_decision  # noqa: E402
from planner.pipeline import build_inputs  # noqa: E402
from shared.config import load_box_config, load_product_config  # noqa: E402

OUT = HERE / "data"
SEED = 20261021
RECORDING = "hidden_spoilage"
CHECKPOINT_H = 50.0  # the checkpoint of `python -m planner demo`
FOOTER = "Synthetic product, model output."


def dump(name: str, obj: dict) -> None:
    OUT.mkdir(exist_ok=True)
    with open(OUT / name, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(obj, handle, indent=1, sort_keys=True)
        handle.write("\n")
    print("wrote", OUT / name)


# ------------------------------------------------------------------------- Chapter 1
def chapter1() -> dict:
    profiles = {
        "active": (
            "config/product_default.yaml",
            "Illustrative profile (Set C), the active profile",
        ),
        "reference": (
            "config/product_team_document.yaml",
            "Reference profile (the team document's constants)",
        ),
    }
    journeys = {"A": (12.0, 8.0), "B": (30.0, 24.0)}  # constant temperature, hours
    out: dict = {
        "note": FOOTER,
        "threshold_c": 8.0,
        "journeys": {k: {"temp_c": v[0], "hours": v[1]} for k, v in journeys.items()},
        "profiles": {},
    }
    for key, (path, label) in profiles.items():
        cfg = load_product_config(REPO / path)
        entry = {
            "label": label,
            "path": path,
            "Ea_over_R": cfg.Ea_over_R,
            "tau_max_h": cfg.tau_max_h,
            "P_min": cfg.P_min,
            "T_ref_c": cfg.T_ref_c,
            "journeys": {},
        }
        for name, (temp, hours) in journeys.items():
            af = arrhenius_acceleration_factor(temp, cfg)
            tau = af * hours
            entry["journeys"][name] = {
                "acceleration_factor": af,
                "tau_eq_h": tau,
                "shelf_life_used_fraction": shelf_life_used_fraction(tau, cfg),
                "shelf_life_used_percent": shelf_life_used_fraction(tau, cfg) * 100.0,
                "potency": potency_from_tau_eq(tau, cfg),
            }
        # the curve the scrub would draw: potency against hours, hourly
        entry["curves"] = {
            name: [
                {
                    "h": h,
                    "potency": potency_from_tau_eq(
                        arrhenius_acceleration_factor(temp, cfg) * h, cfg
                    ),
                }
                for h in range(0, int(hours) + 1)
            ]
            for name, (temp, hours) in journeys.items()
        }
        out["profiles"][key] = entry
    return out


# ------------------------------------------------------------------------- Chapter 5
def futures() -> dict:
    alpha, V, n = 0.95, 50_000.0, 1_200
    spec = {"continue": (0.0, 0.08), "reroute": (5_000.0, 0.005)}  # cost, failure probability
    rng = np.random.default_rng(SEED)
    exact, points = {}, {}
    for name, (cost, p_fail) in spec.items():
        outcomes = [(cost, 1.0 - p_fail), (cost + V, p_fail)]
        exact[name] = {
            "cost": cost, "failure_probability": p_fail,
            "expected_loss": expected_discrete(outcomes), "cvar": cvar_discrete(outcomes, alpha),
        }  # fmt: skip
        failed = rng.random(n) < p_fail
        losses = cost + V * failed
        order = np.argsort(-losses, kind="stable")
        tail = np.zeros(n, dtype=bool)
        tail[order[: int(round((1 - alpha) * n))]] = True  # the worst 5 percent of the drawn sample
        # each point: its loss, whether it failed, a position inside its cluster (the page lays them out)
        points[name] = [
            {
                "loss": float(loss_i),
                "failed": bool(f),
                "tail": bool(t),
                "u": round(float(u), 4),
                "v": round(float(v), 4),
            }
            for loss_i, f, t, u, v in zip(
                losses, failed, tail, rng.random(n), rng.random(n), strict=True
            )
        ]
        exact[name]["sample_expected_loss"] = float(losses.mean())
        exact[name]["sample_cvar"] = cvar_sample(losses, alpha)
        exact[name]["sample_var"] = var_sample(losses, alpha)
    return {
        "note": "Textbook example from the master brief (illustrative placeholders), seeded draws from its two actions.",
        "seed": SEED, "alpha": alpha, "V": V, "points_per_action": n, "exact": exact, "points": points,
        "source": "planner.cvar (exact discrete functions and the sample CVaR); numpy default_rng(seed)",
    }  # fmt: skip


# ------------------------------------------------------------------------- Control Room
def control_room() -> dict:
    product, box = load_product_config(), load_box_config()
    path = REPO / "data" / "recordings" / f"{RECORDING}.jsonl"
    # series from the existing edge pipeline, up to the checkpoint
    source = RecordedSource(path)
    source.start()
    assessor = TrustAssessor(product, TamperMonitor.from_defaults(product, box))
    series = []
    first_alarm: dict[str, float] = {}
    try:
        while (reading := source.read()) is not None:
            if reading.t_s > CHECKPOINT_H * 3600 + 1e-6:
                break
            assessment, potency, state = assessor.update(reading)
            series.append(
                {
                    "t_h": round(reading.t_s / 3600, 4),
                    "temp_c": reading.temp_c,
                    "ambient_c": reading.ambient_c,
                    "twin_c": None if state.predicted_c is None else round(state.predicted_c, 4),
                    "residual_c": None if state.residual_c is None else round(state.residual_c, 4),
                    "cusum_neg": round(state.cusum_neg, 4),
                    "cusum_pos": round(state.cusum_pos, 4),
                    "potency": round(potency.potency, 9),
                    "verdict": assessment.verdict,
                    "trust_level": assessment.trust_level,
                }  # fmt: skip
            )
            for name, flag in (
                ("cusum_neg", state.flag_cusum_neg),
                ("impossible_step", state.flag_step),
                ("impossible_state", state.flag_state),
            ):
                if flag:
                    first_alarm.setdefault(name, round(reading.t_s / 3600, 4))
    finally:
        source.close()
    last = series[-1]
    last_mkt = potency.mkt_c
    # the planner at the same checkpoint, then the backend's extra rule (close call)
    cfg = load_planner_config()
    built = build_inputs(path, CHECKPOINT_H, product, box)
    table = plan(built.inputs, cfg, product, built.twin, built.setpoint_c)
    decision = build_decision(table, built.inputs, cfg)
    decision, flags = apply_backend_rules(decision, table, 5.0, False, False)
    is_close, close_text = close_call(table, 5.0)
    # the signed chain, then a tampered copy (the edit action of scripts/tamper_demo.py)
    import tamper_demo  # noqa: PLC0415

    signer = Signer.from_seed(hashlib.sha256(b"F1 style-frame demo key (TEST ONLY)").digest())
    with tempfile.TemporaryDirectory(prefix="pg_f1_") as tmp:
        run = run_recording(path, product, box, signer, "pg-f1-demo", Path(tmp), "f1")
        with Ledger.open(run.ledger_path) as ledger:
            entries_all = ledger.read_entries()
        keep = [
            e
            for e in entries_all
            if parse_canonical(e.record)["t_ms"] / 3_600_000 <= CHECKPOINT_H + 1e-9
        ]
        prefix_ledger = Ledger.create("f1_prefix", tmp)
        for e in keep:
            prefix_ledger.append(e)
        prefix_ledger.close()
        copy = tamper_demo.make_copy(prefix_ledger.path, Path(tmp), "edit")
        note = tamper_demo.apply_action(copy, "edit", None, 5)
        with Ledger.open(copy) as ledger:
            tampered = ledger.read_entries()
        intact = verify_chain(keep, signer.public_key_bytes, None, "pg-f1-demo")
        broken = verify_chain(tampered, signer.public_key_bytes, None, "pg-f1-demo")
    index = broken.index
    window = range(max(0, index - 14), min(len(tampered), index + 15))
    ribbon = [
        {
            "index": i, "hash_prefix": tampered[i].hash.hex()[:8],
            "status": "verified" if i < index else "broken" if i == index else "after_break",
        }
        for i in window
    ]  # fmt: skip
    rows = [
        {
            "action": a, "cost": table.results[a].cost, "failure_probability": table.results[a].failure_probability,
            "expected_loss": table.results[a].expected_loss, "var": table.results[a].var, "cvar": table.results[a].cvar,
        }
        for a in ACTIONS
    ]  # fmt: skip
    return {
        "note": FOOTER,
        "generated_by": "docs/01-architecture/style-frames/generate_data.py (existing edge, planner and backend code, read-only use)",
        "recording": f"data/recordings/{RECORDING}.jsonl",
        "checkpoint_h": CHECKPOINT_H,
        "series": series,
        "first_alarm_h": first_alarm,
        "now": {
            "potency_percent_reported_by_pipeline": last["potency"] * 100.0,
            "shelf_life_used_percent": float(
                shelf_life_used_fraction(built.inputs.tau_eq_now_h, product) * 100.0
            ),
            "tau_eq_now_h": built.inputs.tau_eq_now_h,
            "mkt_c": last_mkt,
            "sigma_r_c": built.twin.sigma_r_c,
            "cusum_h": assessor.monitor.config.cusum_h,
            "worst_case_potency_percent": potency_from_tau_eq(built.inputs.start_tau_eq_h, product)
            * 100.0,
            "worst_case_shelf_life_used_percent": shelf_life_used_fraction(
                built.inputs.start_tau_eq_h, product
            )
            * 100.0,
            "temp_c": last["temp_c"],
            "ambient_c": last["ambient_c"],
            "trust_level": built.inputs.trust_level,
            "verdict": built.inputs.verdict,
            "start_tau_eq_h": built.inputs.start_tau_eq_h,
            "start_temp_c": built.inputs.start_temp_c,
            "bound_used": built.inputs.bound_used,
            "remaining_h": built.inputs.remaining_h,
        },  # fmt: skip
        "product": {
            "Ea_over_R": product.Ea_over_R,
            "tau_max_h": product.tau_max_h,
            "P_min": product.P_min,
            "T_ref_c": product.T_ref_c,
        },
        "planner": {
            "alpha": cfg.alpha,
            "n_scenarios": cfg.n_scenarios,
            "seed": cfg.seed,
            "V": cfg.V,
            "beta": cfg.beta,
            "v_thr": cfg.v_thr,
            "confidence_gap_thr": cfg.confidence_gap_thr,
            "table": rows,
            "cvar_optimal": table.cvar_optimal,
            "expected_optimal": table.expected_optimal,
            "disagree": table.disagree,
        },  # fmt: skip
        "decision": {
            "chosen_action": decision.chosen_action,
            "route": decision.route,
            "shipment_status": decision.shipment_status,
            "reasons": list(decision.reasons),
            "explanation": decision.explanation,
            "close_call": is_close,
            "close_call_text": close_text,
        },  # fmt: skip
        "chain": {
            "device_id": "pg-f1-demo",
            "entries_total": len(tampered),
            "intact_result": str(intact),
            "tampered_result": str(broken),
            "tamper": note,
            "first_broken_index": index,
            "reason": broken.reason,
            "ribbon": ribbon,
            "key_id": signer.key_id,
        },  # fmt: skip
        "provenance": {
            "source": parse_canonical(keep[0].record)["source"],
            "scenario_id": RECORDING,
            "from_replay": True,
            "sap_adapter_mode": "mock",
            "software_version": SOFTWARE_VERSION,
            "planner_seed": cfg.seed,
            "twin_tau_h": built.twin.tau_h,
        },  # fmt: skip
    }


# ------------------------------------------------------------------------- contrast
def luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    channels = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


TOKENS = {
    "void": "#04070D", "ink-900": "#070C16", "ink-800": "#0B1220", "ink-700": "#111B2E",
    "line": "#1B2A44", "line-strong": "#5E7899",
    "frost": "#E8F4FF", "mist": "#8FA3BF", "mist-hi": "#A9BAD1",
    "ice-400": "#5DD6FF", "ice-300": "#9BE7FF", "ice-700": "#14506B",
    "ember-400": "#FFB347", "ember-500": "#FF7A3D", "ember-600": "#FF3D2E", "danger-text": "#FF8A7A",
    "verify": "#3DF2B1", "planner": "#8B7CFF", "planner-300": "#B7AEFF",
}  # fmt: skip
TEXT_ROLES = [  # (foreground token, role, minimum ratio)
    ("frost", "primary text", 7.0), ("mist-hi", "secondary text", 7.0), ("mist", "tertiary text, large only", 4.5),
    ("ice-400", "cold or safe accent text", 7.0), ("ice-300", "highlight text", 7.0),
    ("ember-400", "warning text", 7.0), ("ember-500", "heat text", 7.0), ("danger-text", "danger or tamper text", 7.0),
    ("ember-600", "danger fill, graphics and large text", 3.0), ("verify", "verified text", 7.0),
    ("planner-300", "planner text", 7.0), ("planner", "planner fill, graphics and large text", 3.0),
    ("line-strong", "borders of controls, chart axes", 3.0),
]  # fmt: skip
BACKGROUNDS = ["void", "ink-900", "ink-800", "ink-700"]


def contrast_table() -> dict:
    rows = []
    for fg, role, minimum in TEXT_ROLES:
        ratios = {bg: round(contrast(TOKENS[fg], TOKENS[bg]), 2) for bg in BACKGROUNDS}
        rows.append(
            {
                "foreground": fg,
                "hex": TOKENS[fg],
                "role": role,
                "minimum": minimum,
                "ratios": ratios,
                "passes_on": [bg for bg, r in ratios.items() if r >= minimum],
            }
        )
    return {
        "tokens": TOKENS,
        "backgrounds": {b: TOKENS[b] for b in BACKGROUNDS},
        "rows": rows,
        "method": "WCAG 2.x relative luminance contrast ratio, computed in this script",
    }


def main() -> None:
    dump("chapter1.json", chapter1())
    dump("futures.json", futures())
    dump("control_room.json", control_room())
    dump("contrast.json", contrast_table())


if __name__ == "__main__":
    main()
