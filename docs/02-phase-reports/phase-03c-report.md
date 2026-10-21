# Phase 3C: close every limitation that can be closed: Report

Date: 2026-10-21. Git commit hash and tag: none yet (the team lead commits). Simulation results on a synthetic box. Not real-world evidence. Final numbers: seeds 50001 to 50200 (mismatch and two-node runs: the first 100), each seed scored once, no tuning on them. Details: `phase-03c-evaluation.md`; decision: `decision-0006b-closing-more-limitations.md`.

## 1. What I was asked to do

Close what software can close of the Phase 3B limits (a mismatched box, shared equations, a loose and sometimes invalid bound, an unexamined choice of k and h), measure the rest, and correct the wording about what Phase 4 covers.

## 2. What I built

- `edge/precheck.py`, `python -m edge precheck`: the pre-trip check.
- `simulator/calibration_set.py`: `calibrate_for_box`, `variant_boxes`, per-box seeds. `scripts/calibrate_variants.py` writes `config/twin_calibrated_variants.yaml`; `edge/thermal_twin.py` `load_variant_twins`.
- `simulator/box_model.py`, `engine.py`, `truth.py`, `recording.py`, `shared/config.py`: the two-node box (`box_model`, `two_node_payload_fraction`, `two_node_coupling_tau_h`; payload series only in two-node ground truth).
- `edge/assessment.py`, `detector_config.py`, `config/detectors.yaml`: `bound_tau_safety_factor` (0.9), the low bound, `bound_tau_eq_h`, `bound_low_tau_eq_h`, `bound_high_tau_eq_h`, shelf-life equivalents; `edge/twin_cli.py` prints the interval. `MonitorState.cusum_skipped` (for the false-alarm study).
- `scripts/evaluate_3c.py` (parallel, `--workers`), additions to `scripts/evaluate_detectors.py` (new seed blocks, ledger, payload truth, `summarise_rows`).
- Tests: `test_phase3c.py` (26), `test_two_node.py` (11). Docs: decision 0006b, addenda, amendment A18, READMEs, prompt archive.

## 3. How to run it

```
$py = "$env:LOCALAPPDATA\potencyguard\venv\Scripts\python.exe"
& $py -m edge precheck --recording data/recordings/baseline_ok.jsonl --hours 6
& $py scripts/calibrate_variants.py
& $py scripts/evaluate_3c.py --workers 12        # about 2 minutes
& $py scripts/evaluate_3c.py --quick --workers 1
```

## 4. How to check it works

`& $py scripts\run_checks.py` prints `Summary: 5 passed, 0 failed`. The nine golden recordings and both shared test-vector files were hashed before and are checked in `tests/test_phase3c.py` against those hashes: unchanged. `git` shows no change to `data/recordings`, `shared/test-vectors` or `config/twin_calibrated.yaml`.

## 5. Test results

run_checks: 5 passed, 0 failed. pytest: 587 passed (550 at the start of the phase, 37 new). Per file: box_simulator 22, calibration 13, channels 30, constants_study 8, evaluation 16, freerun_and_tools 24, heat_allowance 3, hidden_spoilage 8, lie_modes 48, live_simulator 35, phase3c 26, potency 84, potency_tracker 40, profiles 13, scenarios 68, sensor_interface 32, smoke 6, tamper_monitor 36, thermal_twin 17, trust 47, two_node 11.

**Evaluation runtime:** about 1.7 minutes with 12 workers (24 logical CPUs, default is half), against about 50 minutes before; the quick study gives identical results with 1 and 2 workers (tested).

**Tests changed.** `tests/test_trust.py::test_the_streaming_bound_equals_the_batch_bound`: the batch call now passes `CONFIG.bound_tau_safety_factor` (the streaming bound uses the configured factor, 0.9; the batch function defaults to 1.0). Reason: the bound now depends on the factor; the assertion (streaming equals batch) is unchanged. No other existing test was edited.

## 6. What is real and what is simulated

Everything is simulated. `source` stays "sim". The two-node box is one structurally different box of my own design.

