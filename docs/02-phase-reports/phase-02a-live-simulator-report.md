# Phase 2A: Live simulator upgrade: Report

Date: 2026-10-20. Git commit hash: none yet (the team lead commits). Git tag: none.

Pre-flight: `git status --short` was clean, the log showed Phase 0 and Phase 1 committed, and `run_checks.py` showed 5 passed before any change.

## 1. What I was asked to do

Turn the batch simulator into a live one: a cooling unit that cycles on and off (so the temperature wobbles), a different run every time when wanted, a step-by-step engine, faults injected while it runs, free-run trips with no scenario file, new golden recordings, a command line with a live demo, and tests. The dashboard and npm were not touched.

## 2. What I built

New files
- `simulator/engine.py`: `BoxEngine`, the one physics path (hysteresis cooling, substeps, three noise draws per sample).
- `simulator/live.py`: `LiveSimulator` (step, inject, events, snapshot, seeds).
- `simulator/events.py`: event models, the injectable catalogue, `EventRecord`, `InjectionResult`.
- `simulator/truth.py`: `TruthSample`.
- `simulator/expectations.py`: the `expect` block checker.
- `simulator/freerun.py`: `FreerunConfig`, `FreeRun`, `FreeRunPlanner`.
- `simulator/commands.py`: parser for typed commands such as `open_door 30` and `kill_cooling@2h`.
- `simulator/demo.py`: the live-demo loop (pacing through `SimClock`, injectable `sleep`).
- `tests/conftest.py`, `tests/test_live_simulator.py`, `tests/test_freerun_and_tools.py`.
- `docs/03-decisions/decision-0002-live-simulator.md`, this report, `docs/06-prompts/phase-02a-prompt.md`.

Changed files
- `simulator/scenario.py` (ranges, jitter and shift, `expect`, resolution), `simulate.py` (now a thin loop; `RunResult`), `sim_source.py` (wraps `LiveSimulator`, passes `inject` through), `recording.py` (schema 0.2), `box_model.py` (dead controller removed; helper functions kept), `cli.py` (generate, freerun, live-demo).
- `simulator/scenarios/*.yaml` (all eight: ranges and `expect`).
- `edge/recorded_source.py` (reads 0.2, refuses 0.1 with a clear message).
- `shared/config.py` (`BoxConfig` gets three keys; `read_yaml_mapping` is now public), `config/product_default.yaml`.
- `data/recordings/` (16 regenerated files), `simulator/README.md`, `data/README.md`.
- `tests/test_box_simulator.py` and `tests/test_scenarios.py` (rewritten: they encoded the old controller).

## 3. How to run it

```powershell
$py = "$env:LOCALAPPDATA\potencyguard\venv\Scripts\python.exe"
& $py scripts\run_checks.py
& $py -m simulator generate --all
& $py -m simulator live-demo --scenario reefer_failure --speed 3600 --inject "restore_cooling@20h"
& $py -m simulator live-demo --freerun --hours 12
```

## 4. How to check it works

- `run_checks.py`: five `PASS:` lines and `Summary: 5 passed, 0 failed`.
- `generate --all` followed by `git status --short` shows no change in `data/recordings/` the second time (byte-identical).
- `live-demo` prints a seed line, then one line per sample. While it runs you can type `kill_cooling`, `open_door 30`, `spoof_sensor hold 5`, `stop_spoof`, and so on; Ctrl+C stops it.
- Two `live-demo --freerun` runs print different seeds and different values.

## 5. Test results

- `run_checks.py`: 5 passed, 0 failed.
- pytest: 182 passed, 0 failed, 0 skipped. Per file: test_box_simulator 21, test_freerun_and_tools 24, test_live_simulator 35, test_scenarios 64, test_sensor_interface 32, test_smoke 6.
- The 200-seeds-per-scenario expectation sweep runs in full (8 x 200 = 1,600 runs, about 5 s). No shortening was needed.
- The dashboard build and tests ran on the existing install; I did not run npm install or npm ci.

## 6. What is real and what is simulated

Real code: the engine, hysteresis controller, event system, seeds, expectations, free-run planner, recording writer, replay source, command line. Simulated: everything the box measures, the weather, the cooling unit, and all failures and attacks. Every reading has `source: "sim"`. No detector exists yet; spoofs are data only.

## 7. Decisions I made and why

1. **Substeps:** each sample interval is split into the fewest equal steps that are each at most `sim_substep_s` (`ceil(interval / substep)`), so there is never a short leftover step. A test checks this for a 700 s interval.
2. **Order inside step():** the physics moves to the new sample time first, then the sample is emitted. A fault injected after sample k therefore first shows in sample k + 1, as required.
3. **Injection result:** `inject()` returns an `InjectionResult` (accepted or not, with an error text) and never raises, so a bad command cannot crash a run.
4. **restore_cooling** ends every cooling fault that is running, including scheduled and free-run ones, because a presenter expects "restore" to fix a scheduled failure too. `stop_spoof` likewise ends any spoof. The history shows the early end (`ended_by`).
5. **No-op commands are rejected:** `restore_cooling` with nothing to restore and `stop_spoof` with no spoof return `accepted=False` with a message.
6. **Spoof replay** loops from the time the spoof started, so the first spoofed sample is one sample into the loop. Replay adds no extra noise by default (it repeats values that already contain noise); hold and offset add noise by default.
7. **Ranges:** a range for `start_h` must end before the range for `end_h` begins, so every possible draw is a valid event. Violations are refused when the file loads.
8. **Ambient shift** moves the keyframes later; before the first and after the last keyframe the value is held (clamped). This is documented in the code and README.
9. **Expectation limits** can be a number or the name of a product limit (`hard_limit_high_c`, `hard_limit_low_c`); both come from config.
10. **Sensor saturation:** the reported temperature is clipped to the sensor's allowed range (-100 to 150 C), so an extreme injected value can never crash the reading model.
11. **Seeds:** `SimSource` and `generate` default to the scenario's own seed (golden); `LiveSimulator(seed=None)` draws a random one. `generate --seed N` and `--random-seed` write to `data/runs/` by default so they cannot overwrite the golden files.
12. **Recording keys:** schema 0.2 renames the sidecar's `labels` to `events` and adds `seed_mode`, `compressor_on`, `cooling_factor`, `spoof_mode`, `active_event_ids`, `resolved_parameters`, and first/last sample indices per event.
13. **Free-run settings** are flat `freerun_*` keys in the same YAML file, loaded by `load_freerun_config` (a pydantic model). Faults are planned an hour at a time with a two-sample lookahead, so a finite trip and an endless trip with the same seed start identically (a test checks this).
14. **live-demo default speed** is 3600 (a 600 s sample takes about 0.17 s). The prompt's example showed 60, which would take 10 s per sample.
15. **No PROPOSE items** arose.

