# scripts

- What lives here: helper commands: run checks now, demo and tamper tools later.
- `run_checks.py` runs ruff, the format check, pytest and the dashboard build and tests.
- `make_test_vectors.py` regenerates `shared/test-vectors/potency_vectors.json` from the Python potency code.
- Finding things: each script has a one-line description at the top.
- `constants_study.py` is a read-only study (Phase 2C). It runs the eight golden recordings through the potency tracker with five illustrative sets of product constants, built in memory, and writes `docs/02-phase-reports/phase-02c-constants-study.md` and `data/generated/constants_study.json` (git-ignored). It never changes the real configuration.
