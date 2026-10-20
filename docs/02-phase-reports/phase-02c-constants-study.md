# Phase 2C: Product-constants study

## What this is

The potency model has a few made-up product constants: how fast damage grows with temperature (Ea/R) and how long the shelf life is (tau_max). With the values used before Phase 2D (set A, now the reference profile) even the worst golden recording leaves potency near 99 percent, so a pitch has little to show. This study re-runs the same golden recordings (eight when the study was made; Phase 2D added hidden_spoilage) through the same tracker with five illustrative sets of constants and prints what each would show. Nothing in the real configuration was changed. Every candidate value is a placeholder, not sourced [SOURCE NEEDED], and none describes a real product. T_ref (5 C) and P_min (0.90) are the same in all sets.

## How to read the tables

- *rep* is the result from the reported readings (what the box would see); *true* is from the true temperature in the ground-truth file.
- *used %* is the share of the shelf life spent. Potency reaches P_min exactly when it hits 100 percent.
- *extra days lost* is the shelf life lost beyond normal ageing in the same time at the reference temperature: (tau_eq - trip hours) / 24. Negative means the trip was colder than the reference.
- *< P_min* says whether potency fell below the minimum and, if so, the simulated hour.
- *status rep (excl.)* is the final tracker status on the reported series and the number of excluded samples.

Sets: **A** = Ea/R 10000, tau_max 17520 h (the team-document values, now the reference profile); **B** = Ea/R 15000, tau_max 17520 h; **C** = Ea/R 15000, tau_max 8760 h (chosen as the active profile in Phase 2D); **D** = Ea/R 20000, tau_max 8760 h; **E** = Ea/R 15000, tau_max 4380 h

## Set A: Ea/R 10000, tau_max 17520 h

| scenario | used % rep | used % true | potency % rep | potency % true | extra days lost rep | extra days lost true | < P_min rep | < P_min true | status rep (excl.) |
|---|---:|---:|---:|---:|---:|---:|---|---|---|
| baseline_ok | 0.274 | 0.274 | 99.971 | 99.971 | 0.00 | 0.00 | no | no | ok (0) |
| door_open_excursion | 0.201 | 0.202 | 99.979 | 99.979 | 0.47 | 0.47 | no | no | ok (0) |
| freeze_event | 0.098 | 0.098 | 99.990 | 99.990 | -0.78 | -0.78 | no | no | excursion_confirmed (0) |
| heatwave_transit | 2.741 | 2.740 | 99.712 | 99.712 | 17.01 | 17.00 | no | no | ok (0) |
| hidden_spoilage | 0.564 | 16.949 | 99.941 | 98.230 | 0.12 | 119.73 | no | no | ok (0) |
| reefer_failure | 8.881 | 8.877 | 99.069 | 99.069 | 63.33 | 63.30 | no | no | excursion_confirmed (0) |
| sensor_glitch | 0.137 | 0.137 | 99.986 | 99.986 | 0.00 | 0.00 | no | no | ok (1) |
| shock_drop | 0.137 | 0.137 | 99.986 | 99.986 | 0.00 | 0.00 | no | no | ok (0) |
| spoof_attempt | 0.258 | 1.952 | 99.973 | 99.795 | 0.38 | 12.75 | no | no | ok (0) |

- One day at 25 C costs 11.15 days of shelf life; one day at 40 C costs 55.60 days.
- It takes 13.1 days at 40 C to use all of the shelf life.
- Spoof scenario, hidden loss (true minus reported): 1.694 percentage points of shelf life, 0.178 potency percentage points, 12.36 days.

*Simulation result on a synthetic box, with illustrative constants. Not real-world evidence.*

## Set B: Ea/R 15000, tau_max 17520 h

