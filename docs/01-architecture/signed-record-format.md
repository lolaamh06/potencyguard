# Signed record format (schema `pg-record/1`)

Status: implemented in Phase 4 (`edge/chain/`). Another language can reproduce every byte from this page and from `shared/test-vectors/chain_vectors.json`.

## What signing does and does not do

Signatures and the hash chain protect records AFTER they are signed. They detect edits, deletions, reordering and impersonation by someone without the key. They do NOT stop a lie at the sensor before the device signs it: if the sensor input is false, the device signs the false value. A sensor-level mimic liar needs attested or redundant sensors, or out-of-band data (GPS, carrier records). Without an anchor, truncating the tail of a ledger cannot be detected.

## 1. The record

One record per sensor reading. Exactly these fields (no more, no fewer):

| field | type | meaning | unit of the integer |
|---|---|---|---|
| `schema` | string | `"pg-record/1"` | |
| `device_id` | string | non-empty | |
| `seq` | integer | 0, 1, 2, ... without gaps | |
| `t_ms` | integer | time since the start of the run | milliseconds |
| `source` | string | feed type, `"sim"` for the simulator | |
| `temp` | integer | box temperature as reported | 1e-4 degree C |
| `rh` | integer | relative humidity | 1e-4 percent |
| `shock` | integer | shock | 1e-4 g |
| `ambient_c` | integer or null | measured temperature around the box | 1e-4 degree C |
| `cooling_duty` | integer or null | compressor duty of the last interval (0 to 1) | 1e-4 |
| `potency` | integer | potency (a model output) | 1e-9 |
| `shelf_life_used_fraction` | integer | share of shelf life used | 1e-9 |
| `tau_eq_h` | integer | equivalent reference time | 1e-6 hour |
| `verdict` | string | tamper monitor verdict (`ok`, `thermal_anomaly`, `suspected_falsification`, `sensor_glitch`, `twin_out_of_date`) | |
| `trust_level` | string | `trusted`, `low_confidence` or `untrusted` | |
| `bound_tau_eq_h` | integer or null | the HIGH worst-case bound on `tau_eq_h` (null unless untrusted) | 1e-6 hour |
| `bound_low_tau_eq_h` | integer or null | the low end (cooling worked fully); NOT a guarantee | 1e-6 hour |

Every field exists in the current code (`SensorReading`, `PotencyState`, `PotencyAssessment`); none was omitted. `bound_tau_eq_h` is the number a signed record carries as the safety limit.

## 2. Turning a real value into an integer

1. Take the shortest decimal text that round-trips the double (Python `repr(float(x))`; in JavaScript `String(x)` gives the same digits).
2. Multiply that decimal EXACTLY by the unit (a power of ten; use decimal arithmetic, not binary floating point).
3. Round to an integer, **half away from zero**: 2.5 becomes 3 and -2.5 becomes -3. Negative zero becomes 0.
4. The result must satisfy |n| <= 2^53 (so a JavaScript Number holds it exactly); otherwise the record is rejected.

Examples (unit 1e4): 0.00005 -> 1; -0.00005 -> -1; 0.00004 -> 0; 5.00005 -> 50001; 0.1 + 0.2 (= 0.30000000000000004) -> 3000. The vectors file lists more.

Times: `t_ms = scale(t_s, 1000)`. `null` stays `null` (only for the four nullable fields).

## 3. Canonical bytes

UTF-8 encoding of the JSON text with: keys sorted by Unicode code point, no whitespace anywhere, only integers (plain decimal, no leading zeros, no exponent), strings and `null`, no other JSON values. Strings are escaped as required by JSON and nothing else (non-ASCII characters are written as themselves). A reader must reject: a floating-point number, `NaN`, `Infinity`, booleans in integer fields, missing or extra fields, a wrong schema, and bytes that are valid JSON but are not byte-for-byte the canonical form.

## 4. Signature, genesis and chain

- Signature: Ed25519 (RFC 8032) over the canonical bytes of the record. Ed25519 is deterministic, so a vector can list the signature.
- Genesis hash: `SHA-256( b"potencyguard/genesis/v1" || UTF-8 bytes of device_id )`.
- Chain hash: `h_n = SHA-256( h_{n-1} || canonical_bytes_n || signature_n )`, with `h_{-1}` = the genesis hash. The three parts are concatenated as raw bytes (the signature is 64 bytes).
- A stored entry holds: seq, canonical bytes, signature, `h_n`, and the key id (the first 16 hex characters of SHA-256 of the 32-byte public key).

## 5. Anchor (optional)

A signed head statement: the canonical JSON `{"device_id":..., "head":"<hex of h_seq>", "schema":"pg-anchor/1", "seq":<n>}` (sorted keys, no whitespace), signed with the same key. If a verifier has an anchor, a ledger that no longer contains entry `seq` with hash `head` is reported (`truncated` or `anchor_mismatch`). An anchor only protects up to the entry it names; without one, removing entries from the END of a ledger leaves a shorter chain that still verifies.

## 6. Verifying

`verify_chain(entries, public_key, anchor=None, device_id=None)` checks entry 0, 1, 2, ... in this order and returns the FIRST broken entry and why: `malformed` (not canonical or wrong types), `bad_sequence` (record seq is not the position: a deletion or a reorder), `wrong_device`, `bad_signature` (also when the key id differs: impersonation), `bad_hash_link`; then the anchor: `bad_anchor`, `truncated`, `anchor_mismatch`. It never raises on corrupt input. The public key must reach the verifier by a route other than the ledger it checks.

## 7. Keys

The device private key is stored OUTSIDE the repository (`%LOCALAPPDATA%\potencyguard\keys\device_ed25519.key` on Windows, created on first use) and is never written to the repo, tests, logs or reports. Tests and the shared vectors use a TEST ONLY seed that is public by design.
