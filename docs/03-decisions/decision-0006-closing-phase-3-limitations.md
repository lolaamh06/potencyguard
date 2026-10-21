# Decision 0006: closing the Phase 3 limitations

Status: implemented in Phase 3B; the bound-start defect found by the first evaluation was fixed in the Phase 3B fix (sections 4 and 7). Simulation results on a synthetic box. Not real-world evidence. Every threshold below is a placeholder, not sourced [SOURCE NEEDED].

## 1. Why

Phase 3 measured the detectors honestly and found five weaknesses: every tested lie started with a jump; a lie that copies healthy physics had not been measured; a box that differs from the calibration by 15 percent got false tamper verdicts; a detected lie only labelled the potency "untrusted" without saying how bad it could be; and the 60 K heat allowance had no stated origin.

## 2. Two new lie modes (what each tests)

- **drift**: the reported temperature is the true one minus an offset that grows linearly at `rate_c_per_h` (optionally capped by `max_offset_c`). It tests a lie with no jump, so the impossible-step detector has nothing to catch.
- **mimic**: the reported temperature follows a private, healthy copy of the box (cooling factor 1.0, no heat loads, the real ambient, its own on/off controller, started from the true temperature). It is an ATTACKER WITH A MODEL OF THE BOX. It is expected to be invisible to a check that is itself physics, and it tests exactly where that check stops working. It uses no random numbers, so nothing else changes; the nine golden recordings are byte-identical (SHA-256 compared, and a test regenerates and compares them).

The ambient and cooling-duty channels stay honest in both modes (the Phase 3 threat model is unchanged).

## 3. The "twin out of date" self-check

**Method.** Over the last 72 intervals the monitor fits `y = g * x + b * dt_h`: x is the change the twin predicts, y the change observed. If the real box responds differently from the calibration, g moves away from 1 and there is no jump.

**Rule.** The verdict `twin_out_of_date` appears when |g - 1| > 0.08, g is between 0.5 and 2.0, and the gain is measurable (standard error at most 0.04), for 6 evaluations in a row. While it is active a negative CUSUM no longer gives a tamper verdict (the CUSUM values are still reported). Hard physical proofs (a jump that stays, the impossible state, a flat line) are never suppressed, and once one has fired the self-check is off for the rest of the trip. These numbers were chosen on the TRAINING seeds only.

**What the measurements showed.**
- The method does separate the cases in the way intended for the gain: a pure time-constant error gives g about 1.4 (or 0.7) and b about 0; a ramp lie gives g about 1 and a clearly negative b.
- But b is NOT near zero for a mismatched box: a box with different cooling capacity shows b of about -0.9 K per hour (+15 percent) or +0.9 (-15 percent), because the error in cooling strength looks like a steady offset. So b cannot be used on its own to tell a drift lie from a mismatch; the verdict uses the gain only.
- The first selection rule (largest out-of-date coverage) picked a window of 36, which made the thing the target is about worse (about 34 percent of +15 percent runs ending with a tamper verdict, against about 20 percent for window 72). The rule was changed once, after seeing the training sweep, to minimise the share that ends with a tamper verdict. This is disclosed in the report.

**Interpretations I had to make** (the prompt was ambiguous; confirm or correct):
- "No impossible-step flag has ever fired" is read as "no jump that STAYED". A lone jump that reverts is a glitch, not proof, and does not switch the self-check off.
- "No latched falsification" means no latched hard proof. A CUSUM-only falsification verdict that came before the (slow) self-check does not block it; otherwise a mismatched box could never be recognised, because the CUSUM raises its false alarms first.

**Residual risk.** A patient attacker could imitate a gain error, and while the twin is declared out of date a slow lie is no longer reported as a tamper verdict. What the design does instead: `twin_out_of_date` is itself a verdict, is reported and logged, a trip that is out of date from its first window is flagged (`out_of_date_from_start`), and the data are marked untrusted with a worst-case bound rather than silently accepted. It does NOT make that attacker visible.

## 4. The worst-case bound and the assessment

