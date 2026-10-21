# Phase 4 prompt (archived verbatim)

PHASE 4: SIGNED RECORDS, HASH CHAIN, LEDGER, EDGE RUNNER, TAMPER DEMO

READ FIRST. Assume nothing. Read these before doing anything: docs/00-project-brief/master-brief.md (all amendments, especially A18), docs/02-phase-reports/ (the Phase 3C report), edge/assessment.py, edge/potency.py, edge/tamper_monitor.py, edge/sensor_source.py, edge/recorded_source.py, edge/sensor_reading.py, shared/config.py, and scripts/run_checks.py. Write down what the interfaces actually are before designing.

GIT RULES (absolute). You must NEVER run git add, git commit, git tag or git push. Read-only git (status, diff, log) is fine. At the end, print ONE block of explicit-path git add commands and ONE git commit command. No co-author trailers in the message. First check git status. If there are uncommitted changes from earlier phases, stop and tell me.

WHAT SIGNING DOES AND DOES NOT DO (put this wording in the docs and the code comments). Signatures and the hash chain protect records AFTER they are signed. They detect edits, deletions, reordering and impersonation by someone without the key. They do NOT stop a lie at the sensor before the device signs it: if the sensor input is false, the device signs the false value. A sensor-level mimic liar needs attested or redundant sensors, or out-of-band data (GPS, carrier records). Do not claim Phase 4 covers that. Do not use the words "unhackable", "tamper-proof" or "first/unique/novel". Do not state any external statistic (write [SOURCE NEEDED] if one seems needed).

STEP 0. Preflight. Run git status, then scripts/run_checks.py with the venv python (& "$env:LOCALAPPDATA\potencyguard\venv\Scripts\python.exe"). Expect 5 of 5 checks and 587 tests. Report the baseline. If it fails, stop.

STEP 1. Dependency. The only new package allowed is cryptography. Install it into the venv with pip, pin the exact installed version in requirements*.txt (or the repo's dependency file), and report the version. Do NOT run npm install. Do not add any other package. If Ed25519 is not available, stop and report.

STEP 2. Canonical record. Create edge/chain/ with a language-neutral canonical serialisation, integers only, no floats:

t in milliseconds (int); temperature, humidity, shock, ambient and cooling duty in units of 1e-4 (rounded half away from zero, defined explicitly); potency and shelf_life_used_fraction in 1e-9; tau_eq_h and the bounds in 1e-6 h.
Fields: device_id, seq, t_ms, source, temp, rh, shock, ambient_c, cooling_duty, potency, shelf_life_used_fraction, tau_eq_h, verdict, trust_level, bound_tau_eq_h (the HIGH bound), bound_low_tau_eq_h (the low bound, null allowed), plus a schema version string. Use the real names from the code; if a field does not exist in the current assessment, report it and ask nothing: omit it and list it.
Canonical bytes = UTF-8 JSON with sorted keys, no whitespace, integers/strings/null only.
Document the exact rules in docs/ so another language can reproduce them.

STEP 3. Signing and chain.

Ed25519 via cryptography. Genesis hash = SHA-256(b"potencyguard/genesis/v1" || device_id bytes).
Chain: h_n = SHA-256(h_{n-1} || canonical_bytes_n || signature_n). Each stored entry holds the canonical record, the signature, h_n, and the public-key id.
verify_chain(entries, public_key) returns ok, or the index of the FIRST broken entry and the reason (bad signature, bad hash link, bad sequence, malformed). Verify must never raise on corrupt input; it reports.
Optional anchor: a small signed "head" statement (seq, h_n) so tail truncation can be detected when an anchor exists. State plainly that without an anchor, truncating the tail cannot be detected.
Key handling: the private key lives OUTSIDE the repo at %LOCALAPPDATA%\potencyguard\keys\ (create if missing, generated on first use). Never write a private key into the repo, tests, logs or reports. .gitignore must cover any key-looking files and data/runs/. Tests use a TEST-ONLY key derived from a fixed seed stored in the test vectors file, labelled TEST ONLY.

STEP 4. Ledger. SQLite under data/runs/ (git-ignored), append-only API (no update/delete functions in the module), one table for entries and one for anchors, WAL mode is fine. Reading returns entries ordered by seq. A fresh run creates a new ledger file named by run id.

STEP 5. Edge runner. Pipeline: SensorSource → PotencyTracker → TamperMonitor → TrustAssessor → ChainWriter → Ledger. Provide python -m edge run --recording FILE (and --all) that replays a recording through the real pipeline and writes a ledger plus a final anchor, then verifies it and prints a short summary (entries, verdict counts, chain ok, last potency, final trust level). Add a PiSource stub in edge/ that raises NotImplementedError with a clear message. Do not change the behaviour of existing detectors, potency math or twin; the signed values must equal what the existing pipeline already computes. Add a test proving the runner's potency/verdict series equals the existing python -m edge twin outputs for at least three recordings.

STEP 6. Tamper demo tools: scripts/tamper_demo.py taking a ledger and an action: edit one value, delete one entry, reorder two entries, replace the signature, re-sign with a DIFFERENT key (impersonation), truncate the tail (with and without an anchor). Each action works on a COPY and prints what verify_chain reports. Show honestly that tail truncation without an anchor passes.

STEP 7. Shared vectors. Write shared/test-vectors/chain_vectors.json: TEST-ONLY seed, device_id, a short list of records, canonical bytes (hex), signatures (hex), hashes (hex), and the public key, so a TypeScript implementation can be checked later. Do not modify potency_vectors*.json or any golden recording. Prove with a check (hash compare) that the 9 golden recordings and existing vectors are byte-identical to before.

STEP 8. Tests. At minimum: canonical determinism and rounding rules; sign/verify round trip; every tamper action in Step 6 detected (except no-anchor truncation, which is asserted as undetected); wrong-key detection; malformed input never raises; ledger append-only (no mutation API); runner equals existing pipeline; key never inside the repo (scan the repo for the key file and for PEM headers). Add a Phase 4 check to scripts/run_checks.py. Run the full suite and report totals.

STEP 9. Docs. Write docs/02-phase-reports/phase-04-report.md covering what was built, exact serialisation rules, what signing protects and what it does NOT (include the sensor-level lie wording above), the no-anchor truncation limit, tests, anything omitted, and a "can say / must not say" list for slides. Add amendment A19 to the master brief only if something in the brief changed. Archive this prompt under docs/06-prompts/. Add a decision note under docs/03-decisions/ for the canonical format.

STEP 10. Final report to me in simple words: what was built, the baseline vs final test counts, the cryptography version, how to run the runner and the tamper demo (exact PowerShell commands), anything that surprised you, anything you did not do, and the single commit block (explicit paths, no wildcards that could include keys or data/runs, no trailers). Then stop. Do not start Phase 5.
