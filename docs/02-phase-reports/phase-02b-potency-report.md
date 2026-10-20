# Phase 2B: The potency engine: Report

Date: 2026-10-20. Git commit hash: none yet (the team lead commits). Git tag: none.

Pre-flight: `git status --short` was clean, the log showed Phase 2A committed, and `run_checks.py` showed 5 passed with 182 pytest tests before any change.

## 1. What I was asked to do

Two clean-ups from the Phase 2A review (cargo-area wording, quiet no-ops); then the potency engine: pure functions for Arrhenius acceleration, equivalent reference time, potency, shelf life used and time-weighted mean kinetic temperature; a streaming tracker with the suspect-reading rule; shared test vectors for a later TypeScript port; tests; and a command that replays recordings through the tracker. The dashboard and npm were not touched.

## 2. What I built

New files
- `edge/potency.py`: the pure functions, `PotencyState`, `PotencyTracker`.
- `edge/cli.py`, `edge/__main__.py`: `python -m edge potency --recording FILE | --all`.
- `scripts/make_test_vectors.py`: writes the vectors from the Python code.
- `shared/test-vectors/potency_vectors.json`: 24 kB of vectors.
- `tests/test_potency.py` (66 tests), `tests/test_potency_tracker.py` (31 tests).
- `docs/03-decisions/decision-0003-potency-engine.md`, this report, `docs/06-prompts/phase-02b-prompt.md`.

Changed files
- `simulator/live.py`: `stop_spoof` and `restore_cooling` with nothing to do return an accepted result with a note.
- `simulator/demo.py`: strips a leading byte-order mark from piped input (PowerShell adds one).
- `simulator/scenarios/reefer_failure.yaml`, `heatwave_transit.yaml`, `baseline_ok.yaml`: cargo-area wording, numbers unchanged.
- `simulator/events.py`, `simulator/scenario.py`, `simulator/README.md`: wording ("temperature around the box (the cargo area)"), fault table, no-op note.
- `tests/test_live_simulator.py` (two rejection cases removed, no-op tests added), `tests/test_freerun_and_tools.py` (demo checks the no-op message).
- `edge/README.md`, `shared/test-vectors/README.md`, `scripts/README.md`.

## 3. How to run it

```powershell
$py = "$env:LOCALAPPDATA\potencyguard\venv\Scripts\python.exe"
& $py scripts\run_checks.py
& $py -m edge potency --recording data/recordings/spoof_attempt.jsonl
& $py -m edge potency --all
& $py scripts\make_test_vectors.py        # only after changing the maths or the constants
```

## 4. How to check it works

`run_checks.py` prints five `PASS:` lines. `python -m edge potency --all` prints a two-row table for each of the 8 recordings. For `spoof_attempt` the "from reported readings" row shows about 48 h and the "from true temperature" row about 342 h.

## 5. Test results

- `run_checks.py`: 5 passed, 0 failed.
- pytest: 279 passed, 0 failed, 0 skipped. Per file: test_box_simulator 21, test_freerun_and_tools 24, test_live_simulator 35, test_potency 66, test_potency_tracker 31, test_scenarios 64, test_sensor_interface 32, test_smoke 6.
- The documents' worked examples match at the stated precision (checked before any code was written and again in tests).

## 6. What is real and what is simulated

Real code: all potency maths, the tracker, the vector generator, the replay command. Simulated: every temperature the tracker sees comes from the box simulator. Potency is a model output for an imaginary product with assumed constants; no real product was measured. Results below are simulation results on a synthetic box.

## 7. Decisions I made and why

1. **Location:** `edge/potency.py`. The brief's folder layout lists "potency" under `edge/`, so I did not need to ask.
2. **Test-vector folder:** the repo already has `shared/test-vectors/` (hyphen, from amendments A11 and A12 and Phase 0). The prompt wrote `shared/test_vectors/`. I used the existing hyphen folder. A Python-style underscore name is not needed because the folder holds only JSON.
3. **Right-endpoint integration:** as the prompt says; the brief has no rule. A constant temperature gives the same answer under any rule, so the worked examples are unaffected.
4. **Suspect-reading rule:** as the prompt describes; the brief says only that a single extreme reading is suspect and excluded, and that quarantine needs consecutive samples (amendment A5). Hold-last-valid and the retroactive correction fill the gaps. The undecided intervals are kept in a pending list and committed only when decided, so no sum is ever subtracted.
5. **Extra field:** `PotencyState` also carries `effective_temp_c` (the temperature actually used for the latest interval). `current_af` and the projection use it, so they are `None` until a valid temperature exists.
6. **Extra method:** `PotencyTracker.update_sample(t_s, temp_c)` is the core and `update(reading)` calls it. It lets the true series be analysed without building fake readings.
7. **MKT:** computed with a scaled log-sum-exp to avoid underflow. Plain left-to-right sums elsewhere, so a TypeScript port can match.
8. **Helper from the prompt:** `hours_to_min_potency_at_temp` is not in the brief. The brief defines the remaining life at the reference temperature, L_rem = tau_max - tau_eq; the helper is L_rem divided by AF.
9. **Step 1b:** the command parser only turns text into a command, so it needed no change. The no-op results come from the simulator and the live demo prints their message.
10. **Step 1a:** `description` and `title` are not stored in recordings or ground-truth files, so **no committed recording changed**. I checked with `generate --all` and `git status`.
11. **Kinetic constants** are unchanged and already validated by the config loader (Ea/R > 0, tau_max > 0, 0 < P_min < 1, low < T_ref < high, confirmation count >= 1). I added tests for those.

