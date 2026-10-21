# Decision 0008: canonical record format for signed records

Status: implemented in Phase 4. (The number 0007 was left free because an earlier prompt reserved decision numbers; rename this file if 0007 is the intended slot.)

## Decision

Signed records are JSON made only of integers, strings and null, with sorted keys and no whitespace, signed with Ed25519 and linked by SHA-256 as described in `docs/01-architecture/signed-record-format.md`.

## Why integers in fixed units

The brief asked for "fixed number formatting" so that signatures verify identically on any machine. Floating-point text can differ between languages (digits, exponents, `-0`), and a single different digit changes the signature. Integers in a stated unit have one spelling. The units were chosen to keep more digits than the data carry: the simulator rounds readings to 4 decimals (1e-4), potency and shelf-life fractions get 1e-9, hours get 1e-6. Rounding is half away from zero on the exact decimal of the shortest round-trip text, which a TypeScript port can reproduce with decimal or big-integer arithmetic.

Limit: values are signed after rounding, so a verifier recomputing the potency from signed temperatures gets the same number only up to those units.

## Other choices

- The signature covers the canonical bytes; the chain hash binds order and the signature: `h_n = SHA-256(h_{n-1} || canonical_n || signature_n)`. Because the record contains `seq` and `device_id`, a record cannot be moved to another position or device unnoticed.
- The stored hash is recomputed by the verifier, not trusted.
- The anchor is optional and signed; it is the only protection against tail truncation, and it protects only up to the entry it names.
- The ledger is SQLite with triggers that refuse UPDATE and DELETE. That guards against mistakes in the program; against someone with file access the signatures and the chain are the protection.
- The public key is kept beside the ledger as a convenience (`.pubkey`) but a real verifier must obtain it elsewhere.
- The key lives outside the repo. New dependency: `cryptography` 50.0.2 (with `cffi` 2.1.1 and `pycparser` 3.11).

## What it does not do

Signatures and the hash chain protect records AFTER they are signed. They do not stop a lie at the sensor before the device signs it: the device would sign the lie. A sensor-level mimic liar needs attested or redundant sensors, or out-of-band data (GPS, carrier records).
