# test-vectors

- What lives here: JSON test cases that are the single source of truth for numeric tests in Python and TypeScript, so the two implementations are provably identical.
- Filled in by: Phase 2B (`potency_vectors.json`); the TypeScript mirror in Phase F2 must reproduce BOTH vector files.
- Finding things: each JSON file is one family of test cases.

## The two potency vector files

- `potency_vectors.json`: the ACTIVE product profile (`config/product_default.yaml`).
- `potency_vectors_team_document.json`: the REFERENCE profile (`config/product_team_document.yaml`, the team document's constants). Only this file has `document_checks`.

The TypeScript port must reproduce both. Each file has a `meta.profile` note naming its profile and the constants used.

## Contents of each file

Both made by `python scripts/make_test_vectors.py` from the Python reference code in `edge/potency.py`. A test fails if the committed file differs from a fresh generation, so regenerate and commit it whenever the maths or the product constants change.

- `meta`: schema version, the constants used and the integration rule.
- `af_cases`: acceleration factor at ten temperatures.
- `tau_cases`: temperature profiles with the expected equivalent time, potency, shelf life used and mean kinetic temperature.
- `tracker_cases`: reading sequences with the expected status after every sample, the expected running totals, and the final state (suspect readings, confirmed excursions, a glitch as the last sample, uneven time steps).
- `document_checks` (reference file only): the two worked examples from the team document, as rounded numbers with their precision. These are the only numbers not computed by the code.

All values are computed from synthetic product parameters for an imaginary vaccine.

## chain_vectors.json (Phase 4)

Made by `python scripts/make_chain_vectors.py` with a TEST ONLY key (the seed is public; never use it for a real device). Holds rounding cases, four records with their canonical bytes (hex), Ed25519 signatures, chain hashes, the genesis hash, the public key and a signed anchor, so a TypeScript implementation of `docs/01-architecture/signed-record-format.md` can be checked against it. A test fails if the file differs from a fresh generation. `shared/golden_sha256.json` (one level up) holds the SHA-256 of the 9 golden recordings and the two potency vector files, which Phase 4 did not change.
