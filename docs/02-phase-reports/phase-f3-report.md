# Phase F3: the Story (Prologue and Chapters 1 to 7): Report

Date: 2026-10-21. Commit hash and tag: none yet (the team lead commits). Everything shown is an illustrative journey on a synthetic box; every figure is a model output of our own engine for an imaginary product, labelled on screen. Signing protects records after signing and does not stop a lie at the sensor (A18). Money values and thresholds are illustrative placeholders, not sourced [SOURCE NEEDED].

## 1. What was built

- **Exporter fix (Step 1).** `scripts/export_replay.py` now drives the Phase 6 backend itself (in process, new database, `replay_recording` then `POST /decide`), so the exported route, table and reasons ARE the backend's. **Cause of the mismatch:** the F2 exporter rebuilt the planner inputs through `planner.pipeline.build_inputs` (its own remaining-hours default and chain status) and re-applied the backend rules by hand; the backend plans from the verified ledger entries posted up to the checkpoint, with remaining time taken from the scheduled duration. I replaced the copy with the real call instead of isolating which single input differed. Now baseline_ok, door_open_excursion and reefer_failure are auto-approved; spoof_attempt and hidden_spoilage go to a person (same as `python -m backend replay --all`). Replay files regenerated (19 to 69 kB).
- **Story data (Step 2).** New `scripts/export_story.py` (reuses the F1 generator for Chapter 1 and the chain ribbon): `chapter1.json` (6.3 kB, in `src/data/bundled/`, both profiles), `public/story/chapter5.json` (97 kB: 5,000 seeded outcomes per action as failed flags and ranks, plus 100 precomputed alpha rows 0.00 to 0.99 with expected loss, exact CVaR and sample VaR), `public/story/chapter6.json` (6 kB: approval card content from the backend for hidden_spoilage, the chain ribbon from a real edit of a ledger copy, and the backend's own rejection of an edited ledger). Chapters 2 and 3 read the replay files.
- **Scenes (Step 3), 860 vh in total.**
  - Prologue: 3D insulated box, frosted lid and one glowing vial with drifting vapour; the camera pulls back to the globe.
  - Ch1: two traces, two REJECT stamps, two vials, a time handle on the tested potency mirror, end figures from the export, reference figures in a Provenance disclosure.
  - Ch2: the recorded spoof_attempt (reported line, twin ghost line, residual); a draggable or pressable shield shows the recorded alert time; the copy states only what the physics checks catch, plus the signature limit.
  - Ch3: recorded timeline, clock hand, decision marker, hoverable early dot.
  - Ch4: procedural SVG exploded cutaway with the storyboard's generic labels and a "not installed hardware" caption.
  - Ch5: instanced 3D cloud of the exported samples, worst tail in the planner colour, expected-versus-worst bars, an alpha slider that only selects exported rows; the recommendation flips at alpha 0.26 where the exported data flips.
  - Ch6: approval card from backend content, an illustration-only Approve press that seals the ribbon, and a real broken link with later links dimmed.
  - Ch7: Enter button, Enter key at the last chapter, camera dive to `#/control-room`.
- **Architecture change found in review.** The first version used one sticky panel per section, which pinned for only 30 vh. All eight scenes now share one fixed stage and crossfade (reduced motion gets the same crossfade with a still camera); the scroll length is the time in each scene. The chapter on screen uses a reading position that runs from 0 at the top to the full story at the bottom, so the first chapter starts at 0 and the short last chapter is reachable (a plain middle-of-viewport rule made Chapter 7 unreachable).
- **Cleanup (Step 4).** `dashboard/src/smoke/` and its 3 tests deleted (agreed in F2). The "?" overlay lists only working keys (Enter added). 2D fallback: the Prologue shows a vial still and Chapter 5 a flat canvas of the same samples; the other chapters are DOM and SVG, so identical.

## 2. Tests

Before: 8 of 8 checks, 749 Python tests, 77 dashboard tests. New Python: `tests/test_export_story.py` (route equals the backend's for all five, checkpoints equal the backend's demo checkpoints, untrusted cases need a person, Chapter 1/5/6 schema, textbook numbers at alpha 0.95, flip at alpha 0, size limits). New dashboard tests: alpha-row selection and tail lighting, the Chapter 1 scrub (mirror) against the exported figures for both profiles and the hourly curve, validation of the new files, the chapter table (860 vh, eight scenes, exact lengths), the reading position (monotonic, reaches all eight chapters), the stage camera. Targeted runs while working; the full run once at the end (totals in the final message). No performance or soak tests.

## 3. Review (one round, Playwright Chromium)

Console: no errors; only the `THREE.Clock` deprecation warning from React Three Fiber (not our code). Network: no request outside 127.0.0.1:5173. Performance overlay once on High (Chapter 5, 1920x1080): **126.7 fps, 7.9 ms, 19 draw calls; renderer ANGLE (Intel, Intel UHD Graphics, Direct3D11), WebGL 2** (display-capped; one reading, one machine). Screenshots in `docs/05-demo/f3-screenshots/`. Fixed after looking: vial framing and square vapour, the camera starting half-way (timing bug above), sticky versus fixed stage, globe dimmed behind chart chapters, Chapter 1 copy not showing, stamp and label overlaps, a clipped Chapter 3 label, Chapter 5 cloud framing and bars, rail label overlap, 1366x768 ribbon wrapping.

| Scene | Works | Weak |
|---|---|---|
| Prologue | glowing vial in the box, pull-back to the globe | box is plain; lid lift subtle; the shot is the first frame only |
| Ch1 | scrub, stamps, figures match the export | traces are flat lines; vials are SVG, not 3D |
| Ch2 | real recorded alert, honest limit sentence | raw check name ("cusum pos"); label sits on the line |
| Ch3 | clean timeline, hover note | sparse; globe behind is only dimmed |
| Ch4 | readable exploded view | SVG, not 3D; the twin and estimator note is a loose line |
| Ch5 | real samples, slider flips at 0.26 | reads as two slabs, not a plume; the 1920 shot predates the last cloud tweak |
| Ch6 | real card, real broken link, seal | Approve is an illustration; potency sparkline is flat (the reported lie) |
| Ch7 | clear Enter and shortcut | the dive was not recorded in a shot; the Control Room is a placeholder |

## 4. PROPOSE items

1. **Chapter 5 cloud look.** Keep two slabs, or shape each cluster into a plume from the box (more cinematic, more work). Recommendation: plume in F4 polish.
2. **Alpha grid** starts at 0.00, not 0.50: from 0.50 to 0.99 the exported answer never flips, so the flip would be invisible. Recommendation: keep 0.00 to 0.99, labelled "average view at the left".
3. **Real 3D vials in Chapters 1 and 6** (SVG now). Recommendation: only if time remains after the Control Room.
4. **Approve in the story** stays an illustration labelled "nothing is sent". Alternative: hide it. Recommendation: keep.
5. **Code-splitting** (JS still 1.4 MB): do it with the Control Room.

## 5. Problems and omissions

Not done: phone layouts (not requested), a recorded dive, per-tier measurements, a screen reader pass, sound. The exporter now runs the in-process backend (FastAPI test client), so a full export takes about 20 s. The Prologue 1920 shot is the first frame; the pull-back was checked in the browser, not screenshotted separately.

## 6. Can say / must not say

Can say: the Story runs end to end with real exported numbers; the exported routes equal the backend's; the page only selects rows of precomputed planner tables; a changed record is detected (shown with a real edit of a copy); the physics checks fired on the recorded spoof at 8.5 h.

Must not say: that the Control Room exists yet; that any figure is from a real shipment or product; that the physics checks catch every lie; that signing proves the sensor was truthful; that performance is proven on other machines; "tamper-proof" or "unhackable".
