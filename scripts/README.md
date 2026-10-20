# scripts

- What lives here: helper commands: run checks now, demo and tamper tools later.
- `run_checks.py` runs ruff, the format check, pytest and the dashboard build and tests.
- `make_test_vectors.py` regenerates `shared/test-vectors/potency_vectors.json` from the Python potency code.
- Finding things: each script has a one-line description at the top.
- `constants_study.py` is a read-only study (Phase 2C). It runs the eight golden recordings through the potency tracker with five illustrative sets of product constants, built in memory, and writes `docs/02-phase-reports/phase-02c-constants-study.md` and `data/generated/constants_study.json` (git-ignored). It never changes the real configuration.
- `make_test_vectors.py` now writes two files, one per product profile (see `shared/test-vectors/README.md`).
- `evaluate_detectors.py` measures the tamper detectors (Phase 3): a CUSUM settings sweep on training seeds, final scoring on test seeds and a mismatch run against boxes that differ from the calibration. It writes `docs/02-phase-reports/phase-03-evaluation.md` and `data/generated/evaluation.json`. A full run takes about 4 to 5 minutes; `--quick` (5 seeds per family) takes about 10 seconds and is what the tests use.
