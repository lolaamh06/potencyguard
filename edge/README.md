# edge

- What lives here: the edge program: sensor sources, potency, thermal twin, signing and chain.
- Filled in by: Phase 1 (sensor interface, replay), Phase 2B (potency), Phases 3 and 4 (twin, signing).
- Finding things: one module per job, named after what it does.

## Potency (Phase 2B)

`potency.py` holds the pure functions (acceleration factor, equivalent time at the reference temperature, potency, shelf life used, time-weighted mean kinetic temperature) and `PotencyTracker`, which takes one reported reading at a time and returns a `PotencyState`. Potency is a model output for an imaginary product; the constants come from `config/product_default.yaml`.

The tracker integrates each interval with the temperature at its end (right endpoint). A reading outside the hard limits is "suspect" the first time and is left out of the maths (the last good temperature is used for that interval). The configured number of out-of-range readings in a row (2 by default) confirms an excursion, and the earlier suspect readings are then counted once with their own temperatures.

## See it

From the repo root in PowerShell:

```
$py = "$env:LOCALAPPDATA\potencyguard\venv\Scripts\python.exe"
& $py -m edge potency --recording data/recordings/spoof_attempt.jsonl
& $py -m edge potency --all
```

The first prints every 12th sample and a two-row summary (from the reported readings, and from the true temperature in the ground-truth file). `--all` prints just the two-row summary for each recording. These are simulation results on a synthetic box.