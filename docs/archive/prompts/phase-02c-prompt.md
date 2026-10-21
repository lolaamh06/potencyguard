PHASE 2C: PRODUCT-CONSTANTS STUDY (READ-ONLY ANALYSIS, NO CONFIG CHANGES)

READ FIRST, ASSUME NOTHING
1. Read CLAUDE.md, docs/00-project-brief/master-brief.md (including the amendments), docs/02-phase-reports/phase-02b-potency-report.md and docs/03-decisions/decision-0003-potency-engine.md.
2. Read before using: edge/potency.py, edge/cli.py, shared/config.py, config/product_default.yaml, data/recordings/*.jsonl and *.ground_truth.json.
3. If anything here conflicts with the brief or existing code, STOP and tell me the exact conflict. If anything is ambiguous, ASK before writing code.

WHY THIS STEP EXISTS
With the current product constants (Ea/R = 10000 K, tau_max = 17520 h, P_min = 0.90, T_ref = 5 C), potency never falls below P_min in any golden recording, and the spoof scenario's potency gap is only 0.18 percentage points. The decision-maker needs numbers a pitch can use. This step MEASURES several candidate constant sets so the decision can be made from data. It must NOT change the real configuration.

ABSOLUTE RULES
- NEVER run git add, git commit, git tag or git push. At the end print ONE block of commit commands (explicit paths only, no "git add -A" or "git add ."), one commit message, no co-author trailers.
- NEVER run npm install or npm ci. Do not touch the dashboard.
- No new Python packages.
- Do NOT edit config/product_default.yaml, shared/config.py, edge/potency.py or any existing test. Candidate sets are built IN MEMORY (for example with dataclasses.replace on the loaded ProductConfig; if ProductConfig is frozen or not a dataclass, tell me how you built the variants).
- No external statistics anywhere. Every candidate value is an illustrative placeholder: label them "placeholder, not sourced [SOURCE NEEDED]".
- No wording that claims any set describes a real product.
- Files UTF-8 without BOM, LF line endings, written with .NET file writes.

STEP 0: PRE-FLIGHT (read-only)
git status --short and git log --oneline -5. If Phase 2B is uncommitted (tracked files modified), STOP and tell me. Run scripts\run_checks.py: expect 5 passed and 279 tests.

STEP 1: THE STUDY SCRIPT (new file scripts/constants_study.py, read-only analysis)
Candidate sets (T_ref = 5 C and P_min = 0.90 stay as in the config for all of them):
  A: Ea/R 10000, tau_max 17520 h   (current)
  B: Ea/R 15000, tau_max 17520 h
  C: Ea/R 15000, tau_max 8760 h
  D: Ea/R 20000, tau_max 8760 h
  E: Ea/R 15000, tau_max 4380 h
For each set and for each of the 8 golden recordings, run PotencyTracker over (1) the REPORTED series and (2) the TRUE series from the ground-truth file (use update_sample as in edge/cli.py), and compute:
  - final tau_eq in hours,
  - potency percent,
  - shelf life used percent,
  - extra shelf life lost in days = (tau_eq_h - elapsed_hours) / 24, where elapsed_hours is the trip length (this is the loss beyond normal ageing at the reference temperature; may be negative for cold trips: print it as is),
  - whether potency fell below P_min (and, if it did, the simulated hour at which it first did, found by checking potency after every sample),
  - the final status ("ok", "suspect", "excursion_confirmed") and samples excluded.
Also per set: days of shelf life that one day at 25 C and one day at 40 C would cost (AF * 24 h / 24 = AF days, state it as "days lost per day at that temperature"), and how many days at 40 C it takes to use 100 percent of the shelf life (tau_max / AF(40 C) / 24).
Output: print a compact table per set (rows = 8 scenarios; columns: used % reported, used % true, potency % reported, potency % true, extra days lost reported, extra days lost true, below P_min reported (yes/no, hour), below P_min true (yes/no, hour)), then a summary block per set for the spoof scenario: the hidden loss = true minus reported in percent used, in potency percentage points and in days. Footer on every table: "Simulation result on a synthetic box, with illustrative constants. Not real-world evidence."
Also write the same output as a Markdown file docs/02-phase-reports/phase-02c-constants-study.md (with a short plain-English header: what was compared and why, how to read the tables) and keep a machine-readable copy at data/generated/constants_study.json (this folder is git-ignored; do not commit it).
Add a short entry for the script to scripts/README.md.

STEP 2: CHECKS
- Add a small test file tests/test_constants_study.py: (a) set A reproduces the numbers in phase-02b-potency-report.md section 10 (tau_eq within 0.01 h, used percent within 0.001); (b) every set yields finite numbers for all 8 recordings; (c) the study does not modify the loaded ProductConfig (the config object used elsewhere is unchanged after the study runs); (d) config/product_default.yaml is byte-identical before and after running the study (compare a hash).
- Run ruff format, ruff check and scripts\run_checks.py: all five checks must pass.

STEP 3: REPORT AND ARCHIVE
- The study document from Step 1 is the main report. Also write docs/02-phase-reports/phase-02c-report.md (short, same structure as earlier phase reports: what was built, how to run, test results, assumptions, surprises, numbered open questions).
- Archive this prompt text verbatim to docs/06-prompts/phase-02c-prompt.md.

FINAL OUTPUT FORMAT
1. A plain-English summary a student can read.
2. The full tables for ALL five sets pasted into the chat (not just a link), plus the spoof summary block per set.
3. Your own observation, in one paragraph, of which set gives the most useful demo story and why, but do not apply anything.
4. The test summary line.
5. ONE block of commit commands (explicit paths).
Then STOP and wait. Do not change any constant, and do not begin Phase 3.
