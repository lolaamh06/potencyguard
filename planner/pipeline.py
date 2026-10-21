"""From a recording to planner inputs: the existing edge pipeline up to a chosen hour (Phase 5).

Runs RecordedSource -> TrustAssessor (PotencyTracker + TamperMonitor + worst-case bound) exactly as
`python -m edge twin` does, and stops at the chosen hour. Nothing here changes a detector, the
potency maths or the twin. The planner recommends; it never executes. Final authority stays with QA.

The chain status is the Phase 4 check. Without a real ledger it is computed by signing the replayed
readings into a temporary ledger with a throw-away key and verifying that: it shows the replay is
consistent with itself, nothing more. Pass a real ledger and public key to verify the real thing.
A signed record is not treated as true just because it is signed (A18).
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from edge.assessment import TrustAssessor, worst_case_bound
from edge.chain import ChainWriter, Ledger, Signer, verify_chain
from edge.recorded_source import RecordedSource
from edge.runner import record_from_pipeline
from edge.sensor_reading import SensorReading
from edge.tamper_monitor import TamperMonitor
from edge.thermal_twin import TwinParams
from planner.core import TRUSTED, PlannerInputs, conservative_start
from shared.config import BoxConfig, ProductConfig

LOW_CONFIDENCE = "low_confidence"


@dataclass(frozen=True)
class BuiltInputs:
    inputs: PlannerInputs
    potency_curve: list[tuple[float, float]]  # (hours, potency)
    twin: TwinParams
    setpoint_c: float
    chain_detail: str


def _chain_status(
    readings, assessments, potencies, ledger_path, public_key_path
) -> tuple[str, str]:
    if ledger_path is not None:
        if public_key_path is None:
            raise ValueError("--ledger needs --public-key (the key must not come from the ledger)")
        key = bytes.fromhex(Path(public_key_path).read_text(encoding="utf-8").strip())
        with Ledger.open(ledger_path) as ledger:
            result = verify_chain(ledger.read_entries(), key, ledger.latest_anchor())
        return ("ok" if result.ok else "broken"), f"real ledger: {result}"
    with tempfile.TemporaryDirectory(prefix="pg_planner_") as tmp:
        signer = Signer.generate()  # throw-away, never stored
        ledger = Ledger.create("replay", tmp)
        try:
            writer = ChainWriter("pg-replay", signer, ledger)
            for reading, assessment, potency in zip(readings, assessments, potencies, strict=True):
                writer.append(
                    record_from_pipeline("pg-replay", writer.next_seq, reading, potency, assessment)
                )
            result = verify_chain(ledger.read_entries(), signer.public_key_bytes, None)
        finally:
            ledger.close()
    return ("ok" if result.ok else "broken"), (
        f"replayed chain built from this recording and verified ({result.entries_checked} "
        "entries); this only shows the replay is consistent with itself"
    )


def build_inputs(
    recording: Path | str,
    at_hour: float,
    product: ProductConfig,
    box: BoxConfig,
    remaining_h: float | None = None,
    shipment_id: str | None = None,
    ledger_path: Path | str | None = None,
    public_key_path: Path | str | None = None,
) -> BuiltInputs:
    path = Path(recording)
    source = RecordedSource(path)
    source.start()
    monitor = TamperMonitor.from_defaults(product, box)
    assessor = TrustAssessor(product, monitor)
    readings: list[SensorReading] = []
    assessments, potencies, taus = [], [], []
    try:
        header = source.header
        while (reading := source.read()) is not None:
            if reading.t_s > at_hour * 3600.0 + 1e-6:
                break
            assessment, potency, _ = assessor.update(reading)
            readings.append(reading)
            assessments.append(assessment)
            potencies.append(potency)
            taus.append(potency.tau_eq_h)
    finally:
        source.close()
    if not readings:
        raise ValueError(f"no readings up to hour {at_hour}")
    last, assessment, potency = readings[-1], assessments[-1], potencies[-1]
    if last.ambient_c is None:
        raise ValueError("the planner needs the ambient channel")
    duration_h = (header["n_samples"] - 1) * header["sample_interval_s"] / 3600.0
    remaining = remaining_h if remaining_h is not None else duration_h - last.t_s / 3600.0
    if remaining <= 0:
        raise ValueError(
            f"nothing left of the trip after hour {last.t_s / 3600.0:.1f}; give --remaining-hours"
        )

    level = assessment.trust_level
    bound_tau = bound_temp = None
    if level == "untrusted":
        bound_tau = assessment.bound_tau_eq_h
        bound_temp = assessor.last_bound.worst_case_temp_c
    elif level == LOW_CONFIDENCE:
        # Phase 3C gives no bound here; the planner builds the same high bound itself
        # (decision 0009, P1).
        t0 = monitor.untrusted_since_s
        index = next(i for i, r in enumerate(readings) if r.t_s == t0)
        bound = worst_case_bound(
            readings, t0, taus[index], product, monitor.params,
            monitor.config.heat_allowance_c, monitor.config.bound_tau_safety_factor,
        )  # fmt: skip
        bound_tau, bound_temp = bound.tau_eq_total_h, bound.worst_case_temp_c
    start_tau, start_temp, used = conservative_start(
        level, potency.tau_eq_h, last.temp_c, bound_tau, bound_temp
    )
    status, detail = _chain_status(readings, assessments, potencies, ledger_path, public_key_path)
    inputs = PlannerInputs(
        shipment_id=shipment_id or path.stem,
        t_s=last.t_s,
        remaining_h=remaining,
        potency_now=potency.potency,
        tau_eq_now_h=potency.tau_eq_h,
        start_tau_eq_h=start_tau,
        start_temp_c=start_temp,
        ambient_now_c=last.ambient_c,
        bound_used=used,
        trust_level=level,
        verdict=assessment.verdict,
        chain_status=status,
        falsification_latched=monitor.self_check_off,
    )
    curve = [(r.t_s / 3600.0, p.potency) for r, p in zip(readings, potencies, strict=True)]
    return BuiltInputs(inputs, curve, monitor.params, box.box_setpoint_c, detail)


__all__ = ["TRUSTED", "BuiltInputs", "build_inputs"]
