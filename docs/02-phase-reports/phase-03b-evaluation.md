# Phase 3B: Detector evaluation (Phase 3 tables re-measured, then the Phase 3B additions)

Measured with the real simulator, the real monitor and the stored calibration. Simulation result on a synthetic box. Not real-world evidence.

## Seed blocks (disjoint)

- calibration: seeds 9001 to 9010 (fit the twin only)
- training: seeds 10001 to 10100 (100 per family; used only for the sweep below)
- test: seeds 40001 to 40200 (200 per family; final scoring)
- mismatch runs: the first 100 test seeds per family

## CUSUM sweep (training seeds)

False alarms are CUSUM alarm episodes (either side) on the clean families baseline_ok, shock_drop, sensor_glitch and freeze_event, per 1000 simulated hours. Delay is the median time from the first divergence to the negative-side CUSUM alarm on the spoof families (spoof_attempt, hidden_spoilage, injected offset, injected replay).

| k | h | false alarms / 1000 h | CUSUM-neg detection | CUSUM-neg median delay (min) | false alarms / 1000 h on a +15% box | on a -15% box |
|---:|---:|---:|---:|---:|---:|---:|
| 0.25 | 4.0 | 0.00 | 75% | 10.0 | 75.0 | 67.4 |
| 0.25 | 8.0 | 0.00 | 75% | 30.0 | 64.6 | 57.1 |
| 0.25 | 12.0 | 0.00 | 75% | 40.0 | 66.7 | 63.6 |
| 0.5 | 4.0 | 0.00 | 75% | 20.0 | 71.5 | 63.1 |
| 0.5 | 8.0 | 0.00 | 75% | 30.0 | 45.5 | 42.4 |
| 0.5 | 12.0 | 0.00 | 75% | 40.0 | 33.6 | 32.1 |
| 1.0 | 4.0 | 0.00 | 75% | 20.0 | 37.4 | 43.9 |
| 1.0 | 8.0 | 0.00 | 75% | 30.0 | 35.6 | 34.6 |
| 1.0 | 12.0 | 0.00 | 75% | 40.0 | 34.1 | 30.3 |

Selection rule: keep the settings whose false alarms are at most 1.0 per 1000 h, then take the smallest median delay (ties: fewer false alarms, then the larger h). The rule selects k = 0.25, h = 4.0. The settings in config/detectors.yaml are k = 0.25, h = 4.0.

## Final scoring (test seeds)

Tamper families. Detection = a falsification verdict at or after the first divergence (the first sample where the reported temperature is more than the configured divergence threshold from the truth). Delay is measured from that divergence.

| family | runs | detected | still flagged at the end | delay median (min / samples) | delay p90 (min / samples) |
|---|---:|---:|---:|---:|---:|
| spoof_attempt | 200 | 100% | 100% | 10 / 1.0 | 10 / 1.0 |
| hidden_spoilage | 200 | 100% | 100% | 10 / 1.0 | 10 / 1.0 |
| injected_offset | 200 | 100% | 100% | 10 / 1.0 | 10 / 1.0 |
| injected_offset_small | 200 | 100% | 100% | 0 / 0.0 | 60 / 6.0 |
| injected_replay | 200 | 100% | 100% | 10 / 1.0 | 10 / 1.0 |

Per detector on the tamper families (share of runs flagged at or after the divergence, and median delay in minutes):

| family | cusum_pos | cusum_neg | impossible_step | impossible_state | flat_line |
|---|---:|---:|---:|---:|---:|
| spoof_attempt | 100% / 0 | 0% / n/a | 100% / 0 | 0% / n/a | 0% / n/a |
| hidden_spoilage | 100% / 0 | 100% / 20 | 100% / 0 | 100% / 20 | 0% / n/a |
| injected_offset | 0% / n/a | 100% / 20 | 100% / 0 | 27% / 30 | 0% / n/a |
| injected_offset_small | 0% / n/a | 100% / 0 | 40% / 0 | 0% / n/a | 0% / n/a |
| injected_replay | 100% / 0 | 100% / 10 | 100% / 0 | 100% / 20 | 0% / n/a |