| scenario | used % rep | used % true | potency % rep | potency % true | extra days lost rep | extra days lost true | < P_min rep | < P_min true | status rep (excl.) |
|---|---:|---:|---:|---:|---:|---:|---|---|---|
| baseline_ok | 0.275 | 0.275 | 99.971 | 99.971 | 0.00 | 0.01 | no | no | ok (0) |
| door_open_excursion | 0.281 | 0.281 | 99.970 | 99.970 | 1.05 | 1.05 | no | no | ok (0) |
| freeze_event | 0.087 | 0.087 | 99.991 | 99.991 | -0.87 | -0.87 | no | no | excursion_confirmed (0) |
| heatwave_transit | 9.511 | 9.502 | 99.003 | 99.004 | 66.43 | 66.37 | no | no | ok (0) |
| hidden_spoilage | 0.616 | 107.037 | 99.935 | 89.335 | 0.50 | 777.37 | no | yes @ 91.8 h | ok (0) |
| reefer_failure | 81.899 | 81.849 | 91.733 | 91.738 | 596.37 | 596.00 | no | no | excursion_confirmed (0) |
| sensor_glitch | 0.137 | 0.137 | 99.986 | 99.986 | 0.00 | 0.00 | no | no | ok (1) |
| shock_drop | 0.137 | 0.137 | 99.986 | 99.986 | 0.00 | 0.00 | no | no | ok (0) |
| spoof_attempt | 0.323 | 7.204 | 99.966 | 99.244 | 0.86 | 51.09 | no | no | ok (0) |

- One day at 25 C costs 37.24 days of shelf life; one day at 40 C costs 414.62 days.
- It takes 1.8 days at 40 C to use all of the shelf life.
- Spoof scenario, hidden loss (true minus reported): 6.881 percentage points of shelf life, 0.722 potency percentage points, 50.23 days.

*Simulation result on a synthetic box, with illustrative constants. Not real-world evidence.*

## Set C: Ea/R 15000, tau_max 8760 h

| scenario | used % rep | used % true | potency % rep | potency % true | extra days lost rep | extra days lost true | < P_min rep | < P_min true | status rep (excl.) |
|---|---:|---:|---:|---:|---:|---:|---|---|---|
| baseline_ok | 0.549 | 0.549 | 99.942 | 99.942 | 0.00 | 0.01 | no | no | ok (0) |
| door_open_excursion | 0.562 | 0.563 | 99.941 | 99.941 | 1.05 | 1.05 | no | no | ok (0) |
| freeze_event | 0.173 | 0.173 | 99.982 | 99.982 | -0.87 | -0.87 | no | no | excursion_confirmed (0) |
| heatwave_transit | 19.022 | 19.004 | 98.016 | 98.018 | 66.43 | 66.37 | no | no | ok (0) |
| hidden_spoilage | 1.232 | 214.075 | 99.870 | 79.808 | 0.50 | 777.37 | no | yes @ 61.0 h | ok (0) |
| reefer_failure | 163.799 | 163.698 | 84.149 | 84.158 | 596.37 | 596.00 | yes @ 31.7 h | yes @ 31.7 h | excursion_confirmed (0) |
| sensor_glitch | 0.275 | 0.274 | 99.971 | 99.971 | 0.00 | 0.00 | no | no | ok (1) |
| shock_drop | 0.274 | 0.274 | 99.971 | 99.971 | 0.00 | 0.00 | no | no | ok (0) |
| spoof_attempt | 0.646 | 14.408 | 99.932 | 98.493 | 0.86 | 51.09 | no | no | ok (0) |

- One day at 25 C costs 37.24 days of shelf life; one day at 40 C costs 414.62 days.
- It takes 0.9 days at 40 C to use all of the shelf life.
- Spoof scenario, hidden loss (true minus reported): 13.761 percentage points of shelf life, 1.438 potency percentage points, 50.23 days.

*Simulation result on a synthetic box, with illustrative constants. Not real-world evidence.*

## Set D: Ea/R 20000, tau_max 8760 h

