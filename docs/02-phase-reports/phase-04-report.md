# Phase 4: signed records, hash chain, ledger, edge runner, tamper demo: Report

Date: 2026-10-21. Git commit hash and tag: none yet (the team lead commits). Simulation results on a synthetic box. Not real-world evidence.

## 1. What I was asked to do

Sign every sensor reading with Ed25519, link the signed records in a hash chain, store them in an append-only ledger, run the existing pipeline into that ledger (`python -m edge run`), and show what a verifier reports when a copy of the ledger is tampered with.

## 2. What I built

- `edge/chain/canonical.py`: the integer-only canonical record (schema `pg-record/1`).
- `edge/chain/crypto.py`: Ed25519 signer, key file outside the repo, `verify_signature` that never raises.
- `edge/chain/chain.py`: genesis hash, chain hash, `ChainWriter`, signed anchor, `verify_chain`.
- `edge/chain/ledger.py`: append-only SQLite ledger (one file per run id, two tables, triggers refuse UPDATE and DELETE).
- `edge/runner.py` and `python -m edge run --recording FILE | --all`: SensorSource, TrustAssessor (which wraps the existing PotencyTracker and TamperMonitor), ChainWriter, Ledger, final anchor, read back and verify, short summary.
- `edge/pi_source.py`: `PiSource`, a stub that raises `NotImplementedError` with a clear message.
- `scripts/tamper_demo.py`, `scripts/make_chain_vectors.py`, `scripts/check_phase4.py` (a sixth check in `scripts/run_checks.py`).
- `shared/test-vectors/chain_vectors.json` (TEST ONLY key) and `shared/golden_sha256.json` (hashes of the 9 golden recordings and the two potency vector files, taken before Phase 4).
- Docs: `docs/01-architecture/signed-record-format.md` (the exact rules), `docs/03-decisions/decision-0008-canonical-record-format.md`, this report, the prompt archive, READMEs.
- Dependency: `cryptography` 50.0.2 (pulls `cffi` 2.1.1 and `pycparser` 3.11), pinned in `requirements-dev.txt` and `pyproject.toml`. No other package; no `npm` command was run.

## 3. How to run it

```
$py = "$env:LOCALAPPDATA\potencyguard\venv\Scripts\python.exe"
& $py -m edge run --recording data/recordings/hidden_spoilage.jsonl
& $py -m edge run --all
# the run prints the ledger path, e.g. data\runs\20261021T...Z_hidden_spoilage.sqlite
& $py scripts\tamper_demo.py data\runs\<that file>.sqlite all
& $py scripts\tamper_demo.py data\runs\<that file>.sqlite truncate --count 5
```

