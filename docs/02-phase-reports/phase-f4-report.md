# Phase F4: the Control Room and final polish: Report

Date: 2026-10-21. Commit hash and tag: none yet (the team lead commits). Everything shown is a simulation on synthetic data for an imaginary product; every figure is a model output of our own engine and is labelled. Signing protects records after signing and does not stop a lie at the sensor (A18). Money values and thresholds are illustrative placeholders, not sourced [SOURCE NEEDED].

## 1. What was built

- **Control Room** (`dashboard/src/controlroom/`): replay-first and offline, driven by the exported replay files. Top bar with five guarded scenario switches, speed 1x/4x/16x, pause, reset, Provenance, and links to the Story and the shortcuts list. Left: shipment card (route progress, status chip with icon and word, trust chip, verdict). Centre: the globe in a window of the screen, marker coloured by state, planned alternative shown when the recommendation is a reroute. Right: potency ring and big numbers with tweening (reported potency, shelf life used, equivalent time, mean kinetic temperature, box temperature), the backend's recomputed potency shown separately from the reported one, and the worst-case bound labelled "worst-case bound, not an estimate". Chart: canvas lines for the reported temperature, the twin and the residual and CUSUM strips on one shared axis, SVG axes, excursion bands (outside an illustrative 2 to 8 C range) and alert markers; chart text is 12.4 px at 1366x768 (measured). Planner panel: paired bars, chosen action, reasons, close-call flag, trust note, and the approval route (calm "auto-approved within thresholds" or "a person must decide" with Approve, Override and Reject). Event log with a live region.
- **Demo decisions:** Override and Reject need a reason of at least 10 characters (Override also needs a different action). A decision adds a line "Event dispatched (demo adapter)", changes the on-screen status, and says nothing leaves the browser.
- **Scenario console:** guarded switches with a flip-up cover, hold to arm (600 ms, visible progress ring), keyboard path (hold Enter or Space), a 2 s cooldown, disabled states with a visible reason, a timestamped log line per action. The console only selects recorded scenarios; it does not inject faults.
- **Tamper (Step 3):** `scripts/export_replay.py` now records, per scenario and from real runs on ledger copies, the ledger length, the real `verify_chain` result (first broken index and reason) for edits at five positions, and the truncation with and without the anchor. The Control Room shows these as "Result of a real edit on a ledger copy (recorded)": the link cracks, later links dim, the message names the broken entry. No verification runs in the browser. In live mode the control is disabled with an explanation.
- **Provenance drawer** (closed by default): source "sim (Sensor feed, synthetic)", scenario id, seeds, adapter "mock (Enterprise system, simulated)", versions, active illustrative profile, reference-profile figures, "a replay of a recording", and the signing note.
- **Shortcuts:** 1 to 5, Space, R, T, A, P, Q, F, G, C, D, M, ? (the overlay lists only working keys). **Recording mode** `?rec=1`: cursor, overlay, "?" hint and performance overlay hidden, tier locked, and V starts or stops a scripted 33 s sequence (two scenarios, a tamper, an approval, the drawer). No video is made.
- **States:** loading, no data, malformed or missing file (calm message), live mode with the backend down (replay with a calm message), 2D fallback of the globe.
- **Polish:** the 3D code is lazy-loaded; initial JS is **351 kB (116 kB gzip), down from 1,387 kB (397 kB gzip)**; the three.js chunk (919 kB, 244 kB gzip) loads after the shell. Accessibility: visible focus everywhere, landmarks and labelled regions, `role="log"` live region, status never by colour alone (icon plus word), reduced motion honoured (tweens instant), keyboard path for hold-to-arm.

## 2. Tests

Before: 756 Python tests, 88 dashboard tests. Totals after the single full `run_checks.py` run are in the final message. New: `tests/test_export_tamper.py` (exported tamper results equal a fresh `verify_chain` on the same edits, truncation with and without the anchor, worst-case label, provenance, schema); dashboard `controlroom/logic.test.ts` (scenario keys, replay clock and speed, hold-to-arm and cooldown as pure functions, approval and override rules, tamper selection and outcomes, event log, recording sequence, view-model mapping) and `controlroom/store.test.ts` (scenario switching and reset, clock, demo decisions, tamper). Existing tests edited: one (`tests/test_export_replay.py` schema assertion now lists the two new keys).

