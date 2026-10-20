"""Tests for the pure potency functions (Phase 2B): kinetics, acceleration factor, MKT."""

import importlib.util
import json
import math
from pathlib import Path

import pytest

from edge.potency import (
    arrhenius_acceleration_factor,
    equivalent_reference_time_h,
    hours_to_min_potency_at_temp,
    potency_from_tau_eq,
    shelf_life_used_fraction,
    time_weighted_mkt_c,
)

ROOT = Path(__file__).resolve().parent.parent
VECTORS_DIR = ROOT / "shared" / "test-vectors"
ACTIVE_PATH = VECTORS_DIR / "potency_vectors.json"
REFERENCE_PATH = VECTORS_DIR / "potency_vectors_team_document.json"
VECTORS = json.loads(ACTIVE_PATH.read_text(encoding="utf-8"))  # active default profile
REFERENCE_VECTORS = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))  # team document profile
BOTH = [
    ("potency_vectors.json", VECTORS),
    ("potency_vectors_team_document.json", REFERENCE_VECTORS),
]
KELVIN = 273.15


def _af(temp_c, product):
    return math.exp(product.Ea_over_R * (1 / (product.T_ref_c + KELVIN) - 1 / (temp_c + KELVIN)))


# ----------------------------------------------------------------- document checks


# The document's numbers belong to the REFERENCE profile (the team document's constants).


@pytest.mark.parametrize(
    "check", REFERENCE_VECTORS["document_checks"], ids=lambda c: c["description"]
)
def test_worked_examples_match_the_document_at_its_precision(check, reference_product):
    product = reference_product
    af = arrhenius_acceleration_factor(check["temp_c"], product)
    tau_eq = equivalent_reference_time_h([check["temp_c"]], [check["hours"]], product)
    computed = {
        "af": af,
        "tau_eq_h": tau_eq,
        "shelf_life_used_percent": shelf_life_used_fraction(tau_eq, product) * 100,
    }[check["quantity"]]
    assert round(computed, check["rounding_decimals"]) == check["expected_rounded"]


def test_older_brief_values_also_match_at_their_precision(reference_product):
    # Brief section 3.2: 8 h at 12 C and 24 h at 30 C, within the 1% tolerance given there.
    product = reference_product
    assert arrhenius_acceleration_factor(12, product) == pytest.approx(2.42, rel=0.01)
    assert equivalent_reference_time_h([12], [8], product) == pytest.approx(19.3, rel=0.01)
    assert arrhenius_acceleration_factor(30, product) == pytest.approx(19.4, rel=0.01)
    assert equivalent_reference_time_h([30], [24], product) == pytest.approx(466, rel=0.01)
    assert shelf_life_used_fraction(
        equivalent_reference_time_h([12], [8], product), product
    ) * 100 == (pytest.approx(0.11, rel=0.01))


def test_active_profile_has_the_chosen_constants_and_closed_forms(product):
    assert product.Ea_over_R == 15000 and product.tau_max_h == 8760
    assert product.T_ref_c == 5.0 and product.P_min == 0.90
    for temp_c in (12.0, 40.0):
        closed = math.exp(15000 * (1 / 278.15 - 1 / (temp_c + 273.15)))
        assert arrhenius_acceleration_factor(temp_c, product) == pytest.approx(closed, rel=1e-14)
    assert product.k_ref_per_h == pytest.approx(math.log(1 / 0.90) / 8760, rel=1e-14)
    assert potency_from_tau_eq(8760.0, product) == pytest.approx(0.90, rel=1e-14)


# ----------------------------------------------------------------- acceleration factor


def test_af_is_one_at_the_reference_temperature(product):
    assert arrhenius_acceleration_factor(product.T_ref_c, product) == pytest.approx(1.0, abs=1e-15)


def test_af_is_monotonic_and_straddles_one(product):
    temps = [-20, -5, 0, 2, 5, 8, 12, 20, 30, 40, 60]
    values = [arrhenius_acceleration_factor(t, product) for t in temps]
    assert values == sorted(values) and len(set(values)) == len(values)
    assert all(v < 1 for t, v in zip(temps, values, strict=True) if t < product.T_ref_c)
    assert all(v > 1 for t, v in zip(temps, values, strict=True) if t > product.T_ref_c)


@pytest.mark.parametrize("temp_c", [-10, 0, 2, 5, 8, 12, 20, 25, 30, 40])
def test_af_matches_the_closed_form(temp_c, product):
    assert arrhenius_acceleration_factor(temp_c, product) == pytest.approx(_af(temp_c, product))


# ----------------------------------------------------------------- tau_eq and potency


def test_tau_eq_is_additive_over_split_intervals(product):
    whole = equivalent_reference_time_h([17.0], [10.0], product)
    halves = equivalent_reference_time_h([17.0, 17.0], [5.0, 5.0], product)
    assert halves == pytest.approx(whole, rel=1e-14)