The key is created on first use in `%LOCALAPPDATA%\potencyguard\keys\` (outside the repo). `--key-dir` and `--ledger-dir` override the folders; ledgers go to `data\runs\` (git-ignored). The public key is written next to each ledger as `<run>.pubkey` so the demo can verify; a real verifier must obtain the public key elsewhere.

## 4. How to check it works

`& $py scripts\run_checks.py` prints `Summary: 6 passed, 0 failed` (the sixth check is the Phase 4 check: chain vectors identical to their generator, the 9 golden recordings and the potency vectors identical to `shared/golden_sha256.json`, an end-to-end signing run with a throw-away key, an edited copy detected and a truncated copy passing without an anchor).

## 5. Test results

Baseline before the phase: 5 of 5 checks, 587 tests. Now: 6 of 6 checks, **645 tests** (58 new, all in `tests/test_chain.py`). They cover: canonical determinism, rounding rules (ties, negatives, 0.1 + 0.2), rejection of floats, NaN, booleans, extra fields and non-canonical bytes; the shared vectors reproduced from the TEST ONLY seed; sign and verify round trip, wrong key, garbage signatures; every tamper action detected at the first broken entry (edit, delete, reorder, replaced signature, wrong stored hash, impersonation with a rebuilt chain, another device); tail truncation asserted as NOT detected without an anchor and detected with one; forged, foreign and mismatched anchors; malformed input never raising; the ledger being append-only (no mutation functions, the database refuses UPDATE and DELETE, a fresh file per run id); the signed series equal to `python -m edge twin` (potency, shelf life, equivalent time, verdict, trust level and both bounds, for 5 recordings: baseline_ok, hidden_spoilage, spoof_attempt, reefer_failure, sensor_glitch); the key outside the repo and no key-like file or PEM block anywhere in the repo; `.gitignore` coverage; the `run` command and the tamper demo; the PiSource stub.

**Tests changed:** none. No existing test, detector, potency maths or twin file was edited.

## 6. What is real and what is simulated

The signing, chain and ledger are real code. The readings come from simulated recordings; `source` stays "sim". No hardware is attached (`PiSource` is a stub).

## 7. Decisions and PROPOSE items

Decisions: see decision 0008 (integers in fixed units, signature over the canonical bytes, chain over the signature, optional signed anchor, SQLite triggers). I used number 0008 because 0007 was reserved in an earlier prompt; rename if needed.

I chose (please confirm): the signature covers the canonical bytes only (order is bound by `seq` in the record and by the chain hash); the first entry has `seq` 0; the public key sits beside the ledger as a convenience file.

PROPOSE: **P1 anchors during a run.** Today one anchor is signed at the end of a run. (a) keep; (b) anchor every N entries; pro: a stolen or cut ledger shows loss since the last anchor; con: more writes. Recommendation: (b) when a real device runs for days. **P2 key storage.** The key file is unencrypted in the user folder (outside the repo). (a) keep for the demo; (b) use an OS key store or hardware key later.

## 8. Assumptions and unverified claims introduced

Placeholders, not sourced [SOURCE NEEDED]: nothing numeric was added except the units (1e-4, 1e-9, 1e-6), which are format choices, not claims about the world. The device id `pg-sim-001` is a demo name.

## 9. Problems, surprises, omissions

- Surprise: I had assumed that the tamper demo could use the ledger module to edit a copy; the append-only triggers (correctly) refuse that, so the demo drops them in its own copy to play someone who uses other tools.
- The amendment A19 was not added: the brief (sections on signing and canonical serialisation) already asks for exactly this, and nothing in it changed. The wording about what signing does not cover is already in A18.
- Omitted: a `--source` switch between recording, simulator and Pi in the command line (only `--recording`/`--all` exist; `PiSource` is a stub that cannot read anything). Anchors only at the end of a run (P1). The ledger does not store the run's scenario header; the record carries `device_id`, `seq` and `t_ms` only. No field was omitted from the record: every field named in the prompt exists in the code.
- Not done: a TypeScript implementation (the vectors are there to check one later); no frontend change; `dashboard/` untouched.

## 10. What the numbers show (example run)

`hidden_spoilage.jsonl`: 577 signed entries, verdicts ok 102, sensor_glitch 1, suspected_falsification 454, thermal_anomaly 20; chain OK with the anchor checked; final trust level untrusted. Tamper demo on a copy of that ledger: edit, replaced signature: broken at entry 288 (bad_signature); delete, reorder: broken at entry 288 (bad_sequence); re-signed with a different key: broken at entry 0 (bad_signature, key id differs); truncating the last 5 entries: chain OK without an anchor, broken (truncated) with the anchor.

## 11. Can say / must not say (slides)

Can say (simulation, synthetic data):
1. Every reading is signed with Ed25519 and linked into a SHA-256 hash chain, stored in an append-only ledger.
2. The verifier names the first broken entry and why (58 tests, 5 recordings, 9 recordings run end to end).
3. Editing a value, deleting or reordering entries, replacing a signature or re-signing with another key is found by the verifier.
4. The signed potency and verdict series equal what the existing pipeline computes.
5. The record format is integers only, so another language can reproduce the bytes; shared vectors are provided.
6. The signing key stays outside the repository.

Must NOT say: that signatures or the chain stop a false sensor value (the device signs what the sensor says); that the mimic liar is covered by Phase 4; that removing the end of a ledger is always detected (it is not, without an anchor); that the ledger file cannot be edited (it can; the edit is detected); any claim of absolute security; that a real Raspberry Pi or SAP system is connected; that these results describe real shipments.

## 12. Open questions for the decision-maker

1. Decision number 0008 instead of 0007: is 0007 the intended slot?
2. Anchor every N entries during a run (P1)?
3. Should the verifier also be given the device's public key through a registry (out-of-band), and where would that live (Phase 5 backend)?
4. A `--source` option for the runner (recording, simulator, Pi) now, or when the backend needs it?

## 13. Suggested next phase (not started)

The backend that receives ledgers and verifies them against a registered public key, then the dashboard's verify and tamper buttons. Sensor-level protection (attested sensor, a second sensor, GPS and carrier records) is separate work.
