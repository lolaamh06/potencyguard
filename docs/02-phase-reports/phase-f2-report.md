# Phase F2: frontend foundation: Report

Date: 2026-10-21. Git commit hash and tag: none yet (the team lead commits). Everything shown is an illustrative journey on a synthetic box. Signing protects records after signing and does not stop a lie at the sensor (A18). All figures are model outputs for an imaginary product; money values and thresholds are illustrative placeholders, not sourced [SOURCE NEEDED].

## 1. What I was asked to do

Build the foundation of the cinematic front end: app shell, scroll rig, a custom three.js globe, a quality governor, a mode adapter with a Python replay exporter, and a TypeScript mirror of the potency maths that matches the shared test vectors. No Chapters 1 to 7 and no Control Room panels (F3 to F5).

## 2. What existed before

`dashboard/` held the Phase 0 smoke test: Vite, React and TypeScript, a dotted-sphere scene, Lenis and GSAP on one ticker, a three-tier quality helper with 3 tests, and `node_modules` as a junction to `%LOCALAPPDATA%\potencyguard\dashboard-node_modules\node_modules`. `package.json` already listed every library the phase needs.

## 3. What I built

- Shell (`src/app`, `src/theme`): tokens as CSS custom properties plus a TypeScript export (`tokens.ts`, checked against the CSS by a test), self-hosted Fraunces, Inter and JetBrains Mono (7 WOFF2 files and 3 licence texts in `public/fonts/`), hash routes `#/story` and `#/control-room`, the "?" shortcuts overlay (only keys that work), a visible reduce-motion control, an error boundary with a calm fallback, and a second boundary around the 3D scene that falls back to the 2D view.
- Scroll rig (`src/scroll`): Lenis driven by the GSAP ticker, ScrollTrigger kept in step, progress in a plain object read by the render loop (no React state per frame), a progress line and chapter rail, keyboard control (arrows, PageDown, PageUp, Space, Home, End), chapter jumps. The full table is 8 scenes totalling 860 vh (tested). F2 renders the Prologue (real text) and three clearly marked placeholder sections.
- Globe (`src/globe`): land dots sampled from the Natural Earth mask on a Fibonacci lattice, a dark body, an atmosphere rim, seeded stars, a great-circle route tube with a moving pulse, state colours (safe, warning, danger), a dashed violet alternative, a shipment marker, a scroll-driven camera path with smootherstep easing, and props (`GlobeProps`) for later phases. Geometry and materials are declared in JSX so React Three Fiber disposes them on unmount. Context loss and restore is handled; a 2D canvas fallback draws the same dots and route.
- Quality (`src/quality`): four tiers, a pure governor function with tests, Q cycling, `?tier=`, a performance overlay on the D key (hidden by default).
- Data (`src/data`): one typed model with the real field names of the exporter, validation that gives calm messages, and three modes (`?mode=story|replay|live`).
- Potency mirror (`src/potency/mirror.ts`): acceleration factor, equivalent time, potency, shelf life used, mean kinetic temperature and the streaming tracker with the suspect-reading rule.
- Python: `scripts/export_replay.py` (writes `dashboard/public/replay/`), `scripts/make_land_mask.py` (writes `dashboard/public/globe/`), `tests/test_export_replay.py`. Both scripts are ruff-clean.
- Changed: `dashboard/package.json`, `package-lock.json` (vite 8.3.4 to 8.3.5), `tsconfig.json` (`resolveJsonModule`), `vite.config.ts` (proxy, test settings), `index.html`, `src/main.tsx`, `src/App.tsx`. `src/styles.css` was removed (replaced by `src/theme/`). `src/smoke/` is untouched and unused (PROPOSE P5).

## 4. Versions, size and the junction

Exact pins are in decision 0011. Packages in `node_modules`: 125 audited by npm in the work folder (the 21 top-level packages in `package.json` plus their dependencies). Only one package changed: vite 8.3.5; every other package was already the latest at install time (`npm view`). No peer-dependency conflict, no `--force`, no `--legacy-peer-deps`.

Junction procedure (full text in decision 0011): copied `package.json` and the lockfile to `%LOCALAPPDATA%\potencyguard\dashboard-node_modules`, ran `npm install --save-exact vite@8.3.5` there, copied both files back, and checked. Result: `dashboard/node_modules` is still a Junction pointing at the same target; no real `node_modules` folder exists inside OneDrive; `git status` shows no `node_modules`, `dist` or `.playwright-mcp` entries. Worked on the first attempt.

