PHASE 2D: APPLY THE CHOSEN PRODUCT CONSTANTS (SET C) + KEEP THE TEAM-DOCUMENT VALUES AS A REFERENCE PROFILE + ADD THE hidden_spoilage SCENARIO

READ FIRST, ASSUME NOTHING
1. Read CLAUDE.md, docs/00-project-brief/master-brief.md (including all amendments), docs/02-phase-reports/phase-02b-potency-report.md, docs/02-phase-reports/phase-02c-constants-study.md, docs/02-phase-reports/phase-02c-report.md, docs/03-decisions/decision-0003-potency-engine.md.
2. Read before changing: config/product_default.yaml, shared/config.py, edge/potency.py, edge/cli.py, scripts/make_test_vectors.py, scripts/constants_study.py, shared/test-vectors/potency_vectors.json, tests/test_potency.py, tests/test_potency_tracker.py, tests/test_constants_study.py, tests/test_scenarios.py, simulator/scenario.py, simulator/expectations.py, simulator/scenarios/spoof_attempt.yaml, simulator/scenarios/reefer_failure.yaml.
3. If anything here conflicts with the brief or existing code, STOP and tell me the exact conflict. If anything is ambiguous, ASK before writing code. Do not guess numbers, field names or file names.

THE DECISION (made by the decision-maker, with the Phase 2C data)
The ACTIVE product constants become Set C: Ea/R = 15000 K, tau_max = 8760 h. T_ref = 5 C and P_min = 0.90 stay unchanged. These values are an ILLUSTRATIVE profile for a heat-sensitive biologic. They are NOT measured and NOT sourced: label every place they appear "placeholder, not sourced [SOURCE NEEDED]; illustrative profile; replace with the manufacturer's stability data". The team document's values (Ea/R = 10000 K, tau_max = 17520 h) are kept as a REFERENCE profile so the document's worked examples (8 h at 12 C gives 0.110 percent of shelf life; 24 h at 30 C gives 2.66 percent) remain verified. Do not claim anywhere that either profile describes a real product, and do not claim that the 10000 value has a verified source (we have not traced one).

ABSOLUTE RULES
- NEVER run git add, git commit, git tag or git push. At the end print ONE block of commit commands (explicit paths only, no "git add -A" or "git add ."), one commit message, no co-author trailers.
- NEVER run npm install or npm ci. Do not touch the dashboard.
- No new Python packages. No external statistics anywhere.
- No wording that claims hardware or SAP is real. "source" stays "sim".
- No "first", "unique" or "novel" claims.
- Files UTF-8 without BOM, LF line endings, written with .NET file writes.
- Never edit a test just to make it pass: if a test shows a real problem, tell me. Where a test must change because the active constants changed, change only the constants it reads and explain each such change in the report.

STEP 0: PRE-FLIGHT (read-only)
git status --short and git log --oneline -5. Phase 2C should be committed; if tracked files are modified, STOP and tell me. Run scripts\run_checks.py: expect 5 passed and 286 tests.

STEP 1: THE TWO PROFILES
a. Create config/product_team_document.yaml containing EXACTLY the current values of config/product_default.yaml for the product section (the kinetic constants, limits, confirmation count, and anything else in ProductConfig), with a header comment: "Reference profile: values taken from the team's source document. Source of the kinetic constants not independently verified by us [SOURCE NEEDED]. Kept so the document's worked examples stay verifiable." Keep the box simulator and freerun placeholder blocks ONLY in product_default.yaml if load_box_config / load_freerun_config read them from there; check how the loaders work and tell me how you handled it (the reference file may need to hold only the product section if the loader allows it; otherwise keep it a full copy; choose the approach that cannot drift and explain it).
b. Change config/product_default.yaml: Ea_over_R: 15000 and tau_max_h: 8760, nothing else, with the placeholder comment above next to both keys. Add a one-line comment naming the profile ("illustrative heat-sensitive biologic profile").
c. Make sure load_product_config accepts a path (it should already: tests use it) and that tests can load the reference profile by path.