| scenario | used % rep | used % true | potency % rep | potency % true | extra days lost rep | extra days lost true | < P_min rep | < P_min true | status rep (excl.) |
|---|---:|---:|---:|---:|---:|---:|---|---|---|
| baseline_ok | 0.550 | 0.550 | 99.942 | 99.942 | 0.01 | 0.01 | no | no | ok (0) |
| door_open_excursion | 0.874 | 0.876 | 99.908 | 99.908 | 2.19 | 2.20 | no | no | ok (0) |
| freeze_event | 0.163 | 0.163 | 99.983 | 99.983 | -0.91 | -0.91 | no | no | excursion_confirmed (0) |
| heatwave_transit | 71.240 | 71.145 | 92.769 | 92.778 | 257.03 | 256.68 | no | no | ok (0) |
| hidden_spoilage | 1.485 | 1370.621 | 99.844 | 23.596 | 1.42 | 4998.77 | no | yes @ 34.8 h | ok (0) |
| reefer_failure | 1586.877 | 1585.655 | 18.788 | 18.812 | 5790.60 | 5786.14 | yes @ 22.8 h | yes @ 22.8 h | excursion_confirmed (0) |
| sensor_glitch | 0.275 | 0.274 | 99.971 | 99.971 | 0.00 | 0.00 | no | no | ok (1) |
| shock_drop | 0.274 | 0.275 | 99.971 | 99.971 | 0.00 | 0.00 | no | no | ok (0) |
| spoof_attempt | 0.901 | 55.233 | 99.905 | 94.347 | 1.79 | 200.10 | no | no | ok (0) |

- One day at 25 C costs 124.38 days of shelf life; one day at 40 C costs 3091.75 days.
- It takes 0.1 days at 40 C to use all of the shelf life.
- Spoof scenario, hidden loss (true minus reported): 54.332 percentage points of shelf life, 5.558 potency percentage points, 198.31 days.

*Simulation result on a synthetic box, with illustrative constants. Not real-world evidence.*

## Set E: Ea/R 15000, tau_max 4380 h

| scenario | used % rep | used % true | potency % rep | potency % true | extra days lost rep | extra days lost true | < P_min rep | < P_min true | status rep (excl.) |
|---|---:|---:|---:|---:|---:|---:|---|---|---|
| baseline_ok | 1.098 | 1.099 | 99.884 | 99.884 | 0.00 | 0.01 | no | no | ok (0) |
| door_open_excursion | 1.123 | 1.125 | 99.882 | 99.882 | 1.05 | 1.05 | no | no | ok (0) |
| freeze_event | 0.347 | 0.347 | 99.963 | 99.963 | -0.87 | -0.87 | no | no | excursion_confirmed (0) |
| heatwave_transit | 38.045 | 38.009 | 96.071 | 96.074 | 66.43 | 66.37 | no | no | ok (0) |
| hidden_spoilage | 2.465 | 428.150 | 99.741 | 63.693 | 0.50 | 777.37 | no | yes @ 45.3 h | ok (0) |
| reefer_failure | 327.598 | 327.396 | 70.811 | 70.826 | 596.37 | 596.00 | yes @ 27.5 h | yes @ 27.5 h | excursion_confirmed (0) |
| sensor_glitch | 0.550 | 0.548 | 99.942 | 99.942 | 0.00 | 0.00 | no | no | ok (1) |
| shock_drop | 0.548 | 0.549 | 99.942 | 99.942 | 0.00 | 0.00 | no | no | ok (0) |
| spoof_attempt | 1.293 | 28.816 | 99.864 | 97.010 | 0.86 | 51.09 | no | no | ok (0) |

- One day at 25 C costs 37.24 days of shelf life; one day at 40 C costs 414.62 days.
- It takes 0.4 days at 40 C to use all of the shelf life.
- Spoof scenario, hidden loss (true minus reported): 27.523 percentage points of shelf life, 2.854 potency percentage points, 50.23 days.

*Simulation result on a synthetic box, with illustrative constants. Not real-world evidence.*

