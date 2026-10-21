# PotencyGuard design system (Phase F1)

Status: proposal for approval (F1). Binding source for the tokens is `docs/01-architecture/style-frames/tokens.css`; the three style frames and the font comparison use it. Everything shown with this system is an illustrative journey on a synthetic box; numbers on screen come from the project's own code, never typed by hand (vision section 11). Signing protects records after signing; it does not stop a lie at the sensor (A18), and the design never implies otherwise.

## 1. Principles

1. Emotion from clarity: every colour, glow and motion answers "what is this showing?".
2. Colour carries meaning (cold, hot, verified, planned), never decoration, and **colour is never alone** (section 9).
3. One accent family dominates a view. The Control Room is calm: numbers and charts first, 3D second.
4. Offline: every font and asset is local; no CDN, no network request (checked with the browser's network log on every style frame).

## 2. Colour tokens

Palette from the vision (section 3.2), plus the semantic additions marked **new**. A token is a CSS custom property in `tokens.css`; the 3D scene reads the same values.

| token | hex | use |
|---|---|---|
| `--void` | #04070D | page background |
| `--ink-900` | #070C16 | panels |
| `--ink-800` | #0B1220 | raised panels, tracks |
| `--ink-700` | #111B2E | borders, grid |
| `--line` | #1B2A44 | decorative hairlines only (never the only mark of a control) |
| `--line-strong` **new** | #5E7899 | borders of controls, chart axes, dashed outlines (3:1 or better) |
| `--frost` | #E8F4FF | primary text |
| `--mist-hi` **new** | #A9BAD1 | secondary text (7:1 or better on every surface) |
| `--mist` | #8FA3BF | tertiary text and dim states; large text only on `--ink-700` |
| `--ice-400` | #5DD6FF | cold, safe, primary accent |
| `--ice-300` | #9BE7FF | highlights, focus ring |
| `--ice-700` **new** | #14506B | fills behind cold data, bar starts |
| `--ember-400` | #FFB347 | warning |
| `--ember-500` | #FF7A3D | heat, failure marks |
| `--ember-600` | #FF3D2E | danger fill and graphics (not for small text) |
| `--danger-text` **new** | #FF8A7A | danger and tamper TEXT (`--ember-600` is too dark for small text) |
| `--verify` | #3DF2B1 | verified chain, approvals |
| `--planner` | #8B7CFF | planner and CVaR fills and graphics |
| `--planner-300` **new** | #B7AEFF | planner TEXT (`--planner` is 6.2:1 on the page background, short of the 7:1 target) |

Fill gradients: cold data `#26455F` to `--ice-400`; planner data `#3A3380` to `--planner`.

### 2.1 Contrast, computed

Every pair was computed with the WCAG 2.x relative-luminance formula in `style-frames/generate_data.py` (output `style-frames/data/contrast.json`). Targets from the vision: body text 7:1, large text 4.5:1; graphics and control borders 3:1. A cross means the pair must not be used for that role.

| text or graphic token | hex | role | needs | void | ink-900 | ink-800 | ink-700 | passes on |
|---|---|---|---:|---:|---:|---:|---:|---|
| `--frost` | #E8F4FF | primary text | 7:1 | 18.07 ✓ | 17.53 ✓ | 16.78 ✓ | 15.42 ✓ | all four |
| `--mist-hi` | #A9BAD1 | secondary text | 7:1 | 10.21 ✓ | 9.91 ✓ | 9.48 ✓ | 8.71 ✓ | all four |
| `--mist` | #8FA3BF | tertiary text, large only | 4.5:1 | 7.84 ✓ | 7.60 ✓ | 7.27 ✓ | 6.69 ✓ | all four |
| `--ice-400` | #5DD6FF | cold or safe accent text | 7:1 | 12.03 ✓ | 11.67 ✓ | 11.17 ✓ | 10.27 ✓ | all four |
| `--ice-300` | #9BE7FF | highlight text | 7:1 | 14.66 ✓ | 14.23 ✓ | 13.61 ✓ | 12.51 ✓ | all four |
| `--ember-400` | #FFB347 | warning text | 7:1 | 11.32 ✓ | 10.99 ✓ | 10.51 ✓ | 9.66 ✓ | all four |
| `--ember-500` | #FF7A3D | heat text | 7:1 | 7.78 ✓ | 7.55 ✓ | 7.22 ✓ | 6.64 ✗ | void, ink-900, ink-800 |
| `--danger-text` | #FF8A7A | danger or tamper text | 7:1 | 8.80 ✓ | 8.54 ✓ | 8.17 ✓ | 7.51 ✓ | all four |
| `--ember-600` | #FF3D2E | danger fill, graphics and large text | 3:1 | 5.72 ✓ | 5.55 ✓ | 5.31 ✓ | 4.88 ✓ | all four |
| `--verify` | #3DF2B1 | verified text | 7:1 | 13.96 ✓ | 13.54 ✓ | 12.96 ✓ | 11.91 ✓ | all four |
| `--planner-300` | #B7AEFF | planner text | 7:1 | 10.09 ✓ | 9.79 ✓ | 9.37 ✓ | 8.62 ✓ | all four |
| `--planner` | #8B7CFF | planner fill, graphics and large text | 3:1 | 6.17 ✓ | 5.99 ✓ | 5.73 ✓ | 5.27 ✓ | all four |
| `--line-strong` | #5E7899 | borders of controls, chart axes | 3:1 | 4.44 ✓ | 4.31 ✓ | 4.12 ✓ | 3.79 ✓ | all four |

Reading it: `--mist` fails the 7:1 body rule on `--ink-700` (6.69) and is used only for dim, non-essential marks; `--ember-500` as TEXT passes on `--void`, `--ink-900` and `--ink-800` but not `--ink-700` (6.64); `--ember-600` and `--planner` are fills and graphics. The first version of the palette had no passing token for danger text and planner text; the two new text tokens fix that.

## 3. Type

Three roles, one family each (pairing decided by PROPOSE FD-1, section 8). All SIL OFL 1.1, self-hosted, Latin subset WOFF2.

| role | default family | weights | used for |
|---|---|---|---|
| display | Fraunces | 400, 600 | story headlines, big names, the recommendation |
| UI and body | Inter | 400, 500, 600 | everything readable, labels, buttons |
| data | JetBrains Mono | 400, 500 | every number, tabular and slashed-zero (`font-variant-numeric: tabular-nums slashed-zero`) |

Fluid scale (`clamp(min, preferred, max)`); computed sizes in px:

| step | clamp | at 390 | at 1366 | at 1920 | at 3840 | use |
|---|---|---:|---:|---:|---:|---|
| caption | clamp(0.75rem, 0.72rem + 0.12vw, 0.875rem) | 12.0 | 13.2 | 13.8 | 14.0 | footnotes, axis labels |
| small | clamp(0.8125rem, 0.78rem + 0.15vw, 0.9375rem) | 13.1 | 14.5 | 15.0 | 15.0 | chips, captions |
| body | clamp(0.9375rem, 0.9rem + 0.2vw, 1.125rem) | 15.2 | 17.1 | 18.0 | 18.0 | paragraphs |
| lead | clamp(1.125rem, 1rem + 0.5vw, 1.5rem) | 18.0 | 22.8 | 24.0 | 24.0 | story supporting line |
| h3 | clamp(1.25rem, 1.05rem + 0.9vw, 2rem) | 20.3 | 29.1 | 32.0 | 32.0 | card titles |
| h2 | clamp(1.75rem, 1.2rem + 2.2vw, 3.5rem) | 28.0 | 49.3 | 56.0 | 56.0 | chapter headlines |
| h1 | clamp(2.25rem, 1.2rem + 4.2vw, 6rem) | 36.0 | 76.6 | 96.0 | 96.0 | prologue headline |
| number | clamp(2.5rem, 1.5rem + 3.6vw, 6.5rem) | 40.0 | 73.2 | 93.1 | 104.0 | hero numbers |

The Control Room does not use this clamp scale: its whole layout is in `rem` with `html { font-size: calc(100vw / 110) }`, so it scales as one picture from 1366 to 4K (about 12.4 px per rem at 1366 and 17.5 px at 1920). Its smallest text is 0.8 rem (about 10 px at 1366 and 14 px at 1920); chart axis text is sized from the chart height and may be slightly smaller at 1366. Line lengths: body 60 to 75 characters; story headlines at most 18 characters per line when possible (`text-wrap: balance`).

## 4. Spacing, radii, elevation, glow

- Spacing, 4 px base: 0.25, 0.5, 0.75, 1, 1.5, 2, 3, 4.5, 7 rem (`--s-1` to `--s-9`). The Control Room uses 0.8 rem gutters and 0.8 rem gaps.
- Radii: 4 px (tags), 8 px (buttons), 14 px (panels; the Control Room uses 0.9 rem), pill for chips.
- Elevation is a hairline plus a dark shadow, never a light shadow: `--elev-1` for panels, `--elev-2` for drawers and menus.
- Glow is reserved for meaning and used once per element: ice (cold data and the active control), verify (a verified link), planner (a planned or tail item), danger (a broken link). No glow for decoration.
- Texture: film grain at 4.5 percent opacity and a radial vignette on story frames only, switchable off in the low quality tier and by reduced motion.

## 5. Motion tokens

| token | value | use |
|---|---|---|
| `--d-instant` | 120 ms | press feedback, focus |
| `--d-quick` | 220 ms | hover, small state changes |
| `--d-ui` | 360 ms | panel open and close, chip changes |
| `--d-story` | 900 ms | story arrivals (headlines, labels) |
| `--d-slow` | 1400 ms | camera moves, scene changes |
| `--ease-inout` | cubic-bezier(0.65, 0, 0.35, 1) | story moves (like power3.inOut) |
| `--ease-out` | cubic-bezier(0.22, 1, 0.36, 1) | arrivals and fills |
| `--ease-in` | cubic-bezier(0.64, 0, 0.78, 0) | departures |
| `--ease-linear` | linear | scroll-scrubbed values only |

Rules: one hero motion per scene; nothing idles at random (the style frames use two slow ambient loops, a 6.5 s glow breath and a 11 s vapour drift, both removed by `prefers-reduced-motion`); nothing flashes faster than 3 times a second; with `prefers-reduced-motion: reduce` every duration is set to 1 ms and camera moves become crossfades.

## 6. Iconography

A small set of 16 px line icons drawn by hand as inline SVG (`stroke: currentColor`, 1.7 to 2.2 px round caps): check, warning triangle, crack, dash, shield-slash, user, diamond, lock, pause, chevron, cross, dot. No icon font, no third-party set, no logos and no trademarked artwork. Each icon pairs with a label or a shape; icons are `aria-hidden` when a label is present.

## 7. Component inventory

States for all interactive parts: default, hover, focus, active, disabled, error. Focus is a 2 px `--ice-300` ring with 3 px offset on every control; hover raises border contrast (never only colour); disabled uses `--mist` text, `--line` border and `cursor: not-allowed`; error uses `--danger-text` with the warning icon.

| component | what it is | notes on states |
|---|---|---|
| **Potency ring** | two concentric arcs: reported potency (outer, ice) and, when data are not trusted, the worst case (inner, ember), with the number in the middle | default: outer arc only when trusted. Untrusted: inner arc appears with the label "worst case"; error state is the label plus the warning icon, never just a colour change. The number is mono and tweened at `--d-ui` |
| **Chart panel** | stacked strips on one time axis: temperature with the twin prediction, residual in sigma, CUSUM with its threshold; alarm marks as a diamond, a dashed line and a text label | hover shows a crosshair and a readout; focus lets arrow keys step the time; alarm marks never rely on colour (diamond plus label) |
| **Chain ribbon** | a row of tokens linked by threads: verified (check, green outline), broken (crack, red, slightly larger), after the break (dash, dashed outline, dimmed) | broken token flickers once on arrival (one flash, under 3 per second) and then holds; every token has a title with its entry index and hash prefix |
| **Recommendation panel** | the planner table as paired bars (expected loss, worst 5 percent), a check on the recommended action, a diamond on the lowest expected loss, reasons with the user icon, a route chip, Approve, Override, Reject | route states: "Auto-approved within thresholds" (verify chip with check) or "A person must decide" (error-coloured chip with the user icon). Buttons are disabled with the reason as text until the route needs a person; Approve needs a second confirmation |
| **Scenario switch with guarded cover** | a toggle under a hinged cover (stripes, lock icon); flip the cover, then press and HOLD for 800 ms to arm (a ring fills), then it fires and cools down for 3 s | default: covered. Hover: cover lifts 4 px. Focus: ring on the cover. Active: the cover is open and the ring fills (aria-live announces "arming, 60 percent"). Disabled: during the cooldown, with a visible countdown. Error: a refused injection shows the reason in the event log. Keyboard: Enter opens the cover, holding Space arms |
| **Event log** | a timestamped list of what happened, in neutral words ("Sensor feed: reading received", "Physics check fired", "Event dispatched", "Approval recorded") | newest on top; every row has an icon and a time; severity shown by icon plus text; selectable text |
| **Provenance drawer** | closed by default, a small button in the top bar; opens a panel with data source, scenario id, origin (replay or live), enterprise adapter mode, software version, planner seed, twin time constant, recording path | default closed; `P` toggles; `Esc` closes; the content is read from the same JSON as the numbers and always tells the truth in one click |
| **Status chips** | pills with an icon and a label: shipment status, trust level, verdict, route, scenario | one icon plus one word each: shield-slash "quarantined", warning "untrusted", check "verified", user "a person must decide", dot "verdict". Border and text share one token |

## 8. Fonts: the proposal and two alternatives (PROPOSE FD-1)

Rendered side by side in `style-frames/fonts-compare.html` with the same copy and the same numbers (screenshots in `docs/05-demo/f1-screenshots/fonts-compare-*.png`).

- **Pairing A (recommended): Fraunces, Inter, JetBrains Mono.** The vision's default. Fraunces gives headlines warmth and weight without looking like a magazine template; Inter is neutral and very legible on a projector; JetBrains Mono has clear slashed zeros and tall figures, so 0 and O and 1 and l are never confused in a hash or a number. Pro: tested in the Control Room frame at 1366 and 1920. Con: Fraunces' soft shapes are a little less severe than the clinical mood; mitigated by using it only for headlines.
- **Pairing B: Newsreader, IBM Plex Sans, IBM Plex Mono.** Calmer and more editorial; UI and data share one design family. Pro: very coherent. Con: lighter figures at a distance and a more bookish headline voice.
- **Pairing C: Instrument Serif, Instrument Sans, DM Mono.** The most distinctive display face. Pro: elegant at big sizes. Con: the serif has one weight (emphasis must come from italic or colour) and DM Mono is rounder and shorter, which costs legibility for numbers.

Files (Latin subset, only the weights used), fetched with `npm` in a scratch folder OUTSIDE the repository (`%LOCALAPPDATA%\potencyguard\font-work`, nothing installed in `dashboard/` or the repo root) from the Fontsource packages, versions pinned by `--save-exact`:

| family | Fontsource package | version | licence | files | bytes |
|---|---|---|---|---:|---:|
| DM Mono | `@fontsource/dm-mono` | 5.3.0 | OFL-1.1 | 2 | 29,808 |
| Fraunces | `@fontsource/fraunces` | 5.3.0 | OFL-1.1 | 2 | 36,064 |
| IBM Plex Mono | `@fontsource/ibm-plex-mono` | 5.3.0 | OFL-1.1 | 2 | 29,596 |
| IBM Plex Sans | `@fontsource/ibm-plex-sans` | 5.3.0 | OFL-1.1 | 3 | 71,024 |
| Instrument Sans | `@fontsource/instrument-sans` | 5.3.0 | OFL-1.1 | 3 | 51,500 |
| Instrument Serif | `@fontsource/instrument-serif` | 5.3.0 | OFL-1.1 | 2 | 43,160 |
| Inter | `@fontsource/inter` | 5.3.0 | OFL-1.1 | 3 | 72,388 |
| JetBrains Mono | `@fontsource/jetbrains-mono` | 5.3.0 | OFL-1.1 | 2 | 43,000 |
| Newsreader | `@fontsource/newsreader` | 5.3.0 | OFL-1.1 | 2 | 46,356 |

Total 422,896 bytes for all three pairings. Licence texts: `style-frames/fonts/LICENSE-*.txt` (SIL Open Font Licence 1.1). Manifest with every file size: `style-frames/fonts/manifest.json`. Files:
  - DM Mono: dm-mono-latin-400-normal.woff2 (14,820 B), dm-mono-latin-500-normal.woff2 (14,988 B)
  - Fraunces: fraunces-latin-400-normal.woff2 (17,968 B), fraunces-latin-600-normal.woff2 (18,096 B)
  - IBM Plex Mono: ibm-plex-mono-latin-400-normal.woff2 (14,708 B), ibm-plex-mono-latin-500-normal.woff2 (14,888 B)
  - IBM Plex Sans: ibm-plex-sans-latin-400-normal.woff2 (22,588 B), ibm-plex-sans-latin-500-normal.woff2 (24,184 B), ibm-plex-sans-latin-600-normal.woff2 (24,252 B)
  - Instrument Sans: instrument-sans-latin-400-normal.woff2 (16,860 B), instrument-sans-latin-500-normal.woff2 (17,232 B), instrument-sans-latin-600-normal.woff2 (17,408 B)
  - Instrument Serif: instrument-serif-latin-400-italic.woff2 (22,128 B), instrument-serif-latin-400-normal.woff2 (21,032 B)
  - Inter: inter-latin-400-normal.woff2 (23,664 B), inter-latin-500-normal.woff2 (24,272 B), inter-latin-600-normal.woff2 (24,452 B)
  - JetBrains Mono: jetbrains-mono-latin-400-normal.woff2 (21,168 B), jetbrains-mono-latin-500-normal.woff2 (21,832 B)
  - Newsreader: newsreader-latin-400-normal.woff2 (22,480 B), newsreader-latin-600-normal.woff2 (23,876 B)

The shipped build will contain only the chosen pairing (about 120 to 160 KB).

## 9. Colour is never alone

Every state carries a second signal that survives greyscale:

| state | colour | second signal |
|---|---|---|
| verified link | green | check icon, solid outline |
| broken link | red | crack icon, larger token, text "broken" |
| after the break | dim | dash icon, dashed outline |
| trusted / untrusted / low confidence | none / red / amber | words plus icon (check, warning triangle, user icon) |
| cold or safe / hot | ice / ember | numbers with units, position on a labelled axis |
| expected loss / worst 5 percent | ice / violet | position in the pair (first and second bar), different labels, diamond marks for tail points, cross marks for failed futures |
| alarm | red | diamond, dashed vertical line, text label with the time |
| recommended / lowest average | check / diamond | icons in the legend |

## 10. Accessibility

Real DOM text everywhere (selectable); landmarks and headings; focus rings; the Control Room is fully keyboard-driven (presenter shortcuts listed in the vision, section 6); `prefers-reduced-motion` and a visible reduce-motion control; charts carry a text alternative (the SVG and canvas have `role="img"` and an `aria-label` that states what they show); no flashing above 3 per second; text contrast per section 2.1.

## 11. Assets and licences

Fonts: SIL OFL 1.1 (section 8). Icons: hand-drawn inline SVG (no licence needed, no third-party set). Map data (F2 and later): Natural Earth, public domain, with a README beside the asset. No images, models or music of unknown origin. No vendor logos.


## Phase F5 additions: light theme and product components

- **Light tokens** (`dashboard/src/theme/tokens-light.css`, hex in `palette.ts`): the same variable names as the dark set, with pale surfaces (`--void` #eef3f9, cards #ffffff) and dark text and accents (`--frost` #0b1b2e, `--mist-hi` #33445b, `--ice-400` #0a6fa0). `palette.test.ts` computes the WCAG ratio of every text/background pair in both themes (body and secondary text at least 7:1; tertiary, accent and status text at least 4.5:1; control borders 3:1) and checks that the CSS matches the palettes.
- **Theme choice:** Light, Dark or System, remembered in `localStorage` (guarded), applied by an inline script in `index.html` before first paint. The Story is a dark cinematic stage in both themes (`data-theme="dark"` on its wrapper).
- **Components:** buttons (primary, secondary, danger, quiet, big), status chip (colour, icon and word together), card, "?" help popover, modal dialog, tour card, segmented switch, cost bars, timeline, details expander. Base text is 16 px; the smallest label is 14 px; chart text is at least 12 px.
- **Words:** every user-facing term lives in `dashboard/src/copy/glossary.ts` in a Simple and a Technical register.
