# Phase 1: Housekeeping, box simulator and scenario recordings: Report

Date: 2026-10-20. Git commit hash: none yet (the team lead commits). Git tag: none.

## 1. What I was asked to do

Lower the Python target to 3.11 and fix the junction documentation; add numpy and pydantic; build the sensor interface (reading model, abstract source, simulated clock); build a seeded box simulator from the lumped thermal model; define eight scenarios as YAML; write each as a JSONL recording with a ground-truth sidecar; add a replay source and a small command line; test all of it; and write this report. The dashboard was not touched and `npm install` was not run.

## 2. What I built

Housekeeping and dependencies
- `pyproject.toml`: `requires-python >=3.11`, ruff `py311`, pinned `numpy==2.5.4` and `pydantic==2.14.1` as dependencies.
- `requirements-dev.txt`: numpy 2.5.4, pydantic 2.14.1 and pydantic's mandatory dependencies (pydantic_core 2.50.1, annotated-types 0.8.0, typing-inspection 0.4.4, typing_extensions 4.16.0).
- `CLAUDE.md` (rule 10), `README.md` (step 4), `dashboard/README.md`: current junction path plus the npm warning.

Sensor interface (`edge/`)
- `sensor_reading.py`: `SensorReading` (t_s, temp_c, rh_pct, shock_g, source); frozen; rejects NaN, infinity, negative time and out-of-range values.
- `sensor_source.py`: abstract `SensorSource` (start, read, close).
- `sim_clock.py`: `advance_sim_time` (pure), `SimClock`, speed presets 1, 60, 3600. No sleeping, no wall-clock reads.
- `recorded_source.py`: `RecordedSource`, replays a JSONL recording.

Simulator (`simulator/`)
- `box_model.py`: exact step `T[n+1] = T_inf + (T[n] - T_inf) * exp(-dt/tau)`, `T_inf = T_amb + R_th * Q`, and a cooling-only demo controller.
- `scenario.py`: pydantic scenario and event models, YAML loaders.
- `simulate.py`: seeded simulation with noise and injected events, plus labels.
- `sim_source.py`: `SimSource`.
- `recording.py`: writes `<id>.jsonl` and `<id>.ground_truth.json`.
- `cli.py`, `__main__.py`: `python -m simulator generate --all | --scenario <id>`.
- `scenarios/*.yaml`: baseline_ok, door_open_excursion, reefer_failure, freeze_event, heatwave_transit, spoof_attempt, sensor_glitch, shock_drop.
- `README.md`: updated with the CLI.

Config and data
- `config/product_default.yaml`: seven placeholder box and noise keys added.
- `shared/config.py`: `BoxConfig`, `load_box_config`; the repo root constant is now public (`REPO_ROOT`).
- `data/recordings/`: 16 generated files (8 recordings, 8 sidecars), 213 kB in total, committed on purpose so the dashboard replay mode can use them.
- `data/README.md`: updated.

Tests
- `tests/test_sensor_interface.py` (32), `tests/test_box_simulator.py` (11), `tests/test_scenarios.py` (38).

## 3. How to run it

```powershell
$py = "$env:LOCALAPPDATA\potencyguard\venv\Scripts\python.exe"
& $py -m simulator generate --all
& $py -m simulator generate --scenario reefer_failure
& $py scripts\run_checks.py
```

## 4. How to check it works

`run_checks.py` prints five `PASS:` lines and `Summary: 5 passed, 0 failed`. `git status --short` after `generate --all` shows no change in `data/recordings/` (the output is byte-identical).

## 5. Test results

- `scripts/run_checks.py`: 5 passed, 0 failed (ruff check, ruff format check, pytest, dashboard build, dashboard test).
- pytest: 87 passed, 0 failed, 0 skipped.
- The dashboard build and tests ran against the existing install; I did not run npm install or npm ci.

## 6. What is real and what is simulated

Real code: the clock, reading model, box physics, scenario loader, recording writer, replay source, CLI. Simulated: everything the box "measures" (temperature, humidity, shock), the ambient weather, the cooling unit, and the injected failures and attacks. All recordings carry `source: "sim"`. The spoof scenario contains the false data only; no detector exists yet.

## 7. Decisions I made and why, and PROPOSE items

