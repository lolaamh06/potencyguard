# Phase 3: Thermal twin, calibration and tamper detectors: Report

Date: 2026-10-20. Git commit hash: none yet (the team lead commits). Git tag: none.

Pre-flight: `git status --short` was clean, the log showed Phase 2D committed, and `run_checks.py` showed 5 passed with 339 pytest tests before any change.

All numbers below are **simulation results on a synthetic box**, not field results. The full evaluation is in [phase-03-evaluation.md](phase-03-evaluation.md).

## 1. What I was asked to do

Add the two sensor channels the physics needs (ambient and cooling duty) and fix the end-of-trip coverage of events; build a thermal twin, a calibration routine, four tamper detectors and a streaming monitor with a classification; add commands to see it; and measure detection delay and false alarms with an evaluation harness, including runs where the real box differs from the twin's calibration. The dashboard and npm were not touched.

## 2. What I built

New files
- `edge/thermal_twin.py`, `edge/calibration.py`, `edge/detector_config.py`, `edge/tamper_monitor.py`, `edge/twin_cli.py`.
- `config/twin_calibrated.yaml` (fitted parameters), `config/detectors.yaml` (detector settings).
- `simulator/calibration_set.py`, `simulator/divergence.py`, `simulator/calibration_scenarios/` (two clean scenarios and a README).
- `data/calibration/` (10 recordings and 10 ground-truth files, 524 kB, seeds 9001 to 9010).
- `scripts/evaluate_detectors.py`; `docs/02-phase-reports/phase-03-evaluation.md` (generated).
- Tests: `test_channels.py` (30), `test_thermal_twin.py` (17), `test_calibration.py` (13), `test_tamper_monitor.py` (36), `test_evaluation.py` (9).
- `docs/03-decisions/decision-0005-thermal-twin-and-detectors.md`, this report, `docs/06-prompts/phase-03-prompt.md`.

Changed files
- `edge/sensor_reading.py` (optional `ambient_c`, `cooling_duty`), `edge/recorded_source.py` (reads 0.2 and 0.3), `edge/cli.py` (`twin` and `calibrate` commands).
- `shared/config.py`, `config/product_default.yaml` (`sensor_sigma_ambient_c` 0.1, `detect_divergence_c` 1.0).
- `simulator/engine.py`, `live.py`, `events.py`, `truth.py`, `recording.py`, `simulate.py`, `cli.py` (`generate-calibration`).
- All nine golden recordings (schema 0.3), `docs/00-project-brief/master-brief.md` (amendment A16), READMEs (edge, simulator, data, config, scripts).
- Tests changed: section 5a.

## 3. How to run it

```powershell
$py = "$env:LOCALAPPDATA\potencyguard\venv\Scripts\python.exe"
& $py scripts\run_checks.py
& $py -m edge twin --recording data/recordings/hidden_spoilage.jsonl
& $py -m edge twin --all
& $py scripts\evaluate_detectors.py          # about 4 to 5 minutes; add --quick for about 10 seconds
& $py -m simulator generate-calibration
& $py -m edge calibrate
```

## 4. How to check it works

`run_checks.py` prints five `PASS:` lines. `python -m edge twin --all` shows one line per recording: no tamper verdict on the clean ones, "thermal anomaly" for door open, cooling failure and heat wave, and "thermal anomaly > sensor glitch > suspected falsification" for the two spoofs with a 10 minute delay. `git status` after `generate --all` shows the nine recordings changed (new schema) and nothing else under `data/` apart from `data/calibration/`.

## 5. Test results

- `run_checks.py`: 5 passed, 0 failed.
- pytest: 444 passed, 0 failed, 0 skipped (339 before). Per file: test_box_simulator 21, test_calibration 13, test_channels 30, test_constants_study 8, test_evaluation 9, test_freerun_and_tools 24, test_hidden_spoilage 8, test_live_simulator 35, test_potency 84, test_potency_tracker 40, test_profiles 13, test_scenarios 68, test_sensor_interface 32, test_smoke 6, test_tamper_monitor 36, test_thermal_twin 17. The suite takes about 28 seconds; 10 of those are the quick evaluation run.

### 5a. Tests changed, and why

