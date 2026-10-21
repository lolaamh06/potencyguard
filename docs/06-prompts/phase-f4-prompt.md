PHASE F4: THE CONTROL ROOM AND FINAL POLISH

READ FIRST. Read docs/01-architecture/storyboard.md (the Control Room sections and the scenario-console interaction), docs/01-architecture/frontend-vision.md (section 6 and amendments FV-A1 to FV-A5), docs/01-architecture/design-system.md, docs/01-architecture/style-frames/frame-3-control-room.html and its data (your visual reference), the F2 and F3 reports, docs/01-architecture/api.md, and the current dashboard/src/ tree (list it; open only what you touch).

SPEED RULES (binding; the user wants this finished fast).

While working, run ONLY the tests for files you changed. Run scripts/run_checks.py ONCE, at the very end.
Browser review is ONE round, at most 12 screenshots: the Control Room at 1920x1080 for each of the five scenarios (5), at 1366x768 for two of them (2), the Provenance drawer open (1), the tamper result (1), the approval flow (1), plus up to 2 re-shots after fixes. No phone shots, no tier sweeps, no repeated scoring rounds. Read the console once, the network log once.
One fix pass on the top three issues, then stop reviewing.
The soak test is ONE scripted run of 5 minutes, started in the background, while you write the report; record the browser’s JS heap at start and end (and frame-rate readings at start and end) and say plainly how it was measured.
Edit, do not rewrite wholesale. Report under about 120 lines.

GIT RULES (absolute). NEVER run git add, git commit, git tag or git push. Read-only git is fine. First git status; if F3 is uncommitted, stop and tell me. At the end print ONE block of explicit-path git add commands (no wildcards; never node_modules, dist, .playwright-mcp) and ONE git commit command, no co-author trailers.

JUNCTION RULE. Do NOT run npm install inside dashboard/. If a package is truly needed, follow the F2 procedure in decision 0011. Prefer to need none.

HONESTY (binding). Vision section 11 applies to every string. No external statistics. No “first”, “unique”, “novel”, “unhackable”, “tamper-proof”. Neutral wording: “Sensor feed”, “Event dispatched”, “Enterprise system” (never “Connected to SAP” or a named hardware part). The screen never presents simulated parts as real hardware or as a real enterprise connection. Worst-case figures are labelled “worst-case bound, not an estimate”. Reported (signed) values and recomputed values are shown separately. The front end never computes planner numbers.

STEP 0. Preflight. git status; confirm the Playwright tools load. No full check run yet.

STEP 1. The Control Room (replay-first, offline). Build the screen from the storyboard and frame-3 reference, driven by the replay files through the existing mode adapter:

Top bar: wordmark, the five scenario chips (baseline_ok, door_open_excursion, reefer_failure, spoof_attempt, hidden_spoilage), speed (1x, 4x, 16x), pause and reset, a small collapsed Provenance control.
Left: shipment card (id, illustrative route progress, status chip with icon and word, trust level chip).
Centre: the globe with the shipment marker coloured by state and the planned alternative route shown when the recommendation is a reroute.
Right: potency ring and big numbers (potency, shelf life used, remaining life, MKT, current temperature), tabular numerals, smooth tweening, “Illustrative product, model output” where figures first appear.
Bottom left: chart with measured line, twin line, residual strip, CUSUM strip, excursion bands, alert markers, one shared time axis; canvas for lines, SVG for annotations. Minimum chart text size 12 px at 1366x768.
Bottom right: the chain ribbon and a “Tamper a record” control.
Bottom: the recommendation panel: the action table as paired bars (expected loss versus worst-five-percent loss), the chosen action highlighted, plain-language reasons, the close-call flag, the trust and worst-case-bound note, and the approval route: “auto-approved within thresholds” (calm state) or “needs a person” with Approve, Override (choose another action, reason of at least 10 characters) and Reject. A human action appends a line to the event log labelled “Event dispatched (demo adapter)” and changes the on-screen status; nothing leaves the browser. Say so in a small caption.
Event log: timestamped, newest last, neutral wording, includes scenario starts, checks firing, verdict changes, decision, approval, tamper.
The simulated clock follows the replay frames; scenario changes reset cleanly; reaching the end holds the final frame.