Physical families (the correct verdict is thermal anomaly, not tamper). Detection = a thermal-anomaly verdict after the physical event starts; correct class = anomaly seen and no tamper verdict at any time.

| family | runs | anomaly detected | correct class | delay median (min) | tamper verdicts (runs) |
|---|---:|---:|---:|---:|---:|
| door_open_excursion | 200 | 100% | 100% | 7 | 0 |
| reefer_failure | 200 | 100% | 100% | 9 | 0 |
| heatwave_transit | 200 | 100% | 100% | 11 | 0 |

Clean and control families (any tamper verdict is a false positive).

| family | runs | tamper verdicts (runs) | tamper episodes | glitch verdicts (runs) | anomaly verdicts (runs) |
|---|---:|---:|---:|---:|---:|
| baseline_ok | 200 | 1 | 1 | 0 | 1 |
| shock_drop | 200 | 0 | 0 | 0 | 0 |
| sensor_glitch | 200 | 0 | 0 | 200 | 0 |
| freeze_event | 200 | 0 | 0 | 0 | 0 |
| harmless_hold | 200 | 200 | 200 | 0 | 99 |

## Mismatch: the real box differs from the calibration

The twin stays calibrated on the nominal box. 'False tamper' counts tamper verdicts on the clean and physical families (the control family is reported in the table above).

| real box | tamper detection (mean) | median delay (min) | false tamper verdicts | false tamper episodes / 1000 h | physical correct class |
|---|---:|---:|---:|---:|---:|
| nominal | 100% | 10 | 0 | 0.00 | 100% |
| tau, R_th and capacity +15% | 95% | 10 | 700 | 35.68 | 0% |
| tau, R_th and capacity -15% | 84% | 10 | 100 | 4.39 | 100% |
| ambient sensor noise x2 | 100% | 10 | 0 | 0.00 | 100% |

False tamper verdicts by family (runs with a tamper verdict, out of the runs per family):

| real box | baseline_ok | shock_drop | sensor_glitch | freeze_event | door_open_excursion | reefer_failure | heatwave_transit |
|---|---:|---:|---:|---:|---:|---:|---:|
| nominal | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| tau, R_th and capacity +15% | 100 | 100 | 100 | 100 | 100 | 100 | 100 |
| tau, R_th and capacity -15% | 0 | 0 | 0 | 100 | 0 | 0 | 0 |
| ambient sensor noise x2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Seed ledger

| block | seeds | what it was used for | status |
|---|---|---|---|
| calibration | 9001 to 9010 | fit the twin | calibration only |
| training | 10001 to 10100 | chose CUSUM settings and the out-of-date settings | tuning |
| development | 20001 to 20200 | scored the first Phase 3B build; seed 20090 showed a bound violation | diagnosis (no longer unseen) |
| validity (development) | 30001 to 30200 | validated the first bound-start repair (both statistics quiet) | diagnosis (no longer unseen) |
| final | 40001 to 40200 | scores the episode-latched bound start; mismatch runs use the first 100 | final scoring, used once |

The final numbers below come from the final block (40001 to 40200; mismatch runs use its first 100). The development blocks are reported only for comparison.

## Phase 3B: the twin-out-of-date self-check, threshold sweep (training seeds)

Tuned on the training seeds only. 'False out-of-date' is the share of NOMINAL-box clean and physical runs (7 families) in which the verdict twin_out_of_date appeared at any time. 'Worst lie loss' is the largest drop in detection rate, over the nominal lie families spoof_attempt, hidden_spoilage, injected_offset, injected_offset_small, injected_replay, injected_drift_0.5_clean, injected_drift_1_fault, compared with the self-check switched off. The +15% and -15% columns are the share of clean and physical runs on a box whose tau, R_th and capacity differ by that much in which twin_out_of_date appeared, and the share that END with a tamper verdict.