STEP 2: UPDATE THE AFFECTED CODE AND TESTS
Run the full test suite and list every failing test BEFORE changing any test. For each failure decide: (i) the test encodes the document's reference numbers: point it at the reference profile (config/product_team_document.yaml) instead of the default; (ii) the test encodes a Phase 2B/2C result that depends on the active constants: update the expected numbers to the new active-profile values, taken from the study document phase-02c-constants-study.md Set C (the golden-recording table) AND re-derived by running the code, and assert both agree; (iii) anything else: STOP and tell me.
- tests/test_potency.py document checks: keep them, run against the reference profile.
- Add NEW tests: with the active profile, AF(40 C) and AF(12 C) match the closed form for Ea/R = 15000; k_ref follows tau_max = 8760; P at tau_eq = tau_max equals P_min.
- tests/test_constants_study.py: set A still reproduces the Phase 2B table, and the active default now equals Set C (assert that the study's set C constants equal the loaded default).
- Add a regression test file tests/test_profiles.py: both profiles load; the reference profile gives the document's rounded worked examples (document_checks); the active profile gives the Set C numbers for the eight golden recordings within a tight tolerance (store those expected numbers in the test from the study output you just re-derived).

STEP 3: SHARED TEST VECTORS FOR BOTH PROFILES
Update scripts/make_test_vectors.py so it writes TWO files: shared/test-vectors/potency_vectors.json (active default profile) and shared/test-vectors/potency_vectors_team_document.json (reference profile). Each has its own meta block naming the profile and the constants. The document_checks list lives in the reference-profile file. The existing test that compares each committed file to a fresh generation must cover both. Update shared/test-vectors/README.md (say the TypeScript port must reproduce BOTH files).

STEP 4: THE hidden_spoilage SCENARIO
Add simulator/scenarios/hidden_spoilage.yaml, following the Phase 2A scenario format (ranges, ambient_jitter_c, ambient_shift_h, expect block), seed 109, sample_interval_s 600:
- Story (plain, neutral description, no percentages): a multi-day trip. The cooling unit is weak for most of it (a derate, not a total failure) while the cargo area is hot, and from a few hours after the weakness begins the reported temperature is falsified to look cold. The box slowly spoils while the reported series looks perfect.
- Duration around 96 h. Use cooling_factor events (a derate in the range 0.2 to 0.5, starting somewhere in hours 12 to 24, lasting to the end of the trip) and a spoof event (mode hold, reported_c near the setpoint, add_noise true, starting a few hours after the derate begins and lasting to the end).
- Choose the cargo-area ("ambient") profile and ranges so that, with the ACTIVE profile (Set C), for EVERY seed in a test of 200 seeds: (1) the TRUE series makes potency fall below P_min somewhere between hour 48 and hour 90 of the trip; (2) the REPORTED series never makes potency fall below P_min, never confirms an excursion, and has the reported series within the hard limits all trip; (3) the true box temperature stays physically plausible (below 45 C at all times). You may tune ambient values, derate range and spoof start range to achieve this. The tuning must use the real simulator and the real tracker (a small throwaway tuning script under scripts/ is fine; do not commit throwaway scripts unless they are tidy, and tell me).
- Encode what is encodable in the scenario's expect block using the existing keys (true_max_c_gt, reported_true_gap_c_gt, and so on). The potency guarantees (1) and (2) cannot live in the expect block because the simulator package must not import the edge package; put them in a test (tests/test_hidden_spoilage.py) that runs 200 seeds and asserts (1), (2) and (3) using LiveSimulator plus PotencyTracker (reported series for the tracker in (2), the true series via update_sample for (1)).
- Regenerate the golden recordings (python -m simulator generate --all). The eight old recordings must stay BYTE-IDENTICAL; only the new files hidden_spoilage.jsonl and hidden_spoilage.ground_truth.json are added. Confirm this with git status/diff and tell me. If any old recording changes, STOP and tell me why.
- Update the tests that count or enumerate scenarios (for example 8 scenarios to 9 in tests/test_scenarios.py) and the committed-recordings hash test. Update simulator/README.md and data/README.md (nine scenarios).
- Run the 200-seed free-run and 200-seed scenario expectation tests as before; the whole suite must stay fast.

STEP 5: SEE IT
Run: python -m edge potency --recording data/recordings/hidden_spoilage.jsonl and python -m edge potency --all. Extend the two-row summary in edge/cli.py so that it also prints the simulated hour at which potency first fell below P_min (or "never"), for both rows. Keep the footer "Simulation result on a synthetic box. Not real-world evidence." Update tests for the CLI output.

STEP 6: DOCS AND REPORT
- Create docs/03-decisions/decision-0004-active-product-profile.md: why Set C was chosen (from the Phase 2C data), why the team-document profile is kept, the labelling rule (illustrative, replace with manufacturer data), and the consequence: product constants live in swappable profiles.
- Append an amendment to docs/00-project-brief/master-brief.md following the existing amendment numbering/format: the active product constants changed from the team-document values to the illustrative Set C; reasons; the reference profile remains.
- Update CLAUDE.md only if a rule mentions the constants; otherwise leave it.
- Write docs/02-phase-reports/phase-02d-report.md: what was built; files created and changed; how to run; how to check; test counts per file; every test you changed and exactly why; what is real vs simulated; placeholders and assumptions; deviations; problems; the measured numbers for all NINE recordings under the active profile (reported vs true: tau_eq, potency percent, shelf life used percent, extra days lost, hour of crossing P_min), labelled as simulation results; numbered open questions; suggested next phase.
- Archive this prompt verbatim to docs/06-prompts/phase-02d-prompt.md.
- Update scripts/README.md, edge/README.md, simulator/README.md and data/README.md where they changed.

FINAL OUTPUT FORMAT
1. A plain-English summary a student can read.
2. The test summary (run_checks summary line and pytest count, per file counts).
3. Paste the output of: python -m edge potency --recording data/recordings/hidden_spoilage.jsonl (header, ten sample lines and the final table) and python -m edge potency --all.
4. The list of placeholders and assumptions, and the list of tests you changed with reasons.
5. The numbered open questions.
6. ONE block of commit commands (explicit paths, including the new recordings and test-vector files).
Then STOP and wait. Do not begin Phase 3.
