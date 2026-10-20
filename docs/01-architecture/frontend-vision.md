# PotencyGuard: Frontend Vision and Design Direction

Version 1.0 (2026-10-20). Binding on every frontend phase (F1 to F6). Read together with the master brief. If this file and the master brief disagree on frontend matters, this file wins. The honesty rules in section 5 of the master brief and section 11 below always win over anything else.

---

## 1. Purpose in one paragraph

The dashboard is not a utility screen. It is the team's strongest weapon: a cinematic, smooth, scroll-driven 3D experience that makes a judge **feel** the problem before they understand the engineering, then drops them into a live control room where the engineering is visible and real. Judges will see many slide decks and many plain dashboards. They should remember this one. The experience has two halves that share one visual language:

1. **The Story** (scrollytelling): about 90 seconds of scrolling that moves from unease, to clarity, to trust, to awe.
2. **The Control Room** (live demo): the working product, with the four demo scenarios, the approval flow and the tamper moment.

It must run **fully offline**, on an ordinary laptop, on a projector, without a network.

---

## 2. Audience and the feeling we are engineering

Audience: SAP engineers and business people, faculty, and fellow students. They value Domain, Tech and Business thinking. They are not impressed by effects alone. They are impressed when beauty **explains** something.

The emotional arc, which every design decision must serve:

| Moment | Feeling we want | How |
|---|---|---|
| Prologue | Quiet unease, curiosity | dark, cold, a single vial in a box, slow breathing frost, one sentence |
| Chapter 1 | "Wait, that is unfair" | two different journeys get the same verdict from a threshold alarm |
| Chapter 2 | "Can we even trust this?" | a sensor that lies, a line that is too calm |
| Chapter 3 | Helpless lateness | a clock that runs out while a decision waits |
| Chapter 4 | Relief and curiosity | the box opens and we see a brain inside it |
| Chapter 5 | Intellectual delight | the cloud of possible futures, and the worst 5% lit up |
| Chapter 6 | Trust and dignity | a human decides, the record seals |
| Control room | Awe and confidence | everything we just learned, alive and verifiable |

Principle: **emotion from clarity, not from decoration.** Every motion answers "what is this showing the viewer?" If it only looks cool, cut it.

---

## 3. Creative direction

### 3.1 Concept: "The Quiet Clock"
A medicine has an invisible clock: its potency. Heat spends it. Cold keeps it. Most systems only watch a thermometer. We make the clock **visible**.
- **Potency** is shown as a living glow inside a glass vial and as a ring of light. It dims as potency is spent.
- **Heat** is warm light (amber to ember) bleeding into cold blue-white.
- **Trust** is shown as glass seals linked in a chain. Valid links glow signal green. A tampered link cracks and goes dark, and everything after it dims.
- **The world** is a night globe with one thin, glowing route.

### 3.2 Visual identity
Mood: nocturnal, clinical, precise, luxurious. Think a high-end medical-device launch film, not a gaming HUD.

Colour tokens (CSS custom properties; also exported to the 3D scene so there is one source of truth):

| Token | Hex | Use |
|---|---|---|
| `--void` | `#04070D` | page background |
| `--ink-900` | `#070C16` | panels |
| `--ink-800` | `#0B1220` | raised panels |
| `--ink-700` | `#111B2E` | borders, grid |
| `--line` | `#1B2A44` | hairlines |
| `--frost` | `#E8F4FF` | primary text |
| `--mist` | `#8FA3BF` | secondary text |
| `--ice-400` | `#5DD6FF` | cold, safe, primary accent |
| `--ice-300` | `#9BE7FF` | highlights |
| `--ember-400` | `#FFB347` | warm warning |
| `--ember-500` | `#FF7A3D` | heat |
| `--ember-600` | `#FF3D2E` | danger, tamper |
| `--verify` | `#3DF2B1` | verified chain, approvals |
| `--planner` | `#8B7CFF` | planner and CVaR accents |