Production build: JS 1,387 kB (397 kB gzip), CSS 9 kB (2.9 kB gzip), `index.html` 0.5 kB. Vite warns the JS chunk is over 500 kB (three.js and post-processing). Fonts 156 kB, replay files 177 kB in total (largest 69 kB), land mask 7.4 kB.

## 5. Replay export

Each scenario file holds meta (labels "Illustrative product, model output" and "Synthetic data, simulated sensor feed", the active profile, route points marked illustrative, seeds, software version), frames every 30 minutes (temperature, twin, residual, CUSUM, potency, shelf life used, MKT, trust, verdict, flags), events (checks firing, verdict changes, the proposal), the decision at the checkpoint (table, chosen action, reasons, close call, needs a person, worst-case figures) and the chain summary (key id, entries, result, no anchor). Same input gives the same bytes (tested and checked by hash). The ledger is signed with a TEST-ONLY key derived inside the script; no key is written.

| File | Bytes | Frames | Checkpoint |
|---|---|---|---|
| baseline_ok | 33,733 | 97 | 24 h |
| door_open_excursion | 18,974 | 49 | 12 h |
| reefer_failure | 26,837 | 73 | 20 h |
| spoof_attempt | 27,720 | 73 | 20 h |
| hidden_spoilage | 68,885 | 193 | 50 h |

The two untrusted scenarios are quarantined pending review and need a person; the others show Continue (baseline_ok, door_open_excursion, spoof_attempt, hidden_spoilage) or Reroute to depot (reefer_failure) as the planner recommends. Every checkpoint decision here has `needs_human` true, including baseline_ok, because the planner's governance rule routes it that way, not because anything was added.

## 6. Tests

Baseline: 8 of 8 checks, 739 tests (Python) and 3 dashboard tests. Now: **8 of 8 checks, 749 Python tests** (10 new, all in `tests/test_export_replay.py`) and **77 dashboard tests** in 8 files (74 new). No existing test was edited. The dashboard tests cover: the potency mirror against both vector files (every acceleration factor, every equivalent-time, potency, shelf-life and MKT case, every tracker case with statuses, running totals and final state, and the six rounded document checks); the governor; the scroll maths and key map; the globe geometry, land sampling and camera path; the adapter and validation (valid, malformed, empty, wrong schema, hostile file name, bad frame, mode selection, live fallback and same-origin only); the design tokens.

Potency mirror tolerance: the vector files state no tolerance (their `meta` has none) and the Python tests use a relative 1e-14 for closed forms. Mirror tests use a relative 1e-12 because `Math.exp` and `Math.log` may differ from the C library in the last bit. **Every case matched; none needed more than that, and no case failed.** I did not measure the actual largest difference.

Not tested: the automatic governor against real slow frames (its decision function is unit tested; I did not force a slow machine), and any screen reader.

## 7. Performance numbers (browser: Playwright Chromium)

Renderer reported by the page: **ANGLE (Intel, Intel(R) UHD Graphics, Direct3D11), WebGL 2.** That is a real integrated GPU, not a software renderer. The display ran at about 144 Hz, so fps is capped by the display, not the scene. 1920x1080, scene at the top of the story:

| Tier | fps | frame time | draw calls | triangles |
|---|---|---|---|---|
| High | 96 to 119 | 8.4 to 10.4 ms | 24 | 14,673 |
| Medium | 113 | 8.9 ms | 24 | 14,673 |
| Low | 144 | 6.9 ms | 7 | 14,656 |
| 2D | not measured (no WebGL loop; canvas redraws on change) | | | |

Caveats, stated plainly: the browser window was throttled to about 1.5 frames per second during some measurements (raw `requestAnimationFrame` showed the same rate on every tier), so those readings were discarded and the table uses readings from a freshly started browser. These are single short readings on one machine, not a benchmark. Draw calls differ by tier because post-processing passes are counted on High and Medium.

## 8. Behaviour checked in the browser