## 8. Assumptions and unverified claims introduced

- The kinetic constants remain product defaults from the team document for an imaginary vaccine.
- Right-endpoint integration and the retroactive-correction rule are my modelling choices (section 7).
- Vector temperatures and sequences in `scripts/make_test_vectors.py` are hand-designed for coverage, not realistic.
- No external statistics were added. No new placeholders were needed.

## 9. Problems and surprises

**A requirement in the prompt cannot hold, so I changed what the test asserts and I am telling you.** The prompt asked for a test that "reefer_failure true potency falls below P_min". With these constants potency equals P_min exactly when 100 percent of the shelf life is used (that is how k_ref is defined). The worst scenario, `reefer_failure`, uses only 8.88 percent of the shelf life (true potency 99.07 percent). The tracker's `below_min_potency` is therefore false for every golden recording. I did not change any constant or scenario. The test instead asserts that the failure uses more than ten times the baseline's shelf life, has lower potency than the baseline and is a confirmed excursion. This is open question 1.

Smaller points:
- The `spoof_attempt` potency gap between true and reported is real but small in potency terms (0.177 percentage points); in shelf-life terms it is 1.952 percent against 0.274 percent.
- In `spoof_attempt` the last sample (t = 36 h) is outside the spoof window, so the reported series ends with one true-looking warm reading.
- In `freeze_event` the cold readings add almost no damage in the Arrhenius model (cold slows kinetics). Freezing harm is not modelled; it is caught only by the hard-limit rule, as the brief says.
- PowerShell adds a byte-order mark to piped text; the live demo now strips it.
- No OneDrive or sync problems.

## 10. Numbers measured (simulation results, synthetic box, golden recordings at their fixed seeds)

Final values at the end of each recording. "Used" is the percent of the 24 month shelf life.

| Scenario | Reported tau_eq (h) | Potency % | Used % | MKT (C) | True tau_eq (h) | Potency % | Used % | MKT (C) |
|---|---|---|---|---|---|---|---|---|
| baseline_ok | 48.05 | 99.971 | 0.274 | 5.01 | 48.07 | 99.971 | 0.274 | 5.01 |
| door_open_excursion | 35.29 | 99.979 | 0.201 | 8.01 | 35.31 | 99.979 | 0.202 | 8.02 |
| freeze_event | 17.21 | 99.990 | 0.098 | -0.59 | 17.22 | 99.990 | 0.098 | -0.59 |
| heatwave_transit | 480.28 | 99.712 | 2.741 | 20.50 | 480.02 | 99.712 | 2.740 | 20.50 |
| reefer_failure | 1555.97 | 99.069 | 8.881 | 37.55 | 1555.31 | 99.069 | 8.877 | 37.54 |
| sensor_glitch | 24.04 | 99.986 | 0.137 | 5.01 | 24.01 | 99.986 | 0.137 | 5.00 |
| shock_drop | 24.00 | 99.986 | 0.137 | 5.00 | 24.01 | 99.986 | 0.137 | 5.00 |
| spoof_attempt | 48.06 | 99.971 | 0.274 | 7.25 | 341.98 | 99.795 | 1.952 | 23.58 |

Samples excluded: 1 for the reported `sensor_glitch` series, 0 everywhere else. No recording ends below P_min. Worked examples from the code: 8 h at 12 C gives AF 2.41709, tau_eq 19.3367 h, 0.11037 percent; 24 h at 30 C gives AF 19.3919, tau_eq 465.405 h, 2.65642 percent.

## 11. Open questions for the decision-maker

1. Potency drops below P_min only after 100 percent of the shelf life is used, so no demo scenario ever shows "below minimum potency". Options: (a) show "shelf life used" as the headline number and treat P_min as the end of life; (b) add longer or hotter scenarios (for example several days at 40 C or more); (c) revisit the product constants (for example a shorter shelf life or a lower P_min), which are your decision. My recommendation is (a), with (b) for one dramatic scenario.
2. Is the right-endpoint rule fine, or do you want a trapezoid rule? (A trapezoid needs the previous temperature too and changes the numbers slightly.)
3. Should a lone suspect reading that is later recovered keep counting in "samples excluded" (now) or be reported separately as "glitches"?
4. The brief's "L_rem" and my `hours_to_min_potency_at_temp` overlap. Do you want the helper kept for the planner?

## 12. Suggested next phase

Phase 3 (thermal twin, calibration, detectors) can start: the recordings carry ground-truth events and the tracker now provides the potency numbers the detectors will protect. The TypeScript mirror (Phase F2) must reproduce `shared/test-vectors/potency_vectors.json`. Not started.
