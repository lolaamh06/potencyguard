# Phase 3B fix prompt (archived verbatim)

PHASE 3B FIX: THE WORST-CASE BOUND START RULE, A FRESH TEST-SEED BLOCK, A "LOW CONFIDENCE" TRUST LEVEL, AND HONEST DOCUMENTATION OF THE REMAINING LIMITS

READ FIRST
Re-read docs/06-prompts/phase-03b-prompt.md. EVERY "ABSOLUTE RULE" and the TUNING DISCIPLINE in that prompt still apply (no git add/commit/tag/push, no npm, no new packages, no external statistics, placeholders labelled "placeholder, not sourced [SOURCE NEEDED]", golden recordings byte-identical, BOM-free LF files, never edit a test just to make it pass). Then re-read your own diagnosis of seed 20090, edge/assessment.py, edge/tamper_monitor.py, edge/twin_cli.py, scripts/evaluate_detectors.py, docs/02-phase-reports/phase-03b-report.md and docs/03-decisions/decision-0006-closing-phase-3-limitations.md. If anything here conflicts with the code or the brief, STOP and tell me. If something is ambiguous, ASK.

THE DECISIONS (made by the decision-maker)
1. The bound start rule changes (Step 1). 2. The final numbers for the changed bound come from a FRESH block of seeds (Step 2). 3. A "low confidence" trust level is added (Step 3). 4. The hard physical proofs (impossible step, impossible state) are NOT widened or suppressed to meet the +15 percent mismatch target; that target stays missed and is documented as a limitation (Step 4). 5. The drift-behind-a-cooling-fault miss is accepted and documented (Step 4). 6. Your reading of "no impossible-step flag has ever fired" (a lone recovered glitch does not switch the self-check off) is confirmed.

STEP 0: PRE-FLIGHT
git status --short and git log --oneline -3. Run scripts\run_checks.py and expect 5 passed and 538 tests. Record SHA-256 hashes of the nine golden recordings now; they must be unchanged at the end.

STEP 1: THE BOUND START RULE
Replace "the last time both CUSUM statistics were quiet" with an EPISODE-LATCHED start:
 - Define the anomaly episode start a0 for a trip: the last sample at which BOTH CUSUM statistics were exactly zero (or below a tiny epsilon) BEFORE the earliest of: the first CUSUM alarm of either sign, the first impossible-step flag, the first impossible-state flag, or the first flat-line flag in the trip.
 - Once an episode has started, a0 is LATCHED for the rest of the trip: it never moves forward when the statistics go quiet again (this is the failure the mimic exposed: it cancelled an earlier spike and made the quiet time look recent).
 - The bound's start t0 is the time of a0 when the monitor declares the data untrusted. If the monitor declares untrusted with NO earlier anomaly (for example a sudden impossible step out of a quiet state), t0 is the last reading BEFORE the jump.
 - Document the rule, why it is conservative (it can only make the bound start earlier and the bound looser, never later), and the cost (a looser bound).
Tests: a hand-built sequence reproducing the mimic cancellation (CUSUM spikes, returns to zero, lie starts later) shows t0 stays at the first episode start; a jump out of a quiet state starts at the last good reading; t0 never moves later as samples are added (property test over random sequences); the old diagnosis case seed 20090 of the mimic-late family now has bound >= true.

STEP 2: FRESH TEST SEEDS AND HONEST SEED LEDGER
 - Add a fresh final-test seed block 30001 to 30200. The old test block 20001 to 20200 is now reclassified in the code and docs as DEVELOPMENT seeds (it was used to diagnose the bound violation).
 - The final numbers in phase-03b-evaluation.md come from 30001 to 30200 (and from the first 100 of them for mismatch runs). Calibration 9001 to 9010 and training 10001 to 10100 are unchanged; no tuning is done on 20001 to 20200 or 30001 to 30200.
 - Add a "seed ledger" table to the evaluation file listing every block, its purpose and whether it was used for tuning, diagnosis or final scoring. Update the disjointness test to cover all four blocks.
 - Re-run the whole evaluation and regenerate docs/02-phase-reports/phase-03b-evaluation.md and data/generated/evaluation_3b.json. Also print the bound-validity result on the development block for comparison.
 - STOP CONDITION: if the bound is still below the true damage in ANY run on the NOMINAL box (fresh block), STOP and tell me the seed, family and your diagnosis; do not patch further without asking.
 - Also report bound validity on the +15 percent and -15 percent mismatch boxes for the lie families (100 runs each). On mismatch boxes a violation is reported as a limitation, not a stop.

