PHASE 2A: LIVE SIMULATOR UPGRADE (realistic fridge wobble, randomised runs, step-by-step engine, live fault injection)

READ FIRST, ASSUME NOTHING
1. Read CLAUDE.md, then docs/00-project-brief/master-brief.md in full (including the amendments at the end), then docs/01-architecture/frontend-vision.md, then docs/02-phase-reports/phase-01-simulator-report.md. Also read these code files before changing them: edge/*.py, simulator/*.py, simulator/scenarios/*.yaml, shared/config.py, config/product_default.yaml, tests/test_box_simulator.py, tests/test_scenarios.py, tests/test_sensor_interface.py.
2. If anything in this prompt conflicts with the brief, CLAUDE.md or the existing code, STOP and tell me the exact conflict. Do not pick a side.
3. If any detail is missing or ambiguous, ASK me before writing code. Never guess numbers, field names or file names.

WHY THIS PHASE EXISTS
Phase 1 built a batch simulator: it computes a whole trip, writes a file, and replays it. The project needs a LIVE-feeling simulator for stage demos:
(a) every live run must look different, not like a repeated replay;
(b) the box must behave like a real cooled box (a refrigeration unit cycles on and off, so the temperature wobbles around the setpoint, instead of holding a perfectly flat line);
(c) the simulator must advance ONE STEP AT A TIME and accept fault commands injected while it runs (so a person can say "break the cooling now" and the next readings respond);
(d) fixed-seed runs must stay byte-identical, because tests and recorded demo videos depend on that.
There must be exactly ONE physics code path. The old batch function becomes a loop over the new step-by-step engine.

ABSOLUTE RULES
- NEVER run git add, git commit, git tag or git push. At the end print ONE block of commands for me to run (explicit paths only, no "git add -A", no "git add ."), one commit message, no co-author trailers or attribution lines.
- NEVER run npm install or npm ci. Do not touch the dashboard folder at all in this phase. The dashboard junction is fragile.
- No new Python packages. Use only what is already installed (numpy, pydantic, pyyaml, pytest, ruff). Use the standard library "secrets" for entropy.
- No external statistics anywhere (code, comments, YAML, docs). Where a number needs a source, mark it "placeholder, not sourced [SOURCE NEEDED]".
- No wording that claims hardware or SAP is real. Scenario titles and descriptions stay plain and neutral. The "source" field of every reading stays "sim".
- No "first", "unique" or "novel" claims in any file.
- All files UTF-8 without a byte-order mark, LF line endings. Use .NET file writes, not Set-Content, for files written from PowerShell.

STEP 0: PRE-FLIGHT (read-only)
Run git status --short and git log --oneline -5. Phase 1 should already be committed. If git status shows uncommitted changes to tracked files, STOP and tell me, because Phase 1 is not committed yet. Run scripts\run_checks.py and confirm 5 passed before touching anything. Report the result in one line, then continue.

STEP 1: CONFIG ADDITIONS (config/product_default.yaml and shared/config.py)
Add these keys, each with the comment "placeholder, not sourced [SOURCE NEEDED]":
- box_deadband_c: 0.8 (total width of the cooling unit's on/off band around the setpoint: unit switches ON above setpoint + deadband/2 and OFF below setpoint - deadband/2)
- sim_substep_s: 60 (largest internal integration step in seconds; sample interval is separate)
- door_default_power_w: 100
Extend BoxConfig and load_box_config to read them, with validation (deadband > 0, substep > 0, substep must divide the sample interval evenly or the engine must handle a final shorter substep; choose the cleanest approach and tell me which in the report).
Keep ProductConfig unchanged.

STEP 2: THE STEP-BY-STEP ENGINE (new file simulator/engine.py)
Create class BoxEngine holding the physical state and advancing it by one SAMPLE per call to step().
State: sim time t_s, true box temperature T, compressor_on (bool), cooling_factor (float 0..1), active ambient offset, active heat loads, active spoof (or none), history of REPORTED temperatures (needed for replay spoof).
Physics per internal substep dt (<= sim_substep_s): exact exponential step from the brief:
  T_next = T_inf + (T - T_inf) * exp(-dt / tau), with T_inf = T_amb + R_th * Q,
  where tau comes from config in hours (convert units carefully), and Q = Q_heat_loads + Q_cooling.
Cooling unit (replaces the Phase 1 "hold exactly at setpoint" controller): hysteresis control. Compressor turns ON when T > setpoint + deadband/2, OFF when T < setpoint - deadband/2, otherwise keeps its previous state. When ON, Q_cooling = -(capacity * cooling_factor) watts; when OFF, Q_cooling = 0. The unit never heats. Evaluate the on/off decision at the START of each substep. The compressor state at the start of a trip: ON if T starts above the band, else OFF; start the true temperature at the setpoint.
Sample output of step(): returns TWO objects:
  (1) a SensorReading exactly as Phase 1 defines it (source "sim"), containing the REPORTED values (including noise and any spoof/glitch/shock effects);
  (2) a TruthSample (new pydantic model, frozen) with t_s, true_temp_c, reported_temp_c, ambient_c, compressor_on, cooling_factor, spoof_mode (or None), active_event_ids (list), rh_pct.
Rounding: round stored values to 4 decimals as in Phase 1, so files and engine agree exactly.
Humidity and shock keep the Phase 1 simple treatment (baseline plus noise, plus event effects). Keep their existing behaviour.
RNG discipline (important for byte-identical fixed-seed output): use numpy.random.SeedSequence(seed).spawn(n) to make SEPARATE generators for (a) sensor noise, (b) scenario parameter resolution, (c) free-run fault generation. The noise generator must consume exactly the same number of draws per sample regardless of events or injections, so that injecting a fault does not change the noise that follows. Document this in the module docstring.

STEP 3: SCENARIO FORMAT WITH RANDOM RANGES AND EXPECTATIONS (simulator/scenario.py and the eight YAML files)
Extend the scenario schema, backwards compatible with Phase 1 files where sensible:
a. Any numeric event field (start_h, end_h, at_h, power_w, factor, reported_c, value_c, peak_g, and so on) may be EITHER a number OR a range written {min: a, max: b}. A range is resolved once per run by the parameter RNG (uniform). Validate min <= max, and after resolution validate that end_h > start_h and everything lies inside the trip.
b. New optional top-level keys: ambient_jitter_c (random offset added to the whole ambient profile, uniform in +/- this value), ambient_shift_h (random time shift of the ambient keyframes, uniform in +/- this value, wrapping or clamping; choose and document), duration_h stays fixed per scenario.
c. A new "expect" block of simple declarative guarantees that must hold for EVERY seed, for example:
     expect:
       true_max_c_gt: 41       # reefer_failure
     or true_min_c_lt: -1, or reported_true_gap_c_gt: 10, or exactly_one_reported_outlier: true, or true_max_c_lt: 15, and so on.
   Implement the check function (in simulator/ or a new simulator/expectations.py) that takes the resolved scenario, the list of TruthSample and the list of SensorReading, and returns a list of violated expectations. Thresholds relative to product limits (0 C and 40 C hard limits) must be read from config, not hard-coded.
d. Update all eight scenario YAML files: add sensible ranges so each run differs (event start times, durations, sizes, ambient jitter and shift) while the story stays the same. The defining behaviour of each scenario must be protected by an "expect" entry:
     baseline_ok: stays within setpoint +/- 2 C the whole trip (true series).
     door_open_excursion: true max above 9 C and below the 40 C limit; recovers to within 1 C of setpoint before the end.
     reefer_failure: true max above the upper hard limit.
     freeze_event: true min below the lower hard limit.
     heatwave_transit: true max above 25 C and below the upper hard limit [placeholder thresholds].
     spoof_attempt: gap between true and reported exceeds 10 C at some point, and the spoof window begins after the failure begins.
     sensor_glitch: exactly one reported sample deviates from its neighbours by more than 20 C, and the true series never exceeds setpoint + 2 C.
     shock_drop: exactly one shock sample above 5 g; true series stays within setpoint +/- 2 C.
   Keep all descriptions plain, with no percentages and no placeholders in the prose. Mark numbers as placeholders in a YAML comment where needed.
e. spoof event gets a "mode" field: hold (reported is a constant value), offset (reported = true - delta_c), replay (reported replays the earlier REPORTED series from replay_from_h, looping over replay_len_h). For hold and offset the spoofed value still gets the normal sensor noise added (a field "add_noise: true" default). Only the REPORTED series changes; the true series never does. Validate each mode's required parameters.

STEP 4: THE LIVE SIMULATOR WITH INJECTION (simulator/live.py)
Create class LiveSimulator with:
- constructor(scenario_or_freerun, config, seed: int | None). If seed is None, draw one from secrets.randbits(32) and store it in an attribute .seed; the actual seed used is ALWAYS available and printed/recorded so any run can be reproduced.
- step() -> (SensorReading | None, TruthSample | None): None when the scenario has ended (free-run has no end unless max_duration_h is given).
- inject(event: dict | InjectedEvent) -> InjectionResult: apply a fault starting at the CURRENT simulated time. Validate with pydantic; reject unknown types and out-of-range parameters with a clear error (never crash the run). The injectable catalogue is exactly:
    kill_cooling                      (cooling_factor -> 0)
    derate_cooling   factor           (0.0..1.0)
    restore_cooling                   (cooling_factor -> 1)
    open_door        duration_min, power_w (default door_default_power_w)
    heat_soak        delta_c, duration_h, ramp_h (ambient offset ramps up, holds, ramps down)
    cold_snap        delta_c (negative), duration_h, ramp_h
    spoof_sensor     mode (hold | offset | replay) plus that mode's parameters, optional duration_min (otherwise until stopped)
    stop_spoof
    glitch_spike     value_c (applies to exactly the next reported sample)
    shock            peak_g (applies to exactly the next shock sample)
  Each injection gets an id, the simulated time it began, origin "injected", and appears in TruthSample.active_event_ids while active, and in the ground-truth labels afterwards.
- events() returning the history: scheduled events (origin "scheduled"), random free-run events (origin "freerun") and injected ones (origin "injected"), each with start and end sim times.
- A snapshot() method returning plain data (sim time, true temp, compressor_on, cooling_factor, active events) for the future API.
Replacing the old code: simulator/simulate.py's batch function must become a thin loop that builds a LiveSimulator and calls step() until it returns None. simulator/sim_source.py's SimSource must wrap LiveSimulator and expose inject() too. Remove dead code. There must be one physics path.

STEP 5: FREE-RUN MODE (simulator/freerun.py)
A scenario generator that needs no scenario file: it builds a random "trip" from the seed. Climate profile: random base temperature in a plausible band and random daily swing, random phase. Faults: for each fault type in the injectable catalogue that makes sense to schedule (kill_cooling or derate, open_door, heat_soak, cold_snap, spoof_sensor, glitch_spike, shock), a probability per simulated hour and a duration range, all in config under a clearly marked placeholder block "freerun_*" (placeholder, not sourced [SOURCE NEEDED]). Rules: at most one spoof active at a time; a spoof can only start while a physical fault (cooling loss or heat) is active or has been; some seeds must produce no fault at all. Duration: default 48 h, overridable, or endless when asked. Add the config keys and validate them.

STEP 6: GOLDEN RECORDINGS (data/recordings)
Fixed-seed runs of each of the eight scenarios still produce the committed golden recordings (jsonl + ground_truth json). Regenerate them now (they will change because of the new cooling behaviour). The ground-truth sidecar gets new fields: seed, seed_mode ("fixed" or "random"), resolved event parameters (the actual numbers after range resolution), per-sample compressor_on, cooling_factor, ambient_c, and the event list with origins. Bump the recording schema version string and keep RecordedSource able to read the new version; reading an old version must raise a clear error.
Make sure data/recordings still contains exactly the 8 scenarios x 2 files, byte-identical on a second run.

STEP 7: COMMAND LINE (simulator/cli.py)
Commands, all documented in simulator/README.md:
  python -m simulator generate --all
  python -m simulator generate --scenario <id> [--seed N | --random-seed] [--out-dir DIR]
  python -m simulator freerun [--seed N] [--hours H] [--out-dir DIR]   (writes a recording of a free run)
  python -m simulator live-demo --scenario <id> | --freerun [--seed N] [--speed 60] [--inject "kill_cooling@2h"] 
  The live-demo command prints one readable line per sample (sim time, reported temp, true temp, compressor on/off, active events) in a loop paced by SimClock at the chosen speed, accepts typed injection commands on stdin (e.g. "kill_cooling", "open_door 30", "spoof_sensor hold 5", "stop_spoof") while running, and prints the seed at the start. It is a developer tool for me to SEE the live behaviour; keep it simple and robust (Ctrl+C exits cleanly). Make sure the pacing uses the clock abstraction and that logic tests never sleep.
"generate --all" must use each scenario's fixed seed (golden). --random-seed draws a fresh seed and prints it.

STEP 8: TESTS (write them, run them, they must all pass)
Keep every Phase 1 test that is still meaningful (update those that encoded the old controller). Add tests for:
1. Hysteresis cooling: compressor switches on above the band, off below it, never heats; with constant ambient the true temperature stays inside (setpoint +/- deadband/2 + small tolerance) after warm-up; the number of on/off cycles over 24 h is more than a small number (the baseline no longer flat; assert the standard deviation of the true series is above a small threshold).
2. Step-by-step equals batch: stepping a LiveSimulator to the end gives exactly the same samples as the batch wrapper for the same seed.
3. Fixed seed byte-identical twice; different seeds give different files; random-seed mode records the seed it used and re-running with that seed reproduces the run exactly.
4. Noise stream independence: injecting a fault at step k does not change the noise values at steps after k relative to a run without the injection (compare reported minus true in non-affected channels).
5. Every scenario's "expect" block holds for at least 200 different random seeds per scenario (use a loop; keep the runtime reasonable, shorten with coarse parameters only if needed and say so).
6. Range resolution: values fall inside the declared min/max; invalid ranges (min > max, event outside the trip) are rejected with a clear error.
7. Each injectable event type: works mid-run, takes effect on the next sample, appears in active_event_ids and in the final event history with origin "injected", and the true series responds physically (kill_cooling makes it warm; restore_cooling lets it recover; heat_soak raises it; cold_snap lowers it).
8. Spoof modes: hold, offset and replay alter ONLY the reported series; the true series is identical to a run with no spoof (same seed). Replay mode really repeats earlier reported values.
9. Invalid injections (unknown type, factor 1.7, negative duration, missing mode parameter) are rejected with an error and do not corrupt the run: the next step() works normally.
10. Free-run: deterministic for a fixed seed; across 100 seeds no crash, all readings valid, some seeds with no fault and some with faults; at most one spoof active at once; spoof never starts before any physical fault.
11. RecordedSource reads new-version files; old-version files give a clear error.
12. The committed golden recordings match a fresh regeneration (hash test, as in Phase 1).
Run ruff format, ruff check and scripts\run_checks.py; all five checks must pass. Never edit a test just to make it pass; if a test reveals a real design problem, tell me.

STEP 9: DOCS AND REPORT
- Update simulator/README.md (what the engine does, the injectable catalogue as a table, seed modes, CLI examples) and data/README.md.
- Create docs/03-decisions/decision-0002-live-simulator.md: the decisions in this phase (hysteresis controller, RNG streams, ranges plus expect, one physics path, injection catalogue) with the reasons, in plain language.
- Write docs/02-phase-reports/phase-02a-live-simulator-report.md with: what was built; files created and changed; how to run it; how I check it works (include the live-demo commands); test counts per file; what is real and what is simulated; every placeholder added; every deviation from this prompt and why; assumptions; problems and surprises; measured numbers (cycle period and wobble amplitude of the baseline, noise check, for each scenario the true min and max over a fixed-seed run) labelled as simulation results; numbered open questions; and a suggested next phase.
- Archive this prompt text to docs/06-prompts/phase-02a-prompt.md.
- Do NOT start the dashboard. Do NOT run npm.

FINAL OUTPUT FORMAT
1. A plain-English summary a student can understand.
2. The test summary (paste the run_checks summary line and the pytest count).
3. A paste of a short live-demo session: run live-demo for the reefer_failure scenario for a few simulated hours at high speed and paste ten lines of its output, then do the same with --freerun using a random seed, showing that two runs differ.
4. The list of placeholders.
5. The numbered open questions.
6. ONE block of commit commands (explicit paths) for me to run. I commit once per phase.
Then STOP and wait for my reply. Do not begin Phase 2B.
