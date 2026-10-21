# Phase 5 prompt (archived verbatim)

PHASE 5: DECISION PLANNER (CVaR) AND GOVERNANCE RULES

READ FIRST. Assume nothing. Read docs/00-project-brief/master-brief.md (sections 3.5 and 3.6, and every amendment, especially A18), the Phase 3C and Phase 4 reports in docs/02-phase-reports/, edge/assessment.py, edge/thermal_twin.py, edge/potency.py, edge/chain/ (to see the signed fields), shared/config.py and config/*.yaml. Write down the real interfaces before designing. The planner/ package folder already exists in pyproject.toml.

GIT RULES (absolute). NEVER run git add, git commit, git tag or git push. Read-only git is fine. First check git status; if earlier phases are uncommitted, stop and tell me. At the end print ONE block of explicit-path git add commands and ONE git commit command, with no co-author trailers and no wildcards.

WORDING RULES. No "unhackable", "tamper-proof", "first", "unique", "novel". No external statistic: write [SOURCE NEEDED]. All money values, probabilities, delays and thresholds are labelled "illustrative placeholder, not sourced [SOURCE NEEDED]". Results are simulation results on a synthetic box, not real-world evidence. Signing protects records after signing and does not stop a lie at the sensor (A18): the planner must never treat a signed record as true just because it is signed.

NEW PACKAGES. None. Use numpy and pydantic, already installed. Do NOT run npm install.

STEP 0. Preflight. git status, then scripts/run_checks.py with the venv python. Expect 6 of 6 checks and 645 tests. Report the baseline. If anything fails, stop.

STEP 1. Design note first. Before coding, write docs/03-decisions/decision-0009-decision-planner.md with: the actions, the loss function, how scenarios are sampled, the CVaR formula, the governance rules, every PROPOSE item with options and a recommendation, and what is explicitly out of scope. Then build to it.

STEP 2. Actions and loss (master brief 3.5). Actions: continue, expedite, reroute_to_depot, re_source, quarantine.

Loss L(a, omega) = c_a + V * 1[P_arr < P_min] + beta * Delay(a, omega).
All inputs come from one validated config file config/planner.yaml (action costs, V, beta, alpha default 0.95, N default 5000, seed, delay distributions per action, ambient forecast model parameters, thresholds). Every number marked illustrative placeholder.
Sampling: a seeded numpy Generator (SeedSequence), so a fixed seed gives byte-identical results. Sample the remaining ambient profile (a simple documented model: current ambient plus a mean-reverting random walk, with a heat-wave option) and the transit delay per action. Each action has its own remaining transit time and cooling assumption (for example reroute shortens the remaining time; expedite shortens it at a cost; re_source means a new shipment replaces this one; quarantine means holding the goods in a depot under cooling). Write each assumption in the decision note.
Potency at arrival: start from the CURRENT estimated tau_eq (from the potency tracker) and propagate through the thermal twin (single-node twin as built) driven by the sampled ambient, assuming cooling works at a probability you define per action. Use the same Arrhenius functions in edge/potency.py; do not reimplement the maths.
Use the worst-case bound from the Phase 3C assessment: when the trust level is low_confidence or untrusted, the starting tau_eq for the planner must be the HIGH bound (the conservative one), not the point estimate. State this in the note and test it.

STEP 3. CVaR. Implement the Rockafellar-Uryasev form CVaR_alpha(L) = min_eta { eta + (1/(1-alpha)) E[(L - eta)^+] } for a sample (the minimum is at eta = the alpha-quantile, so compute it exactly and also verify by a direct sorted-tail average). Report for every action: cost, failure probability, expected loss, CVaR, the CVaR-optimal action and the expected-loss-optimal action, and say whether they disagree. Handle ties and tiny samples explicitly.

STEP 4. The oracle (must reproduce). Using a discrete two-outcome test mode with V = 50,000 and alpha = 0.95: Continue has cost 0 and 8% failure, expected loss 4,000, CVaR 50,000. Reroute has cost 5,000 and 0.5% failure, expected loss 5,250, CVaR 10,000. The expected-loss-optimal action is continue and the CVaR-optimal action is reroute. Provide an exact (analytic, non-Monte-Carlo) function for discrete losses so the table reproduces exactly, and a Monte Carlo test that matches within a stated tolerance. Add the hand check from the brief (0.00555000 + 0.0455000)/0.05 = 10,000 as a test.

STEP 5. Governance (master brief 3.6). A recommendation is auto-approved only if ALL hold: (1) value at risk is below V_thr; (2) the gap between CVaR and expected loss for the chosen action is below a confidence threshold; (3) the tamper audit is clean (trust level is trusted and no latched falsification). Otherwise create a human approval task. Also:

Any reading that fails the hash or physics check is excluded from decisions, and the shipment is set to quarantined pending review.
A latched falsification or an untrusted trust level means NO auto-approval, ever.
Output a DecisionRecord (pydantic, frozen): shipment id, time, inputs (potency, tau_eq, bound used, trust level, verdict, chain status), the table of alternatives with their numbers, the chosen action, the approval route (auto_approved or needs_human), the reasons (which rule fired, in plain words), a plain-language explanation, and the seed. A human approval task carries: potency curve data, the alternatives with CVaR numbers, chain status, the reason, and a plain-language explanation. Humans may approve, override with another action, or reject; model this as a function that records the human decision (who, when, free-text reason) as a new immutable record, never an edit.
V_thr and the confidence threshold are PROPOSE items: propose values with reasoning and state them as illustrative placeholders.
The planner recommends; it never executes. Final authority stays with QA. Say so in docstrings.

STEP 6. Audit trail. Every DecisionRecord is canonicalised with the same integer-only rules as Phase 4 (reuse edge/chain helpers; add a separate schema string pg-decision/1 and document it), signed and appended to a hash-chained decision log in a separate SQLite ledger file under data/runs/ (git-ignored), using the Phase 4 ledger pattern. A verifier for the decision log names the first broken entry. Do not change Phase 4 behaviour or the existing record schema. Human decisions are appended as new entries that reference the original decision's sequence number.

STEP 7. CLI and demo. python -m planner decide --recording FILE --at-hour H runs the pipeline up to hour H (using the existing pipeline and the potency/trust outputs), builds the decision, prints the table of alternatives, the chosen action, the approval route and the reasons, and writes the decision log entry. python -m planner demo runs a set of the golden recordings (baseline_ok, door_open_excursion, reefer_failure, heatwave_transit, spoof_attempt, hidden_spoilage) at sensible checkpoints and prints one summary table: scenario, hour, trust level, chosen action, CVaR-optimal vs expected-loss-optimal, route. Do not hide cases where the planner looks odd; report them.

STEP 8. Tests (at minimum). Oracle table exact; hand check; Monte Carlo within tolerance; seed reproducibility (same seed same bytes, different seed different samples); CVaR equals the sorted-tail average; CVaR >= expected loss always; alpha edge cases; each governance rule individually forces needs_human; all three satisfied gives auto_approved; untrusted or latched falsification never auto-approves across a sweep of V_thr values; the conservative bound is used when trust is low or untrusted; human decision recorded as a new entry and the log still verifies; tampering with a decision log copy is detected; config validation rejects bad values; no float leaks into the canonical decision bytes; Phase 4 vectors and golden recordings byte-identical (reuse shared/golden_sha256.json). Add a Phase 5 check to scripts/run_checks.py. Do not edit existing tests. Run the full suite and report totals.

STEP 9. Honest evaluation. Write docs/02-phase-reports/phase-05-evaluation.md: for the 6 demo scenarios at their checkpoints, a table of chosen action, CVaR vs expected-loss disagreement, route, and a short plain explanation of why. Run a sweep of V and beta to show how the recommendation changes (a sensitivity table), clearly labelled illustrative. State that these values are placeholders and that the planner is only as good as the potency estimate and the thermal twin (including the known single-node twin limit on two-node boxes; Phase 3D is on the backlog). Do not claim the planner is validated against real decisions.

STEP 10. Docs. Write docs/02-phase-reports/phase-05-report.md (what was built, rules, decisions, PROPOSE items, tests, omissions, a "can say / must not say" list for slides). Update READMEs for planner/, config/, scripts/. Add an amendment to the master brief only if something in it changed. Archive this prompt in docs/06-prompts/. Update docs/00-project-brief open items if needed.

STEP 11. Final report to me in simple words: what was built, baseline vs final test counts, how to run decide and demo (exact PowerShell commands using the venv python), the oracle result, the demo table, anything surprising, anything not done, open questions as a numbered list, and the single commit block. Then stop. Do not start Phase 6.

---

Notes added by the executor when archiving (not part of the prompt):
- The hand check in Step 4 is printed with garbled digits in the prompt; the brief's check is (0.005 * 55,000 + 0.045 * 5,000) / 0.05 = 10,000, which is what the test uses.
- Step 2 says that at low_confidence the starting tau_eq must be the HIGH bound, but Phase 3C deliberately gives no bound at low_confidence. The planner computes the same high bound itself from the time the doubt began (decision 0009, P1).
