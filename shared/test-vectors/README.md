# test-vectors

- What lives here: JSON test cases that are the single source of truth for numeric tests in Python and TypeScript, so the two implementations are provably identical.
- Filled in by: Phase 2B (`potency_vectors.json`); the TypeScript mirror in Phase F2 must reproduce it.
- Finding things: each JSON file is one family of test cases.

## potency_vectors.json

Made by `python scripts/make_test_vectors.py` from the Python reference code in `edge/potency.py`. A test fails if the committed file differs from a fresh generation, so regenerate and commit it whenever the maths or the product constants change.

- `meta`: schema version, the constants used and the integration rule.
- `af_cases`: acceleration factor at ten temperatures.
- `tau_cases`: temperature profiles with the expected equivalent time, potency, shelf life used and mean kinetic temperature.
- `tracker_cases`: reading sequences with the expected status after every sample, the expected running totals, and the final state (suspect readings, confirmed excursions, a glitch as the last sample, uneven time steps).
- `document_checks`: the two worked examples from the team document, as rounded numbers with their precision. These are the only numbers not computed by the code.

All values are computed from synthetic product parameters for an imaginary vaccine.