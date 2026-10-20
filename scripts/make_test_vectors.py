"""Write shared/test-vectors/potency_vectors.json from the Python reference implementation.

Run from the repo root:  python scripts/make_test_vectors.py
Every expected number is computed by the code in edge/potency.py. Only the "document_checks"
list holds numbers typed from the team document (rounded, with the precision they were given).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from edge.potency import (  # noqa: E402
    PotencyTracker,
    arrhenius_acceleration_factor,
    equivalent_reference_time_h,
    potency_from_tau_eq,
    shelf_life_used_fraction,
    time_weighted_mkt_c,
)
from shared.config import ProductConfig, load_product_config  # noqa: E402

OUTPUT = REPO_ROOT / "shared" / "test-vectors" / "potency_vectors.json"
SCHEMA_VERSION = "1"
AF_TEMPS_C = [-10, 0, 2, 5, 8, 12, 20, 25, 30, 40]
SAMPLE_S = 600.0


def _ramp() -> tuple[list[float], list[float]]:
    """A ramp from 5 C to 35 C written as 61 half-hour steps."""
    temps = [5.0 + 0.5 * i for i in range(61)]
    return temps, [0.5] * 61


PROFILES = {
    "constant_12c_8h": ([12.0], [8.0]),
    "constant_30c_24h": ([30.0], [24.0]),
    "two_step_cool_then_warm": ([5.0, 25.0], [6.0, 6.0]),
    "ramp_5_to_35_c_in_half_hour_steps": _ramp(),
    "uneven_dt": ([4.0, 9.5, 2.0, 31.0, 6.5], [0.25, 3.0, 0.5, 12.0, 0.1]),
}


def _sequence(temps: list[float], step_s: float = SAMPLE_S) -> list[dict]:
    return [{"t_s": i * step_s, "temp_c": t} for i, t in enumerate(temps)]


def _tracker_sequences() -> dict[str, list[dict]]:
    clean = [5.0 + 0.3 * ((i * 7) % 5 - 2) / 2 for i in range(24)]
    lone_low = [5.0] * 8 + [-5.0] + [5.0] * 8
    glitch_then_recovery = [5.0, 5.2, 4.9, 61.0, 5.1, 5.0, 4.8]
    high = [5.0] * 6 + [45.0, 46.5, 47.0] + [5.0] * 6
    freeze = [5.0] * 6 + [-2.0, -3.5, -1.0] + [5.0] * 4
    glitch_last = [5.0] * 10 + [88.0]
    uneven = [
        {"t_s": 0.0, "temp_c": 5.0},
        {"t_s": 300.0, "temp_c": 5.5},
        {"t_s": 4500.0, "temp_c": 41.0},
        {"t_s": 4510.0, "temp_c": 42.0},
        {"t_s": 9000.0, "temp_c": 6.0},
        {"t_s": 9000.0, "temp_c": 6.5},
    ]
    return {
        "clean_run": _sequence(clean),
        "lone_low_glitch": _sequence(lone_low),
        "lone_high_glitch_then_recovery": _sequence(glitch_then_recovery),
        "confirmed_high_excursion": _sequence(high),
        "confirmed_low_excursion_freeze": _sequence(freeze),
        "glitch_as_last_sample": _sequence(glitch_last),
        "uneven_time_steps_with_excursion": uneven,
    }


def _state_dict(state) -> dict:
    return state.model_dump()


def build_vectors(cfg: ProductConfig | None = None) -> dict:
    """Return the full vector document as plain data."""
    cfg = cfg or load_product_config()
    af_cases = [
        {"temp_c": t, "expected_af": arrhenius_acceleration_factor(t, cfg)} for t in AF_TEMPS_C
    ]
    tau_cases = []
    for name, (temps, dts) in PROFILES.items():
        tau_eq = equivalent_reference_time_h(temps, dts, cfg)
        tau_cases.append(
            {
                "name": name,
                "temps_c": temps,
                "dts_h": dts,
                "expected_tau_eq_h": tau_eq,
                "expected_potency": potency_from_tau_eq(tau_eq, cfg),
                "expected_shelf_life_used_fraction": shelf_life_used_fraction(tau_eq, cfg),
                "expected_mkt_c": time_weighted_mkt_c(temps, dts, cfg),
            }
        )
    tracker_cases = []
    for name, readings in _tracker_sequences().items():
        tracker = PotencyTracker(cfg)
        per_sample = []
        for reading in readings:
            state = tracker.update_sample(reading["t_s"], reading["temp_c"])
            per_sample.append(
                {
                    "status": state.status,
                    "tau_eq_h": state.tau_eq_h,
                    "samples_excluded": state.samples_excluded,
                }
            )
        tracker_cases.append(
            {
                "name": name,
                "readings": readings,
                "expected_statuses": [p["status"] for p in per_sample],
                "expected_per_sample": per_sample,
                "expected_final_state": _state_dict(tracker.snapshot()),
            }
        )
    document_checks = [
        {
            "description": "8 h at a constant 12 C: acceleration factor",
            "quantity": "af", "temp_c": 12.0, "hours": 8.0,
            "expected_rounded": 2.417, "rounding_decimals": 3,
        },
        {
            "description": "8 h at a constant 12 C: hours at the reference temperature",
            "quantity": "tau_eq_h", "temp_c": 12.0, "hours": 8.0,
            "expected_rounded": 19.34, "rounding_decimals": 2,
        },
        {
            "description": "8 h at a constant 12 C: percent of shelf life used",
            "quantity": "shelf_life_used_percent", "temp_c": 12.0, "hours": 8.0,
            "expected_rounded": 0.110, "rounding_decimals": 3,
        },
        {
            "description": "24 h at a constant 30 C: acceleration factor",
            "quantity": "af", "temp_c": 30.0, "hours": 24.0,
            "expected_rounded": 19.39, "rounding_decimals": 2,
        },
        {
            "description": "24 h at a constant 30 C: hours at the reference temperature",
            "quantity": "tau_eq_h", "temp_c": 30.0, "hours": 24.0,
            "expected_rounded": 465.4, "rounding_decimals": 1,
        },
        {
            "description": "24 h at a constant 30 C: percent of shelf life used",
            "quantity": "shelf_life_used_percent", "temp_c": 30.0, "hours": 24.0,
            "expected_rounded": 2.66, "rounding_decimals": 2,
        },
    ]  # fmt: skip
    return {
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "note": (
                "All expected values are computed by the Python reference implementation "
                "(edge/potency.py) from synthetic product parameters for an imaginary vaccine. "
                "Only document_checks holds rounded numbers taken from the team document."
            ),
            "constants": {
                "Ea_over_R": cfg.Ea_over_R,
                "T_ref_c": cfg.T_ref_c,
                "tau_max_h": cfg.tau_max_h,
                "P_min": cfg.P_min,
                "hard_limit_low_c": cfg.hard_limit_low_c,
                "hard_limit_high_c": cfg.hard_limit_high_c,
                "hard_limit_consecutive_samples": cfg.hard_limit_consecutive_samples,
            },
            "integration_rule": "right endpoint: each sample covers the interval ending at it",
        },
        "af_cases": af_cases,
        "tau_cases": tau_cases,
        "tracker_cases": tracker_cases,
        "document_checks": document_checks,
    }


def render(vectors: dict) -> str:
    return json.dumps(vectors, indent=1) + "\n"


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(render(build_vectors()))
    print(f"wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
