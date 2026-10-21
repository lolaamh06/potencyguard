PHASE 2B: THE POTENCY ENGINE (kinetics, MKT, suspect-reading rule, shared test vectors) + TWO CLEAN-UPS

READ FIRST, ASSUME NOTHING
1. Read CLAUDE.md, then docs/00-project-brief/master-brief.md in full (including the amendments at the end), then docs/01-architecture/frontend-vision.md, then docs/02-phase-reports/phase-02a-live-simulator-report.md and docs/03-decisions/decision-0002-live-simulator.md. Then read these code files before changing or relying on them: shared/config.py, config/product_default.yaml, edge/sensor_reading.py, simulator/engine.py, simulator/live.py, simulator/commands.py, simulator/scenario.py, simulator/scenarios/*.yaml, simulator/recording.py, edge/recorded_source.py.
2. If anything in this prompt conflicts with the brief, CLAUDE.md or the existing code, STOP and tell me the exact conflict. Do not pick a side. The brief wins over this prompt on any maths detail; report every difference.
3. If any detail is missing or ambiguous, ASK me before writing code. Never guess numbers, field names, file names or folder locations. If the brief does not say where the potency code lives, propose edge/potency.py and ask before creating it.

WHY THIS PHASE EXISTS
PotencyGuard decides whether a medicine consignment is still good. The core quantity is REMAINING POTENCY, computed from the temperature history by first-order degradation kinetics with an Arrhenius temperature dependence. This phase builds that engine as pure, well-tested Python, plus a streaming tracker that the edge program will call once per reading, plus machine-readable TEST VECTORS that a later TypeScript port in the dashboard must reproduce exactly.

ABSOLUTE RULES
- NEVER run git add, git commit, git tag or git push. At the end print ONE block of commands for me to run (explicit paths only, never "git add -A" or "git add ."), one commit message, no co-author trailers or attribution lines.
- NEVER run npm install or npm ci. Do not touch the dashboard folder at all in this phase (the dashboard junction is fragile).
- No new Python packages. Use only what is installed (numpy, pydantic, pyyaml, pytest, ruff) and the standard library.
- No external statistics anywhere (code, comments, YAML, JSON, docs). Where a number needs a source, mark it "placeholder, not sourced [SOURCE NEEDED]". The kinetic constants (Ea/R, T_ref, tau_max, P_min) already exist in config as product defaults from the team's document: do not change their values, and do not claim they are measured facts.
- No wording that claims hardware or SAP is real. The "source" field of every reading stays "sim" in this phase.
- No "first", "unique" or "novel" claims in any file.
- All files UTF-8 without a byte-order mark, LF line endings. Use .NET file writes, not Set-Content, for files written from PowerShell.
- Never edit a test just to make it pass. If a test exposes a real design problem, tell me.

STEP 0: PRE-FLIGHT (read-only)
Run git status --short and git log --oneline -5. Phase 2A should be committed. If git status shows uncommitted changes to tracked files, STOP and tell me. Run scripts\run_checks.py and confirm 5 passed (182 pytest tests) before touching anything. Report the result in one line, then continue.

STEP 1: TWO SMALL CLEAN-UPS FROM THE PHASE 2A REVIEW
a. Scenario wording. In simulator/scenarios/reefer_failure.yaml (and any other scenario whose prose or YAML comments talk about very hot "outside" or "ambient" air to justify 46-50 C peaks, check them all), describe the hot temperature as the temperature of the cargo area (for example a sun-heated closed cargo space). Keep the numbers unchanged. If the description text is stored in recording headers or ground-truth files, regenerate the golden recordings with python -m simulator generate --all and tell me which files changed and why. If nothing in the committed recordings changes, say so.
b. Quiet no-ops. stop_spoof with no spoof active, and restore_cooling with nothing to restore, must now return an ACCEPTED result with a short note in the message (for example "nothing to stop") and change nothing. Update the command parser, the live-demo output and the documentation (simulator/README.md fault table) and update the Phase 2A tests that expected a rejection. Other invalid injections (unknown type, out-of-range value, missing parameter) must still be rejected exactly as before.

STEP 2: CONFIG CHECK (shared/config.py, config/product_default.yaml)
Read how ProductConfig exposes the kinetic constants (Ea/R in kelvin, T_ref in C, tau_max in hours, P_min, hard limits low/high in C, the number of consecutive samples that confirm a hard-limit breach). Do not rename or change existing keys. If any constant the maths needs is not in ProductConfig, STOP and ask. Add validation if missing: Ea/R > 0, tau_max > 0, 0 < P_min < 1, low limit < high limit, confirmation count >= 1. Derived constant: k_ref = ln(1 / P_min) / tau_max (per hour). Expose it as a computed property or a function, not a stored duplicate.

STEP 3: PURE POTENCY FUNCTIONS (new module, location as agreed in the READ FIRST step; suggested edge/potency.py)
Implement, with full docstrings that state units, using plain floats (no hidden rounding), with the exact formulas below. All temperatures enter in Celsius and are converted to kelvin by adding 273.15 inside the functions.
1. arrhenius_acceleration_factor(temp_c, cfg) = exp( (Ea/R) * (1 / T_ref_K - 1 / T_K) ). Must equal exactly 1.0 at T_ref (within floating error) and be greater than 1 above T_ref and less than 1 below.
2. equivalent_reference_time_h(temps_c, dts_h, cfg) = sum over i of AF(T_i) * dt_i  (dt in hours; this is tau_eq).
3. potency_from_tau_eq(tau_eq_h, cfg) = exp( - k_ref * tau_eq_h ).
4. shelf_life_used_fraction(tau_eq_h, cfg) = tau_eq_h / tau_max. (The documents' "0.110%" and "2.66%" are this value times 100.)
5. time_weighted_mkt_c(temps_c, dts_h, cfg) = mean kinetic temperature in Celsius:
     T_MKT_K = (Ea/R) / ( - ln( sum_i w_i * exp( - (Ea/R) / T_i_K ) ) ),  w_i = dt_i / sum(dt).
   Return Celsius. Guard against empty input, zero total duration, and numerical underflow (state in the docstring what you do).
6. hours_to_min_potency_at_temp(tau_eq_h, temp_c, cfg) = max(0, (tau_max - tau_eq_h)) / AF(temp_c). This is the projected number of hours until potency reaches P_min if the box stayed at temp_c from now on. (This is an addition of mine for the later planner; label it clearly in the docstring as a derived helper, not from the brief, and tell me in the report if the brief already defines something equivalent.)
Validation: reject NaN, infinity, non-positive absolute temperature, negative dt, mismatched list lengths, with clear ValueError messages. Zero dt is allowed and contributes nothing.

STEP 4: THE STREAMING TRACKER WITH THE SUSPECT-READING RULE (same module or a sibling file)
Create class PotencyTracker. It receives one SensorReading at a time via update(reading) and returns a frozen PotencyState (pydantic model) containing: t_s, tau_eq_h, potency (0..1), shelf_life_used_fraction, mkt_c (over all accepted time so far; None until time has elapsed), current_af, hours_to_min_potency_at_current_temp, status (one of "ok", "suspect", "excursion_confirmed"), below_min_potency (bool, true when potency < P_min), samples_seen, samples_excluded.
Integration method: each sample i (after the first) covers the interval from the previous sample time to this sample time, dt = t_i - t_{i-1} converted to hours, integrated with the temperature of the sample at the END of the interval (right-endpoint rule). Document this choice in the docstring and in the decision document, and check that the brief's worked examples (constant temperature over a duration) are not affected by the choice. If the brief specifies a different rule (left-endpoint, trapezoid), the brief wins: tell me.
Hard-limit rule from the brief: a reading outside [low, high] is "suspect" the first time. A single suspect reading is EXCLUDED from the maths: its interval is integrated using the last accepted (valid) temperature instead (hold-last-valid), it increments samples_excluded, and state.status is "suspect". If the NEXT reading is also outside the limits (the confirmation count is 2 in the default config; read it from config, do not hard-code 2), the breach is CONFIRMED: status becomes "excursion_confirmed", and the earlier suspect reading is retroactively counted as valid (its interval recomputed with its own temperature), because two consecutive out-of-range readings are no longer a lone glitch. A reading back inside the limits after a lone suspect clears the status to "ok". After a confirmed excursion, status stays "excursion_confirmed" until readings return inside the limits, then it returns to "ok" (the excursion remains in the tau_eq it already added). Implement this as a small, clearly documented state machine, with the retroactive correction done exactly (no double counting).
If the brief says something different about excluded readings or confirmation, the brief wins: describe the difference in the report.
The tracker must reject readings whose time goes backwards (ValueError) and must allow dt = 0. It must be deterministic and must not read wall-clock time or use randomness. Provide reset() and a snapshot() that returns the current PotencyState without a new reading.
The tracker consumes the REPORTED reading only (it never sees ground truth).

STEP 5: SHARED TEST VECTORS (machine-readable, for the later TypeScript port)
Create shared/test_vectors/ (check the repo layout for an existing shared folder convention; if none, ask) with potency_vectors.json produced by a small script scripts/make_test_vectors.py (so the file can be regenerated and the test can compare the committed file to a fresh generation). Contents:
- "meta": schema version, the constants used (Ea/R, T_ref_c, tau_max_h, P_min, limits, confirmation count) read from config, and a plain note that all values are computed by the Python reference implementation.
- "af_cases": a list of {temp_c, expected_af} for temperatures -10, 0, 2, 5, 8, 12, 20, 25, 30, 40 (unrounded floats).
- "tau_cases": the two worked examples from the team document: 8 h at constant 12 C and 24 h at constant 30 C, plus 3 more hand-designed profiles (a two-step profile, a ramp described as many small steps, a profile with uneven dt). Each gives inputs (temps list, dts_h list) and unrounded expected tau_eq_h, potency, shelf_life_used_fraction, mkt_c.
- "tracker_cases": at least 6 reading sequences (lists of {t_s, temp_c}) with the expected final PotencyState fields AND the expected status after every sample, covering: a clean run, a lone glitch (exactly one out-of-range sample), a confirmed 2-sample high excursion, a confirmed 2-sample low excursion (freeze), a lone glitch followed by recovery, and a glitch as the very last sample.
All expected numbers are generated by the Python reference code, never typed by hand, EXCEPT the documents' rounded worked-example values, which go in a separate "document_checks" list as {description, expected_rounded, rounding_decimals} so tests can check the reference code matches the team document to the document's own precision. The worked-example oracles are: 8 h at 12 C gives AF about 2.417, tau_eq about 19.34 h, about 0.110 percent of shelf life; 24 h at 30 C gives AF about 19.39, tau_eq about 465.4 h, about 2.66 percent of shelf life. Compute them from the code and compare to these rounded values at the stated precision; if any of them does NOT match, STOP and tell me, do not adjust anything.

STEP 6: TESTS (write, run, all must pass)
In tests/test_potency.py (and tests/test_potency_tracker.py if clearer):
1. Document checks: the worked examples match the rounded values at the documents' precision (use unrounded computation).
2. AF properties: AF(T_ref) = 1; strictly increasing in temperature; AF < 1 below T_ref; matches the closed form at several temperatures.
3. tau_eq: additivity (splitting one interval into two equal halves at the same temperature gives the same tau_eq within float error); non-decreasing as readings are added; zero dt contributes nothing; scaling all dts by a factor scales tau_eq by the same factor.
4. Potency: P(0) = 1; P strictly decreases with tau_eq; P at tau_eq = tau_max equals P_min within float error (this checks k_ref); P in (0, 1].
5. MKT: constant temperature gives that temperature; MKT >= time-weighted arithmetic mean (strict for varying temperatures); MKT lies between min and max; weighting by dt works (a long cool stretch plus a short hot burst vs the reverse); empty input and zero duration raise clear errors; very large and very small inputs do not produce NaN.
6. Validation errors for NaN, inf, negative dt, mismatched lengths.
7. Tracker, using the shared test vectors: after every sample the status matches; final states match to a tight tolerance (relative 1e-12); the committed JSON file equals a fresh regeneration.
8. Tracker suspect-reading rule: lone glitch is excluded (final tau_eq equals the run without the glitch sample's temperature effect, using hold-last-valid) and samples_excluded = 1; two consecutive out-of-range samples confirm the excursion and the earlier one is counted exactly once (no double counting; compare to a hand-computed value); the confirmation count is read from config (change it to 3 in a test config and show it takes 3 samples); status returns to "ok" after recovery; reset() works; time going backwards raises.
9. Tracker vs pure functions: for a clean sequence, the tracker's final tau_eq and mkt equal the pure functions' results (right-endpoint rule).
10. The two clean-ups from Step 1: stop_spoof and restore_cooling no-ops are accepted with a note and change nothing; other invalid injections are still rejected.
11. Recordings: run the tracker over each of the 8 golden recordings (reported series) and over the TRUE series from the ground-truth files; assert the basic expectations: baseline_ok potency stays above P_min and tau_eq is small; reefer_failure true potency falls below P_min; spoof_attempt reported-based potency stays above P_min while true-based potency is lower by a clear margin (assert only that true < reported by more than a small threshold; the exact margin is a printed result, not a test constant); sensor_glitch yields status "suspect" exactly once and never "excursion_confirmed", and the glitch is counted in samples_excluded; freeze_event reaches "excursion_confirmed". (The true series is fed to the tracker only inside this analysis, never in the engine path.)
Run ruff format, ruff check and scripts\run_checks.py. All five checks must pass.

STEP 7: A SMALL TOOL TO SEE IT
Add a command: python -m <package for the potency code> potency --recording data/recordings/spoof_attempt.jsonl
(use the module path that fits the repo layout; if the edge package has no __main__, create one). It replays the recording through PotencyTracker and prints: a header; every 12th sample as a readable line (sim hour, reported temp, tau_eq, potency percent, status); and a final summary table with TWO rows, "from reported readings" and "from true temperature (ground truth)", showing final tau_eq_h, potency, shelf-life used percent, MKT in C, samples excluded, and whether potency fell below P_min. A clearly worded footer: "Simulation result on a synthetic box. Not real-world evidence." Add an --all option that prints just the final two-row summary for each of the 8 recordings. Document in the relevant README.

STEP 8: DOCS AND REPORT
- Create docs/03-decisions/decision-0003-potency-engine.md: formulas used, units, the right-endpoint integration rule, the suspect-reading state machine with the retroactive correction, hold-last-valid for excluded samples, where each constant comes from (the team document, product defaults, not measured), and every point where you followed the brief instead of this prompt. Plain language.
- Write docs/02-phase-reports/phase-02b-potency-report.md with: what was built; files created and changed; how to run it; how I check it works (include the potency commands); test counts per file; what is real and what is simulated; every placeholder or assumption; every deviation from this prompt and why; problems and surprises; MEASURED numbers: for each of the 8 golden recordings the final tau_eq, potency percent, shelf-life used percent and MKT from the REPORTED series and from the TRUE series (a table), labelled as simulation results; numbered open questions; and a suggested next phase.
- Update the README of the package that holds the potency code and shared/test_vectors/README.md.
- Archive this prompt verbatim to docs/06-prompts/phase-02b-prompt.md.
- Do NOT start the dashboard. Do NOT run npm.

FINAL OUTPUT FORMAT
1. A plain-English summary a student can understand (what the engine does, what the suspect-reading rule does, what the two-row summary shows).
2. The test summary (paste the run_checks summary line and the pytest count).
3. Paste the output of: potency --recording spoof_attempt.jsonl (the final summary table and ten sample lines) and potency --all.
4. The list of placeholders and assumptions.
5. The numbered open questions.
6. ONE block of commit commands (explicit paths) for me to run. I commit once per phase.
Then STOP and wait for my reply. Do not begin Phase 3.
