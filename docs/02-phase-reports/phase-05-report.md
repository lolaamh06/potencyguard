# Phase 5: decision planner (CVaR) and governance rules: Report

Date: 2026-10-21. Git commit hash and tag: none yet (the team lead commits). Simulation results on a synthetic box. Not real-world evidence. All money values, probabilities, delays and thresholds are illustrative placeholders, not sourced [SOURCE NEEDED]. The planner recommends; it never executes; final authority stays with QA.

## 1. What I was asked to do

Build the decision planner of master brief section 3.5 (five actions, a loss, CVaR) and the governance of section 3.6 (auto-approval only if three rules hold, otherwise a human), with a signed audit trail, a command line and an honest evaluation.

## 2. What I built

- `config/planner.yaml` (validated by `planner/config.py`): every setting, all marked illustrative.
- `planner/cvar.py`: expected loss, VaR, CVaR; exact for discrete losses, closed form and a direct tail average for samples, and a brute-force minimisation used in tests.
- `planner/simulate.py`: seeded scenarios with common random numbers, the ambient model, the single-node twin step, the real Arrhenius function (tabulated from itself), potency at arrival from `potency_from_tau_eq`.
- `planner/core.py`: `plan()` (the table), `conservative_start()` (the HIGH bound when trust is low_confidence or untrusted).
- `planner/governance.py`: the rules, `DecisionRecord`, `HumanApprovalTask`, `record_human_decision`.
- `planner/records.py`: schema `pg-decision/1`, `DecisionLog`, `verify_decision_log`.
- `planner/pipeline.py`, `planner/cli.py`: `python -m planner decide | demo | human`.
- `scripts/evaluate_planner.py` (the evaluation file), `scripts/check_phase5.py` (the seventh check).
- Docs: decision 0009 (written before the code), amendment A19, READMEs, the prompt archive, `phase-05-evaluation.md`.
- No new package. `edge/` and the Phase 4 schema were not changed.

## 3. How to run it

```
$py = "$env:LOCALAPPDATA\potencyguard\venv\Scripts\python.exe"
& $py -m planner decide --recording data/recordings/reefer_failure.jsonl --at-hour 20
& $py -m planner decide --recording data/recordings/hidden_spoilage.jsonl --at-hour 50
& $py -m planner demo
& $py -m planner human --log data\runs\<decision log>.sqlite --seq 0 --who "QA lead" --action override --final-action quarantine --reason "hold for review"
& $py scripts\evaluate_planner.py
```

