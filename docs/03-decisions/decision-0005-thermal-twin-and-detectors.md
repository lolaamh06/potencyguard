# Decision 0005: The thermal twin and the tamper detectors

Date: 2026-10-20

## What this does

The box has a physics model, the "thermal twin". Given the temperature inside the box a moment ago, the temperature around it, and how hard the cooling unit worked, the twin predicts what the temperature inside should be one sample later. The gap between what the sensor reports and what the twin expects is the **residual**. Four detectors watch the residual and the reported value, and a small classification says what the pattern means.

The claim this supports is narrow: a reported temperature that the box could not physically have produced is flagged. A signature proves a record was not edited after it was made; it does not prove the sensor told the truth. The twin tries to cover that gap.

## The model and the new channels

`T_inf = T_amb - dT_cool * u` and `T_pred[next] = T_inf + (T - T_inf) * exp(-dt / tau)`.

- `T_amb` is the measured temperature around the box (the cargo area), `u` is the cooling duty and `dT_cool` is the largest cooling depression the unit can produce (the wall resistance times the cooling capacity).
- To use the model the box reports two new channels with every reading: **ambient_c** (the temperature around the box, with its own sensor noise) and **cooling_duty** (the fraction of the last interval during which the compressor ran). They default to "not measured" so older code keeps working; the twin requires them.
- The interval from one sample to the next uses the average of the two ambient readings (the ambient moves during the interval) and the duty reported with the later sample.
- Heat the edge cannot see, such as an open door, is deliberately not in the model. It shows up as a warmer-than-expected residual, which is how a physical event is told apart from a lie.
- The ambient noise has its own random stream, so adding the channels did not change any temperature, humidity or shock value in any recording.

## Threat model

**The attacker tampers with the box thermistor only.** The ambient channel and the cooling duty are assumed honest. A coordinated forgery of several channels at once, or of the cooling unit's own signal, is out of scope for physics and is left to signatures and hardware measures.

## Calibration

The twin's numbers (time constant, cooling depression, residual spread) are fitted from clean calibration runs made with the simulator (seeds 9001 to 9010, kept apart from all scoring data). The fit is a least-squares regression, and **there is a known weakness**: the temperature inside the box is a noisy measurement, which biases a plain regression. In a thermostat-controlled box this bias is large, because the cooling duty follows the box temperature and leaves little independent variation to hide the noise behind. On the synthetic data the plain fit gave a time constant of about 1.8 hours instead of 6. The fit used for the twin therefore imposes the physical structure from the brief (the increment of temperature is proportional to the gap to ambient and to the cooling duty), which removes the problem: it recovers 5.98 hours and 29.85 K against the true 6 hours and 30 K. The plain fit is still computed as a consistency check. Calibration refuses runs that are too short, too flat to separate the effects, or that contain tamper, glitch or unobserved heat and cooling events, and it refuses any recording that is not a calibration recording.

## The four detectors

1. **CUSUM drift (from the brief).** A running tally of how many residual spreads the box is warmer or colder than predicted, kept for each direction. It alarms when a tally passes a threshold. The brief writes the absolute value; keeping the two directions separate gives the sign, which the classification needs.
2. **Impossible step (from the brief).** A jump between two samples bigger than the box can physically make. The bound is the brief's, plus a few residual spreads for noise, plus a design allowance for unobserved heat: without the allowance a door held open can make a real step larger than the bound and would be mistaken for a lie.
3. **Impossible state (my addition to the brief).** The reported temperature is below the coldest the box could possibly be. The simple limit (ambient minus the full cooling depression) is only reached after several time constants, so the first version raised false alarms while the ambient was rising. The final version follows the box's own dynamics: the coldest possible temperature starting from the first reading with full cooling all the time. There is no matching upper limit, because heat loads are not observed.
4. **Flat line (from the brief).** The reported temperature barely moves over a window, far less than sensor noise alone would give. The simulator's falsified values carry normal noise, so this detector catches crude freezes only; it is expected to do almost nothing against the simulated attacks.

## The classification

| Pattern | Verdict |
|---|---|
| flat line, impossible state, a negative-side CUSUM alarm, or a jump that stays | suspected falsification |
| a jump that reverts at once (a lone impossible reading) | sensor glitch |
| a positive-side CUSUM alarm and none of the above | thermal anomaly (cooling shortfall or door open: a physical event, not tamper) |
| otherwise | ok |

A positive residual means the box is warmer than expected: physics. A negative residual means the box is reported colder than the physics allows. A jump waits one sample (the same confirmation count the potency tracker uses for a lone out-of-range reading) to see whether it reverts; while it is undecided its samples do not feed the CUSUM. Proof of falsification (a persistent impossible step, the impossible state, a flat line) is **latched** until reset, because a lie that is physically consistent after its first jump, such as a value held at a plausible number, would otherwise look like a harmless cooling shortfall again. A negative CUSUM alarm alone is held for a few samples but not latched.

## How the CUSUM settings were chosen

The settings are placeholders chosen by a sweep on separate training seeds. The rule: keep the settings whose false alarms are at most 1 per 1000 simulated hours, then take the smallest median detection delay. The clean simulation gave no false alarms for any setting, so the rule fell through to the most sensitive setting (k = 0.25, h = 4). The sweep cannot tell the settings apart on false alarms because the clean simulation has Gaussian noise and the twin matches the simulator's equations; the mismatch runs in the evaluation are the real test of that choice, and they show it is fragile.

## The end-of-trip fix

An event whose end is exactly the end of the trip now also covers the final sample. Before, a spoof that "lasts to the end" left one true-looking reading at the end. Only the recordings that have such events changed, and only in their final sample.

## What this decision does not claim

The twin and the simulator use the same family of equations, so good numbers on matched boxes prove little by themselves. That is why the evaluation repeats with boxes that differ from the calibration, and why the results are written as simulation results on a synthetic box, never as field results.