## 8. Assumptions and unverified claims introduced

Placeholders, all "not sourced [SOURCE NEEDED]" in `config/product_default.yaml`:
- `box_deadband_c` 0.8, `sim_substep_s` 60, `door_default_power_w` 100.
- 48 `freerun_*` keys: sample interval 600 s, default 48 h, humidity 45, clean-trip probability 0.25, base temperature 14 to 30 C, daily swing 2 to 8 C, and for each fault type (kill cooling, derate, open door, heat soak, cold snap, spoof, glitch, shock) a probability per hour plus duration and size ranges.
- Scenario YAML numbers: all ambient profiles, jitter and shift (2 to 3 C, 2 to 3 h), event time and size ranges (for example door power 90 to 120 W, derate factor 0.25 to 0.45, glitch 35 to 70 C, shock 8 to 20 g), hold value 4 to 6 C, and the `expect` thresholds (9 C, 25 C, 1 C, 2 C, 5 g, 10 C, 20 C jump).
- Peak outside temperatures of 46 to 50 C in `reefer_failure` are chosen so that every seed passes the upper limit; they are demonstration values, not a claim about any real place.
- The default outlier jump of 20 C and the sanity bounds -100 to 150 C.

## 9. Problems and surprises

- A test of mine expected the wrong passive-cooling end value (2.0 instead of 2.055) and another miscounted a 30-minute spoof; both were test arithmetic mistakes, fixed in the test, not the code.
- With a 600 s sample and a cycle of about 41.5 minutes the compressor state looks irregular when sampled (roughly four samples per cycle). The fine-resolution check below shows the underlying regular cycle.
- `\n` inside a single-quoted PowerShell string is not a newline; one config edit was wrongly written and fixed at once.
- No OneDrive or sync problems occurred.

## 10. Numbers measured (simulation results, synthetic box)

- Baseline cycle (24 h, constant 22 C outside, seed 101, sampled every 60 s): 32 on-switches after warm-up, mean cycle period 41.5 min, true temperature 4.57 to 5.446 C (peak to peak 0.875 K), standard deviation 0.245 K.
- Golden baseline_ok (seed 101, 289 samples at 600 s): true 4.5717 to 5.4455 C, standard deviation 0.244 K.
- Noise: standard deviation of reported minus true is 0.0491 C over the 289-sample golden baseline (configured 0.05); the 3,001-sample test run is within 5 percent.
- True minimum and maximum, fixed seed, one run per scenario:

| Scenario | Seed | Hours | True min (C) | True max (C) |
|---|---|---|---|---|
| baseline_ok | 101 | 48 | 4.5717 | 5.4455 |
| door_open_excursion | 102 | 24 | 4.5699 | 19.0342 |
| reefer_failure | 103 | 36 | 4.5886 | 47.6987 |
| freeze_event | 104 | 36 | -12.9451 | 5.3937 |
| heatwave_transit | 105 | 72 | 4.5823 | 29.5771 |
| spoof_attempt | 106 | 36 | 4.5774 | 29.2518 |
| sensor_glitch | 107 | 24 | 4.5577 | 5.4334 |
| shock_drop | 108 | 24 | 4.5814 | 5.4416 |

- Expectation sweep: seeds 1000 to 1199, every scenario, 0 violations.
- Free-run: 100 seeds (0 to 99, 48 h each) produced both clean and faulty trips, no crash, no overlapping spoofs, no spoof before a physical fault.

## 11. Open questions for the decision-maker

1. A 41.5-minute cycle sampled every 10 minutes looks jagged on a chart. Keep 600 s, or move the default sample interval to 300 s (or 60 s for the control-room chart)?
2. Should `restore_cooling` end scheduled failures too (my choice), or only injected ones?
3. Are the 46 to 50 C peak outside temperatures in `reefer_failure` acceptable as demonstration values, or should the scenario use a cooling derate instead of a high ambient?
4. Should rejected no-op commands (`stop_spoof` with no spoof) be errors (now) or silent successes?
5. Should the replay spoof start its loop at the first spoofed sample instead of the injection time?
6. Is the live-demo default speed of 3600 fine?

## 12. Suggested next phase

Phase 2B as you define it. Independent of that, the thermal twin and detectors (Phase 3) can now use `ground_truth.json` events with their origins and sample indices to score false alarms and detection delay. Not started.
