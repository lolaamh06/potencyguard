"""When does a falsified temperature first differ visibly from the true one? (Phase 3 scoring)"""

from __future__ import annotations

from collections.abc import Sequence

from simulator.truth import TruthSample


def first_divergence_s(truth: Sequence[TruthSample], threshold_c: float) -> float | None:
    """First sample time at which a spoof is active and |reported - true| exceeds threshold_c.

    Returns None if no spoof is ever active or the lie never gets that far from the truth (a
    harmless lie). Only spoofs count; a lone glitch is a different kind of event.
    """
    for sample in truth:
        if sample.spoof_mode is not None and abs(sample.reported_temp_c - sample.true_temp_c) > (
            threshold_c
        ):
            return sample.t_s
    return None
