# scripts

- What lives here: helper commands: run checks now, demo and tamper tools later.
- `run_checks.py` runs ruff, the format check, pytest and the dashboard build and tests.
- `make_test_vectors.py` regenerates `shared/test-vectors/potency_vectors.json` from the Python potency code.
- Finding things: each script has a one-line description at the top.
- `constants_study.py` is a read-only study (Phase 2C). It runs the eight golden recordings through the potency tracker with five illustrative sets of product constants, built in memory, and writes `docs/02-phase-reports/phase-02c-constants-study.md` and `data/generated/constants_study.json` (git-ignored). It never changes the real configuration.
- `make_test_vectors.py` now writes two files, one per product profile (see `shared/test-vectors/README.md`).
- `evaluate_detectors.py` measures the tamper detectors (Phase 3): a CUSUM settings sweep on training seeds, final scoring on test seeds and a mismatch run against boxes that differ from the calibration. It writes `docs/02-phase-reports/phase-03-evaluation.md` and `data/generated/evaluation.json`. A full run takes about 4 to 5 minutes; `--quick` (5 seeds per family) takes about 10 seconds and is what the tests use.

## evaluate_detectors.py (Phases 3 and 3B)

`python scripts/evaluate_detectors.py [--quick] [--sweep-only] [--ood-sweep-only]` measures the detectors on seeded runs and writes `docs/02-phase-reports/phase-03b-evaluation.md` and `data/generated/evaluation_3b.json` (git-ignored). Seed blocks: calibration 9001 to 9010 (fit the twin only), training 10001 to 10100 (all tuning), test 20001 to 20200 (final numbers, used once). Phase 3B adds the drift and mimic lie families, the twin-out-of-date threshold sweep (training seeds only), the before/after comparison with the Phase 3 behaviour, and the worst-case bound validity table. `--quick` uses 5 seeds per family (for the tests). The Phase 3 report `phase-03-evaluation.md` is kept as it was.

## Phase 3C scripts

- `python scripts/evaluate_3c.py [--quick] [--workers N]` writes `docs/02-phase-reports/phase-03c-evaluation.md` and `data/generated/evaluation_3c.json`. Independent runs are spread over N worker processes (default half the CPU count); results are put back in a fixed order, so the numbers do not depend on N. `--sf-sweep-only` and `--fa-only` run the bound safety-factor sweep and the CUSUM false-alarm study alone. Seed blocks: final 50001-50200 (mismatch and two-node rows use the first 100), per-box calibration 9101-9110, 9201-9210, 9301-9310, false-alarm study 60001-61000; 20001-20200, 30001-30200 and 40001-40200 are development blocks. `--quick` uses 40001-40005 and never the final block.
- `python scripts/calibrate_variants.py` fits the three variant twins and writes `config/twin_calibrated_variants.yaml`.

## Phase 4 scripts

- `python scripts/tamper_demo.py LEDGER ACTION [--entry N] [--count N] [--public-key FILE] [--out-dir DIR]` with ACTION one of `edit`, `delete`, `reorder`, `replace-signature`, `resign`, `truncate`, `all`: changes a COPY of a ledger and prints what `verify_chain` reports. Tail truncation without an anchor passes; that is shown, not hidden.
- `python scripts/make_chain_vectors.py [--check]` writes or checks `shared/test-vectors/chain_vectors.json` (TEST ONLY key).
- `python scripts/check_phase4.py` is the sixth check in `scripts/run_checks.py`.

## Phase 5 scripts

- `python scripts/evaluate_planner.py` writes `docs/02-phase-reports/phase-05-evaluation.md`: the oracle, the six demo scenarios, the effect of two modelling fixes, a V and beta sensitivity table and seed stability. Illustrative placeholders; not validated against real decisions.
- `python scripts/check_phase5.py` is the seventh check in `scripts/run_checks.py` (oracle exact, same seed same numbers, untrusted never auto-approved, the decision log verifies and an edited copy is detected).

## Phase 6 script

- `python scripts/check_phase6.py` is the eighth check in `scripts/run_checks.py`: a good ledger is registered, verified, decided and auto-approved through the API (in process), a tampered copy is rejected and quarantined, the database refuses a DELETE, the sandbox adapter is a stub, and the golden files are unchanged. `scripts/tamper_demo.py` is reused by `python -m backend replay --tamper`.

## Phase F2 scripts

- `python scripts/export_replay.py [--out DIR]` writes replay files for the five featured scenarios (baseline_ok, door_open_excursion, reefer_failure, spoof_attempt, hidden_spoilage) and an index to `dashboard/public/replay/`. Read-only use of the existing pipeline; deterministic; TEST-ONLY signing key derived inside the script. Tested by `tests/test_export_replay.py`.
- `python scripts/make_land_mask.py [--width N]` downloads Natural Earth 110m land once (public domain), makes the globe's land mask PNG and its README in `dashboard/public/globe/`. Needs network; the source download is not kept. Standard library only.

## Phase F3 scripts

- `scripts/export_replay.py` now takes each scenario's decision from the Phase 6 backend itself (in process), so the exported route equals `python -m backend replay --all`.
- `python scripts/export_story.py [--out DIR]` writes the Story data: `dashboard/src/data/bundled/chapter1.json` (reuses the F1 generator), `dashboard/public/story/chapter5.json` (5,000 seeded outcomes per action and the precomputed alpha table) and `chapter6.json` (approval card content and the real edit-and-verify). Tested by `tests/test_export_story.py`.

## Phase F4 changes

- `scripts/export_replay.py` now also writes, per scenario: `tamper` (the ledger length, the real `verify_chain` result for edits at five positions, and the truncation with and without the anchor, all on ledger copies), `decision.worst_case` (a bound, not an estimate), `decision.recomputed` (the backend's own recomputation), `provenance` and `meta.cusum_h`. Tested by `tests/test_export_tamper.py` (the exported results equal a fresh `verify_chain` on the same edits).
