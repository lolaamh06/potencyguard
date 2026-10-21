# Phase 3B: closing the Phase 3 limitations: Report (includes the Phase 3B fix)

Date: 2026-10-21. Git commit hash and tag: none yet (the team lead commits). Simulation results on a synthetic box. Not real-world evidence.

**Status of the earlier stop item.** The first Phase 3B build had one bound violation (development seed 20090, `injected_mimic_late`, bound 0.40 of the true value). The Phase 3B fix replaced the bound start rule and re-scored on a fresh seed block. On the nominal box there is now no violation (200 runs of every family, final seeds 40001 to 40200, and none on the development seeds either). On a box 15 percent below the calibration there are 45 violations in 367 bounds (all in one family); this is reported as a limitation.

## 1. What I was asked to do

Phase 3B: measure or fix five weaknesses found in Phase 3 (slow lies, a lie that copies healthy physics, a box that differs from the calibration, an unbounded "untrusted" potency, an underived heat allowance). Phase 3B fix: replace the unsound bound start rule, score it on fresh seeds, add a "low confidence" trust level, and document the remaining limits plainly.

## 2. What I built

- `simulator/events.py`, `engine.py`, `live.py`, `commands.py`: spoof modes `drift` and `mimic`; `open_door` power limit.
- `shared/config.py`, `config/product_default.yaml`: new key `door_max_power_w`.
- `config/detectors.yaml`, `edge/detector_config.py`: documented `heat_allowance_c`; seven keys for the self-check and the trust lookback.
- `edge/tamper_monitor.py`: rolling gain fit, verdict `twin_out_of_date`, suppression rules, trust record; **fix:** the latched anomaly-episode start (`episode_start_s`), the property `trust_level` and the constants `TRUSTED`, `LOW_CONFIDENCE`, `UNTRUSTED` (`QUIET_FRACTION` removed).
- `edge/assessment.py`: `worst_case_bound`, `assess`, `PotencyAssessment` (new fields `trust_level`, `operator_message`), `TrustAssessor` (computes a bound only for `untrusted`).
- `edge/twin_cli.py`: trust level line, operator-review message, trust column with "low confidence".
- `scripts/evaluate_detectors.py`: lie families, ood sweep, before/after; **fix:** final seed block 40001 to 40200, seed ledger, bound validity on the development block and on the +/-15 percent boxes, trust-level counts.
- Tests: `test_lie_modes.py` (48), `test_trust.py` (47), `test_heat_allowance.py` (3), 7 in `test_evaluation.py`.
- Docs: decision 0006, amendment A17 (and its fix paragraph), READMEs, prompt archives (`phase-03b-prompt.md`, `phase-03b-fix-prompt.md`).

## 3. How to run it

```
$py = "$env:LOCALAPPDATA\potencyguard\venv\Scripts\python.exe"
& $py -m edge twin --recording data/recordings/hidden_spoilage.jsonl
& $py -m edge twin --all
& $py scripts/evaluate_detectors.py            # about 50 minutes
& $py scripts/evaluate_detectors.py --quick    # a few minutes
```

## 4. How to check it works

`& $py scripts\run_checks.py` prints `Summary: 5 passed, 0 failed`. The nine golden recordings were hashed (SHA-256) before the fix and after it: no differences.

## 5. Test results

`run_checks`: 5 passed, 0 failed. pytest: 550 passed (538 before the fix; 444 at the start of Phase 3B). New in the fix: 12 tests (episode start latched after a cancelled spike; jump out of a quiet state; the start and the untrusted time never move later on 12 random sequences; seed 20090 now valid; the three trust levels and their order; the trusted flag follows the level; no bound for low confidence; twin command output for the levels).

