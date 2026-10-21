# Decision 0006b: closing more limitations (Phase 3C)

Status: implemented in Phase 3C. Simulation results on a synthetic box. Not real-world evidence. Every threshold below is a placeholder, not sourced [SOURCE NEEDED]. Final numbers come from seeds 50001 to 50200 (mismatch and two-node runs: the first 100), each seed scored once, no tuning on them. The full numbers are in `docs/02-phase-reports/phase-03c-evaluation.md`.

## 1. Per-box calibration (the fix for a mismatched box)

**Procedure.** The twin must be calibrated to the box it is used with. For a box (nominal or a variant) the simulator generates the dedicated clean calibration set for THAT box (the same two clean scenarios as the nominal set, five seeds each) and the existing restricted regression fits the twin (`simulator.calibration_set.calibrate_for_box`). Seeds: 9101 to 9110 (+15 percent box), 9201 to 9210 (-15 percent box), 9301 to 9310 (two-node box). The fits are in `config/twin_calibrated_variants.yaml`; `config/twin_calibrated.yaml` is untouched.

**Evidence.** The fit recovers the box it was given: +15 percent box true tau 6.900 h, fitted 6.862 h, true cooling depression 39.67 K, fitted 39.53 K; -15 percent box 5.100 h and 5.098 h, 21.68 K and 21.59 K.

**Result with the box's own twin (clean and physical families, 700 runs per box):** a tamper verdict at some time in 5 runs (0.7 percent) on the +15 percent box and 2 runs (0.3 percent) on the -15 percent box, against 8 of 1400 (0.6 percent) on the nominal box. With the nominal twin (before): 700 of 700 and 100 of 700. Target "at most the nominal rate plus 1 percentage point": met on both boxes. Target "five lie families detected at least 95 percent with delay within one sample of nominal": met on the -15 percent box; **missed on the +15 percent box**: all five are detected in 100 percent of runs, but `injected_offset_small` has a median delay of 45 minutes against 0 at nominal.

**Operating procedure, in plain words.** Calibrate once per box type at commissioning, from a clean run. Run the pre-trip check before each trip. Recalibrate when it says so.

## 2. The pre-trip check

`python -m edge precheck --recording FILE [--hours H]` (default 6 hours, placeholder) feeds the first hours through the rolling gain estimate of the tamper monitor and prints "twin matches this box (gain g, band ...)", "twin may be out of date: recalibrate before departure (gain g)", or that the gain could not be measured (which is NOT a confirmation). Measured with the NOMINAL twin on clean and physical runs: it says "recalibrate" for 25 of 1400 (2 percent) nominal-box runs, 388 of 700 (55 percent) on the +15 percent box and 275 of 700 (39 percent) on the -15 percent box; the rest are mostly "not checkable" in 6 hours (561 of 1400 nominal, 297 and 423 on the mismatched boxes). So a 6-hour window finds a 15 percent mismatch about half the time and is silent about the rest; it does not replace calibrating per box type. Runs where a lie or fault starts inside the window (100 per box): none of them produced a "recalibrate" (0 of 100 on each box), so no confusion was observed, but the window is short. It does not see a structurally different box (section 3).

## 3. A structurally different box (the shared-equations test)

A second box physics (`box_model: two_node`) has an air node, which the sensor measures, and a payload node, on which the potency depends; the ground truth for potency is the payload node. Parameters (placeholders): half of the capacity in the payload, coupling time constant 1.5 h; the wall resistance and total capacity are set so the slow time constant is 6.0 h (the fast one is 1.0 h). It is ONE structurally different box of my own design, still a simulation.

**What the result shows (nothing was tuned on it).** A single-node twin fitted to this box (seeds 9301 to 9310) gets tau = 2.0 h (the air node dominates what the sensor sees), cooling depression 30.15 K, R squared 0.946, a residual spread of 0.073 C against 0.069 for the nominal box. Clean and physical runs (700) with that twin: a tamper verdict at some time in 238 (34 percent), 109 end with one (99 of 100 freeze_event); with the nominal twin: 700 of 700 and 496 end with one. Lies are still detected (the five families 100 percent). The pre-trip check with the fitted twin says "twin matches" for 590 of 700 runs, so it does NOT detect a structural mismatch. Potency: the air-reported potency differs from the payload truth by at most 0.05 in the median (reefer_failure: reported 0.830, true 0.878, i.e. the air reading is the more pessimistic one; the equivalent-time ratio is 1.44).

