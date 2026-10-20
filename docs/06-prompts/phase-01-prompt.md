PHASE 1: HOUSEKEEPING + THE BOX SIMULATOR + SCENARIO RECORDINGS

READ FIRST, ASSUME NOTHING
1. Read CLAUDE.md, then docs/00-project-brief/master-brief.md in full (including the v1.1 amendments A1-A14 at the end), then docs/01-architecture/frontend-vision.md, then docs/02-phase-reports/phase-00-skeleton-report.md.
2. If anything in this prompt conflicts with the brief or CLAUDE.md, STOP and tell me the exact conflict. Do not pick a side.
3. If any detail is missing or ambiguous, ASK me before writing code. Do not guess numbers, field names or file names.

ABSOLUTE RULES
- NEVER run git add, git commit, git tag or git push. After each numbered step below, print explicit-path "git add <paths>" and "git commit -m ..." commands for me to run. No co-author trailers or attribution lines in the messages. No "git add -A" or "git add .".
- NEVER run "npm install" or "npm ci" in dashboard/ in this phase. The junction at dashboard/node_modules is fragile because npm replaces it. This phase must not touch the dashboard code.
- Do not install anything new in the Python venv except what is listed in Step 2. The venv is at %LOCALAPPDATA%\potencyguard\venv.
- No external statistics anywhere (code, comments, docs, fixtures). Where a number needs a source, write [SOURCE NEEDED].
- No UI-facing text may claim hardware or SAP is real. Use neutral wording: "Sensor feed", "Event dispatched". The "source" field in data stays truthful ("sim" for now).
- No "first", "unique", "novel" claims in any file.

STEP 1: HOUSEKEEPING
a. pyproject.toml: change requires-python to ">=3.11" and ruff target-version to "py311". Run scripts\run_checks.py; all checks must pass.
b. CLAUDE.md rule 10 and dashboard/README.md and the top-level README.md setup step 4: replace the old junction path with the CURRENT working path (...\dashboard-node_modules\node_modules, as documented in the Phase 0 report) and add this warning in plain words: "npm install or npm ci REPLACES the junction with a real folder inside OneDrive. Only run them when a phase says so, then follow the recovery steps."
c. Print the commit commands for this step.

STEP 2: DEPENDENCIES
Add to requirements-dev.txt / pyproject (pinned, exact versions, with the version you actually installed): numpy, pydantic. Nothing else. Install into the venv. Re-run run_checks.py. Print commit commands.

STEP 3: THE SENSOR INTERFACE
Create edge/ package files (follow the folder layout already in the repo; if the layout is unclear, ask me):
- A SensorReading dataclass/pydantic model with: t_s (float seconds since scenario start on the simulated clock), temp_c, rh_pct, shock_g, source (string, "sim" here).
- An abstract SensorSource with methods: start(), read() -> SensorReading | None (None = end of recording), close().
- A SimClock with a speed factor (1x, 60x, 3600x) and a pure function to advance simulated time. No sleeping inside logic; the clock is injectable so tests run instantly.
Unit tests for the clock and the model (valid ranges, rejects NaN, rejects negative time).

STEP 4: THE BOX SIMULATOR (SimSource)
Implement a deterministic, seeded simulator of one insulated shipping box using the lumped thermal model from the brief: T[n+1] = T_inf + (T_n - T_inf) * exp(-dt/tau), T_inf = T_amb + R_th * Q. Take tau, R_th, Q defaults from config/product_default.yaml; if they are not there, ADD them with clearly-labelled placeholder values and a comment "placeholder, not sourced [SOURCE NEEDED]", and tell me in the report. Ambient profile, humidity and shock events come from a scenario definition (Step 5). Add small seeded Gaussian sensor noise with sigma from config. Same seed => byte-identical output (test this).
Tests: determinism; steady ambient converges to T_inf; step change in ambient gives the exponential response (check against the closed form at several times, unrounded); noise has the configured sigma within a tolerance over a long run.

STEP 5: SCENARIO LIBRARY AND RECORDINGS
Define scenarios as YAML files under the scenarios folder (create it per the repo layout), each with id, title, description (plain, no statistics), seed, duration, sample interval, ambient profile, and events:
 1. baseline_ok: stable cold chain, arrives fine.
 2. door_open_excursion: short warm excursion, recovers.
 3. reefer_failure: sustained warming, goes beyond the limit.
 4. freeze_event: drops below 0 C.
 5. heatwave_transit: long hot leg on the road.
 6. spoof_attempt: the reported temperature is falsified to look cold while the box physically warms (the injected lie must violate the thermal model; do NOT build the detector in this phase, only the data).
 7. sensor_glitch: single isolated extreme reading (must be a single sample, to test the 2-consecutive-sample rule later).
 8. shock_drop: one large shock event.
For each, the generator writes a recording file (JSONL, one SensorReading per line, plus a header line with scenario id, seed, sample interval, schema version) into the recordings folder. Add a ground_truth sidecar JSON per recording with the TRUE temperature trace and labels of injected events (so later phases can score detectors). Add a RecordedSource(SensorSource) that replays a recording file.
Tests: every scenario generates; same seed gives identical files (compare hashes); each scenario's defining property holds (e.g. reefer_failure exceeds the hard limit; freeze_event goes below 0; sensor_glitch has exactly one outlier sample; spoof_attempt reported series differs from the true series in the labelled window); RecordedSource replays exactly what was written.
Add a small CLI: python -m <package> generate --all and generate --scenario <id>. Document it in the relevant README.

STEP 6: CHECKS AND REPORT
- Run scripts\run_checks.py; everything must pass. Paste the summary.
- Do NOT start the dashboard.
- Write docs/02-phase-reports/phase-01-simulator-report.md with: what was built, files created (list), test counts, every placeholder value you added, every deviation from this prompt and why, anything you were unsure about, and numbered open questions for me.
- Archive this prompt text to docs/06-prompts/phase-01-prompt.md.
- Print the commit commands for steps 3-6, one block per step.

REPORT BACK
End with: (1) a short plain-English summary, (2) the list of placeholders, (3) the open questions. Then STOP and wait. Do not begin Phase 2.