1. `test_box_simulator::test_box_config_rejects_non_positive_new_keys` (3 cases): the minimal config text in the test lacked the two new required keys; I added them.
2. `test_scenarios::test_fixed_seed_recordings_are_byte_identical` (9 cases): asserted schema version "0.2"; now "0.3".
3. `test_constants_study::test_set_a_reproduces_the_phase_2b_report`: the reported series of `spoof_attempt` lost one stale, true-looking final reading (the last-sample fix), so its reported equivalent time dropped (48.06 h to 45.23 h under the reference constants). That row now asserts "lower than the Phase 2B value"; the true series and all other rows are unchanged and still match.
4. `test_profiles::test_the_active_profile_gives_the_set_c_numbers_...`: the same effect on two rows. `spoof_attempt` reported: 69.23 h to 56.63 h (0.790 to 0.646 percent of shelf life); `hidden_spoilage` reported: 155.90 h to 107.96 h (1.780 to 1.232 percent). True-series numbers unchanged.
5. `test_constants_study::test_the_committed_study_document_matches_a_fresh_run` and the committed-recordings hash tests were not edited: I regenerated the study document and the recordings, and they pass.
6. Not affected: the shared potency test vectors (they do not depend on recordings) and `test_hidden_spoilage` (the 200-seed guarantees hold; the reported series is now even cleaner).

The Phase 2B, 2C and 2D reports still show the older reported numbers for those two rows; they are historical.

### 5b. What the simulator extension changed (verification)

I compared every committed Phase 2D recording with its Phase 3 regeneration, column by column. `temp_c`, `rh_pct`, `shock_g` and `t_s` are identical in all nine recordings except one sample each in two of them: the final reading of `spoof_attempt` (29.34 C became 5.12 C, sample 216) and of `hidden_spoilage` (37.65 C became 4.31 C, sample 576). In the ground-truth files, `true_temp_c` and `compressor_on` are unchanged everywhere; the only other changes are `cooling_factor` at the last sample of `reefer_failure`, and `reported_temp_c`, `cooling_factor` and `spoof_mode` at the last sample of the two spoof recordings. `heatwave_transit` has no event that ends at the trip end, so it is unchanged. These are exactly the effects the prompt predicted.

## 6. What is real and what is simulated

Real code: the twin, calibration, monitor, harness and commands. Simulated: every reading, including the ambient and duty channels; the attacks; the box that the twin is calibrated on. The fitted numbers describe the synthetic box only. No hardware is involved.

## 7. Decisions I made and why

Deviations from the prompt are marked **(deviation)**.