| window | margin | sustained | false out-of-date (nominal) | worst lie loss | +15% out-of-date | +15% ends tamper | -15% out-of-date | -15% ends tamper |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 36 | 0.06 | 6 | 20% | 0% | 85% | 31% | 60% | 0% |
| 36 | 0.06 | 12 | 10% | 0% | 82% | 30% | 54% | 0% |
| 36 | 0.06 | 24 | 2% | 0% | 68% | 28% | 35% | 0% |
| 36 | 0.08 | 6 | 5% | 0% | 85% | 32% | 60% | 0% |
| 36 | 0.08 | 12 | 2% | 0% | 81% | 30% | 53% | 0% |
| 36 | 0.08 | 24 | 0% | 0% | 66% | 29% | 34% | 0% |
| 36 | 0.1 | 6 | 1% | 0% | 84% | 34% | 60% | 0% |
| 36 | 0.1 | 12 | 0% | 0% | 79% | 34% | 51% | 0% |
| 36 | 0.1 | 24 | 0% | 0% | 59% | 35% | 32% | 0% |
| 72 | 0.06 | 6 | 4% | 0% | 76% | 19% | 62% | 0% |
| 72 | 0.06 | 12 | 2% | 0% | 74% | 19% | 57% | 0% |
| 72 | 0.06 | 24 | 1% | 0% | 60% | 30% | 49% | 0% |
| 72 | 0.08 | 6 | 1% | 0% | 74% | 20% | 60% | 0% |
| 72 | 0.08 | 12 | 0% | 0% | 72% | 20% | 56% | 0% |
| 72 | 0.08 | 24 | 0% | 0% | 60% | 30% | 46% | 0% |
| 72 | 0.1 | 6 | 0% | 0% | 72% | 22% | 57% | 0% |
| 72 | 0.1 | 12 | 0% | 0% | 71% | 22% | 53% | 0% |
| 72 | 0.1 | 24 | 0% | 0% | 58% | 32% | 43% | 0% |
| 144 | 0.06 | 6 | 0% | 0% | 35% | 61% | 31% | 0% |
| 144 | 0.06 | 12 | 0% | 0% | 26% | 61% | 22% | 0% |
| 144 | 0.06 | 24 | 0% | 0% | 17% | 62% | 16% | 0% |
| 144 | 0.08 | 6 | 0% | 0% | 32% | 61% | 27% | 0% |
| 144 | 0.08 | 12 | 0% | 0% | 25% | 61% | 20% | 0% |
| 144 | 0.08 | 24 | 0% | 0% | 15% | 62% | 15% | 0% |
| 144 | 0.1 | 6 | 0% | 0% | 30% | 61% | 25% | 0% |
| 144 | 0.1 | 12 | 0% | 0% | 24% | 61% | 19% | 0% |
| 144 | 0.1 | 24 | 0% | 0% | 15% | 62% | 15% | 0% |

Selection rule: keep the settings whose nominal false out-of-date share is at most 2% and whose worst lie loss is at most 1%; then take the smallest mean share of +/-15% runs that end with a tamper verdict (to the nearest percentage point), then the largest mean out-of-date share (ties: smaller window, larger margin, smaller sustained count). The rule selects window = 72, margin = 0.08, sustained = 6. The settings in config/detectors.yaml are window = 72, margin = 0.08, sustained = 6.

## Phase 3B: lie families (test seeds)

Drift lies grow linearly from the start at the stated rate (kelvin per hour); the mimic is an attacker with a model of the box and is EXPECTED to be invisible to physics. 'Detected' = a falsification verdict at or after the first divergence. 'Flagged untrusted' = the monitor declared the data untrusted (falsification or twin out of date). Delay is from the first divergence (minutes / samples).