STEP 2. The Scenario Console (premium interaction, from the storyboard). Guarded switches with a flip-up cover and hold-to-arm (about 600 ms, with a visible progress ring, keyboard equivalent for accessibility), a cooldown after use, disabled states with a reason, and a timestamped log entry per action. Fault actions exist in the replay as the recorded scenario choices (the console selects and arms scenarios; do not pretend it injects faults into a running system). Neutral wording only.

STEP 3. Tamper. Extend the exporter (a new or existing script with a test) so each scenario’s chain data includes, from REAL runs on ledger copies: the ledger length, and for a small set of edited entry positions the real verify_chain result (first broken index and reason) from the Phase 4 code, plus the truncation result with and without the anchor. In the Control Room the “Tamper a record” control lets the presenter pick one of those positions; the ribbon then shows the genuine recorded outcome (the link cracks, later links dim, the message names the first broken entry). Label it “Result of a real edit on a ledger copy (recorded)”. Do not implement signature verification in the browser. In live mode, leave tamper disabled with a calm explanation.

STEP 4. Provenance drawer (closed by default). One click shows the honest facts: source “sim” (Sensor feed, synthetic), scenario id, seed, the enterprise adapter mode (“mock”), software versions, profile in use (active illustrative profile), the reference-profile figures, whether the data are a replay, and the signing note: “Signing protects records after signing. It does not stop a false sensor value.” No other badges or banners elsewhere.

STEP 5. Presenter shortcuts and states. Implement the vision’s shortcuts that make sense now (1 to 5 pick a scenario, Space pause, R reset, T tamper, A approve, P provenance, Q quality, F fullscreen, G jump to Story, C jump to Control Room, ? overlay) and list only working ones. States: loading, no data, malformed file (calm message), backend unreachable in live mode (falls back to replay with a calm message), WebGL unavailable (2D fallback of the globe). Live mode stays minimal: read-only status of the backend; the Control Room runs on replay.

STEP 6. Recording mode. ?rec=1 hides the cursor, the overlay, the “?” hint and the performance overlay, locks the quality tier, and runs a scripted, repeatable demo sequence (scenario selection, a tamper, an approval) at fixed timing, so a clean screen recording can be made. Add a short on-screen-free keyboard way to start and stop it. Do NOT try to create a video file; the user will screen-record.

STEP 7. Polish and resilience (keep it proportionate).

Lazy-load the 3D scenes so the shell and Control Room paint first; report bundle sizes before and after.
Chapter 5: reshape the two clusters into plumes from the box ONLY if it takes a small, contained change; otherwise record it as “later” in the report.
Accessibility pass: visible focus on every control, ARIA labels and landmarks for the Control Room, live region for the event log, no colour-only states, prefers-reduced-motion honoured, hold-to-arm has a keyboard path.
Replace the THREE.Clock warning only if it is simple; otherwise note it.
Fix nothing outside this list unless it is a defect you hit.

STEP 8. Tests (targeted). Vitest for: scenario switching and reset, the replay clock and speed, the approval and override rules (reason length), the hold-to-arm and cooldown logic as pure functions, the tamper selection, recording-mode sequencing, view-model mapping from replay frames (no planner maths). Pytest for the exporter additions (real tamper results equal a fresh verify_chain on the same edits). Reuse the existing patterns.

STEP 9. ONE review round and the soak run (see speed rules). Open the app on 127.0.0.1 with Playwright, take the allowed screenshots into docs/05-demo/f4-screenshots/, look at them, fix the top three issues, re-shot only those. Read the performance overlay once on High (name the renderer). Start the 5-minute soak in the background. For each scenario give a short note, not a rubric table. Say plainly whether the Control Room reads from the back of a room (largest numbers, chart text size at 1366x768).

STEP 10. Final steps. Run scripts/run_checks.py ONCE and report totals. Write a concise docs/02-phase-reports/phase-f4-report.md (built, tests, soak result and method, performance reading with renderer, screenshots with notes, PROPOSE items, problems, omissions, can-say and must-not-say). Archive this prompt in docs/06-prompts/phase-f4-prompt.md. Update READMEs and the shortcuts list.

STEP 11. Final report to me in simple words: what was built, test totals before and after, the exact PowerShell commands to run the app (dev and a production build served locally), which keys and clicks to try in what order for a two-minute demo, the soak result, anything surprising, anything not done, open questions as a numbered list, and the single commit block. Then stop. Do not start any other phase.
