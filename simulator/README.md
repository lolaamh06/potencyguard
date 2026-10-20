# simulator

- What lives here: the live box simulator, the scenario library and the free-run trip generator (Phases 1 and 2A).
- Everything here is synthetic. The box and every number in it are made-up placeholders [SOURCE NEEDED]. Results measured here are simulation results.
- Finding things: `engine.py` is the one physics path; `live.py` is the run you step through and inject into; `scenarios/` holds one YAML per scenario; `freerun.py` builds random trips.

## What the engine does

`BoxEngine` advances the box one sample at a time using the exact exponential step `T_next = T_inf + (T - T_inf) * exp(-dt/tau)`. The cooling unit is an on/off controller with a dead band, so the temperature wobbles around the setpoint like a real cooled box. It only cools, never heats. `LiveSimulator` wraps the engine, resolves the scenario's random ranges, accepts faults while running and keeps the event history. The batch function `simulate()` is just a loop over `LiveSimulator.step()`.

## Seeds

- A fixed seed always gives the same output, byte for byte.
- `seed=None` draws a random seed. The seed used is always available (`.seed`, `.seed_mode`), printed by the tools, and stored in the recording header and ground-truth file, so any run can be repeated.
- Three separate random streams come from one seed: sensor noise (three draws per sample, always), scenario ranges, and free-run faults. Injecting a fault never changes the noise that follows.

## Scenario files

Any number in an event may be a range `{min: a, max: b}`; it is drawn once per run. The start range must end before the end range begins. Optional `ambient_jitter_c` and `ambient_shift_h` randomise the whole profile of the temperature around the box (the cargo area) (the shift moves the profile later; values outside the keyframes are held constant). The `expect:` block lists guarantees that must hold for every seed (see `expectations.py`); thresholds may name product limits such as `hard_limit_high_c`.

There are nine scenarios: baseline_ok, door_open_excursion, reefer_failure, freeze_event, heatwave_transit, spoof_attempt, sensor_glitch, shock_drop and hidden_spoilage (a multi-day trip where weak cooling spoils the box slowly while the reported temperature is falsified; its potency guarantees are checked in `tests/test_hidden_spoilage.py`, because the simulator does not import the edge package).

Event types in scenario files: `heat_load`, `cooling_factor`, `ambient_offset`, `spoof` (modes `hold`, `offset`, `replay`), `glitch`, `shock`.

## Faults you can inject while a run is going

| Command | Parameters | Effect |
|---|---|---|
| `kill_cooling` | none | cooling capacity to 0 |
| `derate_cooling` | `factor` 0..1 | cooling capacity scaled |
| `restore_cooling` | none | ends cooling faults (also scheduled ones); nothing to restore is accepted as a no-op |
| `open_door` | `duration_min`, optional `power_w` | extra heat for a while |
| `heat_soak` | `delta_c`, `duration_h`, `ramp_h` | cargo-area temperature up, hold, down |
| `cold_snap` | `delta_c` (negative), `duration_h`, `ramp_h` | cargo-area temperature down, hold, up |
| `spoof_sensor` | `mode` hold, offset or replay plus its values, optional `duration_min` | reported temperature falsified; the true one is untouched |
| `stop_spoof` | none | ends the spoof; no spoof active is accepted as a no-op |
| `glitch_spike` | `value_c` | the next reported sample only |
| `shock` | `peak_g` | the next shock sample only |

A rejected fault (unknown type, bad value, missing parameter) returns an error result and changes nothing. `stop_spoof` or `restore_cooling` with nothing to stop or restore is accepted with a short note and also changes nothing. A fault shows from the next sample on.

## Commands

From the repo root in PowerShell (`$py` is the venv python):

```
$py = "$env:LOCALAPPDATA\potencyguard\venv\Scripts\python.exe"
& $py -m simulator generate --all                       # golden recordings, fixed seeds, data/recordings/
& $py -m simulator generate --scenario reefer_failure --seed 5      # goes to data/runs/ unless --out-dir
& $py -m simulator generate --scenario reefer_failure --random-seed # prints the seed it used
& $py -m simulator freerun --seed 5 --hours 48          # writes data/runs/freerun_5.jsonl
& $py -m simulator live-demo --scenario reefer_failure --speed 3600 --inject "restore_cooling@20h"
& $py -m simulator live-demo --freerun --hours 12
```

`live-demo` prints one line per sample and accepts typed commands while running, for example `kill_cooling`, `open_door 30`, `spoof_sensor hold 5`, `stop_spoof`. Ctrl+C stops it. `--speed` is simulated seconds per real second (default 3600; a 600 s sample then takes about 0.17 s).

Recordings are written as `<id>.jsonl` (a header line, then one reading per line) and `<id>.ground_truth.json` (true temperature, compressor state, cooling factor, ambient, resolved parameters and the event history with origins). Schema version 0.3 (adds the `ambient_c` and `cooling_duty` channels to every reading and `measured_ambient_c`, `cooling_duty` and `first_divergence_s` to the ground-truth file; the reader still accepts 0.2 files, without those fields).

## Extra sensor channels and the end-of-trip rule (Phase 3)

- Every reading now also carries `ambient_c` (the temperature around the box, the cargo area, with its own sensor noise from a separate random stream) and `cooling_duty` (the fraction of the interval that just ended during which the compressor ran; 0 for the first sample, which has no interval behind it). A spoof changes only `temp_c`; the other channels stay honest.
- An event that ends exactly at the end of the trip also covers the final sample (before, a spoof that "lasted to the end" left one true-looking reading). The ground-truth file marks such events with `covers_final_sample`.
- `python -m simulator generate-calibration` writes the clean recordings used to fit the thermal twin into `data/calibration/` (scenarios in `calibration_scenarios/`, seeds 9001 to 9010). They are never used to score detectors.
