# data

- What lives here: synthetic data only. Nothing here is real patient or shipment data.
- `recordings/` holds the nine golden scenario recordings (a `.jsonl` feed and a `.ground_truth.json` per scenario, schema 0.2) made by `python -m simulator generate --all` with each scenario's fixed seed. They are committed so the dashboard replay mode can use them, and a test checks they match a fresh regeneration.
- `calibration/` holds the ten clean recordings used only to fit the thermal twin (`python -m simulator generate-calibration`, seeds 9001 to 9010); a test checks they match a fresh generation and that they are never evaluation data.
- Runs with other seeds and free runs go to `runs/` by default. Generated outputs go in `generated/` and `runs/`, which are git-ignored.
- Filled in by: Phase 1 onward.

## Phase 3B

No recording changed: the two new lie modes are used by no shipped scenario, and the nine golden recordings are byte-identical to the Phase 3 ones (`tests/test_lie_modes.py` regenerates each and compares the bytes). `data/generated/evaluation_3b.json` (git-ignored) holds the numbers behind `docs/02-phase-reports/phase-03b-evaluation.md`.

## Phase 3C

`data/generated/evaluation_3c.json` (git-ignored) is written by `scripts/evaluate_3c.py`. A ground-truth file of a two-node box has an extra series `true_payload_temp_c` (the payload node; `true_temp_c` stays the air node the sensor measures). The nine golden recordings and their ground-truth files do not have it and are unchanged.