1. **(deviation) The twin is fitted by a restricted regression.** A plain regression of T[n+1] on T[n], ambient and duty is badly biased in a thermostat-controlled box: it gave a time constant of 1.80 h and a cooling depression of 9.0 K, against a true 6 h and 30 K. The cause is measurement noise in T[n] combined with the cooling duty following the box temperature. I tried a two-stage fit with the previous reading as instrument; it was unstable. Imposing the brief's structure (the increment is proportional to the gap to ambient and to the duty) recovers 5.98 h and 29.85 K from the same data. Both fits are computed; the plain one is a reported diagnostic. This is still least squares and still checks b = 1 - a and d = 0 on the plain fit.
2. **(deviation) Calibration scenarios.** The prompt suggested baseline plus a door-open-like scenario. A door open adds heat the twin cannot see, which would bias the fit, so I made two clean scenarios: `calibration_baseline` (the baseline profile) and `calibration_wide` (wide ambient swings, so the cooling runs from off to flat out). They live in `simulator/calibration_scenarios/`, not in the golden set.
3. **(deviation) Impossible state uses a lag-aware floor.** The prompt's floor, ambient minus the cooling depression, is a steady state. My first version raised false "falsification" verdicts in `heatwave_transit` and `hidden_spoilage` because a box lags a rising ambient and can lawfully be colder than that for hours. The detector now compares with the coldest trajectory the box could have followed with full cooling from the first reading. `floor_bound` (the steady value) still exists.
4. **(deviation) The step bound has a heat allowance.** Without it, a door held open produces real steps larger than the prompt's bound and was labelled falsification. `heat_allowance_c` is 60 K, which equals the simulator's largest door heat (120 W through the wall) and so is tuned to the simulator; see limitations.
5. **Latching and holding.** Proof of falsification is latched until reset; a negative CUSUM alarm is held for 6 samples. Without the latch, a value held at a physically plausible number looked like a harmless cooling shortfall again after its first jump.
6. **Lone jumps.** An impossible step waits `N - 1` samples (N is the product config's confirmation count, 2) before it is called a falsification, to see whether it reverts; undecided samples do not feed the CUSUM. This mirrors the potency tracker's suspect rule.
7. **Flat-line factor 0.3 (not 0.5).** At 0.5 a flat-line false alarm appeared by chance in one heat wave run in forty. Because flat-line proof is latched, I lowered the factor; it now catches only exact freezes.
8. **CUSUM settings.** The sweep gave zero false alarms in 13,200 clean hours for every setting, so the stated rule fell through to the smallest delay: k = 0.25, h = 4. See limitations for what that does and does not mean.
9. **RecordedSource** reads schema 0.2 files with `ambient_c` and `cooling_duty` as `None` (the monitor then raises a clear error) and 0.3 files.
10. **`first_divergence_s`** counts only spoof windows, so a lone glitch does not set it.
11. **Event ends at the trip end:** implemented with a `covers_final_sample` flag on the event record, so `end_s` in the history is unchanged.
12. **Extras:** an `edge calibrate` and a `simulator generate-calibration` command, an extra tamper family `injected_offset_small` (offsets of 1.5 to 3 C), and a "flagged at the end" column.

## 8. Assumptions and unverified claims introduced (all placeholders, not sourced [SOURCE NEEDED])

- `sensor_sigma_ambient_c` 0.1; `detect_divergence_c` 1.0; ambient channel range -60 to 80 C.
- `config/detectors.yaml`: `cusum_k` 0.25, `cusum_h` 4.0, cap factor 2.0, false-alarm target 1.0 per 1000 h, step tolerance 5 sigma, heat allowance 60 K, state margin 6 sigma over 3 samples, falsification hold 6 samples, flat-line window 18 samples and factor 0.3.
- Calibration gates in `edge/calibration.py`: at least 500 intervals, ambient spread at least 2 C, duty spread at least 0.1, condition number at most 50.
- The calibration scenarios' temperatures; the injected spoof sizes in the harness (offset 6 to 12 C and 1.5 to 3 C, replay of 1 to 3 hours back for 2 hours).
- The fitted twin: time constant 5.984 h, cooling depression 29.85 K, residual spread 0.0687 C, fitted on 2,880 intervals (R-squared 0.928, condition number 1.59).

## 9. Problems and surprises

- The plain regression bias (decision 1) was the biggest surprise; the "known weakness" in the prompt turned out to make the plain fit unusable here.
- Two false-alarm sources appeared only on the golden runs and were fixed (decisions 3 and 7).
- A sensor that is merely "held at the true value" is still flagged (the control family): see limitations.
- `R` and `r` are aliases in PowerShell; I used the editor tool for multi-line edits.
- No OneDrive or sync problems. `data/calibration/` adds 524 kB to the repo.

## 10. Numbers measured (simulation results, synthetic box)

Runtime: full evaluation about 4 to 5 minutes; quick mode about 10 seconds. Seeds: calibration 9001 to 9010, training 10001 to 10100, test 20001 to 20200 (disjoint; the mismatch runs use the first 100 test seeds).

**Calibration.** Fitted (restricted): 5.984 h, 29.85 K, 0.0687 C. Plain regression on the same data: 1.80 h, 9.00 K, and b - (1 - a) = -0.061 (it should be 0). The plain fit's time constant is about 30 percent of the truth.

**CUSUM sweep (training seeds).** False alarms: 0 in 13,200 clean hours for every (k, h). CUSUM negative-side median delay on the spoof families: k = 0.25 with h = 4, 8, 12 gives 10, 30, 40 min; k = 0.5 gives 20, 30, 40; k = 1.0 gives 20, 30, 40. The negative side detects 75 percent of those spoof runs (it cannot see `spoof_attempt`, see below). Selected by the rule: k = 0.25, h = 4. The same sweep on a box that is 15 percent off in time constant, wall resistance and cooling capacity gives 30 to 75 false CUSUM alarms per 1000 hours for every setting (the full table is in the evaluation file).

**Final scoring (test seeds, 200 runs per family).**

| Tamper family | Detected | Still flagged at the end | Delay median / p90 |
|---|---:|---:|---:|
| spoof_attempt (hold) | 100% | 100% | 10 / 10 min (1 sample) |
| hidden_spoilage (hold) | 100% | 100% | 10 / 10 min |
| injected_offset (6 to 12 C) | 100% | 100% | 10 / 10 min |
| injected_offset_small (1.5 to 3 C) | 100% | 100% | 0 / 60 min |
| injected_replay | 100% | 100% | 10 / 10 min |

| Physical family | Anomaly detected | Correct class | Tamper verdicts | Delay median |
|---|---:|---:|---:|---:|
| door_open_excursion | 100% | 100% | 0 | 7 min |
| reefer_failure | 100% | 100% | 0 | 9 min |
| heatwave_transit | 100% | 100% | 0 | 11 min |

| Clean family | Runs with a tamper verdict | Glitch verdicts |
|---|---:|---:|
| baseline_ok | 1 of 200 | 0 |
| shock_drop | 0 of 200 | 0 |
| freeze_event | 1 of 200 | 0 |
| sensor_glitch | 2 of 200 | 200 of 200 |

False tamper verdicts on the clean and physical families, nominal box: 3 of 700 runs in the first 100 seeds (0.11 per 1000 hours). The control family (a value held at the true temperature, 5.0 C): 200 of 200 runs flagged as tamper, 99 also as a thermal anomaly.

Per detector, at or after the divergence (share of runs, median minutes): `impossible_step` 100 percent at 0 min in four families and 33 percent for small offsets; `cusum_neg` 100 percent at 10 to 20 min for hidden_spoilage, offsets and replay but 0 percent for `spoof_attempt`; `impossible_state` 100 percent at 20 min for hidden_spoilage and replay, 24 percent for large offsets, 0 percent for spoof_attempt and small offsets; `flat_line` 0 percent everywhere.

**Mismatch (the real box differs from the calibration; 100 runs per family).**

| Real box | Tamper detection | Median delay | False tamper verdicts (of 700) | Per 1000 h | Physical correct class |
|---|---:|---:|---:|---:|---:|
| nominal | 100% | 10 min | 3 | 0.11 | 100% |
| time constant, wall resistance and cooling capacity +15% | 100% | 0 min | 700 | 33.11 | 0% |
| same, -15% | 94% | 10 min | 100 (all `freeze_event`) | 4.17 | 100% |
| ambient sensor noise doubled | 100% | 10 min | 3 | 0.11 | 100% |

## 11. Limitations, written plainly

- **Shared equations.** The twin and the simulator use the same family of equations. The good numbers on the matched box prove the code works; they do not show how a real box would behave. The mismatch runs are the more honest result, and they are poor: a +15 percent change in three box parameters (which makes the cooling depression 32 percent larger) causes false tamper verdicts in every run, because the real box is then consistently colder than the twin predicts. A -15 percent change affects only `freeze_event` (the passive cooling-down speed). No setting of the CUSUM survives this; the twin must be calibrated to the real box it is used with.
- **Honest channels.** The ambient and duty channels are assumed honest. An attacker who also falsifies them is not caught by this.
- **Onset dependence.** The 10 minute delay comes from the jump at the start of a lie. After the jump, `spoof_attempt` (a value held at 5 C with a 30 C cargo area) is physically consistent with a weakened cooling unit and is caught only by that onset jump. The simulator has no slowly drifting lie, and I did not add one; such a lie would be harder.
- **Tuned allowances.** The heat allowance (60 K) matches the simulator's door heat range. A bigger real heat load would be mislabelled.
- **Flat line.** It detects only exact freezes; every simulated lie carries sensor noise.
- **Harmless lies are flagged.** A sensor held at the true value is flagged in every run, because it stops responding to the compressor cycling. The detector finds inconsistency with the physics, not harm to the medicine.
- **No humidity or shock physics.** Only temperature is modelled.
- **Selection of k and h.** The sweep could not separate the settings on false alarms (all zero), so the choice rests on delay alone. The chosen setting is the most sensitive in the grid and one false alarm per 700 runs appears in the nominal test.

## 12. Open questions for the decision-maker

1. The mismatch result: the monitor needs a per-box calibration. Is that acceptable for the pitch (calibrate once per box type), or should we add a self-checking step (for example a verdict of "twin out of date" when the CUSUM stays high on both sides in clean conditions)?
2. Should the CUSUM be less sensitive (k = 1, h = 12) for robustness? It would not fix the +15 percent case, and it slows detection of small drifts.
3. The control family shows that a lie that is harmless in potency terms is still flagged. Is that the story we want ("inconsistent with physics") or should the verdict also say how much the potency number could be off?
4. The heat allowance of 60 K equals the simulator's door heat. Keep as a design allowance, or derive it from a stated maximum door-open power in the config?
5. Should a tamper verdict feed the potency tracker (for example mark the potency as untrusted from the verdict time), and where does that live (Phase 4 or 5)?
6. Add a slowly drifting spoof mode to the simulator so that stealthy lies are tested?
7. Is the new cooling-duty channel (a compressor relay signal) acceptable as a hardware assumption for the Pi phase?

## 13. Suggested next phase

Phase 4 (Ed25519 signing, hash chain, `verify_chain`, sensor-source switch). The signed record fields should now include the two new channels and the monitor's verdict. A short follow-up on question 1 (twin out-of-date detection) would make the physics claim more defensible. Not started.
