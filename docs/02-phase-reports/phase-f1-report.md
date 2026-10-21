# Phase F1: art direction, storyboard and style frames: Report

Date: 2026-10-21. Git commit hash and tag: none yet (the team lead commits). Everything shown is an illustrative journey on a synthetic box. Signing protects records after signing and does not stop a lie at the sensor (A18). All money values, probabilities and thresholds are illustrative placeholders, not sourced [SOURCE NEEDED].

## 1. What I was asked to do

Reconcile the frontend vision with Phases 3 to 6 (amendments), write a design system and a storyboard, choose fonts, and build four static pages (three style frames and a font comparison) in plain HTML, CSS and inline SVG or canvas, with real numbers from our own code. Look at them with Playwright, score them, fix the weakest items, and report. No front-end framework.

## 2. What I built

- `docs/01-architecture/frontend-vision.md`: amendments FV-A1 to FV-A5 appended at the end; the original text is unchanged.
- `docs/01-architecture/design-system.md`, `docs/01-architecture/storyboard.md`.
- `docs/01-architecture/style-frames/`: `tokens.css`, `fonts.css`, `fonts/` (21 WOFF2 files, 422,896 bytes, 9 licence texts, manifest), `fonts-compare.html`, `frame-1-prologue.html`, `frame-2-futures.html`, `frame-3-control-room.html`, `generate_data.py`, `data/` (4 JSON files).
- `docs/05-demo/f1-screenshots/`: 11 PNG files, each under 1.2 MB.
- `docs/06-prompts/phase-f1-prompt.md` and this report. READMEs updated.
- Not touched: `dashboard/`, existing Python files, tests, `requirements`. No npm command was run inside the repo (fonts were fetched from the Fontsource packages in a scratch folder outside the repo and pinned at 5.3.0, SIL OFL 1.1).

## 3. How to look at it

The pages read JSON with a same-origin fetch, so they need a local server (opening the file directly will not load the data). From the repo root in PowerShell:

```
$py = "$env:LOCALAPPDATA\potencyguard\venv\Scripts\python.exe"
& $py -m http.server 8809 --bind 127.0.0.1 --directory docs\01-architecture\style-frames
```

Then open `http://127.0.0.1:8809/frame-1-prologue.html`, `.../frame-2-futures.html`, `.../frame-3-control-room.html` and `.../fonts-compare.html`. Stop the server with Ctrl+C. In the Control Room press `P` for the Provenance drawer. To regenerate the data: `& $py docs\01-architecture\style-frames\generate_data.py` (the output is identical on every run; the futures file carries seed 20261021).

## 4. Test results

Baseline before the phase: 8 of 8 checks, 739 tests. Now: **8 of 8 checks, 739 tests** (unchanged; no tests were added or edited). `generate_data.py` is ruff-clean and passes the format check.

## 5. Real and simulated

Real: the numbers in the frames come from our potency, twin, planner, backend-rule and ledger code, run by `generate_data.py` on the recordings and a fixed seed. The tamper result is a real edit of a ledger COPY re-verified by `verify_chain`, signed with a TEST-ONLY demo key derived in the script (no key file is written). Simulated or placeholder: the data (synthetic), the route (illustrative), the 3D globe (a flat 2D placeholder, labelled on the page), the vial scene (SVG, not 3D), and every interaction (the pages are static: the alpha slider, the scenario chips, Approve and the tamper button do not act).

## 6. Decisions needed (PROPOSE)

**FD-1. Font pairing.** A: Fraunces, Inter, JetBrains Mono. B: Newsreader, IBM Plex Sans, IBM Plex Mono. C: Instrument Serif, Instrument Sans, DM Mono. Pros and cons are in `design-system.md` section 8. Recommendation: A.

**FD-2. Scroll length.** A: 1,300 vh (vision figures). B: 860 vh. C: 700 vh. Pros and cons in `storyboard.md` section 1. Recommendation: B.

**FD-3. Scenarios.** The vision lists four; the backend has five (FV-A1). Options: keep five; fold hidden_spoilage into spoof_attempt; show four on stage and five in the full build. Pros of five: matches the data files and shows a falsification that hides real spoilage. Con: one more chip to explain. Recommendation: five.

**FD-4. Chapter 1 figures.** Reference profile (0.11% and 2.66%) or active profile Set C (0.34% and 23.4%). Pro of active: matches what the product computes. Con: 23.4% is a larger, less gentle contrast. Recommendation: active profile on screen, reference figures in the Provenance drawer.

