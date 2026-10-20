# data

- What lives here: synthetic data only. Nothing here is real patient or shipment data.
- `recordings/` holds the eight golden scenario recordings (a `.jsonl` feed and a `.ground_truth.json` per scenario, schema 0.2) made by `python -m simulator generate --all` with each scenario's fixed seed. They are committed so the dashboard replay mode can use them, and a test checks they match a fresh regeneration.
- Runs with other seeds and free runs go to `runs/` by default. Generated outputs go in `generated/` and `runs/`, which are git-ignored.
- Filled in by: Phase 1 onward.