| family | runs | detected | flagged untrusted | ends as | delay median | delay p90 |
|---|---:|---:|---:|---|---:|---:|
| injected_drift_0.25_clean | 200 | 100% | 100% | 200 suspected_falsification | 0 / 0.0 | 0 / 0.0 |
| injected_drift_0.25_fault | 200 | 0% | 0% | 200 thermal_anomaly | n/a / n/a | n/a / n/a |
| injected_drift_0.5_clean | 200 | 100% | 100% | 200 suspected_falsification | 0 / 0.0 | 0 / 0.0 |
| injected_drift_0.5_fault | 200 | 0% | 0% | 200 thermal_anomaly | n/a / n/a | n/a / n/a |
| injected_drift_1_clean | 200 | 100% | 100% | 199 suspected_falsification, 1 twin_out_of_date | 0 / 0.0 | 0 / 0.0 |
| injected_drift_1_fault | 200 | 0% | 0% | 200 thermal_anomaly | n/a / n/a | n/a / n/a |
| injected_drift_2_clean | 200 | 100% | 100% | 200 suspected_falsification | 0 / 0.0 | 0 / 0.0 |
| injected_drift_2_fault | 200 | 100% | 100% | 200 suspected_falsification | 590 / 59.0 | 600 / 60.0 |
| injected_mimic_at_failure | 200 | 0% | 1% | 200 thermal_anomaly | n/a / n/a | n/a / n/a |
| injected_mimic_late | 200 | 0% | 0% | 200 ok | n/a / n/a | n/a / n/a |

## Phase 3B: mismatch, with the new verdict space

Clean and physical families on boxes that differ from the calibration (first 100 test seeds per family). 'Any tamper' = a tamper verdict at any time; 'ends tamper' = the last verdict is a tamper verdict; 'out of date' = twin_out_of_date appeared; 'from start' = already out of date in the first window.

| real box | runs | any tamper | ends tamper | out of date | ends out of date | out of date from start | untrusted |
|---|---:|---:|---:|---:|---:|---:|---:|
| nominal | 700 | 0 | 0 | 7 | 0 | 0 | 7 |
| tau, R_th and capacity +15% | 700 | 700 | 132 | 529 | 399 | 363 | 700 |
| tau, R_th and capacity -15% | 700 | 100 | 0 | 424 | 333 | 255 | 480 |
| ambient sensor noise x2 | 700 | 0 | 0 | 7 | 0 | 0 | 7 |

Runs that END with a tamper verdict, by family:

| real box | baseline_ok | shock_drop | sensor_glitch | freeze_event | door_open_excursion | reefer_failure | heatwave_transit |
|---|---:|---:|---:|---:|---:|---:|---:|
| nominal | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| tau, R_th and capacity +15% | 1 | 0 | 0 | 31 | 0 | 0 | 100 |
| tau, R_th and capacity -15% | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| ambient sensor noise x2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Phase 3B: before and after (same test seeds)

'Before' is the Phase 3 behaviour (the same code with the self-check switched off). Detection and delay are for the five Phase 3 lie families.

| family | detected before | detected after | delay median before (min) | delay median after (min) | delay p90 before | delay p90 after |
|---|---:|---:|---:|---:|---:|---:|
| spoof_attempt | 100% | 100% | 10 | 10 | 10 | 10 |
| hidden_spoilage | 100% | 100% | 10 | 10 | 10 | 10 |
| injected_offset | 100% | 100% | 10 | 10 | 10 | 10 |
| injected_offset_small | 100% | 100% | 0 | 0 | 60 | 60 |
| injected_replay | 100% | 100% | 10 | 10 | 10 | 10 |

| measure (nominal box, test seeds) | before | after |
|---|---:|---:|
| clean + physical runs with a tamper verdict | 1 | 1 |
| clean + physical tamper episodes | 1 | 1 |
| control (harmless_hold) runs with a tamper verdict | 200 | 200 |
| clean + physical runs that went twin_out_of_date | 0 | 10 |

| real box | any tamper before | any tamper after | ends tamper before | ends tamper after |
|---|---:|---:|---:|---:|
| nominal | 0 | 0 | 0 | 0 |
| tau, R_th and capacity +15% | 700 | 700 | 531 | 132 |
| tau, R_th and capacity -15% | 100 | 100 | 0 | 0 |
| ambient sensor noise x2 | 0 | 0 | 0 | 0 |

## Phase 3B: the worst-case bound

