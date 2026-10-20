# Phase 2D: Active product constants (Set C), reference profile, hidden_spoilage: Report

Date: 2026-10-20. Git commit hash: none yet (the team lead commits). Git tag: none.

Pre-flight: `git status --short` was clean, the log showed Phase 2C committed, and `run_checks.py` showed 5 passed with 286 pytest tests before any change.

## 1. What I was asked to do

Make Set C (Ea/R 15000 K, tau_max 8760 h) the active product profile, labelled as illustrative; keep the team document's values as a reference profile so its worked examples stay verifiable; regenerate the shared test vectors for both profiles; add a ninth scenario, `hidden_spoilage`; show the hour potency first fell below the minimum in the `potency` command; update docs and tests. The dashboard and npm were not touched.

## 2. What I built

New files
- `config/product_team_document.yaml`: the reference profile (product section only).
- `shared/test-vectors/potency_vectors_team_document.json`: vectors for the reference profile (includes `document_checks`).
- `simulator/scenarios/hidden_spoilage.yaml`.
- `data/recordings/hidden_spoilage.jsonl`, `data/recordings/hidden_spoilage.ground_truth.json`.
- `tests/test_profiles.py` (13 tests), `tests/test_hidden_spoilage.py` (8 tests).
- `docs/03-decisions/decision-0004-active-product-profile.md`, this report, `docs/06-prompts/phase-02d-prompt.md`.

Changed files
- `config/product_default.yaml`: Ea_over_R 15000 and tau_max_h 8760, with the placeholder labels and a profile name. Nothing else.
- `scripts/make_test_vectors.py`: writes two files (schema version 2, with a `profile` note in each `meta`); `build_all()` added.
- `shared/test-vectors/potency_vectors.json`: regenerated for the active profile (no `document_checks` any more; those live in the reference file).
- `edge/cli.py`: the summary table prints the hour of the first sample below P_min (or "never") for both rows.
- `scripts/constants_study.py` and `docs/02-phase-reports/phase-02c-constants-study.md`: wording that said set A was "current"; the study now covers all golden recordings (nine rows per table). Numbers for the original eight rows are unchanged.
- `docs/00-project-brief/master-brief.md`: amendment A15 appended.
- `docs/03-decisions/decision-0003-potency-engine.md`: a one-line update note.
- READMEs: `config`, `edge`, `scripts`, `simulator`, `data`, `shared/test-vectors`.
- Tests: see section 5a.

## 3. How to run it

```powershell
$py = "$env:LOCALAPPDATA\potencyguard\venv\Scripts\python.exe"
& $py scripts\run_checks.py
& $py -m edge potency --recording data/recordings/hidden_spoilage.jsonl
& $py -m edge potency --all
& $py scripts\make_test_vectors.py     # regenerates both vector files
```

## 4. How to check it works

`run_checks.py` prints five `PASS:` lines. `python -m edge potency --recording data/recordings/hidden_spoilage.jsonl` shows the reported row with "never" and the true row with "61.0 h". After `generate --all`, `git status --short` shows only the two new `hidden_spoilage` files under `data/`; the eight old recordings are byte-identical.

## 5. Test results

- `run_checks.py`: 5 passed, 0 failed.
- pytest: 339 passed, 0 failed, 0 skipped (286 before). Per file: test_box_simulator 21, test_constants_study 8, test_freerun_and_tools 24, test_hidden_spoilage 8, test_live_simulator 35, test_potency 84, test_potency_tracker 40, test_profiles 13, test_scenarios 68, test_sensor_interface 32, test_smoke 6.
- The 200-seed hidden_spoilage tests run once per seed and share the results; the full suite takes about 13 seconds.

### 5a. Tests I changed, and exactly why

I ran the full suite after switching the constants and listed all 35 failures before touching any test. Each fell into a category from the prompt; none needed a stop.

