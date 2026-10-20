# Phase 2C: Product-constants study: Report

Date: 2026-10-20. Git commit hash: none yet (the team lead commits). Git tag: none.

Pre-flight: `git status --short` was clean, the log showed Phase 2B committed, and `run_checks.py` showed 5 passed with 279 pytest tests before any change. The main result is in [phase-02c-constants-study.md](phase-02c-constants-study.md).

## 1. What I was asked to do

Measure five candidate sets of product constants against the eight golden recordings, without changing the real configuration, so the decision-maker can choose from data.

## 2. What I built

- `scripts/constants_study.py`: builds the candidate configurations in memory, runs the potency tracker over the reported and the true series of every recording, and writes a Markdown study and a JSON copy.
- `docs/02-phase-reports/phase-02c-constants-study.md`: the study (five tables, one per set, with a spoof summary each).
- `data/generated/constants_study.json`: machine-readable copy (git-ignored, not committed).
- `tests/test_constants_study.py` (7 tests).
- `scripts/README.md`: an entry for the script. This report and `docs/06-prompts/phase-02c-prompt.md`.

No existing source file, test or config file was changed.

## 3. How to run it

```powershell
$py = "$env:LOCALAPPDATA\potencyguard\venv\Scripts\python.exe"
& $py scripts\constants_study.py
& $py scripts\run_checks.py
```

## 4. How to check it works

The script prints the study and the two paths it wrote. `git status --short` afterwards shows the study document as the only new report file; `config/product_default.yaml` is unchanged.

## 5. Test results

- `run_checks.py`: 5 passed, 0 failed.
- pytest: 286 passed, 0 failed, 0 skipped (279 before, plus 7 new).
- The new tests check that set A reproduces the Phase 2B report table (tau_eq within 0.01 h, used percent within 0.001; the test reads the table from the report itself), that every set gives finite numbers for all eight recordings, that the loaded config object is unchanged, that the YAML file has the same hash before and after, and that the committed study document equals a fresh run.

## 6. What is real and what is simulated

Real code: the study script and the tracker. Simulated: every temperature (synthetic box). Every candidate value (Ea/R of 15000 and 20000, tau_max of 8760 h and 4380 h) is an illustrative placeholder, not sourced [SOURCE NEEDED], and none describes a real product. Set A is the current configuration.

## 7. Decisions I made and why

1. `ProductConfig` is a frozen dataclass, so variants are made with `dataclasses.replace`; the base object is never modified. `k_ref` is derived, so it follows the replaced `tau_max` automatically.
2. "Extra days lost" uses the last sample time as the trip length: (tau_eq - elapsed hours) / 24.
3. The tables carry one extra column, the final tracker status of the reported series with the excluded-sample count, because the prompt asked for these to be computed. The JSON holds the same for the true series.
4. A tiny negative that rounds to zero prints as 0, never "-0.00".

## 8. Assumptions introduced

The five candidate sets. The hour at which potency first falls below P_min is the first sample after it did, so it is exact to the 10 minute sample interval.

## 9. Problems and surprises

- Sets B to E all make one day at 40 C cost more than a year of shelf life (415 days). That is dramatic but extreme; set A costs 56 days per day at 40 C.
- Set D is so steep that the reefer failure ends at about 19 percent potency (1,587 percent of shelf life used), which looks like a different product, not a vaccine that was warmed for a day.
- The `door_open_excursion` scenario is barely visible in any set: it is a one to four hour excursion, so its used percent is within a few hundredths of the baseline's in every set.
- The Ea/R of 10000 in the config comes with a cited source (a published default); the other candidate values have no source, so using any of them loses that grounding.

## 10. Numbers measured

See the study document. Highlights (simulation results, golden recordings, fixed seeds):

| Set | Ea/R | tau_max (h) | reefer_failure used % | below P_min | spoof hidden loss (used points / potency points / days) |
|---|---|---|---|---|---|
| A (current) | 10000 | 17520 | 8.88 | no | 1.68 / 0.18 / 12.25 |
| B | 15000 | 17520 | 81.90 | no | 6.81 / 0.72 / 49.70 |
| C | 15000 | 8760 | 163.80 | yes, at 31.7 h | 13.62 / 1.42 / 49.70 |
| D | 20000 | 8760 | 1586.88 | yes, at 22.8 h | 53.72 / 5.49 / 196.06 |
| E | 15000 | 4380 | 327.60 | yes, at 27.5 h | 27.24 / 2.82 / 49.70 |

## 11. Open questions for the decision-maker

1. Which set (if any) should replace the current constants? My observation is in the chat reply; the decision is yours.
2. If the constants change, the Phase 2B test vectors, the golden-recording analysis tests and the Phase 2B decision record must be regenerated and updated. Do you want that as its own phase?
3. Should the story rest on "shelf life used" and "days lost" rather than on potency percent, whichever set is chosen? Potency percent moves slowly in every set except D.
4. Should a longer or hotter scenario be added so a pitch can show a full-day heat exposure?

## 12. Suggested next phase

Phase 3 (thermal twin, calibration, detectors) is independent of this choice. The constants decision should be made before the dashboard potency mirror (Phase F2). Not started.