Decisions
1. **Folders.** The brief's layout has no scenarios or recordings folder. I used `simulator/scenarios/` for the YAML files and `data/recordings/` for output. `data/generated/` is git-ignored, but the dashboard replay mode needs the files in the repo, so recordings are committed. Say so if you want other names.
2. **Controller.** The simulated cooling unit holds the setpoint, only cools, never heats, and saturates at its capacity. This makes the freeze scenario work (a cold stretch drops the box below 0 because nothing heats it) and the failure scenarios work (capacity scaled to 0 or 0.4).
3. **Box parameters in the config file.** Read by a new `BoxConfig`, so `ProductConfig` is unchanged.
4. **Rounding.** All stored values are rounded to 4 decimals so the simulator and the files agree exactly; tests allow 6e-5 against the unrounded closed form.
5. **Event types.** `heat_load` (door open), `cooling_factor` (failure or derate), `spoof`, `glitch`, `shock`. Times are in hours in the YAML.
6. **Committed recordings test.** A test regenerates every scenario and compares hashes with the committed files, so stale files fail the checks.

PROPOSE items awaiting decision (brief section 3.7)
- **Sample interval.** Options: 10 s (the source document), 60 s, 600 s. I used 600 s. Pros: 48 h is only 289 samples, small files, readable charts, matches the vision's sample file (`sim_sample_interval_s: 600`). Cons: the "about 3 samples" detection target then means about 30 simulated minutes, not 30 s. Recommendation: keep 600 s for the stage story and decide in Phase 3 whether detection targets are stated in samples or in time.
- **Speed factors.** Presets 1, 60, 3600 as the prompt said. Recommendation: keep.
- **Box parameters.** R_th 0.5 K/W, tau 6 h. Check against the worked example: a 1 h, 100 W heat load at 22 C ambient lifts the box from 5 C to about 12.7 C, near the 12 C used in the brief's worked example, and it recovers to about 5.5 C within a day. Recommendation: keep as demonstration values and replace with sourced ones if a real box is ever measured.

## 8. Assumptions and unverified claims introduced

- Placeholder values, "not sourced [SOURCE NEEDED]" (all in `config/product_default.yaml`): box_R_th_k_per_w 0.5; box_tau_h 6.0; box_setpoint_c 5.0; box_cooling_capacity_w 60.0; sensor_sigma_c 0.05; sensor_sigma_rh_pct 0.5; sensor_sigma_shock_g 0.01.
- Scenario numbers are invented for demonstration: ambient keyframes, event times and sizes (for example 100 W for 1 h, factor 0.4, glitch 60 C, shock 15 g, spoof value 5 C), seeds 101 to 108, durations 24 to 72 h, sample interval 600 s, relative humidity baseline 40 to 45 percent.
- `SensorReading` sanity bounds: temperature -100 to 150 C (`ASSUMPTION` comment in code).
- No external statistics were added anywhere.

## 9. Problems and surprises

- Phase 0's `git status` showed Step 1 changes as modified because they were not committed yet; nothing wrong.
- Setting a UTF-8 file with `Set-Content` in Windows PowerShell 5.1 adds a byte-order mark. I rewrote `pyproject.toml` without it and used .NET file writes for the rest.
- The baseline scenario is a flat 5.0 C line plus noise, because the controller holds the setpoint exactly. It is correct for the model but visually dull; see open question 2.
- NumPy does not promise identical random streams across versions. numpy is pinned, and the committed-recordings test will catch any change.

## 10. Numbers measured (simulation results)

- Noise check: over a 3,001-sample run (seed 1, constant ambient), the standard deviation of reported minus true temperature is within 5 percent of the configured 0.05 C, and the mean is within 0.01 C.
- Step response: matches the closed form at 7 times (0 h to 54 h after the step) within 6e-5 C.
- reefer_failure: the true box temperature reaches 43.75 C, with 63 samples above 40 C.
- freeze_event: the true temperature falls to -11.36 C, with 140 samples below 0 C.
- door_open_excursion: peak 12.68 C.
- heatwave_transit: peak 30.7 C.
- spoof_attempt: true temperature rises to 29.67 C while the reported series stays near 5 C.
- Seeds 101 to 108, one per scenario; run lengths 24 to 72 simulated hours.
These are simulation results for a synthetic box, not field results.

## 11. Open questions for the decision-maker

1. Are `simulator/scenarios/` and `data/recordings/` acceptable folder names, and should recordings stay committed?
2. Should the baseline show small natural wobble instead of a flat 5.0 C line (for example a controller with a small swing)? It would look better on screen and would make the later flat-line detector more interesting, at the cost of more model detail.
3. Is 600 s the right sample interval (see section 7)?
4. Should the glitch value (60 C) and shock (15 g) be changed, or are they fine as obvious test values?
5. Should humidity and shock be modelled any further for Phase 3 and later, or is the current simple treatment enough?

## 12. Suggested next phase

Phase 2 (potency maths in Python plus shared test vectors) can run next. It needs no changes to the simulator. In parallel, Phase 3 (thermal twin and detectors) can use these recordings and their ground-truth labels to score false alarms and detection delay. Not started.