**Tests changed.**
- `tests/test_box_simulator.py::test_box_config_rejects_non_positive_new_keys` (earlier in 3B): the required config key list grew by `door_max_power_w`.
- `tests/test_evaluation.py`: `test_the_seed_sets_stay_disjoint_with_the_bound_validity_seeds` was replaced by `test_the_seed_sets_stay_disjoint_across_all_blocks`. Reason: the old test asserted that the test block is 20001 to 20200, which is now the development block; the new test asserts the five blocks (calibration, training, development, validity-development, final) are disjoint and have the stated ranges. It is a stricter test, not a weaker one.
- No other existing test was edited; `edge/assessment.py` keeps the old "still trusts" error message so the old assess test passes unchanged.

## 6. What is real and what is simulated

Everything is simulated. `source` stays "sim". No hardware or SAP is claimed. The mimic liar is a model of an attacker, not a real attack.

## 7. Decisions

Decided by the decision-maker for the fix: new bound start (episode-latched); fresh final seeds; low-confidence level; hard proofs NOT widened (the +15 percent target stays missed); drift behind a cooling fault accepted; "a lone recovered glitch does not switch the self-check off" confirmed.

Interpretations I made, please confirm or correct:
1. The prompt asked for a fresh block 30001 to 30200, but that block was already used (it validated the first bound repair), so it was not unseen. I used **40001 to 40200** as the final block and classed both 20001 to 20200 and 30001 to 30200 as development seeds.
2. **Low confidence is not strictly "out of date is active".** The level follows the trust reason: a CUSUM-only alarm on a mismatched box is `untrusted` until the self-check explains it (about 13 hours of data), then it becomes `low_confidence`. So the level can go untrusted to low_confidence once, never the other way after a hard proof. It is sticky after the self-check clears (the earlier data stay doubtful).
3. The episode start counts ANY anomaly flag, including a lone glitch's impossible-step flag, as the start of an episode. This is conservative (earlier start, looser bound).

## 8. Assumptions and unverified claims introduced

All new numbers are placeholders, not sourced [SOURCE NEEDED]: `door_max_power_w` 120; `heat_allowance_c` 60 (derived); `ood_window_samples` 72; `ood_gain_margin` 0.08; `ood_gain_band_low/high` 0.5 and 2.0; `ood_sustained_samples` 6; `ood_max_gain_se` 0.04; `trust_lookback_samples` 6; the zero threshold for the episode start (1e-9); sweep grids and the targets 2 percent and 1 percent. Drift rates, mimic start times and base scenarios are my own choices.

## 9. Problems and surprises (the bound-fix story, told straight)

- My first bound start (negative CUSUM only) was invalid for a drift lie under a cooling fault (ratio 0.39). I changed it to "both statistics quiet" and validated it on seeds 30001 to 30200.
- The first scoring on seeds 20001 to 20200 found one violation (seed 20090, late mimic, ratio 0.40): the mimic cancelled the fault's residual, so both statistics were momentarily quiet while the reported value was already about 14 K too low. The rule was unsound in general, and I had validated it on seeds that happened to lack that situation. It was diagnosed on a development seed, not patched on the spot.
- The fix is the latched episode start. Both seeds blocks used so far are now development seeds; final numbers are from 40001 to 40200, used once, with no tuning.
- Both mistakes were the same kind: dating a lie from a statistic that a physical fault or the lie itself can reset.
- Honest note on the low-confidence level: because the self-check needs about 13 hours, an early CUSUM alarm on a mismatched box still shows as untrusted first.

## 10. Numbers measured

Seed ledger (details in the evaluation file): calibration 9001 to 9010 (fit the twin); training 10001 to 10100 (tuning); development 20001 to 20200 (diagnosis); validity-development 30001 to 30200 (diagnosis); final 40001 to 40200 (final scoring, mismatch runs use its first 100).

**Targets (placeholders).**