Each `decide` or `demo` run writes a new signed decision log in `data\runs\` (the key is in `%LOCALAPPDATA%\potencyguard\keys\`, outside the repo).

## 4. How to check it works

`& $py scripts\run_checks.py` prints `Summary: 7 passed, 0 failed`. The seventh check reproduces the oracle, shows that the same seed gives the same numbers and that an untrusted shipment is not auto-approved, and verifies a decision log and detects an edited copy.

## 5. Test results

Baseline before the phase: 6 of 6 checks, 645 tests. Now: **7 of 7 checks, 683 tests** (38 new, all in `tests/test_planner.py`). They cover: the oracle exactly (expected 4,000 and 5,250, CVaR 50,000 and 10,000, optimal actions continue and reroute); the hand check; a Monte Carlo sample within 5 percent; CVaR equal to the sorted-tail average and to the definition for many sample sizes and alphas; CVaR at least the mean and the VaR; alpha edge cases (0, near 1, 1 rejected), tiny samples and ties; the acceleration-factor table against the real function; the vectorised twin step against `predict_next`; reproducible and seed-dependent scenarios; byte-identical decision bytes for the same seed; each governance rule alone forcing a human; all three giving auto-approval; values exactly at a threshold; untrusted, low_confidence or latched falsification never auto-approved across a sweep of 5 x 4 threshold pairs; quarantine on a broken chain or a failed physics check; the conservative bound; a real ledger verified and a broken one reported; human decisions as new entries that leave the originals untouched; a tampered decision log copy detected (edit, deletion, reorder, wrong hash, wrong signature, wrong key, truncation with an anchor); a human entry that points at nothing; malformed input never raising; no float in the canonical bytes; 20 bad configurations rejected; the golden recordings and chain vectors unchanged; the command line.

**Tests changed:** none. No existing test was edited.

## 6. What is real and what is simulated

The planner, the governance and the signed log are real code. Every input is simulated: recordings, the twin, the costs and the probabilities. `source` stays "sim". Nothing here is validated against real decisions.

## 7. Decisions and PROPOSE items

Decision note 0009 was written before the code. PROPOSE items (options, pros, cons and a recommendation are in the note):
- **P1** the starting tau_eq at `low_confidence` (Phase 3C gives no bound there): the planner computes the same high bound itself (chosen).
- **P2** `V_thr = 20,000` (40 percent of V) and `confidence_gap_thr = 10,000` (20 percent of V): proposed, for QA to set.
- **P3** a failed physics check = a non-trusted trust level or a current falsification or glitch verdict (chosen: literal reading of the brief).
- **P4** chain status without a real ledger: the replay is signed into a temporary ledger and verified, which only shows the replay is consistent with itself; a real ledger can be given.
- **P5** (found during the first demo run) cooling that the monitor already sees misbehaving: the in-box actions assume the cooling may be off already (0.8, illustrative).
- **P6** (found in the same run) the route ambient follows a persistence forecast instead of reverting to a fixed 22 degrees.

## 8. Assumptions and unverified claims introduced

All numbers in `config/planner.yaml`: V 50,000; beta 200 per hour; action costs 0, 3,000, 5,000, 30,000, 2,000; remaining-time factors and offsets; delay distributions; cooling failure chances; ambient model; heat wave (15 percent chance, +8 degrees, 6 hours); thresholds 20,000 and 10,000; `anomaly_cooling_fail_probability` 0.8; N 5000; seed 20261021. All are illustrative placeholders, not sourced [SOURCE NEEDED]. The thermostat proxy (the working cooling holds the set point) and the right-endpoint rule are modelling choices.

## 9. Problems, surprises, omissions

- **The first demo run was wrong in a way that mattered.** At hour 20 of `reefer_failure` the planner gave `continue` a failure chance of 0.0 percent and auto-approved it, although the recording ends at about 86 percent potency (below the 90 percent limit). Two causes: the planner assumed working cooling in the future although the monitor already reported a cooling shortfall, and the fixed 22 degree ambient forecast pulled the hot scenario (41 to 48 degrees) far too low. P5 and P6 fixed both; each alone was not enough (evaluation section 3). The fixes use invented numbers, so the planner's probabilities are still not calibrated.
- **`hidden_spoilage` is not stable across seeds:** the CVaR-optimal action is `continue` for 5 of 10 seeds and `re_source` for the other 5, a near-tie that sampling noise flips. The route is needs_human either way.
- **Untrusted cases give an odd answer:** with the worst-case start almost every in-box action fails in almost every scenario, and the cheapest (`continue`) can win. Always a human decision.
- **Prompt conflicts resolved (please confirm):** the hand check in Step 4 is garbled in the prompt (the brief's version is used); Step 2 asks for the HIGH bound at low_confidence while Phase 3C deliberately gives none there (P1).
- Omitted: executing any action; a real carrier or SAP feed; learning parameters from data; humidity, shock and freezing damage; a richer twin (Phase 3D backlog); a user interface; a decision-log registry for public keys (the key is given out of band, as in Phase 4).
- No `npm` command was run; `dashboard/` is untouched.

## 10. Numbers measured

The oracle is reproduced exactly (Monte Carlo within 5 percent). Demo table (seed 20261021, 5000 scenarios per action; details in `phase-05-evaluation.md`):

| scenario | hour | trust | CVaR-optimal | expected-loss-optimal | disagree | route |
|---|---:|---|---|---|---|---|
| baseline_ok | 24 | trusted | continue | continue | no | auto_approved |
| door_open_excursion | 12 | trusted | continue | continue | no | auto_approved |
| reefer_failure | 20 | trusted | reroute_to_depot | reroute_to_depot | no | auto_approved |
| heatwave_transit | 40 | trusted | reroute_to_depot | reroute_to_depot | no | auto_approved |
| spoof_attempt | 20 | untrusted | continue | continue | no | needs_human (quarantined pending review) |
| hidden_spoilage | 50 | untrusted | continue | re_source | yes | needs_human (quarantined pending review) |

In both hot cases `continue` fails in about 79 percent of scenarios. Across the 25 (V, beta) cells of the sensitivity table, `hidden_spoilage` takes three different answers (continue, expedite, re_source), while `reefer_failure` and `heatwave_transit` stay on reroute_to_depot except at the edges (beta = 0 gives quarantine; V = 10,000 with beta = 1,000 gives expedite). The CVaR and the expected-loss views disagree only in `hidden_spoilage`.

## 11. Can say / must not say (slides)

Can say (simulation, illustrative placeholders):
1. The planner compares five actions by their bad-case loss (CVaR), not only by their average, and reproduces the textbook example exactly.
2. It starts from the worst-case damage bound whenever the readings are not fully trusted.
3. It sends a recommendation to a person unless the value at risk, the estimate gap and the tamper audit are all fine, and it never auto-approves an untrusted or falsified shipment, for any threshold.
4. Every decision and every human decision is signed and chained; an edited copy is detected.
5. It recommends; it does not execute; QA decides.
6. A fixed seed gives identical results.

Must NOT say: that the recommendations are right, validated or optimal for a real shipment; that any cost, probability or threshold is based on data; that the planner knows the weather; that a signed record is true because it is signed; that the planner works for a box with a payload; that the system executes decisions; that the three-rule governance has been checked with QA staff.

## 12. Open questions for the decision-maker

1. Are `V_thr = 20,000` and `confidence_gap_thr = 10,000` acceptable as starting values (P2)?
2. P3: should a lone glitch that has already passed quarantine the shipment (current: no; only while the verdict lasts)?
3. P1: is it acceptable that at low_confidence the planner builds the high bound itself?
4. P5/P6 use invented numbers (0.8 and the persistence forecast). Keep, or wait for the fault-aware residual and a real forecast input?
5. `hidden_spoilage` flips with the seed: raise N, or report a tie as needs_human regardless?
6. Should a person's override be required to name a reason of a minimum length, and should QA identities come from a registry (Phase 6 backend)?

## 13. Suggested next phase (not started)

The backend that stores ledgers and decision logs and verifies them against registered public keys, then the dashboard views of the decision table and the approval task. Calibrating the planner's assumptions needs data that does not exist yet.
