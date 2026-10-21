PHASE F3: THE STORY (PROLOGUE + CHAPTERS 1 TO 7, ALL INTERACTIONS)

READ FIRST. Read docs/01-architecture/storyboard.md (this is your scene-by-scene spec), docs/01-architecture/frontend-vision.md (with amendments FV-A1 to FV-A5), docs/01-architecture/design-system.md, the F1 and F2 reports, and the F1 style frames. Look at the current dashboard/src/ structure (do not re-read every file; list the tree and open what you touch).

SPEED RULES (binding; the user wants this finished fast).

While working, run ONLY the tests for files you changed (vitest run <file>, pytest <file>). Run the full scripts/run_checks.py ONCE, at the very end.
Browser review is ONE round, at most 12 screenshots in total: 1920x1080 for the Prologue and each of the 7 chapters (8), plus 1366x768 for two worst-case scenes (2), plus up to 2 re-shots after fixes. No phone shots, no tier sweeps, no repeated scoring rounds, no re-measuring performance on every tier. Read the console once. Check the performance overlay once on High.
Do one fix pass on the top three issues you see, then stop reviewing.
Do not rewrite files wholesale; edit. Keep the report under about 120 lines. Keep docs concise.

GIT RULES (absolute). NEVER run git add, git commit, git tag or git push. Read-only git is fine. First git status; if F2 is uncommitted, stop and tell me. At the end print ONE block of explicit-path git add commands (no wildcards; never node_modules, dist, .playwright-mcp) and ONE git commit command, no co-author trailers.

JUNCTION RULE. Do NOT run npm install inside dashboard/. If you truly need a new package, follow the F2 junction procedure from decision 0011 (install in the work folder outside OneDrive, copy package.json and the lockfile back, re-verify the junction). Prefer to need none.

HONESTY (binding). Vision section 11 applies to every string. No external statistics on screen. No “first”, “unique”, “novel”, “unhackable”, “tamper-proof”. Neutral wording for simulated parts. Every figure is a model output of our own engine and is labelled. The front end never computes planner numbers: it shows what the exporter wrote. The only front-end maths is the tested potency mirror. Chapter 2 must say only what the physics checks catch; Chapter 6 must say a changed record is detected. Signing protects records after signing and does not stop a lie at the sensor.

STEP 0. Preflight. git status; confirm the Playwright tools load. Skip the full check run now (you run it once at the end).

STEP 1. Fix the exporter mismatch first. The F2 replay files say the baseline_ok checkpoint decision needs_human is true, but the Phase 6 backend (python -m backend replay --all) auto-approved baseline_ok, door_open_excursion, reefer_failure and heatwave_transit and sent spoof_attempt and hidden_spoilage to a person. Find the difference (inputs such as remaining hours, trust, the backend’s extra rules) in scripts/export_replay.py, make the exporter reuse the same decision path as the backend service (call the same function, do not copy logic), regenerate the five replay files, and add a test that the exported route equals the backend’s route for all five. Report what the cause was.

STEP 2. Export what the Story needs, from the real code, deterministic, small. Extend scripts/export_replay.py (or a sibling script with a test) to write:

Chapter 1: the two journeys’ traces and results (active profile figures; reference-profile figures stored for the Provenance drawer), already partly in the F1 chapter1.json; reuse its generator.
Chapter 2: for one lie scenario (spoof_attempt) the measured line, the twin line, the residual and the alarm time.
Chapter 5: up to 5,000 sampled outcomes per action for continue and reroute from the real planner (seeded, seed recorded), and a precomputed table of expected loss and CVaR per action for an alpha grid (for example 0.50 to 0.99 in steps of 0.01), so the slider only SELECTS rows; the front end must not compute CVaR.
Chapter 6: the approval-card content (potency curve points, residual summary, chain status, the alternatives with CVaR numbers, the reasons) for one needs_human case (hidden_spoilage), and the chain ribbon data with the result of a real edit-and-verify on a ledger copy.
Keep every file small (report sizes). Label everything “illustrative product, model output” in the data.

STEP 3. Build the scenes (follow the storyboard’s exact copy, scroll lengths and reduced-motion alternatives; total 860 vh). Procedural 3D only, no downloaded models, no network:

Prologue: frosted box lid and a single vial, glow tied to potency, cold vapour, camera pulls back to the globe with the route. Caption “An illustrative journey.”
Ch1 “Two alarms. One verdict.”: two traces draw, two identical REJECT stamps, two vials; a draggable time handle uses the TypeScript potency mirror; show the labelled figures.
Ch2 “Whose data is this?”: a calm logger line, the twin ghost line, the residual wedge, a draggable shield that triggers the real recorded alert time. Copy states only what is caught; add the plain limit sentence from FV-A4.
Ch3 “Too late to matter”: the timeline, the decision marker at the end, the early dot with hover.
Ch4 “A box that thinks”: procedural cutaway and exploded view with the generic labels from the storyboard; no real hardware claims.
Ch5 “Plan for the worst five percent”: instanced futures cloud (real exported samples), worst 5 percent lit in the planner colour, expected-versus-worst bars, the alpha slider selecting rows from the precomputed table, the recommendation flipping where the data flips.
Ch6 “A human decides”: the approval card with real exported content, the Approve press, the seal on the chain ribbon, the real tamper result (a broken link dims later links).
Ch7 “Enter the control room”: the dive transition to #/control-room (a placeholder route is fine; F4 builds it) and a visible Enter button plus keyboard shortcut.
Every chapter: presenter skip controls and keyboard control keep working; reduced-motion crossfades; 2D fallback shows the same copy and static versions of the key graphic; text is real DOM text. Keep one hero motion per scene.

STEP 4. Cleanup. Delete the unused dashboard/src/smoke/ folder and its tests (agreed in F2). Update the chapter table, the progress rail and the “?” overlay so only working keys are listed.

STEP 5. Tests (targeted). Vitest for the new pure logic: the alpha-slider row selection, the Chapter 1 scrub using the mirror against the exported figures, data validation for the new files, the chapter table still totals 860 vh. Pytest for the exporter additions and the route-equals-backend test. No performance or soak testing in this phase.

STEP 6. ONE review round (see speed rules). Open the app on 127.0.0.1 with Playwright, take the screenshots, look at them, fix the top three issues, re-shot only those. Save to docs/05-demo/f3-screenshots/. Check the console once and the network log once (no external request). Read the performance overlay once on High and name the renderer. Give each scene a short note (what works, what is weak), not a full rubric table.

STEP 7. Final steps. Run scripts/run_checks.py ONCE and report totals. Write a concise docs/02-phase-reports/phase-f3-report.md (what was built, the exporter cause and fix, data file sizes, test totals, the performance reading with renderer, screenshots with short notes, PROPOSE items, problems, omissions, can-say and must-not-say). Archive this prompt in docs/06-prompts/phase-f3-prompt.md. Update the relevant READMEs.

STEP 8. Final report to me in simple words: what was built, test totals before and after, the exact PowerShell commands to run the dev server and which URL and keys to try, anything surprising, anything not done, open questions as a numbered list, and the single commit block. Then stop. Do not start F4.
