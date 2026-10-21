# Decision 0009: the decision planner (CVaR) and the governance rules

Status: design written BEFORE the code (Phase 5). Simulation only. Every money value, probability, delay and threshold below is an illustrative placeholder, not sourced [SOURCE NEEDED]. Results are simulation results on a synthetic box, not real-world evidence.

The planner RECOMMENDS; it never executes. Final authority stays with QA. Signing protects records after signing and does not stop a lie at the sensor (A18): the planner never treats a signed record as true just because it is signed. It looks at the trust level and the tamper verdict that the physics checks produced.

## 1. Interfaces it builds on (read from the code)

- `PotencyTracker` / `PotencyState`: `potency`, `tau_eq_h` (equivalent hours at the reference temperature), `shelf_life_used_fraction`.
- `edge.potency.arrhenius_acceleration_factor(temp_c, cfg)` and `potency_from_tau_eq(tau_eq_h, cfg)`: the maths is NOT reimplemented. For speed the acceleration factor is tabulated by calling the real function on a 0.01 degree grid and interpolated; a test compares the table with the function.
- `edge.thermal_twin.TwinParams` and the update `T_next = T_inf + (T - T_inf) exp(-dt/tau)`, `T_inf = T_amb - dT_cool * u` (single-node twin as built). Known limit: a single-node twin does not represent a box with a payload (Phase 3C, two-node test; a richer twin, "Phase 3D", is on the backlog).
- `PotencyAssessment` (Phase 3C/4): `trust_level` (trusted, low_confidence, untrusted), `verdict`, `bound_tau_eq_h` (the HIGH bound), `bound_low_tau_eq_h`; the monitor's `self_check_off` is true once a hard proof of falsification has latched.
- `edge.chain`: Ed25519 `Signer`, `Entry`, `Ledger`, `genesis_hash`, `link_hash`, and the integer-only canonical rules (`to_scaled_int`).

## 2. Actions

`continue`, `expedite`, `reroute_to_depot`, `re_source`, `quarantine`. All numbers live in `config/planner.yaml`. Each action has: a cost `c_a`; a remaining time `time_factor * R + time_offset_h` (R = scheduled remaining hours); a sampled extra delay (normal, floored at 0); extra delay hours `extra_delay_h` that the action itself causes; a probability that the cooling unit fails during the horizon (failure time uniform in the horizon, after which the unit stays off); an ambient mode (`route` or `depot`).

| action | what it means in the model | illustrative cost | remaining time |
|---|---|---:|---|
| continue | keep the schedule | 0 | 1.0 R |
| expedite | faster carrier | 3,000 | 0.75 R |
| reroute_to_depot | divert to the nearest depot; the delay of reaching the final destination later is counted as `extra_delay_h` | 5,000 | 0.35 R |
| re_source | a NEW shipment replaces this one: it starts fresh (tau_eq 0, at set point) and has its own transit and lead time; the cost includes writing off the goods | 30,000 | offset 36 h |
| quarantine | hold in a depot under cooling for a fixed time (indoor ambient); counted as delayed until review | 2,000 | offset 24 h |

Potency is evaluated at the END of the action's horizon (arrival, depot arrival, end of the hold, or arrival of the new shipment).

## 3. Loss

`L(a, w) = c_a + V * 1[P_arr(a, w) < P_min] + beta * Delay(a, w)`, with `Delay = extra_delay_h + max(0, time(a, w) - R)` hours. `V` (value of goods plus replacement and shortage), `beta` (price of an hour of delay), `P_min` (from the product config). Defaults, illustrative: V = 50,000, beta = 200 per hour.

## 4. Scenarios

A seeded `numpy` Generator built from `SeedSequence(seed)`, spawned into four children (ambient noise, heat wave, delays, cooling failures) with a fixed draw order, so a fixed seed gives byte-identical results and the actions are compared with COMMON random numbers (the same ambient path for every action).

- Ambient: exact discretisation of a mean-reverting random walk, starting at the current measured ambient: `A_{k+1} = mu + (A_k - mu) e^{-theta dt} + sigma sqrt((1 - e^{-2 theta dt})/(2 theta)) z`. Optional heat wave: with probability `heatwave_probability` an offset `heatwave_offset_c` is added for `heatwave_duration_h` from a uniform start. Depot ambient uses its own mean and spread.
- Delay: `max(0, Normal(delay_mean_h, delay_sd_h))` per action.
- Step: `dt_h` (default 0.5 h); a scenario runs round(horizon / dt) steps.