## 7. Decisions and PROPOSE items

Decided by the prompt: per-box calibration, the two-node test, the sf rule, the false-alarm rule. Interpretations I made (please confirm): (1) clean false-alarm families = the four clean families of the Phase 3 selection, not door-open (a real heat event; its CUSUM alarms are correct, about 190 episodes per 100 runs); (2) "false tamper verdicts" in the target = a tamper verdict at any time (the stricter reading); (3) the field `bound_tau_eq_h` did not exist: I introduced it as the high bound (same number as `bound_high_tau_eq_h`); (4) the quick mode of the evaluation uses 40001 to 40005, after an early smoke run had used 50001 to 50005 once (5 seeds, nothing was tuned on what I saw); (5) the "within one sample" delay test uses the median in samples.

PROPOSE: **P1 a richer twin for boxes with a payload.** (a) none, document (current); (b) a two-node twin (air and payload) fitted by regression; pro: could close the structural gap; con: more parameters, harder calibration, the payload is not measured. Recommendation: (a) for the hackathon, (b) as a later phase. **P2 a longer pre-trip window** (12 hours): pro: fewer "not checkable"; con: later warning. Recommendation: try 12 hours in a later phase and measure.

## 8. Assumptions and unverified claims introduced

Placeholders, not sourced [SOURCE NEEDED]: `box_model` settings (payload fraction 0.5, coupling 1.5 h), `bound_tau_safety_factor` 0.9 and the grid, the pre-trip window (6 hours, at least 12 intervals), the targets (nominal rate plus 1 percentage point, 95 percent, one sample), the false-alarm target 1.0 per 1000 hours, the accuracy tolerance of the calibration test (3 percent).

## 9. Problems, surprises and wording changes

- The first false-alarm run used the door-open family and gave 18 episodes per 1000 hours: those are real heat events. Fixed by using the clean families (above); a second bug (glitch samples that skip the CUSUM) was found by comparing with the monitor and fixed with `cusum_skipped`.
- **Phase 3B wording error corrected.** I wrote that false tamper verdicts on the box 15 percent below the calibration went "from 0 to 0 of 700". The data say: a tamper verdict at some time in 100 of 700 runs (all freeze_event) in Phase 3 AND in Phase 3B; ending with one 0 of 700 in both. The prompt's version ("fell from 100 of 700 in Phase 3 to 0 of 700") matches neither number for Phase 3B; the true improvement for that box came in this phase, with its own twin (2 of 700 any-time, 1 ends with one). I corrected the statement in decision 0006 and the Phase 3B report.
- **Files changed by the wording correction (signatures and Phase 4 versus the mimic):** `docs/03-decisions/decision-0006-closing-phase-3-limitations.md` (section 6 mimic bullet, section 8 mimic bullet, slide item 5, new section 10); `docs/02-phase-reports/phase-03b-report.md` (section 11 summary; section 13 sentence that Phase 4 "actually covers the mimic liar"); `docs/00-project-brief/master-brief.md` (new amendment A18); new text in decision 0006b and this report. Archived prompts (`phase-03b-prompt.md`, `phase-03b-fix-prompt.md`, `phase-03-prompt.md`) were left verbatim; they mention "signature"/"product signatures" in the original prompt text.

## 10. Numbers measured

**Targets (placeholders).**

| target | result |
|---|---|
| +15% box, own twin: false tamper verdicts at most nominal rate plus 1 point | **met**: 5 of 700 (0.7%) against nominal 8 of 1400 (0.6%) |
| +15% box, own twin: five lie families at least 95%, delay within one sample of nominal | **missed**: all 100%, but `injected_offset_small` median delay 45 min against 0 min |
| -15% box, own twin: false tamper verdicts | **met**: 2 of 700 (0.3%) |
| -15% box, own twin: five lie families, delay | **met**: all 100%, delays 10, 10, 10, 0, 10 min |
| nominal box: high bound never below truth, 200 seeds, every lie family | **met**: 0 violations in 2196 bounds |
| bound on +/-15% and two-node boxes (limitation) | 0 violations on all (1229, 1072, 828, 1129, 1600 and 1077 bounds) |
| sf found in the grid | met: 0.9 (1.0 gave 66 violations on the -15% box) |
| k and h unchanged by the larger study | same setting selected: 32 episodes in 132,000 h (0.24 per 1000 h) |
| evaluation runtime | about 1.7 min (was about 50) |