def test_tau_eq_never_decreases_as_readings_are_added(product):
    temps = [5.0, -3.0, 12.0, 30.0, 4.0, 22.0]
    dts = [1.0, 0.5, 2.0, 0.25, 3.0, 1.0]
    previous = 0.0
    for n in range(1, len(temps) + 1):
        current = equivalent_reference_time_h(temps[:n], dts[:n], product)
        assert current >= previous
        previous = current


def test_zero_dt_adds_nothing_and_scaling_dt_scales_tau_eq(product):
    temps, dts = [5.0, 30.0, 12.0], [1.0, 2.0, 3.0]
    base = equivalent_reference_time_h(temps, dts, product)
    with_zero = equivalent_reference_time_h([*temps, 40.0], [*dts, 0.0], product)
    assert with_zero == base
    scaled = equivalent_reference_time_h(temps, [3.5 * d for d in dts], product)
    assert scaled == pytest.approx(3.5 * base, rel=1e-14)


def test_potency_is_one_at_zero_and_strictly_decreasing(product):
    assert potency_from_tau_eq(0.0, product) == 1.0
    values = [potency_from_tau_eq(t, product) for t in (0, 1, 10, 100, 1000, 10000)]
    assert all(a > b for a, b in zip(values, values[1:], strict=False))
    assert all(0 < v <= 1 for v in values)


def test_potency_equals_p_min_at_tau_max(product):
    assert potency_from_tau_eq(product.tau_max_h, product) == pytest.approx(
        product.P_min, rel=1e-14
    )
    assert shelf_life_used_fraction(product.tau_max_h, product) == 1.0


def test_hours_to_min_potency_helper(product):
    at_ref = hours_to_min_potency_at_temp(0.0, product.T_ref_c, product)
    assert at_ref == pytest.approx(product.tau_max_h)
    hot = hours_to_min_potency_at_temp(0.0, 30.0, product)
    assert hot == pytest.approx(product.tau_max_h / arrhenius_acceleration_factor(30.0, product))
    assert hours_to_min_potency_at_temp(product.tau_max_h * 2, 5.0, product) == 0.0


# ----------------------------------------------------------------- MKT


def test_mkt_of_a_constant_profile_is_that_temperature(product):
    for temp in (-5.0, 5.0, 12.0, 30.0):
        assert time_weighted_mkt_c([temp, temp, temp], [1.0, 2.0, 0.5], product) == pytest.approx(
            temp, abs=1e-9
        )


def test_mkt_is_at_least_the_time_weighted_mean_and_inside_the_range(product):
    temps, dts = [4.0, 30.0, 8.0, 15.0], [5.0, 1.0, 3.0, 2.0]
    mean = sum(t * d for t, d in zip(temps, dts, strict=True)) / sum(dts)
    mkt = time_weighted_mkt_c(temps, dts, product)
    assert mkt > mean
    assert min(temps) < mkt < max(temps)


def test_mkt_weights_by_time(product):
    long_cool = time_weighted_mkt_c([5.0, 35.0], [10.0, 1.0], product)
    long_hot = time_weighted_mkt_c([5.0, 35.0], [1.0, 10.0], product)
    assert long_hot > long_cool + 10


def test_mkt_reduces_to_the_equal_interval_form(product):
    temps = [4.0, 9.0, 21.0]
    e = product.Ea_over_R
    direct = e / -math.log(sum(math.exp(-e / (t + KELVIN)) for t in temps) / 3) - KELVIN
    assert time_weighted_mkt_c(temps, [2.0, 2.0, 2.0], product) == pytest.approx(direct, rel=1e-12)


def test_mkt_ignores_zero_duration_entries(product):
    assert time_weighted_mkt_c([5.0, 90.0], [3.0, 0.0], product) == pytest.approx(5.0, abs=1e-9)


@pytest.mark.parametrize(
    ("temps", "dts"),
    [([], []), ([5.0, 6.0], [0.0, 0.0])],
)
def test_mkt_rejects_empty_input_and_zero_duration(temps, dts, product):
    with pytest.raises(ValueError):
        time_weighted_mkt_c(temps, dts, product)


def test_mkt_is_stable_for_extreme_inputs(product):
    for temps in ([-270.0, -270.0], [1000.0, 1000.0], [-200.0, 200.0]):
        result = time_weighted_mkt_c(temps, [1.0, 1.0], product)
        assert math.isfinite(result)
    assert time_weighted_mkt_c([-270.0], [1.0], product) == pytest.approx(-270.0, abs=1e-6)


# ----------------------------------------------------------------- validation


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, -273.15, -300.0])
def test_bad_temperatures_are_rejected(bad, product):
    with pytest.raises(ValueError):
        arrhenius_acceleration_factor(bad, product)
    with pytest.raises(ValueError):
        equivalent_reference_time_h([bad], [1.0], product)


@pytest.mark.parametrize("bad", [-1.0, math.nan, math.inf])
def test_bad_time_steps_are_rejected(bad, product):
    with pytest.raises(ValueError):
        equivalent_reference_time_h([5.0], [bad], product)
    with pytest.raises(ValueError):
        time_weighted_mkt_c([5.0], [bad], product)