## 5. Potency at arrival

Start from the CURRENT equivalent time `tau_eq` and temperature. Each step: the cooling is working (box held at its set point by a thermostat proxy: duty `u = clip((A - T_set)/dT_cool, 0, 1)` so that `T_inf = A - dT_cool u` is the set point when the unit can reach it) or has failed (`u = 0`, the box drifts to the ambient temperature). The twin update gives the new temperature; `tau_eq += AF(T) * dt` (right-endpoint rule, the same as the tracker); `P_arr = potency_from_tau_eq(tau_eq)`. Freezing and heat damage outside the Arrhenius model (the tracker's hard limits) are out of scope here.

**Conservative start (rule).** When the trust level is `low_confidence` or `untrusted`, the planner's starting `tau_eq` is the HIGH worst-case bound, and its starting temperature is the worst-case temperature of that bound, never the point estimate. Because the Phase 3C assessment gives no bound at `low_confidence` (the twin may not match, so a bound from it was withheld), the planner computes the same high bound itself from the time the doubt started (`worst_case_bound`, with the validated safety factor). See PROPOSE P1.

## 6. CVaR

`CVaR_alpha(L) = min_eta { eta + (1/(1 - alpha)) E[(L - eta)^+] }`. For a sample of n losses the minimum is at `eta` = the alpha-quantile (the smallest sorted value x_(k) with k >= alpha n), so it is computed exactly; a second function averages the worst `(1 - alpha) n` losses directly (with a fractional weight on the boundary) and a test checks that both agree. Also reported per action: cost, failure probability, expected loss, VaR_alpha, CVaR_alpha. The CVaR-optimal action minimises CVaR; the expected-loss-optimal action minimises the mean; the table says whether they disagree. Ties are broken by (CVaR, expected loss, cost, action order) with a 1e-9 relative tolerance; `alpha` must be in [0, 1) (alpha = 0 gives the mean); tiny samples are handled by the same formulas (a sample smaller than 1/(1 - alpha) puts the whole weight on the worst values).

**Oracle** (`V = 50,000`, `alpha = 0.95`): an exact function for discrete losses reproduces continue (cost 0, 8 percent failure, expected 4,000, CVaR 50,000) and reroute (cost 5,000, 0.5 percent, expected 5,250, CVaR 10,000); expected-loss-optimal = continue, CVaR-optimal = reroute. Hand check: `(0.005 * 55,000 + 0.045 * 5,000) / 0.05 = 10,000` (the prompt printed this with a typo).

## 7. Governance rules

A recommendation (the CVaR-optimal action) is AUTO-APPROVED only if ALL hold:
1. value at risk of the chosen action (VaR at alpha) is below `V_thr`;
2. the gap between its CVaR and its expected loss is below `confidence_gap_thr`;
3. the tamper audit is clean: trust level is `trusted` and no falsification has latched.

Otherwise a human approval task is created. Overriding rules (checked first):
- A reading that fails the hash or physics check is excluded from decisions and the shipment is set to `quarantined_pending_review`. Hash failure = the chain does not verify. Physics failure = the monitor's trust level is not `trusted`, or the current verdict is a falsification or a sensor glitch. (PROPOSE P3: a glitch that has already passed does not quarantine.)
- A latched falsification or an `untrusted` trust level: NO auto-approval, ever, for any threshold values. `low_confidence` also fails rule 3.

`DecisionRecord` (frozen): shipment id, time, inputs (potency, tau_eq, the tau_eq used and whether a bound was used, trust level, verdict, chain status), the table, the chosen action, the route (`auto_approved` or `needs_human`), the reasons (which rule fired, plainly), a plain-language explanation, the seed. A `HumanApprovalTask` carries the potency curve data, the alternatives, chain status, the reason and the explanation. A human may approve, override with another action, or reject; this is recorded by a function that creates a NEW immutable `HumanDecisionRecord` (who, when, free-text reason, the action finally chosen) that references the original decision's sequence number. Nothing is ever edited.

## 8. Audit trail

Each record becomes canonical bytes with the Phase 4 integer-only rules (schema string `pg-decision/1`, a `kind` of `decision` or `human_decision`; money in 1e-2, probabilities in 1e-6, time in ms), is signed with Ed25519 and appended to a hash-chained decision log, a separate SQLite ledger under `data/runs/` (git-ignored) that uses the Phase 4 `Ledger` and the Phase 4 `link_hash` and genesis rules (genesis text from the planner id). `verify_decision_log` names the first broken entry and why (bad signature, hash link, sequence, malformed, bad reference). The Phase 4 record schema and behaviour are untouched.

## 9. PROPOSE items

**P1. Starting tau_eq at `low_confidence`.** (a) compute the high bound anyway from the start of the doubt, with the safety factor (validated with zero violations on the nominal, +/-15 percent and two-node boxes in Phase 3C); (b) use the point estimate and flag it; (c) refuse to plan and force quarantine. Pros/cons: (a) follows the prompt's rule (conservative start) and keeps the planner useful; the bound's assumption (the twin's time constant) is the very thing in doubt, but sf = 0.9 held on every tested box. (b) breaks the rule. (c) is safe but gives the QA no numbers. Recommendation: (a).

**P2. Thresholds.** `V_thr = 20,000` (40 percent of V: a loss of that size at the 95th percentile is more than a routine decision should risk without a person) and `confidence_gap_thr = 10,000` (20 percent of V: when the tail is much worse than the average, the estimate is not reliable enough to act on alone). Alternatives: tighter (10 percent / 10 percent) means almost everything goes to a human; looser means more automation. Recommendation: the values above, to be set by QA. Illustrative placeholders.

**P3. What counts as a failed physics check.** (a) any non-trusted trust level or a current falsification or glitch verdict (chosen); (b) only a latched falsification. (a) is the literal reading of the brief ("any reading that fails ... is excluded and the shipment quarantined"); it quarantines on a lone glitch while that glitch lasts. Recommendation: (a).

**P4. Chain status when no ledger is given.** `decide` replays the recording, signs it into a temporary ledger and verifies that chain. That check only shows the replay is consistent with itself. With `--ledger FILE --public-key FILE` a real ledger is verified instead. A broken chain quarantines. Recommendation: use the real ledger whenever one exists.

**P5. Cooling that is already misbehaving.** The first demo run showed a flaw: at hour 20 of `reefer_failure` (cooling short of its job since hour 9.7, the monitor says `thermal_anomaly`) the planner gave 0 percent failure for `continue`, because it assumed working cooling for the future, while the recording ends at about 86 percent potency. Options: (a) while the verdict is `thermal_anomaly`, the actions that keep the shipment in the same box (continue, expedite, reroute_to_depot) assume the cooling is already off with probability `anomaly_cooling_fail_probability` (0.8, illustrative); (b) leave as is and document; (c) estimate the cooling effectiveness from the duty and temperature history (a larger model). Pros/cons: (a) uses a verdict that already exists and is cheap, but 0.8 is an invented number and a door held open briefly is treated like a failed unit while the verdict lasts; (b) is simple and misleading; (c) is better and bigger (the same idea as the fault-aware residual on the backlog). Recommendation: (a) now, (c) later. Implemented as (a); the evaluation file shows the table with and without it.

**P6. The ambient forecast.** The first version reverted the route ambient to a fixed 22 degrees. The hot golden scenarios (ambient 41 to 48 degrees in `reefer_failure` and `heatwave_transit`) showed that this pulls the forecast far below the truth. Options: (a) persistence forecast: the ambient wanders around its CURRENT value (chosen); (b) fixed mean (kept as `route_mean_mode: fixed`); (c) a forecast from outside data (out of scope, none exists here). A persistence forecast is a simple baseline; it cannot foresee a cooling front or a heat wave start (the heat wave option adds a random hot spell). Recommendation: (a).

## 10. Out of scope

Executing any action; real SAP or carrier data; learning the parameters from real decisions (the planner is NOT validated against real decisions); humidity, shock and freezing damage; a richer twin for boxes with a payload; a user interface; multi-shipment optimisation.
