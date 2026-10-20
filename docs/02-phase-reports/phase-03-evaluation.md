# Phase 3: Detector evaluation

Measured with the real simulator, the real monitor and the stored calibration. Simulation result on a synthetic box. Not real-world evidence.

## Seed blocks (disjoint)

- calibration: seeds 9001 to 9010 (fit the twin only)
- training: seeds 10001 to 10100 (100 per family; used only for the sweep below)
- test: seeds 20001 to 20200 (200 per family; final scoring)
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
| injected_offset | 0% / n/a | 100% / 20 | 100% / 0 | 24% / 30 | 0% / n/a |
| injected_offset_small | 0% / n/a | 100% / 0 | 33% / 0 | 0% / n/a | 0% / n/a |
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
| baseline_ok | 200 | 1 | 1 | 0 | 0 |
| shock_drop | 200 | 0 | 0 | 0 | 0 |
| sensor_glitch | 200 | 2 | 2 | 200 | 0 |
| freeze_event | 200 | 1 | 1 | 0 | 0 |
| harmless_hold | 200 | 200 | 200 | 0 | 99 |

## Mismatch: the real box differs from the calibration

The twin stays calibrated on the nominal box. 'False tamper' counts tamper verdicts on the clean and physical families (the control family is reported in the table above).

| real box | tamper detection (mean) | median delay (min) | false tamper verdicts | false tamper episodes / 1000 h | physical correct class |
|---|---:|---:|---:|---:|---:|
| nominal | 100% | 10 | 3 | 0.11 | 100% |
| tau, R_th and capacity +15% | 100% | 0 | 700 | 33.11 | 0% |
| tau, R_th and capacity -15% | 94% | 10 | 100 | 4.17 | 100% |
| ambient sensor noise x2 | 100% | 10 | 3 | 0.11 | 100% |

False tamper verdicts by family (runs with a tamper verdict, out of the runs per family):

| real box | baseline_ok | shock_drop | sensor_glitch | freeze_event | door_open_excursion | reefer_failure | heatwave_transit |
|---|---:|---:|---:|---:|---:|---:|---:|
| nominal | 1 | 0 | 1 | 1 | 0 | 0 | 0 |
| tau, R_th and capacity +15% | 100 | 100 | 100 | 100 | 100 | 100 | 100 |
| tau, R_th and capacity -15% | 0 | 0 | 0 | 100 | 0 | 0 | 0 |
| ambient sensor noise x2 | 1 | 0 | 1 | 1 | 0 | 0 | 0 |

*Simulation result on a synthetic box. Not real-world evidence.*