`edge/assessment.py`. When the monitor declares the data untrusted from a time t0, `worst_case_bound()` integrates the twin forward from the reported reading at t0 with NO cooling (duty 0), the measured ambient, and one heat allowance applied to the first step only, and feeds that series to the same Arrhenius and right-endpoint maths as the potency tracker. It returns the added equivalent reference time, the potency and the shelf-life fraction. `assess()` (pure, frozen result) combines it with the reported potency, the trust flag and the reason. Only readings are used; a test checks the module never touches ground truth and that changing the temperatures or duty after t0 does not change the bound.

**What it assumes:** the ambient channel is honest; the box obeys the twin's time constant; the cooling unit does nothing after t0.
**What it ignores:** unseen heat loads beyond one allowance; a falsified ambient channel; any error in the twin's time constant for the real box (so it is NOT validated on a mismatched box, and a box that warms faster than the twin says could exceed it).

**Bound start, version 1 (unsound).** t0 was the last time both CUSUM statistics were "quiet". My first version took only the negative CUSUM's last zero and failed on a drift lie started while a cooling fault was active (ratio 0.39); I changed it to "both statistics quiet" and validated it on seeds 30001 to 30200. The first scoring on seeds 20001 to 20200 then found ONE violation (seed 20090, `injected_mimic_late`, ratio 0.40): the mimic cancels the fault's positive residual, so both statistics pass through "quiet" about 5 hours into the lie, when the reported value is already about 14 K below the truth, and the bound started from that falsified reading. That seed was used to diagnose the defect, so 20001 to 20200 and 30001 to 30200 are development seeds from here on.

**Bound start, version 2 (the fix).** t0 comes from the latched start a0 of the anomaly episode: a0 is the last sample at which both CUSUM statistics were zero BEFORE the first anomaly flag of the trip (either CUSUM alarm, impossible step, impossible state or flat line). Once set, a0 never moves, even when the statistics go quiet again. A jump out of a quiet state starts at the last good reading. When the monitor declares the data untrusted, t0 is the earliest of a0, the start of the proof and (if the twin was out of date) the start of that window, minus the lookback. Why it is conservative: it can only make t0 earlier, so the bound only gets looser, never tighter. Its cost: after any earlier anomaly (for example a real door-open) the bound starts at that anomaly and is looser than needed. Result on 200 fresh seeds (40001 to 40200), nominal box: no violation in any family. On the development seeds, including seed 20090 (now ratio 1.12): no violation. On a box 15 percent above the calibration: 0 violations in 771 bounds. On a box 15 percent below: 45 violations in 367 bounds, all in `injected_drift_2_fault` (55 of 100 valid); the bound uses the twin's time constant, which is too slow for a faster-warming box. This is a limitation, not a defect fixed here: the bound is not valid on every mismatched box.

**Conservativeness.** On the final seeds (nominal box), ratio bound over true, median and 90th percentile: spoof_attempt 1.35 and 1.47; hidden_spoilage 4.31 and 5.56; injected_replay 1.15 and 1.24; drift with a cooling fault 1.15 and 1.24; offsets and drifts on a healthy box about 18.4 and 27 (the real cooling worked, the bound assumes it did not). It is an upper bound for safety decisions, never an estimate of the real damage.

## 5. Heat allowance

`heat_allowance_c` in `config/detectors.yaml` now states its meaning (the largest sudden warming of the box that an unseen heat load can cause in one sample interval) and its derivation: `box_R_th_k_per_w * door_max_power_w` = 0.5 K/W * 120 W = 60 K. A heat load of P watts through the wall resistance R_th pulls the box towards at most R_th * P kelvin above where it would settle. `door_max_power_w` (120 W, placeholder, not sourced [SOURCE NEEDED]) is the largest door power the injectable `open_door` command accepts and the largest any shipped scenario uses (door_open_excursion draws 90 to 120 W). A test asserts allowance >= R_th * door_max_power_w and <= 1.5 times that. The value did not change, so detector behaviour is identical. The key name was kept (renaming it would touch every consumer for no gain).

## 6. What remains limited, and why