## 3. Review (one round, Playwright Chromium, production-like scale at 1920x1080 and 1366x768)

Console: no errors; one `THREE.Clock` deprecation warning from React Three Fiber's own code (not simple to remove, left). Network: nothing outside 127.0.0.1. **Performance overlay once on High: 143.8 fps, 7.0 ms, 26 draw calls, 16,945 triangles; renderer ANGLE (Intel, Intel UHD Graphics, Direct3D11), WebGL 2** (display-capped, one machine). Fixed after looking: the globe window first showed the Prologue's vial (wrong camera in the Control Room), chips wrapped, figures clipped, the override form stretched the planner (now a popover), the tamper note overflowed, the active chip looked disabled, the planner overflowed at 1366x768 (denser table, one reason shown).

| Scenario | Note |
|---|---|
| baseline_ok | calm: trusted, auto-approved, flat chart; the bars for the other actions are far larger |
| door_open_excursion | short excursion band, a verdict change, auto-approved |
| reefer_failure | long excursion band, reroute recommended, dashed alternative on the globe, auto-approved by the backend's rules |
| spoof_attempt | untrusted, quarantined, a person must decide |
| hidden_spoilage | reported 99.9% against a worst-case bound of 75.6% and 265% shelf life used; recomputed value shown separately; a person must decide |

**From the back of a room?** Partly. The potency number (about 2.9 em, 36 px at 1920x1080), the status chips and the recommendation read at distance; at 1920x1080 the table and log text (about 10 to 11 px at 1366x768 for the small labels, 12.4 px for chart text) are for a person near the screen. The screen is a dense instrument panel, not a slide.

## 4. Soak (5 minutes, one scripted run)

Method: the production build served by `vite preview`, the Control Room at 1920x1080 on High, a script inside the page for 300 s: every 2.5 s one action in rotation (select scenarios 1 to 5, T tamper, A approve, P provenance), 120 actions in total, replay at 16x. Every 12 s it recorded the JS heap (`performance.memory.usedJSHeapSize`, coarse, no forced garbage collection) and the frame rate (requestAnimationFrame count per second).

Result: heap 51.7 MB at 3 s, 44.4 MB at 300 s, with no upward trend (range 43.5 to 51.7 MB). Frame rate 140.7 at 3 s and 143.9 to 144 for the rest, on ANGLE (Intel UHD Graphics, Direct3D11); the display is the cap. No console errors during the run. Not tested: other machines, longer runs, the Story, live mode.

Also checked once by script: recording mode (`?rec=1`) hides the cursor, the "?" button and the performance overlay, and V ran the scripted sequence to the end (scenario, tamper, approval, drawer); the 2D fallback renders in the Control Room.

## 5. PROPOSE items

1. **Chapter 5 plumes** were not done (recorded as "later"): shaping the clusters needs changes in the 3D layout and camera that are not small. Recommendation: only if time remains.
2. **THREE.Clock warning** comes from the library; leave until React Three Fiber updates.
3. **Planner panel density** at 1366x768 is tight; if the stage laptop is small, drop the reasons list to one line or enlarge the screen scale. Recommendation: test on the stage laptop.
4. **Live mode** still only reads the backend status; a real live Control Room is a later phase.

## 6. Problems and omissions

Not done: Chapter 5 plumes, phone layout, a recorded video, a screen reader pass, per-tier measurements. The soak heap numbers come from `performance.memory`, which is coarse and not forced to collect garbage. The 1366x768 reefer shot has the performance overlay on top of the planner (it was the allowed overlay reading).

## 7. Can say / must not say

Can say: the Control Room plays five recorded scenarios with real exported numbers; tamper results are real `verify_chain` results on ledger copies; demo decisions change the screen only; the worst-case bound is labelled a bound; reported and recomputed values are shown separately.

Must not say: that anything is connected to an enterprise system or to hardware; that tamper is verified in the browser; that the figures are from real shipments; that the system is "tamper-proof" or "unhackable"; that signing proves the sensor was truthful.