**Per-box calibration (seeds 9101-9110, 9201-9210, 9301-9310).**

| box | true tau (h) | fitted tau | true dT_cool (K) | fitted | sigma_r | R squared |
|---|---:|---:|---:|---:|---:|---:|
| nominal (9001-9010) | 6.000 | 5.984 | 30.00 | 29.85 | 0.0687 | n/a |
| +15% | 6.900 | 6.862 | 39.67 | 39.53 | 0.0688 | 0.925 |
| -15% | 5.100 | 5.098 | 21.68 | 21.59 | 0.0694 | 0.997 |
| two-node (slow 6.0, fast 1.0) | 6.000 | 2.018 | 30.00 | 30.15 | 0.0730 | 0.946 |

**Clean and physical runs (a tamper verdict at some time / ends with one).** nominal 8 / 1 of 1400; +15% nominal twin 700 / 129, own twin 5 / 1 (of 700); -15% nominal twin 100 / 0, own twin 2 / 1; two-node nominal twin 700 / 496, own twin 238 / 109. Trust levels with the own twin: +15% 6 low confidence, 5 untrusted; -15% 9 and 2.

**Pre-trip check, nominal twin (clean and physical runs; recalibrate / matches / not checkable).** nominal box 25 / 814 / 561 of 1400; +15% box 388 / 15 / 297 of 700; -15% box 275 / 2 / 423; two-node box 0 / 0 / 700. With each box's own twin: recalibrate 14, 4 and 8 of 700 (+15%, -15%, two-node). Runs where a lie or fault starts inside the 6-hour window: 200 nominal, 100 on each other box; none gave a "recalibrate". So the check finds a 15 percent mismatch in 55 and 39 percent of runs and is silent (not checkable) in most of the rest; it does not see the two-node box (590 of 700 "matches" with the fitted twin).

**Two-node box, payload truth against reported (median).** baseline 0.9994 / 0.9994; door_open_excursion reported 0.9989, true 0.9994; reefer_failure reported 0.830, true 0.878 (equivalent-time ratio 1.44); heatwave_transit 0.968 / 0.970. The air reading is the more pessimistic one here.

**Lie detection (final seeds).** Five Phase 3 families: 100 percent on every box and twin; drifts on a healthy box: 100 percent with the own twin (nominal twin on the +15% box: 15, 81, 100, 100 percent for 0.25, 0.5, 1, 2 K per hour; on the -15% box 21, 84, 100, 100). Drift behind a cooling fault: 0.25, 0.5 and 1 K per hour 0 percent on the nominal box; 2 K per hour 100 percent, median 590 min. Mimic: 0 percent (nominal box); a mismatched box sometimes "detects" it (92 and 100 percent on the +15% box with the nominal twin) only because the mismatch itself looks like a lie.

**Bound.** High bound with sf = 0.9. Looseness nominal (median / 90th percentile): spoof_attempt 1.41/1.55; hidden_spoilage 4.26/5.56; injected_replay 1.25/1.35; drift with fault 1.25/1.35; offsets and drifts on a healthy box 19.1/27.8. Not tighter than before; safer (see decision 0006b section 4).

**False-alarm table (4000 clean runs, 132,000 h; episodes at selected rows).** k = 0.25: h = 4 32 episodes (0.24 per 1000 h), h = 6, 8, 12 none; k = 0.5, h = 4: 8; every k of 0.75 and 1.0: none. Median delay (training spoof runs): 10 min at (0.25, 4), 20 at (0.5, 4) and (0.25, 6). Mismatched boxes with the nominal twin: 28 to 74 per 1000 h for every row (the reason to calibrate per box).

