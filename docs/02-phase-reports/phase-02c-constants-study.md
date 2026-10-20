# Phase 2C: Product-constants study

## What this is

The potency model has a few made-up product constants: how fast damage grows with temperature (Ea/R) and how long the shelf life is (tau_max). With the current values (set A) even the worst golden recording leaves potency near 99 percent, so a pitch has little to show. This study re-runs the same eight recordings through the same tracker with five illustrative sets of constants and prints what each would show. Nothing in the real configuration was changed. Every candidate value is a placeholder, not sourced [SOURCE NEEDED], and none describes a real product. T_ref (5 C) and P_min (0.90) are the same in all sets.

## How to read the tables

- *rep* is the result from the reported readings (what the box would see); *true* is from the true temperature in the ground-truth file.
- *used %* is the share of the shelf life spent. Potency reaches P_min exactly when it hits 100 percent.
- *extra days lost* is the shelf life lost beyond normal ageing in the same time at the reference temperature: (tau_eq - trip hours) / 24. Negative means the trip was colder than the reference.
- *< P_min* says whether potency fell below the minimum and, if so, the simulated hour.
- *status rep (excl.)* is the final tracker status on the reported series and the number of excluded samples.

Sets: **A** = Ea/R 10000, tau_max 17520 h (current configuration); **B** = Ea/R 15000, tau_max 17520 h; **C** = Ea/R 15000, tau_max 8760 h; **D** = Ea/R 20000, tau_max 8760 h; **E** = Ea/R 15000, tau_max 4380 h

## Set A: Ea/R 10000, tau_max 17520 h

| scenario | used % rep | used % true | potency % rep | potency % true | extra days lost rep | extra days lost true | < P_min rep | < P_min true | status rep (excl.) |
|---|---:|---:|---:|---:|---:|---:|---|---|---|
| baseline_ok | 0.274 | 0.274 | 99.971 | 99.971 | 0.00 | 0.00 | no | no | ok (0) |
| door_open_excursion | 0.201 | 0.202 | 99.979 | 99.979 | 0.47 | 0.47 | no | no | ok (0) |
| freeze_event | 0.098 | 0.098 | 99.990 | 99.990 | -0.78 | -0.78 | no | no | excursion_confirmed (0) |
| heatwave_transit | 2.741 | 2.740 | 99.712 | 99.712 | 17.01 | 17.00 | no | no | ok (0) |
| reefer_failure | 8.881 | 8.877 | 99.069 | 99.069 | 63.33 | 63.30 | no | no | excursion_confirmed (0) |
| sensor_glitch | 0.137 | 0.137 | 99.986 | 99.986 | 0.00 | 0.00 | no | no | ok (1) |
| shock_drop | 0.137 | 0.137 | 99.986 | 99.986 | 0.00 | 0.00 | no | no | ok (0) |
| spoof_attempt | 0.274 | 1.952 | 99.971 | 99.795 | 0.50 | 12.75 | no | no | ok (0) |

- One day at 25 C costs 11.15 days of shelf life; one day at 40 C costs 55.60 days.
- It takes 13.1 days at 40 C to use all of the shelf life.
- Spoof scenario, hidden loss (true minus reported): 1.678 percentage points of shelf life, 0.177 potency percentage points, 12.25 days.

*Simulation result on a synthetic box, with illustrative constants. Not real-world evidence.*

## Set B: Ea/R 15000, tau_max 17520 h

| scenario | used % rep | used % true | potency % rep | potency % true | extra days lost rep | extra days lost true | < P_min rep | < P_min true | status rep (excl.) |
|---|---:|---:|---:|---:|---:|---:|---|---|---|
| baseline_ok | 0.275 | 0.275 | 99.971 | 99.971 | 0.00 | 0.01 | no | no | ok (0) |
| door_open_excursion | 0.281 | 0.281 | 99.970 | 99.970 | 1.05 | 1.05 | no | no | ok (0) |
| freeze_event | 0.087 | 0.087 | 99.991 | 99.991 | -0.87 | -0.87 | no | no | excursion_confirmed (0) |
| heatwave_transit | 9.511 | 9.502 | 99.003 | 99.004 | 66.43 | 66.37 | no | no | ok (0) |
| reefer_failure | 81.899 | 81.849 | 91.733 | 91.738 | 596.37 | 596.00 | no | no | excursion_confirmed (0) |
| sensor_glitch | 0.137 | 0.137 | 99.986 | 99.986 | 0.00 | 0.00 | no | no | ok (1) |
| shock_drop | 0.137 | 0.137 | 99.986 | 99.986 | 0.00 | 0.00 | no | no | ok (0) |
| spoof_attempt | 0.395 | 7.204 | 99.958 | 99.244 | 1.38 | 51.09 | no | no | ok (0) |

- One day at 25 C costs 37.24 days of shelf life; one day at 40 C costs 414.62 days.
- It takes 1.8 days at 40 C to use all of the shelf life.
- Spoof scenario, hidden loss (true minus reported): 6.809 percentage points of shelf life, 0.715 potency percentage points, 49.70 days.

*Simulation result on a synthetic box, with illustrative constants. Not real-world evidence.*

## Set C: Ea/R 15000, tau_max 8760 h

