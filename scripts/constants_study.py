"""Read-only study: how do candidate product constants change the potency story? (Phase 2C)

Candidate sets are built IN MEMORY with dataclasses.replace on the loaded ProductConfig. The real
configuration, edge/potency.py and every existing test are untouched. All candidate values are
illustrative placeholders, not sourced [SOURCE NEEDED]; none describes a real product.

Run from the repo root:  python scripts/constants_study.py
Writes docs/02-phase-reports/phase-02c-constants-study.md and data/generated/constants_study.json.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from collections.abc import Sequence
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from edge.cli import DEFAULT_RECORDINGS_DIR, analyse_recording  # noqa: E402
from edge.potency import PotencyState, arrhenius_acceleration_factor  # noqa: E402
from shared.config import ProductConfig, load_product_config  # noqa: E402

DEFAULT_MARKDOWN = REPO_ROOT / "docs" / "02-phase-reports" / "phase-02c-constants-study.md"
DEFAULT_JSON = REPO_ROOT / "data" / "generated" / "constants_study.json"
FOOTER = (
    "Simulation result on a synthetic box, with illustrative constants. Not real-world evidence."
)
SPOOF_SCENARIO = "spoof_attempt"
# placeholder, not sourced [SOURCE NEEDED]: illustrative candidate sets (T_ref and P_min unchanged).
CANDIDATES: dict[str, dict[str, float]] = {
    "A": {"Ea_over_R": 10000, "tau_max_h": 17520},
    "B": {"Ea_over_R": 15000, "tau_max_h": 17520},
    "C": {"Ea_over_R": 15000, "tau_max_h": 8760},
    "D": {"Ea_over_R": 20000, "tau_max_h": 8760},
    "E": {"Ea_over_R": 15000, "tau_max_h": 4380},
}
SET_NOTES = {"A": "current configuration"}


def make_variant(base: ProductConfig, values: dict[str, float]) -> ProductConfig:
    """A copy of the loaded config with some values replaced. The base is never modified."""
    return dataclasses.replace(base, **values)


def _series_result(states: Sequence[PotencyState], cfg: ProductConfig) -> dict:
    last = states[-1]
    elapsed_h = last.t_s / 3600.0
    first_below = next((s.t_s / 3600.0 for s in states if s.below_min_potency), None)
    return {
        "tau_eq_h": last.tau_eq_h,
        "potency_percent": last.potency * 100.0,
        "used_percent": last.shelf_life_used_fraction * 100.0,
        "elapsed_h": elapsed_h,
        "extra_days_lost": (last.tau_eq_h - elapsed_h) / 24.0,
        "below_p_min": last.below_min_potency,
        "first_below_p_min_hour": first_below,
        "status": last.status,
        "samples_excluded": last.samples_excluded,
    }


def study_set(cfg: ProductConfig, recordings_dir: Path = DEFAULT_RECORDINGS_DIR) -> dict:
    """Run every golden recording through the tracker for one candidate configuration."""
    scenarios = {}
    for path in sorted(recordings_dir.glob("*.jsonl")):
        analysis = analyse_recording(path, cfg)
        scenarios[analysis.scenario_id] = {
            "reported": _series_result(analysis.reported_states, cfg),
            "true": _series_result(analysis.true_states, cfg),
        }
    af25 = arrhenius_acceleration_factor(25.0, cfg)
    af40 = arrhenius_acceleration_factor(40.0, cfg)
    spoof = scenarios[SPOOF_SCENARIO]
    return {
        "Ea_over_R": cfg.Ea_over_R,
        "tau_max_h": cfg.tau_max_h,
        "T_ref_c": cfg.T_ref_c,
        "P_min": cfg.P_min,
        "k_ref_per_h": cfg.k_ref_per_h,
        "days_lost_per_day_at_25c": af25,
        "days_lost_per_day_at_40c": af40,
        "days_at_40c_to_use_all_shelf_life": cfg.tau_max_h / af40 / 24.0,
        "scenarios": scenarios,
        "spoof_hidden_loss": {
            "used_percent_points": spoof["true"]["used_percent"]
            - spoof["reported"]["used_percent"],
            "potency_percentage_points": spoof["reported"]["potency_percent"]
            - spoof["true"]["potency_percent"],
            "extra_days_lost": spoof["true"]["extra_days_lost"]
            - spoof["reported"]["extra_days_lost"],
        },
    }


def run_study(base: ProductConfig | None = None, recordings_dir: Path = DEFAULT_RECORDINGS_DIR):
    """Return the whole study as plain data. Does not touch files or the base configuration."""
    base = base or load_product_config()
    return {
        "note": FOOTER,
        "base": {"T_ref_c": base.T_ref_c, "P_min": base.P_min},
        "sets": {
            name: study_set(make_variant(base, values), recordings_dir)
            for name, values in CANDIDATES.items()
        },
    }


# ----------------------------------------------------------------------------- text output


def _f(value: float, decimals: int) -> str:
    """Format a number; a tiny negative that rounds to zero prints as 0 (no "-0.00")."""
    text = f"{value:.{decimals}f}"
    return text[1:] if text.startswith("-") and float(text) == 0.0 else text


def _below(result: dict) -> str:
    if not result["below_p_min"]:
        return "no"
    return f"yes @ {result['first_below_p_min_hour']:.1f} h"


def _table(name: str, data: dict) -> list[str]:
    head = (
        "| scenario | used % rep | used % true | potency % rep | potency % true | "
        "extra days lost rep | extra days lost true | < P_min rep | < P_min true | "
        "status rep (excl.) |"
    )
    rule = "|---|---:|---:|---:|---:|---:|---:|---|---|---|"
    rows = [head, rule]
    for scenario_id, item in data["scenarios"].items():
        rep, true = item["reported"], item["true"]
        rows.append(
            f"| {scenario_id} | {rep['used_percent']:.3f} | {true['used_percent']:.3f} "
            f"| {rep['potency_percent']:.3f} | {true['potency_percent']:.3f} "
            f"| {_f(rep['extra_days_lost'], 2)} | {_f(true['extra_days_lost'], 2)} "
            f"| {_below(rep)} | {_below(true)} | {rep['status']} ({rep['samples_excluded']}) |"
        )
    return rows


def render_markdown(study: dict) -> str:
    lines = [
        "# Phase 2C: Product-constants study",
        "",
        "## What this is",
        "",
        "The potency model has a few made-up product constants: how fast damage grows with "
        "temperature (Ea/R) and how long the shelf life is (tau_max). With the current values "
        "(set A) even the worst golden recording leaves potency near 99 percent, so a pitch has "
        "little to show. This study re-runs the same eight recordings through the same tracker "
        "with five illustrative sets of constants and prints what each would show. Nothing in the "
        "real configuration was changed. Every candidate value is a placeholder, not sourced "
        "[SOURCE NEEDED], and none describes a real product. T_ref (5 C) and P_min (0.90) are the "
        "same in all sets.",
        "",
        "## How to read the tables",
        "",
        "- *rep* is the result from the reported readings (what the box would see); *true* is "
        "from the true temperature in the ground-truth file.",
        "- *used %* is the share of the shelf life spent. Potency reaches P_min exactly when it "
        "hits 100 percent.",
        "- *extra days lost* is the shelf life lost beyond normal ageing in the same time at the "
        "reference temperature: (tau_eq - trip hours) / 24. Negative means the trip was colder "
        "than the reference.",
        "- *< P_min* says whether potency fell below the minimum and, if so, the simulated hour.",
        "- *status rep (excl.)* is the final tracker status on the reported series and the number "
        "of excluded samples.",
        "",
        "Sets: "
        + "; ".join(
            f"**{n}** = Ea/R {int(v['Ea_over_R'])}, tau_max {int(v['tau_max_h'])} h"
            f"{' (' + SET_NOTES[n] + ')' if n in SET_NOTES else ''}"
            for n, v in CANDIDATES.items()
        ),
        "",
    ]
    for name, data in study["sets"].items():
        hidden = data["spoof_hidden_loss"]
        lines += [
            f"## Set {name}: Ea/R {int(data['Ea_over_R'])}, tau_max {int(data['tau_max_h'])} h",
            "",
            *_table(name, data),
            "",
            f"- One day at 25 C costs {data['days_lost_per_day_at_25c']:.2f} days of shelf life; "
            f"one day at 40 C costs {data['days_lost_per_day_at_40c']:.2f} days.",
            f"- It takes {data['days_at_40c_to_use_all_shelf_life']:.1f} days at 40 C to use all "
            "of the shelf life.",
            "- Spoof scenario, hidden loss (true minus reported): "
            f"{hidden['used_percent_points']:.3f} percentage points of shelf life, "
            f"{hidden['potency_percentage_points']:.3f} potency percentage points, "
            f"{hidden['extra_days_lost']:.2f} days.",
            "",
            f"*{FOOTER}*",
            "",
        ]
    return "\n".join(lines)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare candidate product constants.")
    parser.add_argument("--markdown", default=str(DEFAULT_MARKDOWN))
    parser.add_argument("--json", default=str(DEFAULT_JSON))
    args = parser.parse_args(argv)
    study = run_study()
    markdown = render_markdown(study)
    _write(Path(args.markdown), markdown + "\n")
    _write(Path(args.json), json.dumps(study, indent=1) + "\n")
    print(markdown)
    print(f"wrote {args.markdown} and {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