- Keyboard: Space and PageDown move one chapter, Home and End go to the edges, `?` opens and Esc closes the overlay, Q cycles High, Medium, Low, 2D, High.
- `?tier=` forces a tier (all four tried). Forcing the 2D tier shows the canvas fallback with the same copy.
- Reduced motion (emulated): the control reads pressed, no smooth scroll, jumps are instant, the camera is still.
- WebGL context lost and restored through `WEBGL_lose_context`: a calm notice shows, the page stays alive, rendering resumes (about 100 fps afterwards).
- Modes: story (bundled figures, no request), replay (5 scenarios loaded), live with no backend (calm fallback message and replay data), live with the backend running (reached, 0 shipments, read-only `GET /health` and `GET /shipments` only). All requests stayed on `127.0.0.1:5173`; no external request. I stopped the backend afterwards.
- Console: no errors. One recurring warning, `THREE.Clock: This module has been deprecated`, comes from React Three Fiber's own use of three; it is not from our code. With the backend down, live mode's polling makes the browser log failed requests (expected).

## 9. Screenshots and scores

In `docs/05-demo/f2-screenshots/` (all under 1.1 MB): story-top, story-middle, story-end at 1920x1080 and 1366x768; story-top at 390x844; tier-low and tier-2d at 1920x1080; reduced-motion-end at 1920x1080.

Scores 1 to 5 against vision section 12 (my own judgement; this is a foundation, so several criteria have little to judge):

| Criterion | Score |
|---|---|
| Hierarchy and clarity | 4 |
| Typography | 4 |
| Colour with meaning | 4 |
| Motion with purpose | 3 |
| 3D craft | 3 |
| Performance and smoothness | 4 |
| Accessibility | 3 |
| Honesty of copy | 4 |
| Story coherence | 3 |
| Memorability | 3 |

Weakest two: **3D craft** (the globe is dots, a dark ball and a rim; the rim needed three adjustments and still looks like a flat band on Low) and **story coherence and memorability** (three placeholder sections carry only a chapter name). I tuned the rim and the camera distance and offset after looking at the first screenshots, and the phone layout (the header overflowed and the text sat on the globe). Re-scored: 3D craft stays 3; the placeholders cannot improve until F3. Accessibility stays 3 because it was not tested with a screen reader and the canvas only has a label.

## 10. PROPOSE items

**P1. Code-splitting.** The JS chunk is 1.4 MB (397 kB gzip). Options: (a) leave as is: simple, works offline from a local server; (b) lazy-load the 3D scene so the shell paints first: faster first paint, slightly more code; (c) split vendor chunks: better caching, no help on first load. Recommendation: (b), in a later phase, when the Story has content.

**P2. Governor thresholds** (25 ms bad frame, 3 windows of 60 frames, 2 warm-up windows). Options: keep; make it stricter (20 ms); make it looser (33 ms). Pros of keeping: conservative, never steps down on a good machine. Con: not tested on a weak GPU. Recommendation: keep, and test on the stage laptop before the demo.

**P3. Dot sizes and counts per tier** (36,000, 20,000, 9,000 lattice samples, kept on land). Recommendation: keep; revisit after the Control Room adds its own load.

**P4. Live mode scope.** F2 only checks the backend and lists shipments. Options: (a) keep that until the Control Room exists; (b) map a live shipment into frames now. Recommendation: (a), per "replay first, live after replay is solid".

**P5. The Phase 0 smoke folder** (`src/smoke/`, unused, 3 tests). Options: delete it (cleaner; its tests go too); keep it as a reference. I left it because I was told not to edit existing tests. Recommendation: delete in F3.

**P6. Pause live polling errors.** With the backend down, the browser logs a failed request every 3 seconds. Option: back off to 15 seconds after a failure. Recommendation: do it when live mode gets real work.

## 11. Problems, surprises, omissions

- A browser throttling problem made the first fps readings meaningless (section 7).
- The `THREE.Clock` warning (section 8).
- Not done: Chapters 1 to 7, the Control Room panels, the vial and box scenes, the Provenance drawer, sound, any screen reader test, the Chapter 1 scrub UI (the mirror is ready and tested), code-splitting, automatic governor test on a slow machine. d3-scale and d3-shape are installed and unused.
- `src/styles.css` was deleted (replaced). `dashboard/dist` is git-ignored and was rebuilt locally.

## 12. What we can say and must not say

Can say: the foundation runs on this laptop's integrated GPU at display speed on every WebGL tier; the TypeScript potency mirror reproduces both shared vector files; the front end shows replay data exported by our own pipeline and makes no external request; live mode reads the backend read-only and falls back calmly.

Must not say: that Chapters or the Control Room exist yet; that the numbers are from real shipments; that performance is proven on other machines; that signing proves the sensor was truthful; that the system is "tamper-proof" or "unhackable".