1. `test_smoke::test_default_config_loads`: reads the active constants. Expected values changed to Ea/R 15000, tau_max 8760, k_ref = ln(1/0.9)/8760 = 1.20275e-05. (category ii)
2. `test_potency::test_worked_examples_...` (6 cases) and `test_older_brief_values_...`: these encode the document's numbers. They now use the new `reference_product` fixture (the reference profile) and the vectors file for that profile. (category i)
3. `test_potency` vector tests (constants, AF, tau, committed-equals-fresh) and `test_potency_tracker::test_tracker_matches_the_shared_vectors`: they read vectors that depend on the constants. They are now parametrised over both vector files, each checked against its own profile, and the fresh-generation test covers both files. (category ii)
4. `test_potency::test_kinetic_constants_are_validated` (2 cases): built bad config files by replacing the text `Ea_over_R: 10000` and `tau_max_h: 17520` in the default file; the strings are now `15000` and `8760`. (category ii)
5. `test_potency_tracker::test_reefer_failure_uses_far_more_shelf_life_than_the_baseline` became `test_reefer_failure_pushes_potency_below_the_minimum`: it asserted potency stays above P_min, which was true only for the old constants. Under the active profile the recording ends at 84.2 percent potency. (category ii; the Phase 2B report predicted this)
6. `test_potency_tracker`: "all eight recordings" and the `--all` output counts changed from 8 to 9 (a ninth scenario exists).
7. `test_constants_study`: the "config unchanged" test compared against 10000; now 15000. The per-set recordings count changed from 8 to 9. A new test asserts the active default equals the study's Set C.
8. `test_scenarios`: the scenario enumeration and golden-folder tests now expect nine scenarios.
9. `tests/conftest.py` gained a `reference_product` fixture; `product` is unchanged and means the active profile.

New tests: active-profile closed forms and k_ref (in `test_potency.py`), `test_profiles.py` (both profiles load, they differ only in the two kinetic constants, labels are honest, the reference profile reproduces the document's rounded examples, the active profile reproduces the Set C numbers for all nine recordings and agrees with the Phase 2C study document), `test_hidden_spoilage.py`, and two CLI output tests.

## 6. What is real and what is simulated

Real code: the profiles, vector generator, potency maths, CLI. Simulated: every temperature. The active constants are an illustrative profile, not measured and not sourced; the reference constants are from the team document and not independently verified. Neither describes a real product. All results are simulation results on a synthetic box.

## 7. Decisions I made and why

1. **Reference profile file holds only the product section.** `load_product_config` reads only the product keys and ignores others, while `load_box_config` and `load_freerun_config` read only the box and free-run keys from `product_default.yaml`. So the reference file cannot drift on those. For the product keys that appear in both files (limits, confirmation count, alpha, Monte Carlo count), `test_profiles.py` asserts they are equal except for the two kinetic constants.
2. **No claim about the 10000 value's source.** The original config comment said "Source: USP default Ea = 83.144 kJ/mol", which the brief also states. As instructed, the reference file now says "as stated in the team document ... we have not traced or verified that source [SOURCE NEEDED]". The active file makes no source claim. (The brief's section 3.1 text is unchanged; amendment A15 explains.)
3. **`hidden_spoilage` parameters.** Duration 96 h, cargo-area profile 24 C rising to 46 C by hour 24 and staying there (jitter +/-1 C, shift +/-2 h), a cooling derate to a factor of 0.24 to 0.38 starting between hours 12 and 18 and lasting to the end, and a hold spoof at 4 to 6 C starting between hours 20 and 26, with noise, lasting to the end. I narrowed the derate range from the prompt's 0.2 to 0.5 and the start ranges (derate 12 to 18, spoof 20 to 26) so that the spoof always begins after the derate, and so every seed crosses the minimum inside the window. I tuned with a throwaway script that is not in the repo.
4. **Tuning evidence.** Over seeds 1000 to 1199 and, separately, seeds 7000 to 7199, every run crossed P_min between 50.5 and 85.5 hours, the reported series never fell below P_min, never left the hard limits and never confirmed an excursion, and the true temperature peaked at 39.5 C (plausibility limit 45 C).
5. **Expect block** for the scenario: true max above 25 and below 45, reported-true gap above 15, spoof begins after the failure. The potency guarantees live in `tests/test_hidden_spoilage.py`.
6. **The study document** is regenerated and now has a `hidden_spoilage` row in every table. This was not requested; it follows from the study script reading every golden recording, and the committed-equals-fresh test requires it.
7. **CLAUDE.md** is unchanged: no rule mentions the constants.
8. **Amendment numbering:** appended as A15 at the end of the existing amendments section.

## 8. Assumptions introduced