Rules: never more than one accent family dominant in a view. Text on `--void` must meet at least 7:1 contrast for body text. Keep the palette restrained; colour must carry **meaning** (cold, hot, verified, planned), never decoration.

Typography (all open-licence, self-hosted through Fontsource packages, never from a CDN):
- Display (story headlines): a high-contrast serif. DEFAULT **Fraunces**.
- UI and body: a clean grotesk. DEFAULT **Inter**.
- Data and numbers: monospace with tabular numerals. DEFAULT **JetBrains Mono**.
- Final pairing is a **PROPOSE** item in F1 (give 2 alternatives with a rendered comparison).
- Type scale: fluid (`clamp`) from phone to 4K. Headlines large and sparse. Numbers in the control room must be readable from the back of a room.

Texture: a very subtle film grain and a soft vignette, GPU-cheap, switchable off in low quality tiers.

### 3.3 Motion principles
- **Everything is scroll-scrubbed or intentionally timed.** No random idle bouncing.
- Easing: slow in, slow out (custom cubic-bezier, similar to `power3.inOut`); long, calm durations (600 to 1400 ms) for story moves, short (120 to 220 ms) for control-room feedback.
- **One hero motion per scene.** Everything else supports it.
- Parallax is subtle and always depth-consistent.
- Respect `prefers-reduced-motion`: replace camera moves with crossfades.
- No flashing faster than 3 times per second anywhere.
- Smooth scrolling through Lenis, synchronised with GSAP ScrollTrigger on one shared ticker, so DOM and 3D never drift apart.

### 3.4 Sound
Off by default. No audio assets in V1. (Optional later: a single low ambience toggle. Not needed.)

---

## 4. The Story: chapter by chapter

Total scroll length is a **PROPOSE** item (target roughly 800 to 1000 vh). A persistent thin progress rail and chapter names appear at the edge. Each chapter is a pinned scene with scroll-scrubbed animation. Every chapter also has a **skip control** for presenters (jump to the next chapter or straight to the Control Room), and keyboard control (arrow keys, `PageDown`, `Space`).

Copy below is a **draft in our own words**. Claude Code may tighten it but must keep the meaning and must obey section 11. No external statistics appear anywhere in the story. Every number shown is either a model output from our own engine (labelled "synthetic product, model output" in small type) or a generic illustration.

### Prologue: "The Quiet Clock" (about 120 vh)
- **Visual:** black. A frosted insulated box lid, camera inside, looking at a single glass vial. Cold breath of vapour. A faint pulse of glow inside the vial: its potency. The camera slowly pulls back through the lid, the box shrinks, and the night globe fades in beneath it with one thin glowing route from an origin to a destination.
- **Copy (one line at a time, fades in and out):**
  - "Somewhere between the factory and the clinic, a medicine can stop being medicine."
  - "And the box carries no way to say so."
- **Small caption, bottom corner:** "An illustrative journey." (Required: the route and the story are not a real shipment.)
- **Interaction:** none. Pure atmosphere. A subtle "scroll" cue.

### Chapter 1: "Two alarms. One verdict." (about 180 vh) [Pain: G1, binary thinking]
- **Visual:** the globe tilts away; two temperature traces draw side by side on a luminous chart. Journey A: 8 h at 12 °C. Journey B: 24 h at 30 °C. A threshold line at 8 °C. Both traces cross it; two identical red "REJECT" stamps land. Then the vials appear, one beside each trace. Scroll scrubs time: vial A's glow dips barely, vial B's glow visibly drains.
- **Numbers shown (computed live by our engine):** A uses **0.11%** of shelf life; B uses **2.7%**. Caption: "Synthetic product, model output."
- **Copy:**
  - "Two journeys. The alarm gives them the same verdict."
  - "8 hours at 12 °C spends almost nothing. A day at 30 °C spends far more."
  - "The alarm cannot tell the difference. The medicine can."
