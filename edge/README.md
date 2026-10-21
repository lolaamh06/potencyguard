# edge

- What lives here: the edge program: sensor sources, potency, thermal twin, signing and chain.
- Filled in by: Phase 1 (sensor interface, replay), Phase 2B (potency), Phases 3 and 4 (twin, signing).
- Finding things: one module per job, named after what it does.

## Potency (Phase 2B)

`potency.py` holds the pure functions (acceleration factor, equivalent time at the reference temperature, potency, shelf life used, time-weighted mean kinetic temperature) and `PotencyTracker`, which takes one reported reading at a time and returns a `PotencyState`. Potency is a model output for an imaginary product; the constants come from the active profile `config/product_default.yaml` (illustrative, placeholder, not sourced [SOURCE NEEDED]). The team document's original constants are kept in `config/product_team_document.yaml` as a reference profile.

The tracker integrates each interval with the temperature at its end (right endpoint). A reading outside the hard limits is "suspect" the first time and is left out of the maths (the last good temperature is used for that interval). The configured number of out-of-range readings in a row (2 by default) confirms an excursion, and the earlier suspect readings are then counted once with their own temperatures.

## See it

From the repo root in PowerShell:

```
$py = "$env:LOCALAPPDATA\potencyguard\venv\Scripts\python.exe"
& $py -m edge potency --recording data/recordings/spoof_attempt.jsonl
& $py -m edge potency --all
```

The first prints every 12th sample and a two-row summary (from the reported readings, and from the true temperature in the ground-truth file). `--all` prints just the two-row summary for each recording. These are simulation results on a synthetic box.

The summary table also prints the simulated hour at which potency first fell below the minimum ("never" if it did not). The tracker reads the active profile by default; pass another `ProductConfig` to use the reference profile.

## Thermal twin and tamper monitor (Phase 3)

- `thermal_twin.py`: the physics model of the box, the physical step bound and the lag-aware lower envelope.
- `calibration.py`: fits the twin from clean calibration runs (and refuses evaluation data).
- `tamper_monitor.py`: the four detectors (CUSUM drift, impossible step, impossible state, flat line) and the classification into ok, thermal anomaly, sensor glitch and suspected falsification. It needs readings that carry `ambient_c` and `cooling_duty`, and it never sees ground truth.
- `detector_config.py`: reads `config/detectors.yaml`.

```
$py = "$env:LOCALAPPDATA\potencyguard\venv\Scripts\python.exe"
& $py -m edge twin --recording data/recordings/hidden_spoilage.jsonl
& $py -m edge twin --all
& $py -m edge calibrate
```

`twin` replays a recording through the monitor and the potency tracker together and prints the verdicts, the first alarm of each detector and, from the ground-truth file, the detection delay. Simulation results on a synthetic box.

## Twin out of date, trust and the worst-case bound (Phase 3B)

- `tamper_monitor.py` now also fits `y = g * x + b * dt_h` over a rolling window (x the change the twin predicts, y the change observed). A box that differs from the calibration shows a gain `g` away from 1 with no jump; the monitor then reports the verdict `twin_out_of_date` and stops turning a CUSUM alarm into a tamper verdict. Hard physical proofs (a jump that stays, the impossible state, a flat line) are never suppressed. The monitor also keeps `untrusted_since_s`, the time from which the reported data are doubtful.
- `assessment.py`: `worst_case_bound()` is an UPPER BOUND on the damage since that time (no cooling at all, the honest ambient channel, one heat allowance), `assess()` combines it with the reported potency into a `PotencyAssessment`, and `TrustAssessor` does it one reading at a time. It never uses ground truth.

```
$py = "$env:LOCALAPPDATA\potencyguard\venv\Scripts\python.exe"
& $py -m edge twin --recording data/recordings/hidden_spoilage.jsonl
& $py -m edge twin --all
```

`twin --recording` now prints a Trust block: whether the data are trusted, whether the twin is in date, and, when they are not trusted, the reported shelf life used next to "worst case from hour t0: at most X percent of shelf life used". `twin --all` adds a trust column. The bound is deliberately pessimistic: it assumes the cooling unit did nothing after t0, so it can be far above the true value when the cooling in fact worked.

## Phase 3C: per-box twins, the pre-trip check and the bound interval

- `python -m edge precheck --recording FILE [--hours H]` feeds the first H hours (default 6, placeholder) through the rolling gain estimate and prints either "twin matches this box (gain g, band ...)", "twin may be out of date: recalibrate before departure (gain g)", or that the gain could not be measured (which is NOT a confirmation). Library: `edge.precheck.precheck(readings, twin, config) -> PrecheckResult`.
- Operating procedure: calibrate the twin once per box type at commissioning from a clean run, run the pre-trip check before each trip, recalibrate when it says so. The twin must be calibrated to the box it is used with.
- `edge.thermal_twin.load_variant_twins()` reads `config/twin_calibrated_variants.yaml` (simulation only).
- `PotencyAssessment` now carries `bound_tau_eq_h` (the HIGH bound, the field a signed record would carry), `bound_high_tau_eq_h` (same value), `bound_low_tau_eq_h` (cooling worked fully; NOT a guarantee) and shelf-life equivalents. `python -m edge twin` prints "between A percent (cooling worked fully) and B percent (no cooling) of shelf life used". The high bound integrates the twin with its time constant times `bound_tau_safety_factor`.
- Signatures and hash chains (Phase 4) protect records after the device signs them; they do not defend against a lie that arrives at the sensor input before signing.

## Phase 4: signed records, hash chain, ledger, runner

- `python -m edge run --recording FILE | --all [--key-dir D] [--ledger-dir D] [--device-id ID]` replays a recording through the real pipeline (potency tracker, tamper monitor, trust assessment) and signs every reading into a hash chain stored in an append-only SQLite ledger (`data/runs/`, git-ignored), signs a final anchor, reads the ledger back, verifies it and prints a short summary.
- `edge/chain/`: `canonical.py` (integer-only record, schema `pg-record/1`), `crypto.py` (Ed25519, key outside the repo), `chain.py` (`ChainWriter`, `verify_chain`, anchors), `ledger.py`. Exact rules: `docs/01-architecture/signed-record-format.md`.
- `edge/pi_source.py`: a stub for a real Pi feed; it raises `NotImplementedError` (no hardware is attached).
- Signatures and the hash chain protect records AFTER they are signed. They do not stop a lie at the sensor before the device signs it. Without an anchor, truncating the tail of a ledger cannot be detected.
