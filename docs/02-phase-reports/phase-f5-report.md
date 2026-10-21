# Phase F5: product UX overhaul: Report

Date: 2026-10-21. Commit hash and tag: none yet (the team lead commits). The data are sample data from a simulation; actions on screen change the screen only; the enterprise system is a demo stand-in. Signing protects records after signing and does not stop a false sensor value (A18). Money values and thresholds are illustrative placeholders, not sourced [SOURCE NEEDED]. No Python, exporter, replay data or backend file was changed.

## 1. What was built

- **Seven pages** (hash routes): Home, Shipments (five cards, one marked "Start here"), Shipment (plain headline, playback, gauge, temperature chart, recommendation with two cost bars, approval buttons, "What happened" sentences, "Show details"), Decisions (queue, three buttons with confirm dialogs), Proof (check, try to change a record with Early/Middle/Late, deleted-records case, the honest limit), About this data (real versus simulated, reference constants, collapsed technical list), and the existing Story. The old single Control Room page and the hold-to-arm control are gone.
- **Navigation** on every page in the same place and order, current page marked by colour, underline and `aria-current`; Help, Light/Dark/System and Simple/Technical in the bar; a Menu button on phones. Every page has a title and a one-line purpose, a Back link (Shipment has a breadcrumb), and a "Next step" button; a "Skip to content" link; the footer links to About this data.
- **Glossary** (`src/copy/glossary.ts`): 27 terms in two registers with a one-sentence explanation each, plus lookups for actions, verdicts and the trust answer (Yes / Partly / No). Components ask for a term by id and the reading mode. CUSUM, residual and the twin are hidden in Simple mode. A "?" button with a keyboard-accessible popover explains terms that stay visible. The switch is global, remembered, and defaults to Simple.
- **Plain sentences from data:** `copy/headline.ts` builds the headline, the status word (All good / Needs a person / Data not trusted / Problem found) and the reasons from verdict, trust, route, chosen action and event times; `copy/timeline.ts` builds "What happened". No figure is typed by hand. Wording stays true: untrusted shipments say "we cannot trust this data" and "A person needs to approve this".
- **Themes:** a light token set (`theme/tokens-light.css`, `palette.ts`), a toggle remembered in guarded storage, applied by an inline script before first paint. The globe and the chart read the palette and re-theme live (pale globe with dark dots in light mode, no bloom or stars). The Story stays a dark cinematic stage in both themes (decision below).
- **Guided tour** (5 steps, first visit offer on Home, skippable, restart from Help) and a **Help dialog** (pages, buttons, working shortcuts). Dialogs trap focus and close on Esc. Every button has a text label; no icon-only buttons; risky actions use a confirm dialog.
- **Recording mode** `?rec=1`: V starts and stops a scripted run through the new pages (open two shipments, approve, Proof with a recorded change, About), pressing the same visible buttons at fixed times.
- Logic reused unchanged: replay clock, store, approval validation, tamper selection, view-model mapping (`controlroom/logic.ts`, `store.ts`). The store gained a per-shipment `outcomes` map and an `ignoreClock` option so the Decisions page works without playing a shipment.

## 2. Tests

Before: 760 Python tests, 122 dashboard tests. Totals after the one full `run_checks.py` run are in the final message. New dashboard tests: `theme/palette.test.ts` (WCAG contrast of every text/background pair in both themes, and that the CSS matches the palettes), `theme/prefs.test.ts` (theme persistence helper, safe fallbacks), `copy/copy.test.ts` (glossary complete in both registers, plain wording, Simple/Technical lookup, headline builder for all five scenarios with true statements), `app/route.test.ts` (route map: every page reachable, Back on every page but Home, Next-step chain visits each page once with no loop), `app/ui.test.ts` (the switch, theme, tour), `pages/decisions.test.ts` (queue and form validation).

**Existing tests edited (all minimal):** `controlroom/store.test.ts` (added `clearDecisions()` to `beforeEach`, because decisions now persist across scenario changes); `controlroom/logic.test.ts` (the recording-sequence kinds list and its title, because the sequence now drives pages instead of scenario chips). The hold-to-arm and cooldown functions and their tests are kept (pure, unused by the screen).

## 3. Click path (from Home)

| Page | Clicks from Home | Its "Next step" leads to |
|---|---|---|
| Home | 0 | Shipments ("Try the demo") |
| Shipments | 1 | the Start here shipment |
| Shipment | 2 (Shipments, Open) | Decisions |
| Decisions | 1 | Proof |
| Proof | 1 | About this data |
| About this data | 1 | none (ends with "Back to Home" and "Watch the story") |
| Story | 1 | none (its last scene has "Try the demo") |

## 4. Review (one round, Playwright Chromium, 13 screenshots in `docs/05-demo/f5-screenshots/`)

Console: no errors (one `THREE.Clock` library warning). Network: nothing outside 127.0.0.1. Performance overlay once on High: **113 fps, 8.8 ms, 24 draw calls, ANGLE (Intel UHD Graphics, Direct3D11), WebGL 2.** Fixed after looking: the Menu button showed on desktop; the cost bars did not draw (class clash with Chapter 5, renamed); card buttons stretched full width; the Shipments lead repeated the hint; an untrusted shipment showed "100.0%" without saying the readings are not trusted (note added); in the light theme the Story's headline was dark on the dark stage (fixed).

Could a first-time visitor know what to click?
- **Home:** yes, two big buttons ("Watch the story", "Try the demo") and a tour offer.
- **Shipments:** yes, "Pick a shipment to begin", one card says Start here, every card has Open.
- **Shipment:** mostly; Play, Restart and the three speeds are labelled, but the page is long and the buttons for deciding sit below the chart.
- **Decisions:** yes, three labelled buttons per item and a confirm that says nothing is sent.
- **Proof:** yes, numbered steps, each with one button.
- **About this data:** yes, it is reading only, with Back to Home and Watch the story at the end.
- **Story:** yes for scrolling (rail and the keys), but its copy was not rewritten in plain words and its controls are unchanged.

## 5. PROPOSE items

1. **Story theme:** it stays dark in both themes (its 3D scenes use additive glow that vanishes on a pale stage). Alternative: a light version of every scene. Recommendation: keep dark.
2. **Shipment page length:** move the approval buttons beside the headline. Recommendation: yes, in a polish pass.
3. **The old Story copy** still uses some technical words in Chapter 2 and 6. Recommendation: leave it (it explains them) or add Simple wording later.
4. **Phone layout** is only checked by CSS, not by a screenshot (none were requested).

## 6. Problems and omissions

Not done: a screenshot at phone width, a screen reader pass, the tour was not clicked through step by step in the browser (its logic is unit tested), the Technical-mode chart was not screenshotted. The tour offer shows only on first visit and needs `localStorage`. Some Story panels share class names with the new pages (`.card`, `.btn`, `.ribbon`); the Story was checked at its first screen only.

## 7. Can say / must not say

Can say: a first-time visitor can start on Home, reach any page in one click, and follow a guided path; every term has a plain version and a technical version; both themes meet the contrast rules we test; the wording stays true when the data are untrusted.

Must not say: that the Story was rewritten in plain words; that it works on every phone; that anything is connected to an enterprise system; that the records are "tamper-proof" or "unhackable"; that the figures are real.
