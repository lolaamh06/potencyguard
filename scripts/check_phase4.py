"""Phase 4 check (part of scripts/run_checks.py): chain vectors, golden files, end-to-end signing.

1. shared/test-vectors/chain_vectors.json is exactly what scripts/make_chain_vectors.py produces.
2. The 9 golden recordings and the existing potency vector files are byte-identical to the SHA-256
   hashes recorded in shared/golden_sha256.json (taken before Phase 4).
3. A recording is run through the real pipeline with a throw-away key outside the repo, the ledger
   verifies, an edited copy is detected, and a truncated copy passes without an anchor.

Signatures and the chain protect records after signing; they do not stop a lie at the sensor.
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import make_chain_vectors  # noqa: E402
import tamper_demo  # noqa: E402

from edge.chain import Ledger, Signer, verify_chain  # noqa: E402
from edge.runner import run_recording  # noqa: E402
from shared.config import load_box_config, load_product_config  # noqa: E402

GOLDEN = REPO_ROOT / "shared" / "golden_sha256.json"


def main() -> int:
    problems: list[str] = []
    if make_chain_vectors.main(["--check"]) != 0:
        problems.append("chain_vectors.json differs from the generator")
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))["sha256"]
    for relative, digest in expected.items():
        actual = hashlib.sha256((REPO_ROOT / relative).read_bytes()).hexdigest().upper()
        if actual != digest:
            problems.append(f"{relative} changed")
    with tempfile.TemporaryDirectory(prefix="pg_phase4_") as tmp:
        signer = Signer.generate()  # throw-away, never stored
        summary = run_recording(
            REPO_ROOT / "data" / "recordings" / "baseline_ok.jsonl",
            load_product_config(),
            load_box_config(),
            signer,
            runs_dir=tmp,
        )
        if not summary.chain.ok or summary.entries < 10:
            problems.append(f"end-to-end chain not ok: {summary.chain}")
        with Ledger.open(summary.ledger_path) as ledger:
            entries, anchor = ledger.read_entries(), ledger.latest_anchor()
        out = Path(tmp)
        for action, must_fail in (("edit", True), ("truncate", False)):
            copy = tamper_demo.make_copy(summary.ledger_path, out, action)
            tamper_demo.apply_action(copy, action, None, 3)
            with Ledger.open(copy) as ledger:
                result = verify_chain(ledger.read_entries(), signer.public_key_bytes)
            if result.ok == must_fail:
                problems.append(f"tamper action {action} gave {result}")
        if not verify_chain(entries, signer.public_key_bytes, anchor).ok:
            problems.append("original ledger does not verify")
    for problem in problems:
        print(f"FAIL: {problem}")
    if not problems:
        print("phase 4 check: vectors identical, golden files identical, signing end to end ok")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