- **Shared equations.** The twin and the simulator use the same family of equations, so every number is optimistic for a real box; the mismatch runs only partly compensate.
- **Honest channels.** Ambient and duty are assumed honest. A lie on them is out of scope.
- **The mimic liar.** Physics cannot see it by construction. Covering it needs something that is not physics: signed hardware readings, a redundant independent sensor, or product signatures.
- **No humidity or shock physics.** Those channels are not modelled.
- **Hard proofs under mismatch.** On a +15 percent box the impossible-state proof fires falsely (the real box has more cooling than the twin believes) and the prompt forbids suppressing it.
- **Slow lies behind a fault.** A drift of 1 K per hour or less is not detected while a cooling fault is active: the fault's own residual hides it.

## 7. Trust levels (Phase 3B fix)

`PotencyAssessment.trust_level` is `trusted`, `low_confidence` or `untrusted`; the `trusted` flag is derived from it. `untrusted`: a hard proof, or CUSUM evidence that the self-check has not explained; a worst-case bound is given. `low_confidence`: the twin is suspected not to match the box and there is no hard proof; NO bound is given, because the bound's assumptions (the twin's time constant) are exactly what is in doubt, and the output says "operator review recommended: the twin may not match this box". A CUSUM-only alarm on a mismatched box is untrusted until the self-check (which needs about 13 hours of data) explains it; then the level becomes low_confidence. A hard proof later turns an out-of-date trip untrusted and it never clears. Measured on clean and physical runs (final seeds, first 100 per family): nominal box 693 trusted, 7 low confidence, 0 untrusted; +15 percent 0, 325, 375; -15 percent 220, 425, 55.

## 8. Remaining limits in plain language (final seeds, simulation results on a synthetic box)

- **Mismatch.** The twin must be calibrated to the box it is used with. On a box whose time constant, wall resistance and cooling capacity are 15 percent above the calibration, 132 of 700 clean and physical runs (19 percent) still end with a tamper verdict (100 heatwave_transit from the hard impossible-state proof, 31 freeze_event and 1 baseline from the negative CUSUM); on a box 15 percent below, 0 of 700. We did not weaken the hard proofs to hide this, and the 5 percent target for the +15 percent box is MISSED. Operationally: calibrate per box type, re-check at commissioning, and treat these verdicts as operator-review flags.
- **Drift behind a cooling fault.** Drifts of 0.25, 0.5 and 1 K per hour are missed (0 percent detected, 200 runs each) while a cooling fault is active, because the fault's own residual hides them; 2 K per hour is detected in 100 percent with a median delay of 590 minutes. A fault-aware model is future work. Accepted and documented.
- **Mimic liar.** Detected in 0 percent of runs, by construction: physics cannot see a reading that follows a healthy box. It is covered only by signatures, attested hardware or a redundant sensor.
- **The bound** is for safety decisions only, never an estimate (section 4 gives the ratios). It holds on the nominal box and the +15 percent box in these runs and not on every -15 percent run.
- **Shared equations, honest channels, no humidity or shock physics** (section 6) all still apply.

## 9. What we can say on a slide, and what we must NOT say

Can say (each tied to a number in docs/02-phase-reports/phase-03b-evaluation.md; simulation results on a synthetic box, not real-world evidence):
1. On the nominal box, all five Phase 3 lie families are detected in 100 percent of 200 runs, median delay 10 minutes or less.
2. Slow drifts of 0.25 to 2 K per hour on a healthy box are detected in 100 percent of 200 runs each.
3. When the data are untrusted, a worst-case bound on the damage is given; it was never below the true damage in 200 fresh runs of any family on the nominal box.
4. The bound is far above the truth where the cooling really worked (median about 18 times) and close to it where the cooling failed (1.15 to 1.35 times).
5. The self-check removed false tamper verdicts on a box 15 percent below the calibration (0 of 700 runs end with one) and cut them from 531 to 132 of 700 on a box 15 percent above.
6. A box that does not match the twin is reported as low confidence with an operator-review message, not as a proven lie.
7. The false-alarm figures on the nominal box did not get worse (1 clean or physical run with a tamper verdict, as before).
8. The limits are measured and listed: the mimic (0 percent), drift behind a cooling fault at 1 K per hour or less (0 percent), the +15 percent box (19 percent still end with a tamper verdict).

Must NOT say: that the mimic liar is caught; that a mismatched box is handled; that slow lies are caught in every situation; that the worst-case bound is an estimate of the damage; that the bound is valid on every box; that these results describe real boxes, real sensors or real shipments; that any threshold has been sourced.