- The active constants (illustrative, placeholder, not sourced [SOURCE NEEDED]; replace with the manufacturer's stability data).
- The `hidden_spoilage` numbers: cargo-area temperatures up to 46 C, derate 0.24 to 0.38, spoof value 4 to 6 C, and the expect thresholds (25, 45, 15). All placeholders.

## 9. Problems and surprises

- A spoof or derate ending exactly at the trip end does not cover the final sample (events end exclusive of their end time), so in `hidden_spoilage` the last reported reading (96 h) is the true 37.7 C. That one 10-minute interval at a very high acceleration factor adds about 48 h to the reported tau_eq (155.9 h; about 108 h without it) and puts a visible spike at the end of the reported series. The same happens in the other scenarios whose spoof ends at the trip end. I did not change event timing, because that would change the old golden recordings.
- Before the spoof starts, the reported series shows a brief warm rise (up to about 19 C around hour 20) and then drops to about 4 C. That is intended by the story ("from a few hours after the weakness begins") and is also physically impossible for the box, which makes it a good detector test.
- Under Set C the true `hidden_spoilage` total is 214 percent of the shelf life and 777 "extra days lost", more than the whole 365 day shelf life. These numbers are correct for the model but look odd on a slide; see question 3.
- `R` is a built-in PowerShell alias, which silently swallowed a first attempt at editing a script; I redid the edits with the editor tool.

## 10. Numbers measured (simulation results, synthetic box, active profile Set C, golden recordings at their fixed seeds)

| Scenario | Rep tau_eq (h) | Rep potency % | Rep used % | Rep extra days | Rep < P_min | True tau_eq (h) | True potency % | True used % | True extra days | True < P_min |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline_ok | 48.10 | 99.942 | 0.549 | 0.00 | never | 48.12 | 99.942 | 0.549 | 0.01 | never |
| door_open_excursion | 49.20 | 99.941 | 0.562 | 1.05 | never | 49.28 | 99.941 | 0.563 | 1.05 | never |
| freeze_event | 15.18 | 99.982 | 0.173 | -0.87 | never | 15.19 | 99.982 | 0.173 | -0.87 | never |
| heatwave_transit | 1666.36 | 98.016 | 19.022 | 66.43 | never | 1664.79 | 98.018 | 19.004 | 66.37 | never |
| hidden_spoilage | 155.90 | 99.813 | 1.780 | 2.50 | never | 18752.95 | 79.808 | 214.075 | 777.37 | 61.0 h |
| reefer_failure | 14348.78 | 84.149 | 163.799 | 596.37 | 31.7 h | 14339.93 | 84.158 | 163.698 | 596.00 | 31.7 h |
| sensor_glitch | 24.07 | 99.971 | 0.275 | 0.00 | never | 24.02 | 99.971 | 0.274 | 0.00 | never |
| shock_drop | 24.00 | 99.971 | 0.274 | 0.00 | never | 24.03 | 99.971 | 0.274 | 0.00 | never |
| spoof_attempt | 69.23 | 99.917 | 0.790 | 1.38 | never | 1262.12 | 98.493 | 14.408 | 51.09 | never |

The old eight recordings are unchanged files; only their potency numbers changed with the constants.

## 11. Open questions for the decision-maker

1. Event windows end exclusive of the end time, so a spoof that "lasts to the end" leaves the final sample true (see section 9). Make the last sample covered, even though that changes event timing and would regenerate the old recordings? Or accept the spike as a feature of the data?
2. In `hidden_spoilage` the reported series is warm for a few hours before the lie begins. Keep (more realistic, easier for a detector) or start the spoof together with the derate?
3. For presentation, "shelf life used" above 100 percent (214) and "extra days lost" above the shelf life (777 days) look odd. Should the dashboard cap them and show "shelf life exhausted at hour 61" instead?
4. Both profiles are unsourced. Who will supply manufacturer stability data, and should a third, sourced profile replace Set C once available?
5. Should the Phase 2C study document stay as a living document (now nine rows) or be frozen at the eight recordings it was made with?

## 12. Suggested next phase

Phase 3 (thermal twin, calibration, detectors) is next. `hidden_spoilage` and `spoof_attempt` give it two attack recordings with ground truth, and the physically impossible drop in `hidden_spoilage` is a natural first detection target. Not started.
