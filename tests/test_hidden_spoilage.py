"""hidden_spoilage must keep its story for every seed (Phase 2D), under the ACTIVE profile.

The potency guarantees cannot live in the scenario's expect block, because the simulator
package must not import the edge package, so they are checked here with the real simulator
and the real tracker.
"""

import pytest

from edge.potency import PotencyTracker
from simulator.live import LiveSimulator
from simulator.scenario import load_all_scenarios

SCENARIO = load_all_scenarios()["hidden_spoilage"]
SEEDS = range(1000, 1200)  # 200 seeds
WINDOW_H = (48.0, 90.0)
PLAUSIBLE_MAX_C = 45.0


def _run(box, product, seed):
    sim = LiveSimulator(SCENARIO, box, seed)
    true_tracker, reported_tracker = PotencyTracker(product), PotencyTracker(product)
    crossing = None
    reported_problems = []
    true_max = float("-inf")
    while True:
        reading, truth = sim.step()
        if reading is None or truth is None:
            break
        true_state = true_tracker.update_sample(truth.t_s, truth.true_temp_c)
        reported_state = reported_tracker.update(reading)
        true_max = max(true_max, truth.true_temp_c)
        if crossing is None and true_state.below_min_potency:
            crossing = truth.t_s / 3600.0
        if reported_state.below_min_potency:
            reported_problems.append(("below P_min", truth.t_s))
        if reported_state.status != "ok":
            reported_problems.append((reported_state.status, truth.t_s))
        if not product.hard_limit_low_c <= reading.temp_c <= product.hard_limit_high_c:
            reported_problems.append(("outside hard limits", truth.t_s))
    return crossing, reported_problems, true_max


def test_the_description_is_plain_and_neutral():
    text = SCENARIO.description.lower()
    assert "%" not in text and "[source needed]" not in text
    assert "sap" not in text and "raspberry" not in text


@pytest.fixture(scope="module")
def results(box, product):
    """One run per seed, shared by the tests below."""
    return {seed: _run(box, product, seed) for seed in SEEDS}


def test_true_potency_crosses_the_minimum_inside_the_window_for_every_seed(results):
    for seed, (crossing, _, _) in results.items():
        assert crossing is not None, f"seed {seed}: true potency never fell below P_min"
        assert WINDOW_H[0] <= crossing <= WINDOW_H[1], f"seed {seed}: crossing at {crossing} h"


def test_the_reported_series_stays_clean_for_every_seed(results):
    for seed, (_, problems, _) in results.items():
        assert not problems, f"seed {seed}: {problems[:3]}"


def test_the_true_temperature_stays_physically_plausible(results):
    for seed, (_, _, true_max) in results.items():
        assert true_max < PLAUSIBLE_MAX_C, f"seed {seed}: true max {true_max}"


def test_the_story_runs_in_order(box):
    sim = LiveSimulator(SCENARIO, box, 1)
    kinds = {e.kind: e for e in sim.events()}
    assert kinds["spoof"].start_s > kinds["cooling_factor"].start_s
    assert 0.24 <= kinds["cooling_factor"].params["factor"] <= 0.38
    assert 12 * 3600 <= kinds["cooling_factor"].start_s <= 18 * 3600


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_runs_differ_between_seeds(box, seed):
    a = LiveSimulator(SCENARIO, box, seed).events()
    b = LiveSimulator(SCENARIO, box, seed + 100).events()
    assert [e.start_s for e in a] != [e.start_s for e in b]
