PHASE 3: THE THERMAL TWIN, CALIBRATION AND TAMPER DETECTORS (plus a simulator extension: ambient and cooling-duty channels, and a last-sample fix)

READ FIRST, ASSUME NOTHING
1. Read CLAUDE.md, then docs/00-project-brief/master-brief.md in full (section 3.3 on the thermal twin and detectors especially, and all amendments at the end), then docs/01-architecture/frontend-vision.md, then every phase report in docs/02-phase-reports/ and every decision record in docs/03-decisions/.
2. Read before changing: edge/*.py, simulator/*.py (engine.py, live.py, scenario.py, events.py, truth.py, recording.py, expectations.py, freerun.py, commands.py, demo.py), simulator/scenarios/*.yaml, shared/config.py, config/*.yaml, data/recordings/*, tests/*, scripts/*.
3. If anything in this prompt conflicts with the brief or existing code, STOP and tell me the exact conflict. If anything is ambiguous, ASK before writing code. Never guess numbers, field names, file names or folder locations.

WHY THIS PHASE EXISTS
The strongest claim of PotencyGuard is physics-based tamper detection: a reported temperature that the box could not physically have produced is flagged. This phase builds (a) the extra sensor channels the physics needs, (b) a thermal twin with a calibration routine, (c) four detectors, (d) a streaming monitor that classifies what it sees, and (e) an evaluation harness that MEASURES detection delay and false alarms over hundreds of runs, including runs where the real box differs from the twin's model. The numbers must be honest: the twin and the simulator use the same family of equations, so we also test mismatch and we say so.

ABSOLUTE RULES
- NEVER run git add, git commit, git tag or git push. At the end print ONE block of commands for me to run (explicit paths only, never "git add -A" or "git add ."), one commit message, no co-author trailers or attribution lines.
- NEVER run npm install or npm ci. Do not touch the dashboard at all.
- No new Python packages. Use numpy, pydantic, pyyaml, pytest, ruff and the standard library.
- No external statistics anywhere (code, comments, YAML, docs). Every invented number is labelled "placeholder, not sourced [SOURCE NEEDED]".
- No wording that claims hardware or SAP is real. The "source" field of readings stays "sim". No UI wording in this phase.
- No "first", "unique" or "novel" claims in any file.
- Files UTF-8 without BOM, LF line endings, written with .NET file writes (not Set-Content).
- Never edit a test just to make it pass. When the schema or recordings change, update only the numbers or fields that legitimately changed, list every such test with the reason in the report, and STOP and tell me if a change is not explained by this prompt.
- The calibration data must NEVER be the data used to score detectors. Enforce this in code (distinct seeds, distinct files) and in a test.

STEP 0: PRE-FLIGHT (read-only)
git status --short and git log --oneline -5. Phase 2D must be committed; if tracked files are modified, STOP and tell me. Run scripts\run_checks.py: expect 5 passed and 339 tests.

STEP 1: SIMULATOR EXTENSION (new sensor channels, last-sample fix)
a. New OPTIONAL fields on SensorReading (edge/sensor_reading.py): ambient_c (float or None; measured temperature around the box, the "cargo area" temperature; validate a sane range, say -60 to 80 C) and cooling_duty (float or None; the fraction 0..1 of the last sample interval during which the cooling unit's compressor was running). They default to None so Phase 1 to 2D code keeps working; the twin REQUIRES them.
b. The engine (simulator/engine.py) computes cooling_duty exactly as the fraction of internal substeps in the sample interval during which compressor_on was true (document the definition). ambient_c is the true ambient plus Gaussian sensor noise with a new config key sensor_sigma_ambient_c (placeholder 0.1, not sourced [SOURCE NEEDED]). The ambient noise MUST come from a NEW, separate random stream added by extending the SeedSequence spawn (spawn children keep earlier children identical), so that the existing temperature, humidity and shock noise values do NOT change for any seed. Verify this explicitly: after the change, the temp_c/rh_pct/shock_g columns of every existing golden recording must be unchanged except where Step 1c legitimately changes them. State the check you ran.
c. Last-sample fix: an event whose end equals the trip duration must also cover the final sample (today it does not, so for example a "lasts to the end" spoof leaves one true-looking reading at the end). Implement the minimal change that does this for all scheduled event types and for injected events with no explicit duration; document the rule in simulator/README.md and decision record. Expected legitimate effects: the last sample of spoof_attempt, reefer_failure, heatwave_transit and hidden_spoilage may change (and the potency numbers that depend on them). Report exactly which recordings and which values changed.
d. The spoof event affects ONLY temp_c. ambient_c and cooling_duty stay honest. Add this to the threat model section of the docs: "the attacker tampers with the box thermistor only".
e. TruthSample and the ground-truth sidecar get the new channels and the label timeline needed for scoring: for every spoof/glitch/ambient event keep start and end times; add a derived field first_divergence_s (first time |reported - true| exceeds a divergence threshold, config key detect_divergence_c, placeholder 1.0 C) for scenarios with a spoof.
f. Bump the recording schema version (0.3) and keep RecordedSource reading 0.2 files with ambient_c and cooling_duty = None, or refuse them with a clear message (choose and tell me which). Regenerate the golden recordings. Update the committed-recordings hash test.
g. Update every test and number affected (potency expectations for the changed recordings, crossing hours, vector files if tracker vectors depend on recordings (they should not), CLI tests, study document if it is regenerated by tests). List them all in the report.

STEP 2: THE THERMAL TWIN (new file edge/thermal_twin.py)
Model (brief section 3.3), in terms the edge can observe:
  T_inf[n] = T_amb[n] - dT_cool * u[n],   u[n] = cooling_duty of the interval,   dT_cool = R_th * Q_cap (kelvin; the largest temperature depression the cooling unit can produce relative to ambient).
  T_pred[n+1] = T_inf[n] + (T[n] - T_inf[n]) * exp(-dt / tau)
Use the measured (reported) T[n] and the measured ambient and duty of the interval ending at n+1 (state clearly in the docstring which sample's inputs drive which interval; the engine's duty at a sample describes the interval just ended). Parameters: tau (hours), dT_cool (kelvin), sigma_r (residual standard deviation). Pure, frozen pydantic model TwinParams; function predict_next(T_n, T_amb, duty, dt_s, params). Validate inputs (finite, dt > 0, 0 <= duty <= 1).
Also provide physical bounds used by the detectors:
  - max_step_bound(T_n, T_amb, dt_s, params): the largest |dT| physically possible in one step, from the brief's non-physical jump bound |dT| <= |T_inf,max - T_n| * (1 - exp(-dt/tau)), where T_inf,max is the farthest equilibrium reachable (ambient with no cooling, or ambient minus dT_cool with full cooling), take the larger distance; add a tolerance of a few sigma_r for noise.
  - floor_bound(T_amb, params) = T_amb - dT_cool (the coldest steady temperature full cooling can reach at this ambient; also the brief-derived "impossible state" limit). This is an ADDITION of mine to the brief: flag it as such in the docstring and the decision record.

STEP 3: CALIBRATION (new file edge/calibration.py)
Estimate TwinParams from a calibration run (list of readings carrying ambient_c and cooling_duty) by ordinary least squares:
  T[n+1] = a*T[n] + b*T_amb[n] + c*u[n] + d, with theory a = exp(-dt/tau), b = (1 - a), c = -(1 - a)*dT_cool, d = 0.
Fit with numpy.linalg.lstsq; derive tau = -dt / ln(a) and dT_cool = -c / (1 - a). Report goodness-of-fit and consistency checks (b close to 1 - a, d close to 0); sigma_r = standard deviation of the residuals on the calibration data. State in the docstring and decision record the known weakness (noise in the regressor T[n] biases a slightly toward zero: quantify it on the synthetic data in the report). Reject calibration runs that are too short, too flat (no excitation of ambient or cooling: condition number check) or that contain tamper labels. Provide calibrate_from_recordings(paths) that refuses any recording whose scenario id is in the evaluation set.
Calibration data: generate a dedicated calibration set with the simulator, NOT the golden recordings: for example 5 runs of the baseline scenario and 5 of a "door_open_excursion"-like clean scenario with seeds 9001 to 9010 (random seed mode off, fixed seeds), written under data/calibration/ and committed (small), plus a generator command python -m simulator generate-calibration. Calibrate once, store the fitted TwinParams in config/twin_calibrated.yaml with a header "fitted from data/calibration/, simulation only" and read it from there; the fitting date and the seed list go in the file.

STEP 4: DETECTORS AND MONITOR (new file edge/tamper_monitor.py)
Streaming class TamperMonitor with update(reading) -> MonitorState (frozen pydantic): t_s, residual_c, residual_sigma (residual/sigma_r), cusum_pos, cusum_neg, and four detector flags, plus an overall verdict and the verdict history. Detectors:
 1. CUSUM drift detector (brief): two-sided, S+_n = max(0, S+_{n-1} + r_n/sigma_r - k), S-_n likewise for -r_n; alarm when either exceeds h. (The brief writes |r|; two sided gives the sign, which classification needs. Say so in the decision record.) Defaults k and h are PROPOSE items: choose them by the sweep in Step 6, record the chosen values in config with the placeholder label, and report the sweep.
 2. Impossible-step detector (brief): flag when |T_meas[n+1] - T_meas[n]| exceeds max_step_bound.
 3. Impossible-state detector (my addition): flag when the reported temperature stays below floor_bound(T_amb) - margin for m consecutive samples (margin and m placeholders in config, labelled; margin a few sigma_r; m small). Include the symmetric ceiling check only if the physics supports one (a box cannot be hotter than ambient plus the heat a door-open load can add; since heat loads are not observed, do NOT include a ceiling; say so).
 4. Flat-line detector (brief): flag when the reported temperature over a window of w samples has a standard deviation far below what the sensor noise alone would give (use sigma_sensor from config times a factor; window and factor placeholders in config, labelled). Note that the Phase 2A spoof modes add noise, so this detector is expected to catch only crude freezes; report that honestly.
 Classification (document the rules in the decision record, implement as a small table):
   - residual consistently POSITIVE (reported warmer than the twin predicts) with no impossible-step/state flag: "thermal anomaly: cooling shortfall or door open" (a physical event, not tamper);
   - residual consistently NEGATIVE (reported colder than predicted), or any impossible-step or impossible-state flag, or a flat line: "reported value inconsistent with the physics: suspected falsification or sensor fault";
   - a lone isolated impossible step followed by immediate recovery: "sensor glitch" (this must agree with the PotencyTracker's suspect-reading rule; reuse its limits and confirmation count where that makes sense, and explain the relationship).
 The monitor never sees ground truth. It consumes readings (with ambient_c and cooling_duty). If a reading lacks them, raise a clear error.
 Warm-up: define how many samples the monitor needs before it can alarm (the first sample has no previous state); document.
 Provide reset() and snapshot().

STEP 5: A COMMAND TO SEE IT
Add: python -m edge twin --recording FILE [--verbose]. It replays a recording through TamperMonitor and PotencyTracker together and prints, per ~12 samples (or every verdict change), a readable line: sim hour, reported temp, twin prediction, residual in sigma units, flags, verdict, potency %. Then a summary: first alarm time per detector, the verdict timeline (start hour to end hour per verdict), and, using the ground-truth sidecar, the true divergence start and the detection delay in minutes and samples. Footer: "Simulation result on a synthetic box. Not real-world evidence." Add --all for a compact one-line-per-recording summary.

STEP 6: EVALUATION HARNESS (new file scripts/evaluate_detectors.py)
Measure, with the real simulator, the real monitor and the stored calibration:
 a. Parameter sweep for CUSUM k and h (small grid, e.g. k in {0.25, 0.5, 1.0}, h in {4, 8, 12}) on a CLEAN training set of runs that is separate from both the calibration seeds and the final test seeds (e.g. seeds 10001 to 10100): report false alarms per 1000 simulated hours and the median detection delay on spoof scenarios from the same training seeds; choose k and h by a stated rule (for example: false alarms below a stated target per 1000 h, then the smallest delay) and write the chosen values and the target to config as labelled placeholders. The rule and the sweep table go in the report.
 b. Final evaluation on fresh seeds (e.g. 20001 to 20200, never used above): for each scenario family with a physical or tamper event, per detector and for the combined monitor: detection rate (fraction of runs flagged at all), detection delay measured from first_divergence_s (median, 90th percentile, in minutes and samples), and false alarm counts on the clean families (baseline_ok, shock_drop, sensor_glitch, door_open_excursion; for door_open the correct verdict is "thermal anomaly", not tamper: count a tamper verdict there as a false positive). Also report, for each tamper family, the share of runs in which the verdict was the correct class.
 c. Spoof families to include: spoof_attempt (hold), hidden_spoilage (hold, slow), plus runs made by injecting offset and replay spoofs through LiveSimulator.inject at random times (the harness generates these itself, seeds listed), plus a "hold at a value equal to the true temperature" control that SHOULD NOT be detectable until divergence (a harmless lie).
 d. MISMATCH ROBUSTNESS: repeat the final evaluation with the simulated box deliberately different from the twin's calibration: build BoxConfig variants in memory (dataclasses.replace) with box_tau_h and R_th/capacity scaled by +15 percent and -15 percent, and with sensor_sigma_ambient_c doubled; keep the twin calibrated on the nominal calibration set. Report how detection rate, delay and false alarms change. This is the honest answer to "the twin and the simulator share equations".
 e. Print compact tables and write them to docs/02-phase-reports/phase-03-evaluation.md (plus data/generated/evaluation.json, git-ignored). Everything is labelled "Simulation result on a synthetic box. Not real-world evidence." The harness must be deterministic (fixed seeds) and finish in a reasonable time (state the runtime; if the full run takes more than about 3 minutes, provide a --quick option and use it in tests).

STEP 7: TESTS (write, run; all must pass)
 1. Channels: ambient_c and cooling_duty validation; engine duty equals the exact substep fraction; hand-checked on a tiny scenario; determinism; the independence check from Step 1b (temp/rh/shock columns unchanged for several seeds versus the previous schema in runs with no end-of-trip event).
 2. Last-sample fix: an event ending at the trip duration covers the final sample; an event ending earlier does not; injected open-ended events cover subsequent samples.
 3. Twin: predict_next matches the closed form; with exact parameters and no noise the residuals of a clean run are ~0 (use a noise-free configuration); bounds behave (max_step_bound shrinks when T_n is near the equilibrium); floor_bound value.
 4. Calibration: recovers tau and dT_cool within a stated tolerance on a noise-free run and within a looser tolerance on a noisy run; rejects short, flat and tamper-labelled input; refuses evaluation recordings; the fitted config file loads.
 5. Detectors, on synthetic hand-built sequences: CUSUM stays quiet on pure noise and fires on a sustained bias of the stated size within the expected number of samples; impossible step fires on a jump beyond the bound and not below it; impossible state fires only after m consecutive samples below the floor; flat-line fires on a frozen sensor and not on noisy data; classification table: positive residual drift is "thermal anomaly", negative drift is "suspected falsification", a lone impossible step with immediate recovery is "sensor glitch".
 6. Monitor on golden recordings: baseline_ok, shock_drop and sensor_glitch produce no tamper verdict (sensor_glitch yields the glitch verdict at most once); reefer_failure and door_open_excursion produce "thermal anomaly" and never "suspected falsification" at the golden seeds; spoof_attempt and hidden_spoilage produce "suspected falsification" within a stated number of samples of the first divergence at the golden seeds (set the bound from the measured delay plus a small margin and explain).
 7. Evaluation harness: --quick mode runs in tests, is deterministic (two runs identical), calibration seeds are disjoint from training and test seeds (assert on the seed lists), the chosen k and h are read from config.
 8. CLI: the twin command prints the summary and footer; --all prints one line per recording (nine recordings).
Run ruff format, ruff check and scripts\run_checks.py: all five checks must pass.

STEP 8: DOCS AND REPORT
- docs/03-decisions/decision-0005-thermal-twin-and-detectors.md: model, channels, threat model (box thermistor only; a coordinated multi-channel forgery is out of scope for physics and left to signatures and hardware), calibration method and its weakness, the four detectors, the classification table, the additions to the brief (two-sided CUSUM, floor bound), how k and h were chosen, the last-sample fix, plain language.
- Append an amendment to docs/00-project-brief/master-brief.md in the existing amendment format covering the new channels and the additions.
- Update READMEs: edge, simulator, data (calibration folder), scripts, config.
- Write docs/02-phase-reports/phase-03-twin-and-detectors-report.md with the usual sections plus: every changed test with the reason; the sweep table; the final evaluation tables; the mismatch tables; limitations written plainly (shared equations; ambient and duty channels assumed honest; flat-line weakness; no humidity or shock physics); numbered open questions; suggested next phase.
- Archive this prompt verbatim to docs/06-prompts/phase-03-prompt.md.

FINAL OUTPUT FORMAT
1. A plain-English summary a student can read (what the twin is, what each detector catches, what the numbers say).
2. The test summary (run_checks summary line, pytest count, per-file counts).
3. Paste: python -m edge twin --recording data/recordings/hidden_spoilage.jsonl (ten lines and the summary), the same for spoof_attempt.jsonl, and python -m edge twin --all.
4. Paste the sweep table, the final evaluation tables and the mismatch tables (compact).
5. The list of placeholders and assumptions, and the list of tests changed with reasons.
6. The numbered open questions.
7. ONE block of commit commands (explicit paths, including data/calibration/, new recordings and config/twin_calibrated.yaml).
Then STOP and wait. Do not begin Phase 4.