| target | result |
|---|---|
| clean and physical runs ending with a tamper verdict below 5 percent, +15 percent box | **MISSED**: 132 of 700 (19 percent); before 531 of 700. 100 are heatwave_transit (impossible-state proof), 31 freeze_event, 1 baseline_ok. The hard proofs were deliberately not widened |
| same, -15 percent box | met: 0 of 700 |
| twin_out_of_date reported in most of those runs | met: 529 of 700 (76 percent) at +15, 424 of 700 (61 percent) at -15 |
| nominal box: five Phase 3 lie families detected at least 95 percent, median delay not worse by more than a sample | met: 100 percent, same delays (10, 10, 10, 0, 10 minutes) |
| control and false-alarm figures not worse | met: clean + physical runs with a tamper verdict 1 before and 1 after; 10 of 1400 runs went out of date on the nominal box |
| bound never violated on the nominal box | **met on fresh seeds**: no violation in 200 runs of any family (and none on the development seeds, including seed 20090 at ratio 1.12) |
| bound on mismatched boxes (limitation, not a target) | +15 percent: 0 violations in 771 bounds; -15 percent: 45 violations in 367, all in `injected_drift_2_fault` (55 of 100 valid) |

**Before and after the Phase 3B fix (bound).**

| | first 3B build | after the fix |
|---|---|---|
| bound start rule | last time both statistics were quiet | latched episode start |
| development seeds (20001 to 20200) | 1 violation (seed 20090, ratio 0.40) | 0 violations (seed 20090 ratio 1.12) |
| fresh nominal seeds | not available (the first rule's block was development) | 0 violations (final 40001 to 40200) |
| mismatched boxes | not measured | +15 percent 0 of 771; -15 percent 45 of 367 |

**Lie families (final seeds, 200 runs each).** Drift 0.25, 0.5, 1 and 2 K per hour on a healthy box: detected 100 percent, median delay 0 minutes. Drift with a cooling fault already active: 0.25, 0.5 and 1 K per hour detected **0 percent**; 2 K per hour detected 100 percent, median delay 590 minutes. Mimic: `injected_mimic_at_failure` 0 percent (1 percent flagged untrusted), `injected_mimic_late` 0 percent.

**Bound conservativeness (ratio bound over true, median / 90th percentile, final seeds, nominal box).** spoof_attempt 1.35 / 1.47; hidden_spoilage 4.31 / 5.56; injected_replay 1.15 / 1.24; drift 2 K per hour with a fault 1.15 / 1.24; injected_offset 18.5 / 27.7; drifts on a healthy box about 18.4 / 27. It is for safety decisions only, never an estimate.

**Trust levels, clean and physical runs (700 per box).** nominal 693 trusted, 7 low confidence, 0 untrusted; +15 percent 0, 325, 375; -15 percent 220, 425, 55.

## 11. What we can say on a slide / what we must NOT say

Can say (simulation results on a synthetic box, not real-world evidence): see decision 0006 section 9. In short: five lie families detected in 100 percent of 200 runs; slow drifts of 0.25 to 2 K per hour detected on a healthy box; a worst-case bound that was never below the truth on 200 fresh nominal runs of any family; false tamper verdicts on a box 15 percent below the calibration are gone (0 of 700) and cut from 531 to 132 on a box 15 percent above; mismatched boxes are flagged low confidence; the limits are measured and listed.

Must NOT say: that the mimic is caught; that a mismatched box is handled; that slow lies are caught in every situation; that the bound is an estimate or valid on every box; that these results describe real boxes; that any threshold is sourced.

## 12. Open questions for the decision-maker

1. Please confirm the choice of 40001 to 40200 as the final block (section 7, item 1).
2. Is the low-confidence rule (section 7, item 2) what you meant, including that an early CUSUM alarm on a mismatched box shows as untrusted for about 13 hours before it is downgraded?
3. The bound is invalid on some -15 percent runs with a fault (45 of 367). Accept as a documented limit, or should an out-of-date trip use a faster assumed time constant in the bound? (Not done. I did not check how many of those 45 trips were also flagged out of date.)

## 13. Suggested next phase (not started)

Phase 4 (signing and hash chain), which is what actually covers the mimic liar; or a fault-aware residual for slow lies behind a fault and the impossible-state proof under mismatch.
