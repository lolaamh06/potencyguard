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
