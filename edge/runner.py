"""The edge runner: sensor source -> potency -> tamper monitor -> trust assessment -> signed chain.

    SensorSource -> PotencyTracker -> TamperMonitor -> TrustAssessor -> ChainWriter -> Ledger

TrustAssessor wraps the existing PotencyTracker and TamperMonitor, so the signed values are exactly
what `python -m edge twin` already computes; nothing here changes a detector, the potency maths or
the twin. After the last reading a final anchor is signed, the ledger is read back and verified.

Signatures and the hash chain protect records AFTER they are signed. They do NOT stop a lie at the
sensor before the device signs it: if the sensor input is false, the device signs the false value.
A sensor-level mimic liar needs attested or redundant sensors, or out-of-band data.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from edge.assessment import PotencyAssessment, TrustAssessor
from edge.chain import (
    ChainWriter,
    Ledger,
    Signer,
    VerifyResult,
    build_record,
    new_run_id,
    verify_chain,
)
from edge.potency import PotencyState
from edge.recorded_source import RecordedSource
from edge.sensor_reading import SensorReading
from edge.sensor_source import SensorSource
from edge.tamper_monitor import TamperMonitor
from shared.config import BoxConfig, ProductConfig

DEFAULT_DEVICE_ID = "pg-sim-001"


def record_from_pipeline(
    device_id: str,
    seq: int,
    reading: SensorReading,
    potency: PotencyState,
    assessment: PotencyAssessment,
) -> dict:
    """The canonical record dict for one reading (see edge/chain/canonical.py for the units)."""
    return build_record(
        device_id=device_id,
        seq=seq,
        t_s=reading.t_s,
        source=reading.source,
        temp_c=reading.temp_c,
        rh_pct=reading.rh_pct,
        shock_g=reading.shock_g,
        ambient_c=reading.ambient_c,
        cooling_duty=reading.cooling_duty,
        potency=potency.potency,
        shelf_life_used_fraction=potency.shelf_life_used_fraction,
        tau_eq_h=potency.tau_eq_h,
        verdict=assessment.verdict,
        trust_level=assessment.trust_level,
        bound_tau_eq_h=assessment.bound_tau_eq_h,
        bound_low_tau_eq_h=assessment.bound_low_tau_eq_h,
    )


@dataclass(frozen=True)
class RunSummary:
    recording: str
    ledger_path: Path
    key_id: str
    entries: int
    verdict_counts: dict[str, int]
    chain: VerifyResult
    last_potency: float | None
    final_trust_level: str | None

    def lines(self) -> list[str]:
        counts = ", ".join(f"{k} {v}" for k, v in sorted(self.verdict_counts.items()))
        potency = "n/a" if self.last_potency is None else f"{self.last_potency * 100:.3f} percent"
        return [
            f"Recording {self.recording}: {self.entries} signed entries (key id {self.key_id})",
            f"  verdicts      {counts}",
            f"  chain         {self.chain}",
            f"  last potency  {potency}",
            f"  final trust   {self.final_trust_level}",
            f"  ledger        {self.ledger_path}",
        ]


def run_source(
    source: SensorSource,
    label: str,
    product: ProductConfig,
    box: BoxConfig,
    signer: Signer,
    device_id: str = DEFAULT_DEVICE_ID,
    runs_dir: Path | str | None = None,
    run_id: str | None = None,
) -> RunSummary:
    """Run a source to its end through the real pipeline, anchor, read back and verify."""
    assessor = TrustAssessor(product, TamperMonitor.from_defaults(product, box))
    ledger = Ledger.create(run_id or new_run_id(label), runs_dir)
    verdicts: Counter[str] = Counter()
    last_potency: float | None = None
    last_trust: str | None = None
    try:
        writer = ChainWriter(device_id, signer, ledger)
        source.start()
        try:
            while (reading := source.read()) is not None:
                assessment, potency, _ = assessor.update(reading)
                writer.append(
                    record_from_pipeline(device_id, writer.next_seq, reading, potency, assessment)
                )
                verdicts[assessment.verdict] += 1
                last_potency, last_trust = potency.potency, assessment.trust_level
        finally:
            source.close()
        if writer.next_seq > 0:
            writer.anchor()
        entries = ledger.read_entries()
        result = verify_chain(entries, signer.public_key_bytes, ledger.latest_anchor(), device_id)
        pub = ledger.path.with_suffix(".pubkey")
        pub.write_text(signer.public_key_bytes.hex() + "\n", encoding="utf-8", newline="\n")
        return RunSummary(
            label, ledger.path, signer.key_id, len(entries), dict(verdicts), result,
            last_potency, last_trust,
        )  # fmt: skip
    finally:
        ledger.close()


def run_recording(
    path: Path | str,
    product: ProductConfig,
    box: BoxConfig,
    signer: Signer,
    device_id: str = DEFAULT_DEVICE_ID,
    runs_dir: Path | str | None = None,
    run_id: str | None = None,
) -> RunSummary:
    recording = Path(path)
    return run_source(
        RecordedSource(recording), recording.stem, product, box, signer, device_id, runs_dir, run_id
    )
