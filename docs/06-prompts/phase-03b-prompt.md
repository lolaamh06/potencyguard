PHASE 3B: CLOSING THE PHASE 3 LIMITATIONS (slow-drift and mimic lies, "twin out of date" self-check, worst-case damage bound, heat allowance in config)

READ FIRST, ASSUME NOTHING
1. Read CLAUDE.md, docs/00-project-brief/master-brief.md in full (all amendments, especially A16), every phase report in docs/02-phase-reports/ (phase-03-twin-and-detectors-report.md and phase-03-evaluation.md especially) and every decision record in docs/03-decisions/ (decision-0005 especially).
2. Read before changing: edge/thermal_twin.py, edge/calibration.py, edge/detector_config.py, edge/tamper_monitor.py, edge/twin_cli.py, edge/cli.py, edge/potency.py, edge/sensor_reading.py, config/detectors.yaml, config/twin_calibrated.yaml, config/product_default.yaml, shared/config.py, simulator/*.py (engine.py, live.py, events.py, scenario.py, commands.py, divergence.py, truth.py, demo.py), simulator/scenarios/*.yaml, scripts/evaluate_detectors.py, tests/test_tamper_monitor.py, tests/test_evaluation.py, tests/test_channels.py.
3. If anything here conflicts with the brief or existing code, STOP and tell me the exact conflict. If anything is ambiguous, ASK before writing code. Never guess numbers, field names, file names or folder locations.

WHY THIS PHASE EXISTS
Phase 3 measured the detectors honestly and exposed five weaknesses: (1) every tested lie starts with a sudden jump, so slow lies are untested; (2) a lie that mimics healthy physics cannot be seen by physics and this has not been measured; (3) when the real box differs from the twin's calibration by +15 percent, 100 percent of runs get a false tamper verdict; (4) when a lie is detected, potency is only labelled untrusted, not bounded; (5) the 60 K heat allowance is tuned to the simulator and lives in code/config without a stated derivation. This phase measures or fixes each one. It must report results HONESTLY: if a target below is not met, say so with the numbers and do not tune on the test seeds to hide it.

ABSOLUTE RULES
- NEVER run git add, git commit, git tag or git push. At the end print ONE block of commit commands (explicit paths only, never "git add -A" or "git add ."), one commit message, no co-author trailers or attribution lines.
- NEVER run npm install or npm ci. Do not touch the dashboard.
- No new Python packages (numpy, pydantic, pyyaml, pytest, ruff, standard library only).
- No external statistics anywhere. Every invented number is labelled "placeholder, not sourced [SOURCE NEEDED]".
- No claims that hardware or SAP is real; "source" stays "sim". No "first", "unique" or "novel" claims.
- Files UTF-8 without BOM, LF line endings, .NET file writes.
- Never edit a test just to make it pass. If a recording or number changes, say exactly why. The nine golden recordings must stay BYTE-IDENTICAL in this phase (no existing scenario uses the new modes); confirm with a hash comparison and STOP if any changes.
- TUNING DISCIPLINE: any threshold you tune is tuned on the TRAINING seeds (10001 to 10100) only. The test seeds (20001 to 20200) are used once for the final numbers. Calibration seeds (9001 to 9010) stay for calibration only. Assert the seed sets are disjoint in a test.

STEP 0: PRE-FLIGHT (read-only)
git status --short and git log --oneline -5. Phase 3 must be committed; if tracked files are modified, STOP and tell me. Run scripts\run_checks.py: expect 5 passed and 444 tests.

STEP 1: TWO NEW LIE MODES IN THE SIMULATOR
Add to the spoof event (scenario files and the injectable spoof_sensor command, the command parser, the live-demo help, simulator/README.md fault table):
 a. mode "drift": the reported temperature equals the true temperature minus an offset that grows linearly from 0 at the spoof start at rate_c_per_h (kelvin per hour), up to an optional max_offset_c; sensor noise is added as in the other modes. Required parameter: rate_c_per_h > 0; optional max_offset_c.
 b. mode "mimic": the reported temperature follows what a HEALTHY box would show: the attacker runs a copy of the box model with cooling_factor 1.0 and no unseen heat loads, driven by the real ambient temperature and the real compressor duty pattern of a healthy box (the copy runs its own hysteresis controller on its own state, started from the true temperature at the spoof start), plus sensor noise. It is a knowledgeable liar. Implement it inside the engine as a separate state so that the true series and the other random streams are unaffected (use the existing separate noise stream discipline; do not change the number of draws per sample for any existing mode, and verify that all nine golden recordings stay byte-identical).
 c. Validation, tests, and ground-truth labelling: spoof windows record the mode and parameters; first_divergence_s works for both modes (the first time |reported - true| exceeds detect_divergence_c).
 d. The ambient and cooling-duty channels stay honest in both modes (threat model unchanged). Say in the docs that a mimic lie is an ATTACKER WITH A MODEL OF THE BOX and is expected to be invisible to physics.
Tests: determinism; drift offset grows as specified (check at several times); mimic stays inside the healthy envelope (never colder than the floor bound, never warmer than ambient); true series identical with and without a spoof (same seed); injection works mid-run; invalid parameters rejected.

STEP 2: HEAT ALLOWANCE IN CONFIG WITH A STATED DERIVATION
Replace the bare heat_allowance_c with a config key whose documentation states what it means and where it comes from: "largest sudden warming of the box (kelvin) that an unseen heat load can cause in one sample interval" and derive the simulator-matching value from config values (R_th, tau, door_default_power_w) in a comment and in a test: assert that the allowance in config/detectors.yaml is at least R_th * (the largest door power any shipped scenario or injectable command can request) and that the allowance is NOT larger than a stated multiple (say 1.5) of that, so it stays tied to the simulator. Add config key door_max_power_w (placeholder, not sourced [SOURCE NEEDED]) used by the injectable open_door validation (reject larger values) and by that test. If this changes any scenario validation, list it.
Keep the detector behaviour identical for existing settings (the numbers in phase-03-evaluation.md must still be reproduced on the golden recordings).

STEP 3: THE "TWIN OUT OF DATE" SELF-CHECK
Goal: tell "my model is off" apart from "someone lied", by the SHAPE of the error. Add to TamperMonitor a model-health estimator and a new verdict "twin_out_of_date" (with classification table rows and tests).
 Method (implement, evaluate, and report; if it cannot separate the cases, say so and describe what you tried):
 - Maintain a rolling window (length W samples, placeholder) of pairs (x_n, y_n) with x_n = T_pred[n+1] - T_meas[n] (the change the twin predicts) and y_n = T_meas[n+1] - T_meas[n] (the change observed).
 - Rolling ordinary least squares of y = g * x + b * dt_h (a gain g and a drift slope b in kelvin per hour). A mismatched box (wrong time constant, wall resistance or cooling capacity) shows g away from 1 with b near 0 and NO sudden jump; a slow drift lie shows b away from 0 with g near 1; a held or jumped lie shows an impossible-step flag or g near 0.
 - Verdict rule (thresholds are placeholders in config/detectors.yaml, tuned on the TRAINING seeds only): "twin_out_of_date" when the gain deviates from 1 by more than a margin (and stays inside a plausible band such as 0.5 to 2) for a sustained run of samples, AND no impossible-step flag has ever fired in the trip, AND no latched falsification exists. While twin_out_of_date is active, CUSUM-based tamper verdicts are suppressed (the verdict is twin_out_of_date, the underlying CUSUM values are still reported). Hard physical proofs (impossible step, impossible state) are NOT suppressed.
 - Be explicit in the docs about the residual risk: a patient attacker could imitate a gain error; state what the design does about it (for example: twin_out_of_date is itself reported and logged, and a trip that is out of date from the very first window is flagged to an operator, never silently accepted; it also marks potency untrusted-low-confidence in Step 4).
 Targets for the evaluation (placeholders; report whether they were met, do not hide misses): under the +15 percent and -15 percent mismatch boxes, the share of clean/physical runs that end with a TAMPER verdict falls below 5 percent and the monitor reports twin_out_of_date in most of those runs; on the NOMINAL box, detection of the five Phase 3 lie families stays at or above 95 percent with a median delay no more than one sample worse than Phase 3; the control family and false-alarm figures do not get worse.

STEP 4: WORST-CASE DAMAGE BOUND AND THE ASSESSMENT OBJECT (new file edge/assessment.py)
 a. worst_case_bound(...): when the monitor has declared reported data untrusted from time t0 (latched falsification, or twin_out_of_date), compute an UPPER BOUND on the equivalent reference time tau_eq accumulated from t0 to the current time, assuming the honest ambient channel and NO cooling at all (duty 0) and no unseen heat load beyond the configured heat allowance applied once. Method: integrate the twin forward from the last trusted reading with duty 0 using the measured ambient; feed that worst-case temperature series to the potency maths (same Arrhenius and right-endpoint rule as the PotencyTracker). Return the bounded tau_eq, the bounded potency, the bounded shelf-life-used fraction and the hour t0. Document clearly what the bound assumes and what it ignores (unseen heat loads beyond the allowance, a falsified ambient channel).
 b. assess(potency_state, monitor_state, bound) -> PotencyAssessment (frozen pydantic): reported potency, trusted (bool), trust_reason, untrusted_since_s, worst_case_potency (or None), worst_case_shelf_life_used_fraction (or None), and the monitor verdict. Pure function; unit tested.
 c. The assessment must NEVER use ground truth. The bound uses only readings (reported temperature up to t0, honest ambient channel, duty not used after t0).
 d. Test the bound: on the golden recordings spoof_attempt and hidden_spoilage, and over 200 fresh seeds of each plus injected offset and drift runs, assert worst-case tau_eq >= TRUE tau_eq (true series fed to the tracker inside the test only) from t0 to the end; and report how conservative it is (ratio worst-case / true, median and max) in the report. If the bound is violated in any run, STOP and tell me.

STEP 5: COMMANDS
 - python -m edge twin --recording FILE prints, in addition to the current output, the trust status and, when untrusted, the worst-case bound lines ("worst case from hour t0: at most X percent of shelf life used"; "reported (untrusted): Y percent").
 - python -m edge twin --all adds the trust column.
 Update tests for the CLI output.

STEP 6: EVALUATION (extend scripts/evaluate_detectors.py)
 Keep every Phase 3 table and add:
 a. Lie families on the TEST seeds: injected_drift at rates 0.25, 0.5, 1.0 and 2.0 K per hour (random start times, with a physical fault active or not: say which, include both variants), injected_mimic. For each: detection rate, delay from first_divergence_s (median, p90), the verdict class, and the share where the worst-case bound was computed and valid. For the mimic family the expected result is "not detected"; report it plainly as the physics limit and state what covers it (signatures, hardware, a redundant sensor). Do not tune anything to make the mimic detectable.
 b. The mismatch tables again (+15, -15, ambient noise x2) with the new verdict space: counts of tamper verdicts, twin_out_of_date verdicts, ok, and the nominal-box comparison to the Phase 3 numbers.
 c. A "before/after" table comparing Phase 3 and Phase 3B on the same test seeds for: detection rate and delay on the five Phase 3 lie families, false tamper verdicts on clean and physical families, and mismatch false tamper verdicts.
 d. Bound validity table and conservativeness.
 e. Threshold tuning for the new thresholds happens on TRAINING seeds only: print the training sweep.
 f. Write docs/02-phase-reports/phase-03b-evaluation.md (generated) plus data/generated/evaluation_3b.json (git-ignored). Keep a --quick mode for tests. Everything labelled "Simulation result on a synthetic box. Not real-world evidence."

STEP 7: TESTS (all must pass)
 Beyond the tests listed in the steps: classification table rows for twin_out_of_date and its suppression/non-suppression rules; the rolling regression on hand-built sequences (pure gain error gives g about 1.3 and b about 0; a ramp drift gives b negative and g about 1; a jump gives the impossible-step flag); an assessment test showing trusted/untrusted transitions; the seed-disjointness test; the evaluation --quick run deterministic; the Phase 3 golden-recording expectations (baseline/shock/sensor_glitch no tamper; reefer/door/heatwave thermal anomaly only; spoof_attempt and hidden_spoilage suspected_falsification within the same delay) still hold. Run ruff format, ruff check and scripts\run_checks.py: all five must pass.

STEP 8: DOCS AND REPORT
 - docs/03-decisions/decision-0006-closing-phase-3-limitations.md (plain language): the two new lie modes and what each tests; the self-check method, its thresholds and its residual risk; the worst-case bound with its assumptions and what it ignores; the heat allowance derivation; which limitations remain (shared equations, honest channels, mimic liar, no humidity or shock physics) and why.
 - Append an amendment to docs/00-project-brief/master-brief.md in the existing amendment format.
 - Update READMEs (edge, simulator, config, scripts, data).
 - Write docs/02-phase-reports/phase-03b-report.md with the usual sections plus: every changed test with reason; the before/after table; targets met or missed (explicit list); limitations written plainly; numbered open questions; suggested next phase.
 - Archive this prompt verbatim to docs/06-prompts/phase-03b-prompt.md.

FINAL OUTPUT FORMAT
1. A plain-English summary a student can read (what each fix does and whether it worked).
2. The test summary (run_checks line, pytest count, per-file counts).
3. Paste: python -m edge twin --recording data/recordings/hidden_spoilage.jsonl (ten lines, summary, trust and bound lines) and python -m edge twin --all.
4. Paste the before/after table, the drift and mimic tables, the mismatch tables and the bound-validity table (compact).
5. An explicit list: each of the five limitations, with "fixed", "measured and reported" or "not fixed" and the one-line reason.
6. The placeholders and assumptions, and the tests changed with reasons.
7. The numbered open questions.
8. ONE block of commit commands (explicit paths).
Then STOP and wait. Do not begin Phase 4.