| scenario | used % rep | used % true | potency % rep | potency % true | extra days lost rep | extra days lost true | < P_min rep | < P_min true | status rep (excl.) |
|---|---:|---:|---:|---:|---:|---:|---|---|---|
| baseline_ok | 0.549 | 0.549 | 99.942 | 99.942 | 0.00 | 0.01 | no | no | ok (0) |
| door_open_excursion | 0.562 | 0.563 | 99.941 | 99.941 | 1.05 | 1.05 | no | no | ok (0) |
| freeze_event | 0.173 | 0.173 | 99.982 | 99.982 | -0.87 | -0.87 | no | no | excursion_confirmed (0) |
| heatwave_transit | 19.022 | 19.004 | 98.016 | 98.018 | 66.43 | 66.37 | no | no | ok (0) |
| reefer_failure | 163.799 | 163.698 | 84.149 | 84.158 | 596.37 | 596.00 | yes @ 31.7 h | yes @ 31.7 h | excursion_confirmed (0) |
| sensor_glitch | 0.275 | 0.274 | 99.971 | 99.971 | 0.00 | 0.00 | no | no | ok (1) |
| shock_drop | 0.274 | 0.274 | 99.971 | 99.971 | 0.00 | 0.00 | no | no | ok (0) |
| spoof_attempt | 0.790 | 14.408 | 99.917 | 98.493 | 1.38 | 51.09 | no | no | ok (0) |

- One day at 25 C costs 37.24 days of shelf life; one day at 40 C costs 414.62 days.
- It takes 0.9 days at 40 C to use all of the shelf life.
- Spoof scenario, hidden loss (true minus reported): 13.617 percentage points of shelf life, 1.423 potency percentage points, 49.70 days.

*Simulation result on a synthetic box, with illustrative constants. Not real-world evidence.*

## Set D: Ea/R 20000, tau_max 8760 h

| scenario | used % rep | used % true | potency % rep | potency % true | extra days lost rep | extra days lost true | < P_min rep | < P_min true | status rep (excl.) |
|---|---:|---:|---:|---:|---:|---:|---|---|---|
| baseline_ok | 0.550 | 0.550 | 99.942 | 99.942 | 0.01 | 0.01 | no | no | ok (0) |
| door_open_excursion | 0.874 | 0.876 | 99.908 | 99.908 | 2.19 | 2.20 | no | no | ok (0) |
| freeze_event | 0.163 | 0.163 | 99.983 | 99.983 | -0.91 | -0.91 | no | no | excursion_confirmed (0) |
| heatwave_transit | 71.240 | 71.145 | 92.769 | 92.778 | 257.03 | 256.68 | no | no | ok (0) |
| reefer_failure | 1586.877 | 1585.655 | 18.788 | 18.812 | 5790.60 | 5786.14 | yes @ 22.8 h | yes @ 22.8 h | excursion_confirmed (0) |
| sensor_glitch | 0.275 | 0.274 | 99.971 | 99.971 | 0.00 | 0.00 | no | no | ok (1) |
| shock_drop | 0.274 | 0.275 | 99.971 | 99.971 | 0.00 | 0.00 | no | no | ok (0) |
| spoof_attempt | 1.518 | 55.233 | 99.840 | 94.347 | 4.04 | 200.10 | no | no | ok (0) |

- One day at 25 C costs 124.38 days of shelf life; one day at 40 C costs 3091.75 days.
- It takes 0.1 days at 40 C to use all of the shelf life.
- Spoof scenario, hidden loss (true minus reported): 53.715 percentage points of shelf life, 5.493 potency percentage points, 196.06 days.

*Simulation result on a synthetic box, with illustrative constants. Not real-world evidence.*

## Set E: Ea/R 15000, tau_max 4380 h

| scenario | used % rep | used % true | potency % rep | potency % true | extra days lost rep | extra days lost true | < P_min rep | < P_min true | status rep (excl.) |
|---|---:|---:|---:|---:|---:|---:|---|---|---|
| baseline_ok | 1.098 | 1.099 | 99.884 | 99.884 | 0.00 | 0.01 | no | no | ok (0) |
| door_open_excursion | 1.123 | 1.125 | 99.882 | 99.882 | 1.05 | 1.05 | no | no | ok (0) |
| freeze_event | 0.347 | 0.347 | 99.963 | 99.963 | -0.87 | -0.87 | no | no | excursion_confirmed (0) |
| heatwave_transit | 38.045 | 38.009 | 96.071 | 96.074 | 66.43 | 66.37 | no | no | ok (0) |
| reefer_failure | 327.598 | 327.396 | 70.811 | 70.826 | 596.37 | 596.00 | yes @ 27.5 h | yes @ 27.5 h | excursion_confirmed (0) |
| sensor_glitch | 0.550 | 0.548 | 99.942 | 99.942 | 0.00 | 0.00 | no | no | ok (1) |
| shock_drop | 0.548 | 0.549 | 99.942 | 99.942 | 0.00 | 0.00 | no | no | ok (0) |
| spoof_attempt | 1.581 | 28.816 | 99.834 | 97.010 | 1.38 | 51.09 | no | no | ok (0) |

- One day at 25 C costs 37.24 days of shelf life; one day at 40 C costs 414.62 days.
- It takes 0.4 days at 40 C to use all of the shelf life.
- Spoof scenario, hidden loss (true minus reported): 27.235 percentage points of shelf life, 2.824 potency percentage points, 49.70 days.

*Simulation result on a synthetic box, with illustrative constants. Not real-world evidence.*