**What it does NOT show.** It does not show how a real box behaves, and it does not show that a two-node twin would work; it shows that a single-node twin cannot represent a box with a payload and that per-box calibration does not fix a structural mismatch. A richer twin would be a design change.

## 4. The worst-case bound: safety factor and interval

`bound_tau_safety_factor` sf (config/detectors.yaml) multiplies the twin's time constant in the HIGH bound (a box that tracks the ambient faster is at an equal or higher temperature). Chosen on the training seeds 10001 to 10100, nominal and +/-15 percent boxes with the nominal twin, every lie family: sf = 1.0 gave 66 violations (all on the -15 percent box, `injected_drift_2_fault` and `injected_replay`); 0.9, 0.8, 0.7, 0.6 gave none; the rule picks the largest, **0.9**. Median looseness on the nominal box, training seeds: 14.6 (sf 1.0), 15.2 (0.9), 16.8 (0.6). So the factor makes the bound safer and slightly looser, not tighter; the bound is still about 19 times the true value where the cooling really worked.

**Validity, final seeds, zero violations** on the nominal box (2196 bounds, 200 seeds of every lie family), the +15 percent box (1229 with the nominal twin, 1072 with its own), the -15 percent box (828 and 1129) and the two-node box (1600 and 1077). Looseness (bound over true, median / 90th percentile, nominal): spoof_attempt 1.41/1.55; hidden_spoilage 4.26/5.56; injected_replay 1.25/1.35; drift with a cooling fault 1.25/1.35; offsets and drifts on a healthy box about 19.1/27.8.

**The interval.** A LOW bound is added: the damage if the cooling had worked at full effectiveness from t0 (duty 1.0, the twin's own tau, honest ambient). The assessment carries `bound_low_tau_eq_h` and `bound_high_tau_eq_h` (and `bound_tau_eq_h`, the same number as the high one, the field a signed record would carry; it did not exist before this phase) with shelf-life equivalents, and `python -m edge twin` prints "between A percent (cooling worked fully) and B percent (no cooling) of shelf life used". The low bound is NOT a guarantee: a heat load could add damage beyond it. Only the high bound is meant as a limit, and only where its assumptions hold. A test checks low <= truth <= high on the golden spoof recordings.

## 5. The false-alarm study for k and h

Clean runs only, seeds 60001 to 61000: 4000 runs, 132,000 simulated hours (baseline_ok, shock_drop, sensor_glitch, freeze_event, the four clean families of the Phase 3 selection). At the current setting (k = 0.25, h = 4): 32 alarm episodes in 132,000 hours, 0.24 per 1000 hours, against a target of at most 1.0 (at the target rate about 132 episodes would be expected). With h = 6 or more, or k = 0.75 or more, there were none. The rule (false alarms at most the target, then the smallest median delay on the training spoof runs) selects the same setting, k = 0.25 and h = 4 (median delay 10 minutes). Nothing was changed. On the mismatched boxes with the nominal twin the same setting gives about 74 and 69 episodes per 1000 hours, which is what per-box calibration removes.

I read "door-open-type" clean runs in the prompt as not clean: the door-open scenario contains a real heat event, so CUSUM alarms there are correct detections (about 190 episodes per 100 runs); counting them as false alarms would have made the study meaningless.

## 6. Wording correction (Phase 3C addendum)

Signatures and hash chains (Phase 4) protect the records AFTER the device signs them and stop impersonation by anyone without the key. They do NOT defend against an attacker who controls the sensor input before the device signs it: the device would sign the lie. A sensor-level mimic liar is covered only by attested sensors, a second independent sensor, or out-of-band data (for example GPS and carrier records). Two limits are not fixable in software: a drift that stays inside the cooling-partly-works envelope, and the mimic. Earlier text that said otherwise was corrected: see the Phase 3C report, section 9.

## 7. Limits that are NOT fixable in software

- **Mimic liar**: 0 to 4 percent detected on the box it was designed for (both mimic families, final seeds); on a mismatched box it is sometimes "detected" (92 and 100 percent with the nominal twin on the +15 percent box, 98 percent for one family on the two-node box) only because the mismatch itself looks like a lie. Not a defence.
- **Slow drift behind a cooling fault** (the drift stays inside the envelope of "cooling partly working"): drifts of 0.25, 0.5 and 1 K per hour are detected in 0 percent of runs; 2 K per hour in 100 percent with a median delay of 590 minutes.
- **Honest channels** (ambient and duty) are an assumption. **No humidity or shock physics.** **Everything is a simulation.**
