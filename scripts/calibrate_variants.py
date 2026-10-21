"""Fit one thermal twin per box variant and write config/twin_calibrated_variants.yaml (Phase 3C).

Run from the repo root:  python scripts/calibrate_variants.py

For each variant (+15 percent box, -15 percent box, two-node box) the simulator generates the
dedicated clean calibration set FOR THAT BOX (seeds 9101-9110, 9201-9210, 9301-9310) and the same
restricted regression as the nominal calibration fits the twin. The nominal file
config/twin_calibrated.yaml is not touched. Simulation only.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from edge.calibration import write_variant_twins  # noqa: E402
from edge.thermal_twin import VARIANT_TWIN_PATH, load_twin_params  # noqa: E402
from shared.config import load_box_config  # noqa: E402
from simulator.calibration_set import (  # noqa: E402
    VARIANT_LABELS,
    VARIANT_SEEDS,
    calibrate_for_box,
    variant_boxes,
    variant_seed_plan,
)


def main() -> int:
    box = load_box_config()
    nominal = load_twin_params()
    fitted = {}
    print(f"nominal twin: tau = {nominal.tau_h:.3f} h, dT_cool = {nominal.dT_cool_c:.2f} K")
    for name, variant in variant_boxes(box).items():
        result = calibrate_for_box(variant, variant_seed_plan(name))
        fitted[name] = (result, VARIANT_SEEDS[name], VARIANT_LABELS[name])
        p = result.params
        print(
            f"{name:9s} tau = {p.tau_h:.3f} h, dT_cool = {p.dT_cool_c:.2f} K, "
            f"sigma_r = {p.sigma_r_c:.4f} C, R^2 = {result.r_squared:.4f}"
        )
    write_variant_twins(VARIANT_TWIN_PATH, fitted)
    print(f"wrote {VARIANT_TWIN_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
