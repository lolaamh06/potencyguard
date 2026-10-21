"""Signed records, hash chain and ledger (Phase 4).

Signatures and the hash chain protect records AFTER they are signed. They detect edits, deletions,
reordering and impersonation by someone without the key. They do NOT stop a lie at the sensor
before the device signs it: if the sensor input is false, the device signs the false value.
"""

from edge.chain.canonical import (
    SCHEMA_VERSION,
    build_record,
    canonical_bytes,
    parse_canonical,
    to_scaled_int,
)
from edge.chain.chain import (
    Anchor,
    ChainWriter,
    Entry,
    VerifyResult,
    genesis_hash,
    link_hash,
    make_anchor,
    verify_chain,
)
from edge.chain.crypto import Signer, default_key_dir, load_or_create_signer, verify_signature
from edge.chain.ledger import Ledger, new_run_id

__all__ = [
    "SCHEMA_VERSION",
    "Anchor",
    "ChainWriter",
    "Entry",
    "Ledger",
    "Signer",
    "VerifyResult",
    "build_record",
    "canonical_bytes",
    "default_key_dir",
    "genesis_hash",
    "link_hash",
    "load_or_create_signer",
    "make_anchor",
    "new_run_id",
    "parse_canonical",
    "to_scaled_int",
    "verify_chain",
    "verify_signature",
]
