"""Ed25519 signing keys and key files (Phase 4).

The private key lives OUTSIDE the repository, at %LOCALAPPDATA%\\potencyguard\\keys\\ on Windows
(created on first use). It is never written into the repo, tests, logs or reports; only the key id
(the first 16 hex characters of SHA-256 of the public key) is ever printed. Tests use a TEST ONLY
key derived from a fixed seed stored in shared/test-vectors/chain_vectors.json.

Signing protects a record after the device signs it. It does not stop a lie at the sensor before
signing (the device would sign the lie).
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

KEY_FILE_NAME = "device_ed25519.key"
PUBLIC_KEY_LEN = 32
SIGNATURE_LEN = 64


def default_key_dir() -> Path:
    """%LOCALAPPDATA%\\potencyguard\\keys (outside the repo); a home-directory path elsewhere."""
    base = os.environ.get("LOCALAPPDATA")
    root = Path(base) if base else Path.home() / ".local" / "share"
    return root / "potencyguard" / "keys"


def key_id_of(public_key_bytes: bytes) -> str:
    return hashlib.sha256(public_key_bytes).hexdigest()[:16]


class Signer:
    """A private key that can sign. `repr` never shows key material."""

    def __init__(self, private_key: Ed25519PrivateKey) -> None:
        self._key = private_key
        self.public_key_bytes: bytes = private_key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        self.key_id: str = key_id_of(self.public_key_bytes)

    @classmethod
    def from_seed(cls, seed: bytes) -> Signer:
        """Deterministic key from a 32-byte seed (TEST ONLY use)."""
        if len(seed) != 32:
            raise ValueError("an Ed25519 seed is 32 bytes")
        return cls(Ed25519PrivateKey.from_private_bytes(seed))

    @classmethod
    def generate(cls) -> Signer:
        return cls(Ed25519PrivateKey.generate())

    def sign(self, message: bytes) -> bytes:
        return self._key.sign(message)

    def __repr__(self) -> str:
        return f"Signer(key_id={self.key_id})"


def load_or_create_signer(key_dir: Path | str | None = None) -> Signer:
    """Load the device key from key_dir, or generate and store it there on first use."""
    folder = Path(key_dir) if key_dir is not None else default_key_dir()
    path = folder / KEY_FILE_NAME
    if path.exists():
        key = serialization.load_pem_private_key(path.read_bytes(), password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise ValueError(f"{path} is not an Ed25519 key")
        return Signer(key)
    folder.mkdir(parents=True, exist_ok=True)
    signer = Signer.generate()
    pem = signer._key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    with open(path, "xb") as handle:
        handle.write(pem)
    return signer


def verify_signature(public_key_bytes: bytes, signature: bytes, message: bytes) -> bool:
    """True only for a valid signature. Never raises: bad input is simply not valid."""
    try:
        if len(public_key_bytes) != PUBLIC_KEY_LEN or len(signature) != SIGNATURE_LEN:
            return False
        Ed25519PublicKey.from_public_bytes(public_key_bytes).verify(signature, message)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False
