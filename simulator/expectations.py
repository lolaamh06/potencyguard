"""Declarative guarantees a scenario must keep for EVERY seed (the "expect" block).

Limits are never hard-coded here: a threshold may be a number or the name of a product limit
("hard_limit_high_c" or "hard_limit_low_c"), and "setpoint" comparisons read the box config.
"""

from __future__ import annotations

from collections.abc import Sequence

from edge.sensor_reading import SensorReading
from shared.config import BoxConfig, ProductConfig
from simulator.events import KIND_COOLING, KIND_HEAT, KIND_SPOOF, EventRecord
from simulator.truth import TruthSample

LIMIT_NAMES = ("hard_limit_high_c", "hard_limit_low_c")
# ASSUMPTION: jump size that counts as an isolated outlier when the scenario does not say.
DEFAULT_OUTLIER_JUMP_C = 20.0

THRESHOLD_KEYS = (
    "true_max_c_gt",
    "true_max_c_lt",
    "true_min_c_gt",
    "true_min_c_lt",
    "reported_true_gap_c_gt",
    "true_within_setpoint_c",
    "true_max_above_setpoint_c_lt",
    "final_true_within_setpoint_c",
    "exactly_one_shock_above_g",
    "outlier_jump_c",
)
FLAG_KEYS = ("exactly_one_reported_outlier", "spoof_begins_after_failure")
EXPECT_KEYS = THRESHOLD_KEYS + FLAG_KEYS


def validate_expect_block(expect: dict) -> None:
    """Raise ValueError for unknown keys or values of the wrong type."""
    for key, value in expect.items():
        if key not in EXPECT_KEYS:
            raise ValueError(f"unknown expect key {key!r}; known: {', '.join(EXPECT_KEYS)}")
        if key in FLAG_KEYS:
            if not isinstance(value, bool):
                raise ValueError(f"expect {key} must be true or false (got {value!r})")
        elif isinstance(value, str):
            if value not in LIMIT_NAMES:
                raise ValueError(f"expect {key} must be a number or one of {LIMIT_NAMES}")
        elif isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError(f"expect {key} must be a number (got {value!r})")


def _threshold(value: float | str, product: ProductConfig) -> float:
    if isinstance(value, str):
        return getattr(product, value)
    return float(value)


def check_expectations(
    expect: dict,
    events: Sequence[EventRecord],
    truth: Sequence[TruthSample],
    readings: Sequence[SensorReading],
    box: BoxConfig,
    product: ProductConfig,
) -> list[str]:
    """Return a list of violated expectations (empty means all hold)."""
    true = [s.true_temp_c for s in truth]
    reported = [r.temp_c for r in readings]
    setpoint = box.box_setpoint_c
    problems: list[str] = []

    def need(key: str, ok: bool, detail: str) -> None:
        if key in expect and not ok:
            problems.append(f"{key}={expect[key]!r} violated: {detail}")

    if "true_max_c_gt" in expect:
        limit = _threshold(expect["true_max_c_gt"], product)
        need("true_max_c_gt", max(true) > limit, f"true max {max(true):.2f} <= {limit}")
    if "true_max_c_lt" in expect:
        limit = _threshold(expect["true_max_c_lt"], product)
        need("true_max_c_lt", max(true) < limit, f"true max {max(true):.2f} >= {limit}")
    if "true_min_c_gt" in expect:
        limit = _threshold(expect["true_min_c_gt"], product)
        need("true_min_c_gt", min(true) > limit, f"true min {min(true):.2f} <= {limit}")
    if "true_min_c_lt" in expect:
        limit = _threshold(expect["true_min_c_lt"], product)
        need("true_min_c_lt", min(true) < limit, f"true min {min(true):.2f} >= {limit}")
    if "reported_true_gap_c_gt" in expect:
        gap = max(abs(r - t) for r, t in zip(reported, true, strict=True))
        limit = float(expect["reported_true_gap_c_gt"])
        need("reported_true_gap_c_gt", gap > limit, f"largest gap {gap:.2f} <= {limit}")
    if "true_within_setpoint_c" in expect:
        worst = max(abs(t - setpoint) for t in true)
        limit = float(expect["true_within_setpoint_c"])
        need("true_within_setpoint_c", worst <= limit, f"worst distance {worst:.2f} > {limit}")
    if "true_max_above_setpoint_c_lt" in expect:
        above = max(true) - setpoint
        limit = float(expect["true_max_above_setpoint_c_lt"])
        need("true_max_above_setpoint_c_lt", above < limit, f"max above setpoint {above:.2f}")
    if "final_true_within_setpoint_c" in expect:
        last = abs(true[-1] - setpoint)
        limit = float(expect["final_true_within_setpoint_c"])
        need("final_true_within_setpoint_c", last <= limit, f"final distance {last:.2f} > {limit}")
    if "exactly_one_shock_above_g" in expect:
        limit = float(expect["exactly_one_shock_above_g"])
        count = sum(1 for r in readings if r.shock_g > limit)
        need("exactly_one_shock_above_g", count == 1, f"{count} samples above {limit} g")
    if expect.get("exactly_one_reported_outlier"):
        jump = float(expect.get("outlier_jump_c", DEFAULT_OUTLIER_JUMP_C))
        count = sum(
            1
            for i in range(1, len(reported) - 1)
            if abs(reported[i] - reported[i - 1]) > jump
            and abs(reported[i] - reported[i + 1]) > jump
        )
        need("exactly_one_reported_outlier", count == 1, f"{count} outlier samples (jump {jump})")
    if expect.get("spoof_begins_after_failure"):
        spoofs = [e.start_s for e in events if e.kind == KIND_SPOOF]
        failures = [
            e.start_s
            for e in events
            if e.kind == KIND_HEAT or (e.kind == KIND_COOLING and e.params.get("factor", 1.0) < 1.0)
        ]
        ok = bool(spoofs) and bool(failures) and min(spoofs) > min(failures)
        need("spoof_begins_after_failure", ok, f"spoof starts {spoofs}, failures start {failures}")
    return problems