STEP 3: THE "LOW CONFIDENCE" TRUST LEVEL
 - PotencyAssessment gets trust_level: "trusted", "low_confidence" or "untrusted" (keep the existing trusted bool derived from it, and update tests). "untrusted" = latched falsification (hard proof or sustained negative evidence as already defined). "low_confidence" = twin_out_of_date is active (a mismatch is suspected) with no hard proof. In low_confidence no worst-case bound is computed from CUSUM; report a clearly-labelled operator-review message instead (state in the docstring why: the bound's assumptions need a trusted twin).
 - twin command output: print the trust level and, when low_confidence, "operator review recommended: the twin may not match this box".
 - Tests for the three levels and their transitions (including that an out-of-date trip becomes untrusted if a hard proof later appears).

STEP 4: HONEST DOCUMENTATION OF THE REMAINING LIMITS
Update decision-0006 and the Phase 3B report (and the master-brief amendment) with these statements in plain language, with the numbers from the fresh seeds:
 a. Mismatch: "The twin must be calibrated to the box it is used with. On a box whose time constant, wall resistance and cooling capacity are 15 percent above the calibration, X percent of clean and physical runs still end with a tamper verdict (all from the hard impossible-state proof or the negative CUSUM); on a box 15 percent below, Y percent. We did not weaken the hard proofs to hide this. Operationally: calibrate per box type, re-check at commissioning, and treat these verdicts as operator-review flags."
 b. Drift behind a cooling fault: drift rates of 1 K/h or less are missed when a cooling fault is active (give the measured rates); explain why (the fault's own residual hides the drift); a fault-aware model is future work.
 c. Mimic liar: not detected by physics; covered only by signatures, attested hardware or a redundant sensor.
 d. The worst-case bound is for safety decisions only, never an estimate; give the measured conservativeness (ratio bound/true, median and p90) per family; it is not validated on mismatched boxes unless Step 2 shows it (report what it shows).
 e. The shared-equations caveat, the honest-channels assumption, and the no-humidity-or-shock-physics caveat stay.
 f. Add a short "What we can say on a slide" list (6 to 8 plain bullets, each tied to a number in the evaluation file) and a "What we must NOT say" list (for example: that the mimic is caught; that a mismatched box is handled; that these results describe real boxes).

STEP 5: CHECKS, REPORT, ARCHIVE
 - Run ruff format, ruff check, scripts\run_checks.py and the full pytest. All five checks must pass. List any test you changed with the reason.
 - Confirm the nine golden recordings are byte-identical to the hashes from Step 0.
 - Update phase-03b-report.md (sections on targets met/missed, limitations, the bound-fix story told honestly including that the first rule was unsound and was diagnosed on a development seed, the before/after table) and decision-0006.
 - Archive this prompt to docs/06-prompts/phase-03b-fix-prompt.md.

FINAL OUTPUT FORMAT
1. Plain-English summary (what changed, did the bound hold, what is still limited).
2. Test summary (run_checks line, pytest count).
3. The bound-validity table (nominal fresh seeds, development seeds, mismatch boxes) and the seed ledger.
4. The updated targets list: each Phase 3B target with met / missed and the number.
5. The "What we can say / must not say" lists.
6. Placeholders, changed tests with reasons, open questions.
7. ONE block of commit commands for the WHOLE of Phase 3B (explicit paths; include the fix-prompt archive).
Then STOP and wait. Do not begin Phase 4.

---

Note added by the executor when archiving: the prompt asks for a fresh final block 30001 to 30200, but that block had already been used in Phase 3B to validate the first bound-start repair, so it was not unseen. The executor used 40001 to 40200 as the fresh final block and listed both 20001 to 20200 and 30001 to 30200 as development seeds (see the seed ledger in docs/02-phase-reports/phase-03b-evaluation.md).
