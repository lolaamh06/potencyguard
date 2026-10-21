# planner

- What lives here: the decision planner (CVaR) and the governance rules (Phase 5). The planner RECOMMENDS; it never executes. Final authority stays with QA.
- Filled in by: Phase 5.
- Finding things:
  - `cvar.py`: expected loss, VaR and CVaR (Rockafellar-Uryasev), exact for discrete losses, exact closed form plus a direct tail average for samples.
  - `simulate.py`: seeded scenarios (common random numbers for all actions), the ambient model, and the potency at arrival through the single-node thermal twin with the real Arrhenius function.
  - `core.py`: `plan()` returns the table of alternatives; `conservative_start()` starts from the HIGH bound when trust is low_confidence or untrusted.
  - `governance.py`: the three auto-approval rules, quarantine of readings that fail the hash or physics check, `DecisionRecord`, `HumanApprovalTask`, `record_human_decision`.
  - `records.py`: schema `pg-decision/1`, the signed hash-chained decision log and its verifier.
  - `pipeline.py`: the existing edge pipeline up to a chosen hour; `cli.py`: `decide`, `demo`, `human`.
- Settings: `config/planner.yaml`. Every number is an illustrative placeholder, not sourced [SOURCE NEEDED]. Design and reasons: `docs/03-decisions/decision-0009-decision-planner.md`.
- Signing protects records after signing and does not stop a lie at the sensor: the planner uses the physics-based trust level, never the signature, to decide whether a reading may drive a decision.

```
$py = ".\.venv\Scripts\python.exe"   # run from the repo root after scripts\setup.ps1
& $py -m planner decide --recording data/recordings/reefer_failure.jsonl --at-hour 20
& $py -m planner demo
& $py -m planner human --log data\runs\<decision log>.sqlite --seq 0 --who "QA lead" --action override --final-action quarantine --reason "hold for review"
```