For every run the monitor declared untrusted, the bound on the equivalent reference time accumulated from t0 to the end was compared with the TRUE value (the true temperature series fed to the potency maths, in the scoring code only). 'Valid' = bound >= true. Ratio = bound / true.

| family | runs | untrusted | bound computed | valid | ratio median | ratio p90 | ratio max |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline_ok | 200 | 3 | 1 | 1 | 15.91 | 15.91 | 15.91 |
| spoof_attempt | 200 | 200 | 200 | 200 | 1.35 | 1.47 | 1.57 |
| hidden_spoilage | 200 | 200 | 200 | 200 | 4.31 | 5.56 | 6.22 |
| injected_offset | 200 | 200 | 200 | 200 | 18.47 | 27.68 | 33.02 |
| injected_offset_small | 200 | 200 | 199 | 199 | 18.44 | 26.99 | 33.02 |
| injected_replay | 200 | 200 | 200 | 200 | 1.15 | 1.24 | 1.35 |
| harmless_hold | 200 | 200 | 199 | 199 | 18.44 | 26.99 | 33.02 |
| injected_drift_0.25_clean | 200 | 200 | 199 | 199 | 18.44 | 26.99 | 33.02 |
| injected_drift_0.5_clean | 200 | 200 | 199 | 199 | 18.40 | 26.99 | 33.02 |
| injected_drift_1_clean | 200 | 200 | 200 | 200 | 18.47 | 27.68 | 33.02 |
| injected_drift_2_clean | 200 | 200 | 200 | 200 | 18.47 | 27.68 | 33.02 |
| injected_drift_2_fault | 200 | 200 | 200 | 200 | 1.15 | 1.24 | 1.35 |

## Phase 3B fix: bound validity, three places

### A. Nominal box, FINAL seeds (40001 to 40200)

| family | runs | level untrusted | bound computed | valid | ratio median | ratio p90 | ratio max |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline_ok | 200 | 1 | 1 | 1 | 15.91 | 15.91 | 15.91 |
| spoof_attempt | 200 | 200 | 200 | 200 | 1.35 | 1.47 | 1.57 |
| hidden_spoilage | 200 | 200 | 200 | 200 | 4.31 | 5.56 | 6.22 |
| injected_offset | 200 | 200 | 200 | 200 | 18.47 | 27.68 | 33.02 |
| injected_offset_small | 200 | 199 | 199 | 199 | 18.44 | 26.99 | 33.02 |
| injected_replay | 200 | 200 | 200 | 200 | 1.15 | 1.24 | 1.35 |
| harmless_hold | 200 | 199 | 199 | 199 | 18.44 | 26.99 | 33.02 |
| injected_drift_0.25_clean | 200 | 199 | 199 | 199 | 18.44 | 26.99 | 33.02 |
| injected_drift_0.5_clean | 200 | 199 | 199 | 199 | 18.40 | 26.99 | 33.02 |
| injected_drift_1_clean | 200 | 200 | 200 | 200 | 18.47 | 27.68 | 33.02 |
| injected_drift_2_clean | 200 | 200 | 200 | 200 | 18.47 | 27.68 | 33.02 |
| injected_drift_2_fault | 200 | 200 | 200 | 200 | 1.15 | 1.24 | 1.35 |

Violations on the nominal box, final seeds: none.

### B. Nominal box, DEVELOPMENT seeds (20001 to 20200), for comparison

