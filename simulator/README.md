# simulator

- What lives here: the seeded box simulator and the scenario library (Phase 1).
- Filled in by: Phase 1 (done). Everything here is synthetic; the box and its numbers are made-up placeholders [SOURCE NEEDED].
- Finding things: `scenarios/` holds one YAML per scenario; `simulate.py` runs the physics; `recording.py` writes recordings.

## Generate recordings

From the repo root (PowerShell):

```
& "$env:LOCALAPPDATA\potencyguard\venv\Scripts\python.exe" -m simulator generate --all
& "$env:LOCALAPPDATA\potencyguard\venv\Scripts\python.exe" -m simulator generate --scenario reefer_failure
```

Files go to `data/recordings/` (change with `--out-dir`): `<id>.jsonl` (a header line, then one reading per line) and `<id>.ground_truth.json` (the true temperature and labels of the injected events). The same seed always gives byte-identical files.

Scenarios: baseline_ok, door_open_excursion, reefer_failure, freeze_event, heatwave_transit, spoof_attempt, sensor_glitch, shock_drop.