## 11. What we can say on a slide / what we must NOT say

Can say (simulation results on a synthetic box, not real-world evidence; seed blocks given):
1. Calibrating the twin to the box removes most of the false tamper verdicts of a mismatched box: 5 of 700 (+15%) and 2 of 700 (-15%) clean and physical runs, against 700 and 100 with the nominal twin (final seeds 50001-50100).
2. The fit recovers the box it is given: tau 6.862 h against 6.900 and 5.098 against 5.100 (per-box seeds 9101-9110, 9201-9210).
3. All five lie families are still detected in 100 percent of 100 runs on the calibrated mismatched boxes (50001-50100); on the +15 percent box one family is slower than the target (45 min against 0).
4. The worst-case damage bound was never below the true damage in 2196 bounds on the nominal box (200 seeds per family, 50001-50200) nor on the +/-15 percent and two-node boxes (50001-50100).
5. The bound is a safety limit, not an estimate: about 19 times the true value where the cooling really worked, 1.25 to 1.4 where it failed.
6. With the settings k = 0.25 and h = 4 there were 32 false alarm episodes in 132,000 simulated clean hours (60001-61000).
7. The whole evaluation runs in about 2 minutes on 12 workers and gives the same numbers for any number of workers.
8. The limits are measured and listed (section 12).

Must NOT say: that the mimic liar is caught; that a mismatched box is handled without calibrating it; that the twin handles a box with a payload (a single-node twin gave false tamper verdicts in 34 percent of runs on the two-node box); that slow drifts are caught in every situation; that the pre-trip check always finds a mismatch (55 and 39 percent, many "not checkable"); that the bound is an estimate or tighter than before; that signatures or hash chains stop a lie that arrives at the sensor before signing; that the false tamper verdicts of a box 15 percent below the calibration "went from 0 to 0" or "from 100 to 0" (see section 9); that these results describe real boxes.

## 12. Final limitations table

| limit | status | evidence |
|---|---|---|
| Mismatched box (+/-15%) | **fixed by per-box calibration** (needs a calibration per box type) | 5 and 2 of 700 against 700 and 100 (50001-50100); the pre-trip check finds it in 55 and 39 percent of runs only |
| Shared equations | **reduced**: tested against one box of my own design that does not follow the twin | single-node twin on the two-node box: 238 of 700 any-time, 109 end with a tamper verdict; pre-trip check does not see it; not fixed |
| Bound validity | **fixed in these runs** (sf 0.9) | 0 violations on every box; sf 1.0 had 66 on the -15% box (training) |
| Bound looseness | not fixed | about 19 times where the cooling worked; the interval's low end gives context but is not a guarantee |
| k and h choice | **examined, unchanged** | 0.24 false alarms per 1000 h at 4000 clean runs |
| Drift behind a cooling fault (1 K/h or less) | **not fixable in software** | 0 percent detected |
| Mimic liar | **not fixable in software** | 0 percent; covered only by attested sensors, a second sensor or out-of-band data |
| Honest ambient and duty channels, no humidity or shock physics, simulation only | remain | assumptions |

## 13. Open questions for the decision-maker

1. Door-open excluded from the false-alarm families (section 7, item 1): confirm.
2. Is the "100 of 700 to 0 of 700" statement in the prompt a different metric than I used (section 9)? I report the numbers as measured.
3. The +15 percent box misses the delay target for `injected_offset_small` (45 min against 0): accept, or investigate in a later phase?
4. A twin for boxes with a payload (P1): do it in a later phase or document only?
5. Pre-trip window: keep 6 hours, or measure 12 hours (P2)?
6. OK to keep the new field name `bound_tau_eq_h` (it did not exist before)?
7. The seed block 50001 to 50005 was scored once by an early smoke run (nothing tuned on it): acceptable?

## 14. Suggested next phase (not started)

Phase 4 (signing and hash chain), with the wording correction in mind: it protects the records after signing, not the sensor input. The sensor-level options (attested sensor, second sensor, out-of-band data) are separate work.