def test_mismatched_lengths_are_rejected(product):
    with pytest.raises(ValueError, match="same length"):
        equivalent_reference_time_h([5.0, 6.0], [1.0], product)
    with pytest.raises(ValueError, match="same length"):
        time_weighted_mkt_c([5.0], [1.0, 2.0], product)


def test_bad_tau_eq_is_rejected(product):
    for bad in (-1.0, math.nan, math.inf):
        with pytest.raises(ValueError):
            potency_from_tau_eq(bad, product)
        with pytest.raises(ValueError):
            shelf_life_used_fraction(bad, product)
        with pytest.raises(ValueError):
            hours_to_min_potency_at_temp(bad, 5.0, product)


# ----------------------------------------------------------------- shared vectors (pure part)


PROFILE_FIXTURE = {
    "potency_vectors.json": "product",
    "potency_vectors_team_document.json": "reference_product",
}
AF_CASES = [(name, case) for name, doc in BOTH for case in doc["af_cases"]]
TAU_CASES = [(name, case) for name, doc in BOTH for case in doc["tau_cases"]]


@pytest.mark.parametrize(("name", "document"), BOTH)
def test_vector_constants_match_the_profile_they_name(name, document, request):
    cfg = request.getfixturevalue(PROFILE_FIXTURE[name])
    constants = document["meta"]["constants"]
    assert constants["Ea_over_R"] == cfg.Ea_over_R
    assert constants["tau_max_h"] == cfg.tau_max_h
    assert constants["P_min"] == cfg.P_min
    assert constants["hard_limit_consecutive_samples"] == cfg.hard_limit_consecutive_samples
    assert "[SOURCE NEEDED]" in document["meta"]["profile"]


def test_the_two_vector_files_hold_the_two_profiles():
    assert VECTORS["meta"]["constants"]["Ea_over_R"] == 15000
    assert REFERENCE_VECTORS["meta"]["constants"]["Ea_over_R"] == 10000
    assert "document_checks" in REFERENCE_VECTORS and "document_checks" not in VECTORS


@pytest.mark.parametrize(
    ("name", "case"), AF_CASES, ids=lambda v: v if isinstance(v, str) else str(v["temp_c"])
)
def test_af_vectors(name, case, request):
    cfg = request.getfixturevalue(PROFILE_FIXTURE[name])
    assert arrhenius_acceleration_factor(case["temp_c"], cfg) == pytest.approx(
        case["expected_af"], rel=1e-12
    )


@pytest.mark.parametrize(
    ("name", "case"), TAU_CASES, ids=lambda v: v if isinstance(v, str) else v["name"]
)
def test_tau_vectors(name, case, request):
    cfg = request.getfixturevalue(PROFILE_FIXTURE[name])
    tau_eq = equivalent_reference_time_h(case["temps_c"], case["dts_h"], cfg)
    assert tau_eq == pytest.approx(case["expected_tau_eq_h"], rel=1e-12)
    assert potency_from_tau_eq(tau_eq, cfg) == pytest.approx(case["expected_potency"], rel=1e-12)
    assert shelf_life_used_fraction(tau_eq, cfg) == pytest.approx(
        case["expected_shelf_life_used_fraction"], rel=1e-12
    )
    assert time_weighted_mkt_c(case["temps_c"], case["dts_h"], cfg) == pytest.approx(
        case["expected_mkt_c"], rel=1e-12
    )


def test_committed_vectors_equal_a_fresh_generation_for_both_profiles():
    spec = importlib.util.spec_from_file_location(
        "make_test_vectors", ROOT / "scripts" / "make_test_vectors.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fresh = module.build_all()
    assert set(fresh) == {"potency_vectors.json", "potency_vectors_team_document.json"}
    for name, vectors in fresh.items():
        committed = (VECTORS_DIR / name).read_text(encoding="utf-8")
        assert module.render(vectors) == committed, name


# ----------------------------------------------------------------- config validation


@pytest.mark.parametrize(
    ("old", "new", "key"),
    [
        ("Ea_over_R: 15000", "Ea_over_R: 0", "Ea_over_R"),
        ("tau_max_h: 8760", "tau_max_h: -5", "tau_max_h"),
        ("P_min: 0.90", "P_min: 1.0", "P_min"),
        ("hard_limit_low_c: 0.0", "hard_limit_low_c: 50.0", "hard_limit_low_c"),
        ("hard_limit_consecutive_samples: 2", "hard_limit_consecutive_samples: 0", "consecutive"),
    ],
)
def test_kinetic_constants_are_validated(old, new, key, tmp_path):
    from shared.config import ConfigError, load_product_config

    text = (ROOT / "config" / "product_default.yaml").read_text(encoding="utf-8")
    assert old in text
    bad = tmp_path / "bad.yaml"
    bad.write_text(text.replace(old, new, 1), encoding="utf-8")
    with pytest.raises(ConfigError, match=key):
        load_product_config(bad)


def test_k_ref_is_derived_not_stored(product):
    assert product.k_ref_per_h == pytest.approx(math.log(1 / product.P_min) / product.tau_max_h)
    assert "k_ref_per_h" not in type(product).__dataclass_fields__