| family | runs | level untrusted | bound computed | valid | ratio median | ratio p90 | ratio max |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline_ok | 200 | 1 | 1 | 1 | 13.31 | 13.31 | 13.31 |
| sensor_glitch | 200 | 2 | 2 | 2 | 12.19 | 16.21 | 17.22 |
| freeze_event | 200 | 1 | 1 | 1 | 1.43 | 1.43 | 1.43 |
| spoof_attempt | 200 | 200 | 200 | 200 | 1.36 | 1.50 | 1.59 |
| hidden_spoilage | 200 | 200 | 200 | 200 | 4.39 | 5.55 | 6.09 |
| injected_offset | 200 | 200 | 200 | 200 | 18.98 | 28.68 | 33.04 |
| injected_offset_small | 200 | 200 | 200 | 200 | 18.98 | 28.68 | 33.04 |
| injected_replay | 200 | 200 | 200 | 200 | 1.15 | 1.27 | 1.33 |
| harmless_hold | 200 | 198 | 198 | 198 | 19.00 | 28.70 | 33.04 |
| injected_drift_0.25_clean | 200 | 200 | 200 | 200 | 18.98 | 28.68 | 33.04 |
| injected_drift_0.5_clean | 200 | 199 | 199 | 199 | 19.00 | 28.64 | 33.04 |
| injected_drift_1_clean | 200 | 200 | 200 | 200 | 18.98 | 28.68 | 33.04 |
| injected_drift_2_clean | 200 | 200 | 200 | 200 | 18.98 | 28.68 | 33.04 |
| injected_drift_2_fault | 200 | 200 | 200 | 200 | 1.15 | 1.27 | 1.33 |
| injected_mimic_late | 200 | 1 | 1 | 1 | 1.12 | 1.12 | 1.12 |

Violations on the development seeds: none.

### C. Mismatched box (tau, R_th and capacity +15%), lie families, first 100 final seeds

| family | runs | level untrusted | bound computed | valid | ratio median | ratio p90 | ratio max |
|---|---:|---:|---:|---:|---:|---:|---:|
| injected_drift_0.25_clean | 100 | 1 | 1 | 1 | 13.76 | 13.76 | 13.76 |
| injected_drift_0.25_fault | 100 | 100 | 100 | 100 | 1.40 | 1.52 | 1.62 |
| injected_drift_0.5_clean | 100 | 57 | 57 | 57 | 30.99 | 40.56 | 47.04 |
| injected_drift_0.5_fault | 100 | 100 | 100 | 100 | 1.40 | 1.52 | 1.62 |
| injected_drift_1_clean | 100 | 96 | 96 | 96 | 25.35 | 35.91 | 43.57 |
| injected_drift_1_fault | 100 | 100 | 100 | 100 | 1.40 | 1.52 | 1.62 |
| injected_drift_2_clean | 100 | 100 | 100 | 100 | 23.69 | 32.84 | 41.48 |
| injected_drift_2_fault | 100 | 100 | 100 | 100 | 1.40 | 1.52 | 1.62 |
| injected_mimic_at_failure | 100 | 17 | 17 | 17 | 1.44 | 1.55 | 5.62 |
| injected_mimic_late | 100 | 100 | 100 | 100 | 1.40 | 1.52 | 1.62 |

Bounds computed: 771; violations: 0.

### C. Mismatched box (tau, R_th and capacity -15%), lie families, first 100 final seeds

| family | runs | level untrusted | bound computed | valid | ratio median | ratio p90 | ratio max |
|---|---:|---:|---:|---:|---:|---:|---:|
| injected_drift_0.25_clean | 100 | 12 | 12 | 12 | 28.69 | 30.76 | 31.03 |
| injected_drift_0.5_clean | 100 | 60 | 60 | 60 | 23.87 | 29.76 | 31.87 |
| injected_drift_1_clean | 100 | 95 | 95 | 95 | 20.98 | 28.70 | 31.87 |
| injected_drift_2_clean | 100 | 100 | 100 | 100 | 20.96 | 28.69 | 31.87 |
| injected_drift_2_fault | 100 | 100 | 100 | 55 | 1.00 | 1.06 | 1.10 |

Bounds computed: 367; violations: 45 (reported as a limitation, not a stop).

### Trust levels of clean and physical runs on mismatched boxes

| real box | runs | trusted | low confidence | untrusted |
|---|---:|---:|---:|---:|
| nominal | 700 | 693 | 7 | 0 |
| tau, R_th and capacity +15% | 700 | 0 | 325 | 375 |
| tau, R_th and capacity -15% | 700 | 220 | 425 | 55 |
| ambient sensor noise x2 | 700 | 693 | 7 | 0 |

Simulation result on a synthetic box. Not real-world evidence.

*Simulation result on a synthetic box. Not real-world evidence.*