- **Emotional beat:** after the stamps, a quiet line: "At the other end, a clinic is still waiting."
- **Interaction:** a draggable time handle lets the viewer scrub both journeys. The potency numbers update live.

### Chapter 2: "Whose data is this?" (about 200 vh) [Pain: G2, untrusted data]
- **Visual:** a logger trace appears, suspiciously calm. A ghost line (the thermal twin's prediction) rises away from it as the true box warms. A wedge of red light opens between them: the residual. A hand-shaped shield icon drops over the sensor (a simple abstract mark) and the measured line flattens.
- **Copy:**
  - "A logger can be shielded, swapped or replayed."
  - "A signature proves a record was not edited. It cannot prove the sensor told the truth."
  - "But a box obeys physics. Data that does not, gets caught."
- **Interaction:** the viewer drags a "shield" onto the sensor and watches the residual open and the alert fire.
- **Data:** drawn from the recorded S4 attack scenario.

### Chapter 3: "Too late to matter" (about 150 vh) [Pain: G3, late decisions]
- **Visual:** a long horizontal timeline of the journey. Today: a single marker at the very end, "decision at delivery", with a clock hand sweeping past every chance to act. A pulsing dot shows where the excursion began, far earlier.
- **Copy:**
  - "By the time anyone decides, the journey is already over."
  - "Every hour between the excursion and the decision is a rescue that never happened."
- **Interaction:** none, or a gentle hover on the early dot to show "what could have been done here".

### Chapter 4: "A box that thinks" (about 200 vh) [The solution, the edge]
- **Visual:** the camera dives to the box; it cuts away like a technical illustration, then explodes along its axis: insulated shell, vial rack, a sensor probe, a small computer board, a control module. Each part lights up in turn with a short label. Potency, physics and proof appear as three rings around the computer.
- **Labels (generic, no brand names unless true):** "Sensors", "Edge computer", "Thermal twin", "Potency estimator", "Signed log".
- **Copy:**
  - "Potency, physics and proof, computed where the medicine is."
  - "It works even when the network does not."
- **Note:** the 3D box is a stylised procedural model. The labels describe the **design**; they must not claim that specific hardware is installed in a real box.

### Chapter 5: "Plan for the worst five percent" (about 220 vh) [CVaR]
- **Visual:** thousands of points (our Monte Carlo futures) spray out of the box like a sparkler into a loss landscape. Two clusters: "Continue" and "Reroute". The worst 5% of each is lit in violet. Continue's average looks low, but its violet tail is huge. Reroute's tail is small.
- **Numbers (from the oracle table, synthetic):** Continue: expected loss 4,000, worst-5% average 50,000. Reroute: expected loss 5,250, worst-5% average 10,000. Show as "expected" vs "worst 5%" bars.
- **Copy:**
  - "The average says continue."
  - "The worst five percent says reroute."
  - "We choose by the tail, because a lost shipment is a lost patient's dose."
  - (The last line may be softened; keep the point: rare, severe losses matter more than the average.)
- **Interaction:** a slider for the risk level (alpha) that re-lights the tail; the recommendation flips live at a sensible threshold.

### Chapter 6: "A human decides" (about 150 vh) [Governance]
- **Visual:** an approval card slides forward, carrying the potency curve, residual plot, chain status and the alternatives. A cursor presses **Approve**. A glass seal drops onto the end of the chain and the whole chain pulses signal green.
- **Copy:**
  - "The system recommends. A qualified person decides."
  - "Every decision is sealed into a record that cannot be quietly changed."
- **Note:** authority stays with QA (section 3.6 of the master brief).

### Chapter 7: "Enter the control room" (about 80 vh)
- **Visual:** the camera dives from the story globe into the live Control Room. The scroll story ends and the product begins, with the same globe now carrying the live shipment.
- **Control:** a clear button "Enter" and a keyboard shortcut. Presenters can also jump here directly at any time.

---

## 5. The 3D scenes: specifications

Build everything procedurally or from open data. No downloaded paid or copyrighted models.

**5.1 The globe.** A stylised night globe, not a photoreal earth.
- Land rendered as a dot-matrix or fine-grain glow, generated at build time from public-domain **Natural Earth** data into a compact mask texture (committed to the repo as a small asset, with a README stating its origin and licence).
- Atmosphere: a soft fresnel rim glow in `--ice-400`. A faint star field.
- Route: a great-circle arc between two points, drawn as a thin glowing line with a moving pulse. Waypoints are **illustrative** (generic city points are fine as geography; never real facility names). Route line colour follows the shipment's state: cold-blue safe, amber warning, ember danger, violet planned alternative, dashed.
- Camera choreography is driven by scroll progress and by control-room events (for example, "reroute chosen" swings the camera to the alternative route).
- **Decision:** a custom three.js globe, **not CesiumJS**. Reasons: Cesium excels at real terrain and imagery but brings heavy assets and, for default imagery, an online token and tile-service dependency; fully-offline use needs extra setup, and that is an avoidable stage risk. Our globe needs a look, a route and a camera, not real terrain. (If a later phase proves a real need, propose it.)

**5.2 The vial.** Glass shader with an inner liquid volume. Liquid glow intensity and hue map to potency and temperature: ice-blue bright when healthy, dimming as potency falls, shifting ember with heat. Subtle caustics; no heavy refraction in low tiers.

**5.3 The box.** A stylised procedural cutaway of an insulated shipper: outer shell, foam wall, inner cavity, vial rack, sensor probes, a small board, a control module. An exploded view driven by scroll. Heat appears as a warm glow creeping in from the outer skin, matching the thermal twin's time constant (physically motivated, not random).

**5.4 The futures cloud.** An instanced point cloud (up to about 5,000 points) representing the planner's Monte Carlo outcomes, positioned on a loss axis, with the worst 5% highlighted. Data comes from the planner export (section 7), never invented in the front end.

**5.5 The chain ribbon.** A row of glass tokens (3D or CSS-3D) representing records, linked by luminous threads. Valid: signal green. Tampered link: cracks, flickers once, goes dark; all later links dim. Driven by real `verify_chain` results.

**5.6 Post-processing.** Light bloom, subtle vignette, optional film grain. Everything switchable by quality tier. No heavy depth-of-field.

---

## 6. The Control Room

A single wide screen designed for a projector: large numbers, generous space, clear hierarchy. Layout (a **starting wireframe**; refine in F1):

```
+----------------------------------------------------------------------------+
| logo/wordmark      Scenario: S1 S2 S3 S4        speed 1x 4x 16x    [Provenance]
+-------------+--------------------------------------------+-----------------+
| SHIPMENT    |                                            | POTENCY RING    |
| id, route   |            3D GLOBE + ROUTE                | 98.9%           |
| progress    |     (shipment marker coloured by state)    | remaining life  |
| status chip |                                            | MKT   T_now     |
|             |                                            | time-in-excursion
+-------------+--------------------------------------------+-----------------+
| TEMPERATURE vs TWIN PREDICTION + RESIDUAL + CUSUM   |  CHAIN RIBBON         |
| (shared time axis, excursion bands, alert markers)  |  [Tamper a record]    |
+-----------------------------------------------------+-----------------------+
| RECOMMENDATION: action, CVaR vs expected loss bars, reason, [Approve][Reject]|
+----------------------------------------------------------------------------+
```

Panels and behaviour:
- **Potency ring + big numbers:** potency %, fraction of shelf life used, remaining life in hours, MKT, current temperature. Tabular numerals; smooth number tweening.
- **Chart:** measured temperature, twin prediction (ghost line), residual strip, CUSUM strip, excursion bands, alert markers. One shared time axis. Canvas for performance, SVG for annotations.
- **Chain ribbon:** from section 5.5. A **"Tamper a record"** control really edits a stored record through the backend (or the replay engine in offline mode) and re-verifies, so the break is genuine.
- **Recommendation panel:** the planner's action table (cost, failure probability, expected loss, CVaR) as paired bars, the chosen action highlighted, plain-language reason, and **Approve / Reject** when governance requires a human. Auto-approved cases show a calm "auto-approved within thresholds" state.
- **Scenario controls:** S1 Normal, S2 Mild excursion, S3 Severe excursion, S4 Attack. Speed control for the simulated clock. Pause and reset.
- **Provenance drawer:** closed by default, a small, tasteful control in the top bar. Opens to show data source, scenario id, SAP adapter mode, software version, seed. Honest in one click (master brief section 5, rule 2).
- **Presenter shortcuts:** `1` to `4` pick a scenario, `Space` pause or resume, `R` reset, `T` tamper, `A` approve, `P` provenance drawer, `Q` cycle quality tier, `F` fullscreen, `G` jump to Story, `C` jump to Control Room. Show a discoverable "?" overlay listing them.

Zero-state and error-state design are required: loading, no data, backend unreachable (fall back to replay with a calm message), WebGL unavailable (2D fallback).

---

## 7. Data contract (draft; finalised in Phase 1 and Phase 6)

The frontend must work in **three modes**, selectable by URL parameter and a hidden setting:

1. **Story mode:** self-contained, offline, uses bundled sample data.
2. **Replay mode:** plays **recorded scenario files** (JSON) exported by the simulator and engine. Works with no backend. This is also the safe stage fallback.
3. **Live mode:** subscribes to the backend over WebSocket or server-sent events.

All three consume the **same event format** through one adapter layer, so every visual is mode-agnostic.

Scenario recording (draft):

```json
{
  "meta": {
    "scenario_id": "S3_severe_excursion",
    "schema_version": "0.1",
    "seed": 42,
    "sim_sample_interval_s": 600,
    "speed_factor": 60,
    "product": { "Ea_over_R": 10000, "T_ref_c": 5.0, "tau_max_h": 17520, "P_min": 0.90 },
    "route": { "waypoints": [ { "lat": 0.0, "lon": 0.0, "label": "Origin (illustrative)" } ],
               "alternative": [ ] }
  },
  "frames": [
    { "t_sim_s": 0, "T_c": 4.8, "T_amb_c": 28.0, "T_pred_c": 4.9, "residual_c": -0.1,
      "cusum": 0.0, "rh_pct": 45.0, "shock_g": 0.02,
      "potency": 1.0, "tau_eq_h": 0.0, "l_rem_h": 17520.0, "mkt_c": 4.8,
      "flags": { "jump": false, "drift": false, "flat": false, "suspect": false, "hard_limit": false },
      "chain": { "n": 0, "hash_prefix": "a1b2c3d4", "ok": true },
      "route_progress": 0.0 }
  ],
  "events": [
    { "t_sim_s": 36000, "type": "excursion_start", "payload": {} },
    { "t_sim_s": 41000, "type": "decision", "payload": {
        "actions": [ { "name": "continue", "cost": 0, "p_fail": 0.08, "expected_loss": 4000, "cvar": 50000 },
                     { "name": "reroute_to_depot", "cost": 5000, "p_fail": 0.005, "expected_loss": 5250, "cvar": 10000 } ],
        "recommended": "reroute_to_depot", "auto_approved": false,
        "reason": "worst-case loss falls by 80% (synthetic)", "needs_human": true } },
    { "t_sim_s": 41100, "type": "approval", "payload": { "by": "QA (demo)", "decision": "approved" } }
  ],
  "futures_sample": { "alpha": 0.95, "per_action": { "continue": [ 0, 0, 50000 ], "reroute_to_depot": [ 5000, 55000 ] } }
}
```

Rules: the front end **never computes planner numbers itself**; it displays what the engine exports. The one exception is the Chapter 1 scrub, which uses a small TypeScript mirror of the potency formulas, verified against the **same shared test vectors** (JSON files in `shared/test-vectors/`) that the Python tests use, so both implementations are provably identical.

---

## 8. Technology decisions (DEFAULTS; changes only by PROPOSE)

| Concern | Choice | Why |
|---|---|---|
| App | React + TypeScript + Vite | fast, standard, easy for the team to read |
| 3D | three.js via `@react-three/fiber` and `@react-three/drei` | declarative scenes, large ecosystem, scroll-friendly, offline |
| Post-processing | `@react-three/postprocessing` (light bloom, vignette) | cheap, effective |
| Scroll engine | **Lenis** for smooth scroll + **GSAP ScrollTrigger** for scrubbing | the standard pairing for award-style scrollytelling; GSAP is free to use |
| State | Zustand | small, simple, fast |
| Charts | custom Canvas/SVG with `d3-scale` and `d3-shape` | full visual control, no heavy chart library look |
| Tests | Vitest (logic) and Playwright (visual and flow checks) | repeatable |
| Fonts | Fontsource, self-hosted | offline |
| Not used | CesiumJS (see 5.1), any CDN script or font, any runtime network call to third parties, any large UI kit that gives a generic look |

Versions: install the latest stable at install time and **pin exact versions**. Record them in the phase report.

---

## 9. Performance and reliability (non-negotiable for a live demo)

- **Targets:** 60 fps on a mid-range laptop at 1080p; never below 30 fps in the worst scene; first meaningful paint under 3 s from a local build; production bundle and assets as small as practical (report sizes).
- **Quality tiers:** High, Medium, Low, and **2D fallback** (no WebGL). Tiers change device pixel ratio, post-processing, particle counts, shadow and grain. An **automatic governor** (for example, drei's `PerformanceMonitor`) steps tiers down when frame time worsens and never steps up mid-scene. Presenters can force a tier with `Q`.
- **Offline-first:** no network calls. Fonts, textures, data bundled.
- **WebGL safety:** handle context loss and restore; dispose geometries, materials and textures on unmount; no memory growth over a 30-minute session (test it).
- **Instancing and shaders** for anything repeated. Avoid per-frame React state updates for 3D; use refs and the render loop.
- **Responsive:** laptop and projector first (16:9 and 16:10), usable at phone width for the story, 4K aware.
- **Resilience:** the app must never show a blank screen. Any failure shows a calm, branded fallback and the Replay mode.

---

## 10. Accessibility and inclusion

- Respect `prefers-reduced-motion` and offer a visible "reduce motion" control.
- Full keyboard operation. Visible focus states. Semantic landmarks and headings for the story text; meaningful ARIA labels in the control room.
- Contrast: body text at least 7:1 on dark, large text at least 4.5:1. Never rely on colour alone: pair colour with icon, label or shape (important because heat and verify states use colour).
- No flashing above 3 flashes per second.
- Text in the story is real DOM text (selectable, translatable), not baked into 3D.

---

## 11. Copy and honesty rules for the UI (binding)

1. No false statements. Neutral wording for simulated parts: "Sensor feed", "Event dispatched", "Enterprise system". Never "Live Raspberry Pi", "Connected to SAP S/4HANA", never a named real sensor model, unless true at that moment.
2. The story is an **illustrative journey**. Keep the small "An illustrative journey" caption. Personas, if any, are "composite / illustrative" and carry no invented quotes, names or statistics.
3. **No external statistics on screen** (no "35 billion", no "half of vaccines", no clinic wastage percentages). Only numbers computed by our own engine are shown, and those carry "synthetic product, model output" in small type where they first appear.
4. No "first", "unique" or "novel" claims.
5. The Provenance drawer always works and always tells the truth.
6. No SAP logos or trademarked artwork. Mentioning "SAP BTP" in text is fine where accurate.
7. Targets from the project document are never shown as results.

---

## 12. Quality bar and the review loop

The standard: **would a senior product designer and a senior creative developer both be proud to ship this?**

Anti-patterns to avoid: generic purple-blue gradients, glassmorphism everywhere, default system fonts, stock 3D blobs, cramped dashboards, centred-everything layouts, placeholder text, unexplained motion, console errors, janky scroll, layout shift.

Review loop (every frontend phase):
1. Build the scene or screen.
2. **Look at it.** Use the Playwright browser tools (if installed) to open the page, take screenshots at 1920x1080 and 1366x768 and at three scroll positions, and inspect them. Fix what a critical designer would fix: spacing, hierarchy, contrast, alignment, clipping, motion timing.
3. Check the **performance overlay** and console. No errors, no warnings you cannot explain.
4. Score against the rubric below (1 to 5 each), list the weakest two items, fix them, and re-score. Put the final scores and screenshots in the phase report.

Rubric: hierarchy and clarity; typography; colour with meaning; motion with purpose; 3D craft; performance and smoothness; accessibility; honesty of copy; story coherence; "memorability".

---

## 13. Frontend phases (these slot into the master roadmap; backend phases continue in parallel)

| Phase | Name | Deliverable | Done when |
|---|---|---|---|
| F1 | Art direction and storyboard | `docs/01-architecture/design-system.md` (tokens, type, motion, components), a storyboard of every chapter with the final copy, and 3 static style frames as HTML pages | team lead approves the look; font pairing and scroll length decided |
| F2 | Frontend foundation | app shell, Lenis + ScrollTrigger rig, 3D canvas, globe, quality governor, mode adapter (story, replay, live), shared test vectors and TypeScript potency mirror | smooth 60 fps globe with scroll-driven camera; tiers work; mirror matches vectors |
| F3 | Story chapters 1 to 3 (the pain) | Prologue, Chapters 1 to 3 | the unease lands; interactions work; reviewed with the loop |
| F4 | Story chapters 4 to 7 (the answer) | Chapters 4 to 7 | the box cutaway, futures cloud, approval and chain seal are polished |
| F5 | Control Room | all panels, scenarios, approval, tamper, provenance drawer, presenter shortcuts | S1 to S4 run flawlessly in replay and live |
| F6 | Polish, resilience, recording mode | performance pass, accessibility pass, soak test, a clean "recording mode", a pre-recorded fallback video | 30-minute soak test passes; screen recording looks flawless |

F1 starts after the simulator and engine can export scenario recordings (Phase 1 onward) or in parallel with them, using hand-made sample recordings.

---

## 14. Asset and licence policy

- Fonts: SIL Open Font Licence families only, installed through Fontsource.
- Map data: Natural Earth (public domain). Keep the origin and licence in a README next to the asset.
- No images, 3D models, music or icons from unknown sources. Generate procedurally, or use icon sets with permissive licences (record each in `docs/` with its licence).
- No SAP, vendor or logo artwork.

---

## 15. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Projector or venue laptop has a weak GPU | quality tiers, auto governor, 2D fallback, replay mode, pre-recorded video |
| Venue Wi-Fi fails | offline-first, no network calls |
| Time spent on visuals starves the Round 1 slides | Round 1 slides keep priority; frontend phases are scheduled around them, never before them |
| Scope creep (more scenes, more shipments, more effects) | the chapter list and panel list above are the scope; extras go in a "later" list in the report |
| OneDrive syncing `node_modules` | see the Phase 0 prompt: `node_modules` is kept outside the synced folder |
| Visuals outrun substance | every motion must answer "what is this showing?"; judges reward beauty that explains |
| Heavy 3D hurting readability | the Control Room prioritises numbers and charts; 3D supports, never hides, data |

---

## 16. Decisions reserved for the decision-maker (PROPOSE, never silent)

- Final font pairing; total scroll length; final chapter copy.
- Exact route waypoints (illustrative only).
- Whether to add ambient synthetic shipments to the globe (a stretch idea; default no).
- Any new dependency beyond section 8.
- Any change of the 3D approach (for example Cesium) and any change to quality tiers.