**FD-5. Chapter 5 closing line.** (a) "a lost shipment is a lost patient's dose", (b) "rare, severe losses matter more than the average", (c) none. Recommendation: (b).

**FD-6. Live or replay first.** Replay first is safer on stage (no service to fail) and lets the visuals be built and judged early; live adds a dependency and the backend has no authentication yet. Recommendation: replay first, live after replay is solid.

## 7. Contrast summary

Computed with the WCAG 2.x formula in `generate_data.py` (output `data/contrast.json`, table in `design-system.md` section 2.1). Primary text and secondary text (`--mist-hi`) reach 7:1 on all four surfaces. `--mist` is limited to large text and dim states. Accent and status colours reach 4.5:1 or better on the surfaces where they are used as text; new tokens (`--line-strong`, `--danger-text`, `--ice-700`, `--planner-300`) were added where an existing token failed. Colour never carries meaning alone: every status has an icon and a word.

## 8. Screenshots and scores

All in `docs/05-demo/f1-screenshots/`: frame-1-prologue (1920x1080, 1366x768, 390x844), frame-2-futures (same three), frame-3-control-room (1920x1080, 1366x768, plus provenance-open 1920x1080), fonts-compare (1920x1080, 1366x768).

Scores are 1 to 5 against vision section 12, my own judgement, not an outside review. "n/a" means the criterion cannot be judged on a static page.

| Criterion | Frame 1 | Frame 2 | Frame 3 |
|---|---|---|---|
| Hierarchy and clarity | 4 | 4 | 4 |
| Typography | 4 | 4 | 3 |
| Colour with meaning | 4 | 4 | 4 |
| Motion with purpose | n/a | n/a | n/a |
| 3D craft | n/a (SVG) | n/a | n/a (placeholder) |
| Performance and smoothness | n/a | n/a | n/a |
| Accessibility | 3 | 3 | 3 |
| Honesty of copy | 4 | 4 | 4 |
| Story coherence | 4 | 4 | 4 |
| Memorability | 3 | 4 | 3 |

Weakest two: (1) Control Room typography at 1366x768, where chart axis text is about 10 px; I raised the small text sizes and shortened the planner legend so nothing wraps, which fixed the clipping but not the size, so the score stays 3 at 1366 (it reads as 4 at 1920). (2) Memorability of frames 1 and 3: the vial is a flat SVG and the globe a placeholder; this needs the 3D build, so the score stays 3. Accessibility stays at 3 because contrast was computed and the pages use real text, landmarks and focus rings, but no screen reader test was done.

## 9. Problems, surprises, omissions

- Console: no errors or warnings on the final Control Room page; the only network request is the same-origin JSON fetch. A favicon 404 seen early was fixed with an inline icon.
- Early versions had overflowing panels, a clipped ring number, overlapping chart labels and a page taller than the screen; all fixed and rechecked at both sizes.
- In hidden_spoilage the twin's one-step-ahead line barely separates from the measured line, so the chart leads with the residual and CUSUM strips; the physics checks fire at 20.3 h, when the reported temperature drops about 15 degrees in one step.
- The Control Room shows reported potency 99.92% beside a worst-case potency of 75.6% and 265% of shelf life used (worst-case start). This is the planner's high bound, shown to make the point that signed data are not trusted just because they verify.
- Frame 1 at 1366x768 is 1.1 MB (grain); the 1920 shot was taken with the grain layer hidden to stay small.
- Not done: no 3D, no scroll behaviour, no working controls, no screen reader test, no phone layout for the Control Room (it is a projector screen), no performance overlay (nothing to measure on static pages).
- Fonts: only Latin subsets; any later need for other scripts would add files.

## 10. What we can say and must not say

Can say: the style frames show the intended look with real numbers from our own code; the planner prefers Continue on expected loss and Reroute on the worst five percent in the oracle example (4,000 and 50,000 against 5,250 and 10,000); a copy of the ledger that is edited fails verification at the edited entry; the physics checks fire on a feed that breaks physics.

Must not say: that the globe, vial or box are 3D yet; that the controls work; that the figures are measurements of real shipments or real products; that signing proves the sensor was truthful; that the system is "tamper-proof" or "unhackable"; any outside statistic.
