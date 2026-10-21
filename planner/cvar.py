"""CVaR, VaR and expected loss (Phase 5).

Rockafellar-Uryasev form:  CVaR_alpha(L) = min_eta { eta + (1/(1-alpha)) E[(L - eta)^+] }.
For a sample the minimum is at eta = the alpha-quantile, so it is computed exactly. A second,
direct function averages the worst (1 - alpha) share of the losses (fractional weight on the
boundary); the two agree (tested). alpha must be in [0, 1): alpha = 0 gives the mean.

These are plain loops/sorting over numbers; no Monte Carlo happens here. Illustrative placeholder
numbers only; simulation results on a synthetic box.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

TIE_RELATIVE_TOLERANCE = 1e-9


def _check_alpha(alpha: float) -> None:
    if isinstance(alpha, bool) or not isinstance(alpha, int | float) or not 0.0 <= alpha < 1.0:
        raise ValueError(f"alpha must be a number in [0, 1) (got {alpha!r})")


def var_discrete(outcomes: Sequence[tuple[float, float]], alpha: float) -> float:
    """VaR_alpha: the smallest loss x with P(L <= x) >= alpha. outcomes = (loss, probability)."""
    _check_alpha(alpha)
    ordered = _ordered(outcomes)
    cumulative = 0.0
    for loss, p in ordered:
        cumulative += p
        if cumulative >= alpha - 1e-12:
            return loss
    return ordered[-1][0]


def cvar_discrete(outcomes: Sequence[tuple[float, float]], alpha: float) -> float:
    """Exact CVaR of a discrete loss: eta + (1/(1-alpha)) sum p_i (L_i - eta)^+ at eta = VaR."""
    _check_alpha(alpha)
    ordered = _ordered(outcomes)
    eta = var_discrete(ordered, alpha)
    excess = sum(p * max(loss - eta, 0.0) for loss, p in ordered)
    return eta + excess / (1.0 - alpha)


def expected_discrete(outcomes: Sequence[tuple[float, float]]) -> float:
    return sum(loss * p for loss, p in _ordered(outcomes))


def _ordered(outcomes: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    if not outcomes:
        raise ValueError("need at least one outcome")
    total = 0.0
    for loss, p in outcomes:
        if not (math.isfinite(loss) and math.isfinite(p)) or p < 0:
            raise ValueError("losses must be finite and probabilities non-negative")
        total += p
    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"probabilities must sum to 1 (got {total})")
    return sorted(outcomes, key=lambda item: item[0])


def _sorted_sample(losses) -> np.ndarray:
    arr = np.sort(np.asarray(losses, dtype=float))
    if arr.size == 0:
        raise ValueError("need at least one sampled loss")
    if not np.all(np.isfinite(arr)):
        raise ValueError("sampled losses must be finite")
    return arr


def var_sample(losses, alpha: float) -> float:
    """The alpha-quantile of a sample: the smallest sorted value x_(k) with k >= alpha * n."""
    _check_alpha(alpha)
    arr = _sorted_sample(losses)
    k = max(1, math.ceil(alpha * arr.size - 1e-12))
    return float(arr[k - 1])


def cvar_sample(losses, alpha: float) -> float:
    """Rockafellar-Uryasev CVaR of a sample, with eta at the alpha-quantile."""
    _check_alpha(alpha)
    arr = _sorted_sample(losses)
    eta = var_sample(arr, alpha)
    return eta + float(np.maximum(arr - eta, 0.0).sum()) / (arr.size * (1.0 - alpha))


def cvar_tail_average(losses, alpha: float) -> float:
    """The same number computed directly: the mean of the worst (1 - alpha) share of the sample."""
    _check_alpha(alpha)
    arr = _sorted_sample(losses)
    n = arr.size
    tail_mass = (1.0 - alpha) * n  # in sample units, may be fractional (or below 1 for tiny n)
    remaining, total = tail_mass, 0.0
    for value in arr[::-1]:
        take = min(1.0, remaining)
        total += take * float(value)
        remaining -= take
        if remaining <= 1e-12:
            break
    return total / tail_mass


def cvar_by_minimisation(losses, alpha: float) -> float:
    """CVaR from the definition: minimise eta + E[(L - eta)^+]/(1 - alpha) over the sample values.

    The objective is convex and piecewise linear in eta with kinks at the sample values, so its
    minimum is at one of them. Slower (O(n^2)); used only to check the closed form in tests.
    """
    _check_alpha(alpha)
    arr = _sorted_sample(losses)
    best = math.inf
    for eta in np.unique(arr):
        value = float(eta) + float(np.maximum(arr - eta, 0.0).mean()) / (1.0 - alpha)
        best = min(best, value)
    return best


def choose_action(values: dict[str, dict[str, float]], key: str, order: Sequence[str]) -> str:
    """The action with the smallest `key` (cvar or expected). Ties (relative 1e-9) are broken by
    expected loss, then cost, then the fixed action order."""
    names = list(order)
    smallest = min(values[a][key] for a in names)
    scale = max(1.0, abs(smallest))
    tied = [a for a in names if values[a][key] - smallest <= TIE_RELATIVE_TOLERANCE * scale]
    return min(tied, key=lambda a: (values[a]["expected"], values[a]["cost"], names.index(a)))
