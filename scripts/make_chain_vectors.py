"""Write shared/test-vectors/chain_vectors.json (Phase 4). TEST ONLY key; deterministic.

Run from the repo root:  python scripts/make_chain_vectors.py        (writes the file)
                         python scripts/make_chain_vectors.py --check (compares, exit 1 if different)

The file lets another implementation (for example TypeScript) check its canonical bytes,
Ed25519 signatures (Ed25519 is deterministic) and hash chain against this one.
Signing protects records after signing; it does not stop a lie at the sensor before signing.
"""
# ruff: noqa: E501  (long literal lines in vectors and messages)

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from edge.chain import Signer, build_record, canonical_bytes, genesis_hash, link_hash  # noqa: E402
from edge.chain.canonical import SCHEMA_VERSION, UNIT_E4, UNIT_E6, UNIT_E9, UNIT_MS, to_scaled_int  # noqa: E402
from edge.chain.chain import make_anchor  # noqa: E402

PATH = REPO_ROOT / "shared" / "test-vectors" / "chain_vectors.json"
SEED_TEXT = b"potencyguard TEST ONLY chain vector seed v1"
DEVICE_ID = "pg-test-001"

ROUNDING_CASES = [
    (0.00005, UNIT_E4), (-0.00005, UNIT_E4), (0.00004, UNIT_E4), (5.00005, UNIT_E4),
    (-5.00005, UNIT_E4), (0.1 + 0.2, UNIT_E4), (4.2265, UNIT_E4), (2.5e-9, UNIT_E9),
    (0.9999999995, UNIT_E9), (0.0005, UNIT_MS), (600.0, UNIT_MS), (1.2345675, UNIT_E6),
    (-0.0, UNIT_E4), (0, UNIT_E4),
]  # fmt: skip

RECORD_INPUTS = [
    dict(t_s=0.0, source="sim", temp_c=5.0123, rh_pct=45.2, shock_g=0.0123, ambient_c=21.5, cooling_duty=0.0,
         potency=1.0, shelf_life_used_fraction=0.0, tau_eq_h=0.0, verdict="ok", trust_level="trusted",
         bound_tau_eq_h=None, bound_low_tau_eq_h=None),
    dict(t_s=600.0, source="sim", temp_c=5.0456, rh_pct=45.0, shock_g=0.0, ambient_c=22.0, cooling_duty=0.5,
         potency=0.999999912, shelf_life_used_fraction=0.000000879, tau_eq_h=0.077005, verdict="ok",
         trust_level="trusted", bound_tau_eq_h=None, bound_low_tau_eq_h=None),
    dict(t_s=1200.0, source="sim", temp_c=-0.5, rh_pct=44.8, shock_g=1.5, ambient_c=None, cooling_duty=None,
         potency=0.9999, shelf_life_used_fraction=0.00123456789, tau_eq_h=10.8, verdict="thermal_anomaly",
         trust_level="low_confidence", bound_tau_eq_h=None, bound_low_tau_eq_h=None),
    dict(t_s=1800.0, source="sim", temp_c=12.3456, rh_pct=46.0, shock_g=0.0, ambient_c=30.0, cooling_duty=1.0,
         potency=0.95, shelf_life_used_fraction=0.5, tau_eq_h=4380.123456, verdict="suspected_falsification",
         trust_level="untrusted", bound_tau_eq_h=4400.5, bound_low_tau_eq_h=4381.25),
]  # fmt: skip


def build() -> dict:
    signer = Signer.from_seed(hashlib.sha256(SEED_TEXT).digest())
    previous = genesis_hash(DEVICE_ID)
    records = []
    for seq, inputs in enumerate(RECORD_INPUTS):
        record = build_record(device_id=DEVICE_ID, seq=seq, **inputs)
        canonical = canonical_bytes(record)
        signature = signer.sign(canonical)
        digest = link_hash(previous, canonical, signature)
        records.append(
            {
                "inputs": inputs,
                "record": record,
                "canonical_utf8": canonical.decode("utf-8"),
                "canonical_hex": canonical.hex(),
                "signature_hex": signature.hex(),
                "hash_hex": digest.hex(),
            }
        )
        previous = digest
    anchor = make_anchor(signer, DEVICE_ID, len(records) - 1, previous)
    return {
        "WARNING": "TEST ONLY. The seed below is public and must never be used for a real device.",
        "description": "Vectors for the Phase 4 signed record format; see docs/01-architecture/signed-record-format.md",
        "schema": SCHEMA_VERSION,
        "test_only_seed_text": SEED_TEXT.decode("ascii"),
        "test_only_seed_sha256_hex": hashlib.sha256(SEED_TEXT).hexdigest(),
        "device_id": DEVICE_ID,
        "public_key_hex": signer.public_key_bytes.hex(),
        "key_id": signer.key_id,
        "genesis_prefix": "potencyguard/genesis/v1",
        "genesis_hash_hex": genesis_hash(DEVICE_ID).hex(),
        "units": {"t_ms": UNIT_MS, "e4": UNIT_E4, "e9": UNIT_E9, "e6_hours": UNIT_E6},
        "rounding_cases": [
            {"value": v, "unit": u, "expected": to_scaled_int(v, u)} for v, u in ROUNDING_CASES
        ],
        "records": records,
        "anchor": {
            "seq": anchor.seq,
            "head_hex": anchor.head.hex(),
            "statement_utf8": anchor.statement.decode("utf-8"),
            "signature_hex": anchor.signature.hex(),
        },
    }


def text() -> str:
    return json.dumps(build(), indent=1, sort_keys=True) + "\n"


def main(argv: list[str]) -> int:
    expected = text()
    if "--check" in argv:
        same = PATH.exists() and PATH.read_text(encoding="utf-8") == expected
        print("chain vectors: " + ("identical" if same else "DIFFERENT from the file"))
        return 0 if same else 1
    with open(PATH, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(expected)
    print(f"wrote {PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
