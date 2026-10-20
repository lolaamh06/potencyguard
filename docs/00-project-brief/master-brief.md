# PotencyGuard: Master Brief for Claude Code

Version: 1.0 (2026-10-20). Author: the project's decision-maker (Claude, in the planning chat), on behalf of the team. Read this whole file before doing anything else.

---

## 0. How to read this brief and what your role is

You are the **executor** (builder) on a hackathon project. A separate planning chat holds the **decision-maker** role. The team lead (a student, not an expert programmer) sits between you: they paste you prompts, then carry your reports back to the decision-maker.

This brief gives you the full context so that every later prompt can be short. It does not ask you to build anything. The last section tells you exactly what to do after reading it.

Your working rules, in one paragraph: plan before you build; build in small steps; stay inside the current phase; never make a silent decision that belongs to the decision-maker; end every phase with a written report; stop and wait for the next phase prompt.

Where this brief says **DEFAULT**, it is a decision already made that you should follow. Where it says **PROPOSE**, you must put a recommendation in your phase report and wait. Where it says **ASSUMPTION**, a number or fact is not verified and must be labelled as such everywhere it appears.

---

## 1. The event, the rules, and what matters

**SAP Hackfest 2026, Bengaluru Region.** Run by SAP with New Horizon College of Engineering (NHCE) and LTM. Students only. Team of 5 from BMS Institute of Technology and Management, Bengaluru.

Fixed calendar (cannot move):
- Registration closes **21 Oct 2026**.
- Regional (college) round: **5 to 24 Oct 2026**. Slide-based pitch only, 10 minutes plus 5 minutes of Q&A. No code required. Judged on domain, tech and business thinking, grounded in SAP Learning Hub, student edition.
- Top 5 teams per college are shortlisted **25 Oct 2026**.
- Finale build window **26 Oct to 3 Nov 2026**. Teams must build a **functional prototype** that leverages SAP technologies, using vibe coding and agent frameworks.
- Finale and winners: **4 Nov 2026**, in person at NHCE, Bengaluru.

Rules that affect engineering:
- **Hardware-only entries are disqualified.** Hardware plus software, or pure software, is allowed. PotencyGuard is software-first.
- One team, one idea.
- SAP frames problems through **Domain, Tech and Business** lenses. Code alone is not the edge.

**Priority order for the whole project:**
1. The Round 1 slide package (research, story, business model, Q&A readiness). This decides whether we reach the Finale.
2. A short screen-recording of the prototype as a Round 1 bonus.
3. The full Finale prototype, only if shortlisted.

You build number 2 and 3. Whatever you build must never put number 1 at risk.

---

## 2. The idea: PotencyGuard V1 (in plain words)

**Theme:** Resilient Supply Chains (Theme 1).

**The problem.** Medicines such as vaccines and insulin must stay cold in transit. Today a data logger records temperatures and raises an alarm when a scalar threshold is crossed. Three gaps remain:
- **G1, binary thinking.** A short 12 °C blip and a full day at 30 °C look identical to a threshold rule, but consume very different amounts of shelf life.
- **G2, untrusted data.** Nobody can prove a logger's data is genuine. Sensors can be shielded, swapped or replayed, and edits leave no trace.
- **G3, late, manual decisions.** The dispose-or-deliver decision comes hours or days late.

**The idea.** Put intelligence in the shipment box and a decision layer in the cloud.
- **In the box (edge program, designed for a Raspberry Pi):** (1) compute remaining **potency** from the temperature history using Arrhenius kinetics and mean kinetic temperature; (2) check every reading against a **lumped thermal model** of the box, so spoofed, replayed or physically impossible data is caught; (3) **sign and hash-chain** every record.
- **In the cloud (designed for SAP BTP):** a **Decision Planner** picks among *continue, expedite, reroute to depot, re-source, quarantine* by minimising **CVaR** (worst-case loss), and a **Governance Agent** auto-approves only safe cases and sends the rest to a human QA person with full evidence.

**Three contributions in the source document:** potency-aware decisions; physics-verified data; tail-risk-optimal, governed actions.

**Agents (each has a role and a hard boundary):**

| Agent | Where | Role | Boundary |
|---|---|---|---|
| Sentinel | edge | sampling, signing, local alerts | read-only on the shipment |
| Potency Estimator | edge | kinetic potency, remaining life | takes no actions |
| Tamper Auditor | edge | physics-residual check, chain verification | flags only |
| Decision Planner | cloud | CVaR action ranking | recommends; acts only inside thresholds |
| Governance Agent | cloud | routing to human approval, audit log | final authority stays with QA |

Hard principle: **disposition authority stays with a qualified human.** The system supports quality assurance and is not a regulatory certification.

---

## 3. Technical specification (the maths you must implement)

All maths is deterministic code. **An LLM must never compute or change a number.** Use SI-style units internally: kelvin for Arrhenius, seconds or hours for time (state which, per function).

### 3.1 Product parameters (DEFAULTS for the synthetic product)
These are for an **imaginary** 2 to 8 °C vaccine. No real product is measured. Label them "synthetic product parameters" everywhere.
- `Ea_over_R = 10000` K (USP default: Ea = 83.144 kJ/mol, R = 8.314 J/(mol K)).
- `T_ref = 5 °C` (278.15 K).
- Shelf life at `T_ref`: 24 months = **17,520 h**. Call this `tau_max`.
- `P_min = 0.90` minimum acceptable potency; therefore `k_ref = ln(1 / P_min) / tau_max` per hour (about 6.01e-6 per hour).
- Hard limits (ASSUMPTION, configurable): any sample below **0.0 °C** or above **40.0 °C** forces **quarantine** regardless of potency. Reason: Arrhenius does not model freezing or heat denaturation.
- Put every parameter in one config file (`config/product_default.yaml` or similar), never hard-coded.

### 3.2 Potency model
- First-order kinetics: `dP/dt = -k(T) * P`.
- Arrhenius: `k(T) = A * exp(-Ea / (R*T))`, T in kelvin.
- Acceleration factor: `AF(T) = exp[(Ea/R) * (1/T_ref - 1/T)]`.
- Equivalent time at reference: `tau_eq = sum_i AF(T_i) * dt_i`.
- Potency: `P = exp(-k_ref * tau_eq)`.
- Remaining life: `L_rem = tau_max - tau_eq`.
- Fraction of shelf life used: `tau_eq / tau_max`.
- Mean kinetic temperature (equal intervals): `T_MKT = (Ea/R) / ( -ln[ (1/n) * sum_i exp(-(Ea/R)/T_i) ] )`.
  - For unequal intervals, use time-weighted form. Document which one the code uses.

**Test oracles (must pass, tolerance 1%):**
- 8 h at 12 °C: `AF = 2.42`, `tau_eq = 19.3 h`, **0.11%** of shelf life.
- 24 h at 30 °C: `AF = 19.4`, `tau_eq = 466 h`, **2.7%** of shelf life.
- Constant temperature at `T_ref` for any duration: `AF = 1`.
- MKT of a constant profile equals that constant temperature.
- MKT is always greater than or equal to the arithmetic mean temperature for a varying profile.

### 3.3 Thermal twin and tamper detection
Lumped model of the insulated box:
- `C * dT/dt = (T_amb - T) / R_th + Q` (Q is control heat input; cooling is negative).
- Time constant `tau = R_th * C`. With inputs constant over one sample, the exact discretisation is:
  - `T_inf = T_amb + R_th * Q`
  - `T_pred[n+1] = T_inf + (T[n] - T_inf) * exp(-dt / tau)`
- Residual: `r[n] = T_meas[n+1] - T_pred[n+1]`. During calibration, estimate `R_th`, `C` by least squares and measure noise `sigma`.
- **Drift detector (CUSUM):** `S[n] = max(0, S[n-1] + |r[n]| / sigma - k)`; alarm when `S[n] > h`. Catches shielded or slowly biased sensors and door-open events.
- **Non-physical jump bound:** `|dT| <= |T_inf,max - T[n]| * (1 - exp(-dt / tau))`. Any bigger step is physically impossible for this box, so flag spoof, replay or sensor fault.
- **Residual signatures to classify:**
  - exponential drift: door-open or cooling failure;
  - impossible step: spoof, replay or fault;
  - flat line: frozen sensor or replay.
- Defaults `k` and `h` are **PROPOSE** items (report the values you pick and the false-alarm and detection numbers they give).

### 3.4 Trusted logging
- Record `m_n = (device_id, n, t_n, T_n, RH_n, shock_n, P_n)`.
- **DESIGN EXTENSION (decided):** the signed content also includes `source` (the feed type, for example `sim` or `pi`) and `scenario_id`. These fields exist in the data and in the audit store but are **not shown in the main dashboard** (see section 5).
- Signing: `sigma_n = Sign_sk(m_n)` with **Ed25519**. Chain: `h_n = SHA-256( h_{n-1} || m_n || sigma_n )`.
- Use a **canonical serialisation** (for example JSON with sorted keys and fixed number formatting) so signatures verify identically on any machine.
- The key lives in software in the prototype. In production it would sit in a secure element (ATECC608). Never commit private keys. Generate the key at first run and store it outside the repo.
- Required function: `verify_chain(records)` returning pass or fail plus the index of the first broken record.
- Editing, deleting or reordering any record must break verification of all later records.

### 3.5 Decision under uncertainty
- Actions: `a in {continue, expedite, reroute_to_depot, re_source, quarantine}`.
- For each action, run `N` Monte Carlo scenarios `omega` that sample the remaining ambient profile and transit delay. Use a **seeded** random generator so runs are reproducible. DEFAULT `N = 5000` (configurable).
- Potency at arrival: `P_arr(a, omega) = P_now * exp(-k_ref * sum_j AF(T_j(a, omega)) * dt_j)`, with `T_j` produced by the thermal twin driven by sampled ambient forecasts.
- Loss: `L(a, omega) = c_a + V * 1[P_arr < P_min] + beta * Delay(a, omega)`.
  - `c_a` action cost, `V` value of goods plus replacement and shortage cost, `beta` price of delay.
- CVaR at level `alpha` (DEFAULT 0.95), Rockafellar-Uryasev form: `CVaR_alpha(L) = min_eta { eta + (1/(1-alpha)) * E[(L - eta)^+] }`. Choose `a* = argmin_a CVaR_alpha(L(a, .))`.
- Also compute and report the expected loss and the expected-loss-optimal action, to show where CVaR disagrees.

**Test oracle (must reproduce, `V = 50,000`, `alpha = 0.95`):**

| Action | Cost | Failure prob. | Expected loss | CVaR 0.95 |
|---|---|---|---|---|
| Continue | 0 | 8% | 4,000 | 50,000 |
| Reroute | 5,000 | 0.5% | 5,250 | 10,000 |

Reading: the average-optimal choice is *continue*, the CVaR-optimal choice is *reroute*. Check by hand: reroute loss is 5,000 with probability 0.995 and 55,000 with probability 0.005; the worst 5% averages (0.005 * 55,000 + 0.045 * 5,000) / 0.05 = 10,000.

### 3.6 Governance and handoff
A recommendation is **auto-approved only if all three hold**:
1. value at risk is below `V_thr`;
2. the gap between CVaR and expected loss is below a confidence threshold;
3. the Tamper Auditor is clean.

Otherwise create a **human approval task** that carries: the potency curve, residual plots, chain status, the alternatives with their CVaR numbers, and a plain-language explanation. Any reading that fails the hash or physics check is **excluded from decisions** and the shipment is **quarantined pending review**. `V_thr` and the confidence threshold are **PROPOSE** items.

### 3.7 Time handling in the simulator
Real shipments last hours to days. A demo lasts minutes. Therefore the simulator must have a **simulated clock** and a **speed factor**:
- potency maths always uses simulated time;
- the sample interval in the source document is 10 s; in simulated time it may differ. The detection-latency target is "about 3 samples". **PROPOSE** the sample interval, speed factor and box parameters (`R_th`, `C`, `tau`) in Phase 1 and justify them against the worked examples.

---

## 4. Architecture and data flow

```
[Box simulator]  ->  [Edge program]  ->  [Backend API]  ->  [Dashboard]
 (or real sensors     potency, twin,      verify chain,       live screen,
  later)              detectors,          store, planner,     approval screen,
                      sign + chain,       governance,         scenario buttons
                      local SQLite        audit log
                                               |
                                               v
                                         [SAP adapter]
                                         (mock now; one real
                                          sandbox API later)
```

**Key design rule: one edge program, swappable sensor source.** The edge program reads from a `SensorSource` interface with two implementations:
- `SimSource` (reads the box simulator),
- `PiSource` (reads real sensors on a Raspberry Pi, **added only in Phase 11**; until then it is a clearly marked stub).
The program picks the source from configuration, with an automatic Pi-detection option. The same code must run unchanged on a Windows laptop and later on a Raspberry Pi.

**Transport:** DEFAULT plain **HTTP** from edge to backend now. **MQTT** (Mosquitto) is added later, during the Pi phase, not before.

**Storage:** SQLite for edge buffer and for backend store and audit log.

### 4.1 Real versus simulated (authoritative table)

| Part | Status | Notes |
|---|---|---|
| Potency maths, thermal twin, detectors | Real, running code | tested against the oracles above |
| Ed25519 signing, hash chain, verification | Real, running code | tamper button really edits stored data |
| CVaR planner, governance rules | Real, running code | seeded Monte Carlo |
| Backend API, storage, audit log | Real, running code | |
| Dashboard | Real, running code | |
| Temperature, humidity, shock feed | **Simulated** | physics-based box simulator with scripted events |
| Shipments, ambient forecasts, delays | **Simulated** | synthetic |
| Attacks (shield, replay, spoof, frozen) | **Simulated** | injected by the simulator or the attack tool |
| SAP endpoint | **Mock** until a sandbox API is confirmed | one adapter interface, two implementations |
| Raspberry Pi | **Not yet available** | Pi port is Phase 11 |
| Joule Studio and other SAP agent tooling | **Simulate only** | do not integrate |
| LLM | Optional | explanations and report drafting only, with a template fallback |

---

## 5. Honesty and disclosure rules (project policy, binding on you)

The team will say out loud and on a slide what is simulated. The decision-maker agreed that the **main dashboard does not display source badges** (no "SIMULATOR" banner) as a presentation choice. In exchange, these rules are non-negotiable:

1. **No false statements anywhere in the UI, code, docs or reports.** Do not write UI text such as "Live Raspberry Pi sensor", "Connected to SAP S/4HANA", or a named real sensor model (for example "DHT22") unless it is true at that moment. Use neutral wording: "Sensor feed", "Event dispatched", "Enterprise system".
2. **Provenance is always recorded and always reachable.** `source`, `scenario_id`, the SAP adapter mode and the software version are stored in the signed data and shown in a **collapsed "Provenance" drawer** in the dashboard (closed by default, opened with a visible but unobtrusive control). If a judge asks "what is this reading from?", opening that drawer must answer honestly in one click.
3. **README, phase reports and docs state plainly what is simulated.** Documentation is the honest record; only the live UI is visually neutral.
4. **Results measured on simulated data are called "simulation results"**, never "field results" or "hardware results".
5. **Targets are not findings.** The source document's numbers such as "95% spoof recall" and "40 to 60% fewer rejections" are **design targets**. Report only what you actually measure, with the run length and seed.
6. **Potency is a model output** for an imaginary product with assumed `Ea` and `P_min`. Say so in docs.
7. **No real personal or patient data.** Synthetic data only.
8. If a later prompt asks you to do something that would break rules 1 to 7, stop and flag it in your report instead of doing it.

---

## 6. Claims discipline (what we may and may not say)

A prior-art search was done on 2026-10-19 (11 searches). Findings you must respect in any text you write:
- **No single component is new.** Kinetic potency from temperature history, signed hash-chained logs and quality-aware action choice all exist in papers or products. **Never write "first", "unique" or "novel" about a component.**
- The defensible claim is the **integration**: "potency-aware, physics-verified, tail-risk decisions in one edge-to-SAP loop". The most differentiated piece is **physics-based detection of spoofed or shielded sensor data** (a signature proves data was not edited after signing; it does not prove the sensor was not shielded).
- Closest related work to name when needed: the arXiv paper 2608.15082 (quality-aware decision intelligence for cold-chain IoT), vendor products (Controlant, Sensitech, Shipsy), and SAP partner solutions (Infosys and Fusion cold-chain solutions on SAP).
- **Statistics are not yet verified.** Do **not** put any of these in code comments, README or UI as fact: "USD 35B yearly loss", "up to half of vaccines wasted", "20% of shipments see an excursion", the Nasarawa wastage percentages. If a doc needs a statistic, write a placeholder `[SOURCE NEEDED]`. The decision-maker owns the research register.
- The document's savings example (10,000 consignments, 20% excursions, USD 20,000 each, 40% safe, USD 16M recovered) is **illustrative assumptions**. Label it "illustrative" if used.
- Known weak spot: freezing is not an Arrhenius effect. The system handles it through hard limits. Make this visible in code comments and docs.

---

## 7. SAP touchpoints and access reality

- **Business Accelerator Hub sandbox APIs:** real access, sample data. **Which API fits is not chosen yet.** Do not guess an API.
- **BTP trial, generative AI hub trial:** limited, per-person and time-limited. They are started near 26 Oct, after the shortlist, and **only with the team lead's step-by-step confirmation**.
- **SAP Learning Hub practice systems:** access unclear.
- **Joule Studio and new SAP supply-chain agents:** simulate only.
- Therefore, **build an `SapAdapter` interface** with a `MockSapAdapter` (logs the event and returns a fake acknowledgement) and leave a clearly marked, unimplemented `SandboxSapAdapter`. All SAP calls go through the interface. Never hard-code SAP URLs, credentials or endpoints.
- SAP positioning (for docs): extensions run on BTP and talk to SAP planning and logistics through **released APIs**, keeping the core clean (clean core). The demo uses synthetic data and a mocked endpoint. The exact SAP integration services are **to be verified on SAP Learning Hub**; do not state them as fact.

---

## 8. Repository, folders, naming, environment

Repo: private GitHub repo `lolaamh06/potencyguard`, cloned to `C:\Users\Lolaa M H\OneDrive\Desktop\potencyguard`. The team lead chose to keep it inside OneDrive despite a warning. **Be careful about OneDrive:** do not create thousands of small files unnecessarily, avoid watch-heavy tooling where possible, and report any "file in use" or sync errors in your phase report.

Target layout (DEFAULT, create in Phase 0):

```
potencyguard/
  README.md                  what this is, how to run it, what is simulated
  CLAUDE.md                  short rules you read automatically each session
  .gitignore
  config/                    product parameters and tunables (yaml)
  docs/
    00-project-brief/        this master brief
    01-architecture/         diagrams, how parts connect
    02-phase-reports/        one report per phase
    03-decisions/            decision records (why we chose things)
    04-test-evidence/        simulation results, with seeds and run lengths
    05-demo/                 demo script, storyboard, recording notes
  simulator/                 the box simulator and scenario scripts
  edge/                      the edge program (sensor sources, potency, twin, chain)
  planner/                   decision engine and governance rules
  backend/                   API, storage, SAP adapter
  dashboard/                 the screen
  scripts/                   helper commands (run demo, run tests, tamper tool)
  tests/                     automated tests (mirrors the code layout)
  data/                      synthetic data only
```

Naming rules (DEFAULT):
- Folders and doc files: lowercase with hyphens (`phase-reports`, `thermal-twin-notes.md`). Phase reports: `phase-00-skeleton-report.md`, `phase-01-simulator-report.md`, and so on.
- Python files and functions: lowercase with underscores (`thermal_twin.py`, `verify_chain`). Classes in CapWords.
- Prefer clear names over short names. A human should find any component in under a minute.
- Every folder has a short `README.md` saying what lives there.

Environment (DEFAULT):
- Python **3.13.5**, Node **22.17.1**, npm 10.9.2, Git 2.52, Windows. The team lead's shell is PowerShell in VS Code; you may also run a Git-Bash-style shell. **Write scripts in Python or in commands that work in PowerShell**, not Bash-only syntax.
- Create the **Python virtual environment outside the repo** (for example under `%LOCALAPPDATA%\potencyguard\venv`) to keep thousands of files out of OneDrive. Document the activation command. Never commit it.
- Dependencies pinned in `requirements.txt` (or `pyproject.toml`) with exact versions for reproducibility.
- Dashboard dependencies live in `dashboard/` with `package.json`; `node_modules` is git-ignored.

---

## 9. Stack defaults (decided; change only by PROPOSE)

- **Language and libs:** Python 3.13; `numpy` (maths and Monte Carlo); `cryptography` or `PyNaCl` for Ed25519 (PROPOSE which in Phase 4); `hashlib` for SHA-256; `pydantic` for data models; `FastAPI` + `uvicorn` for the backend; `sqlite3` or SQLAlchemy for storage (PROPOSE); `pytest` for tests; `ruff` for lint and format.
- **Dashboard:** `React` + `TypeScript` + `Vite`, charts via `Recharts` or `uPlot` (PROPOSE in Phase 7), live updates over WebSocket or server-sent events. Design must look polished: clean layout, readable charts, consistent colour, light and dark friendly, large readable numbers for a projector.
- **LLM use:** optional, only for plain-language explanations and audit-report drafting, behind an interface with a **deterministic template fallback**. No API keys in the repo. LLM never touches numbers.
- **Agents:** the five agents in section 2 are implemented as plain, testable Python classes with explicit inputs, outputs and boundaries. An agent-framework wrapper is a later **PROPOSE** item; do not add one now.

---

## 10. Coding standards

- Small, single-purpose functions; clear names; type hints on all public functions; short docstrings that cite the section of this brief or the source document they implement.
- **Determinism:** every random process takes a seed. The same seed gives the same result. Tests use fixed seeds.
- **Config over constants:** all tunables in `config/`. No magic numbers in code.
- **Tests first for maths.** The oracles in sections 3.2 and 3.5 become unit tests before or with the implementation. Add property-style checks (potency never increases, AF monotonic in temperature, chain breaks on any edit).
- **Fail loudly and clearly.** Validate inputs; raise readable errors; never swallow exceptions.
- **No secrets in git.** Keys, tokens and `.env` files are git-ignored. If you find a secret in the repo, stop and report.
- **Logging:** structured, leveled, no personal data.
- **Comments explain why, not what.** Highlight assumptions with `ASSUMPTION:` in comments.
- **Do not over-engineer.** The prototype must be reliable and demonstrable, not enterprise-scale.

---

## 11. Working protocol (follow exactly, every phase)

1. **Read the phase prompt fully.** If anything is ambiguous, list numbered questions in your reply and **stop**. Do not guess.
2. **Plan first.** Before editing anything, write a short plan: files you will create or change, steps in order, risks, and any **PROPOSE** items you will need decided. Wait for the team lead's go-ahead only if the phase prompt says so; otherwise proceed with the plan.
3. **Build in small steps.** Run tests and the code as you go. Do not move on while tests fail.
4. **Stay inside the phase.** Do not start the next phase, refactor unrelated files or add features that were not asked for. Note ideas in the report instead.
5. **Commit as you go.** Small commits with plain-English messages (what and why). Work directly on `main` for now; when a phase is done, create a git tag `phase-NN-done`. **Never** force-push, rewrite history, delete branches, or change git config. Push to `origin` at the end of the phase.
6. **Safety rules.** Do not delete or overwrite files outside the repo. Do not install global tools without asking. Do not read or print secrets. Do not call external network services that the prompt did not name. Download nothing unrequested.
7. **Write the phase report** (template below) into `docs/02-phase-reports/` and **also print a short plain-English summary** in your final message.
8. **Stop.** Do not continue until the next phase prompt arrives. The team lead will bring your report to the decision-maker, who will explain it, discuss it, and only then issue the next prompt.

### 11.1 Phase report template

```
# Phase NN: <name>: Report
Date, git commit hash, git tag

1. What I was asked to do (one paragraph)
2. What I built (list of files and folders, one line each)
3. How to run it (exact commands, PowerShell-friendly)
4. How to check it works (exact commands and expected output)
5. Test results (counts, any failures, any skipped tests and why)
6. What is real and what is simulated in this phase
7. Decisions I made and why (and PROPOSE items awaiting decision, each with
   options, pros, cons and my recommendation)
8. Assumptions and unverified claims introduced
9. Problems, surprises, OneDrive/Windows issues
10. Numbers measured (with seeds and run lengths), labelled "simulation results"
11. Open questions for the decision-maker (numbered)
12. Suggested next phase (one paragraph, not started)
```

The plain-English summary in your final message must be readable by a non-programmer: what now works, what to click or run to see it, what to worry about.

---

## 12. Phase roadmap (for orientation only; each phase arrives as its own prompt)

| Phase | Goal | Done when |
|---|---|---|
| 0 | Project skeleton: folders, README, `CLAUDE.md`, `.gitignore`, environment, tooling, test runner, move this brief into `docs/00-project-brief/` | `pytest` and lint run on an empty skeleton; first commit pushed |
| 1 | Box simulator and scenario scripts (normal, mild excursion, severe excursion, attacks) with a simulated clock | deterministic traces; scenarios plotted to image files |
| 2 | Potency maths | all section 3.2 oracles pass |
| 3 | Thermal twin, calibration routine, detectors | attack scenarios flagged; false-alarm and latency numbers reported |
| 4 | Ed25519 signing, hash chain, `verify_chain`, `SensorSource` switch | tamper-and-verify tests pass |
| 5 | Decision Planner (CVaR) and governance rules | section 3.5 oracle table reproduced |
| 6 | Backend API, storage, audit log, `SapAdapter` (mock) | API tests pass; end-to-end data flow works headless |
| 7 | Dashboard (live screen, approval screen, scenario buttons, collapsed provenance drawer, tamper button) | demo flows work in the browser |
| 8 | Polished demo scenarios and a recording mode | a clean 60 to 90 second run, repeatable |
| 9 | Tests and evidence runs (many seeded runs) | simulation results written to `docs/04-test-evidence/` |
| 10 | Documentation pass | README, architecture notes and decision records are accurate |
| 11 | Raspberry Pi port | edge program runs on a Pi; update timing measured |
| 12 | One real SAP touchpoint (only after shortlist, one step at a time) | one sandbox call works |

Round 1 slides do not depend on phases 11 and 12.

---

## 13. Glossary (plain words)

- **Potency:** how much of a medicine's original strength is left.
- **Arrhenius:** the rule that chemical damage speeds up sharply as temperature rises.
- **Acceleration factor (AF):** how many times faster damage happens at temperature T than at the storage reference temperature.
- **MKT (mean kinetic temperature):** the single steady temperature that would cause the same total damage as the varying temperature actually seen.
- **Thermal twin:** a small physics model of the box that predicts what the temperature should do next.
- **Residual:** actual reading minus the twin's prediction; large or odd residuals mean something is wrong.
- **CUSUM:** a running tally that grows when residuals keep leaning one way.
- **Hash chain:** each record contains a fingerprint of the previous one, so editing any record breaks everything after it.
- **CVaR:** the average loss in the worst few percent of cases (here the worst 5%).
- **Excursion:** a period outside the allowed temperature range.
- **QA:** quality assurance, the human who decides whether a shipment is used.
- **BTP:** SAP Business Technology Platform.
- **Clean core:** keeping SAP's core system unmodified and extending it through released APIs.
- **Edge:** computing done at the shipment box rather than in the cloud.

---

## 14. Decisions still open (do not decide these yourself)

- Which SAP sandbox API to call in Phase 12.
- Real-sensor hardware for the Finale (the team currently has none; the Pi is arriving later).
- Dashboard charting library and exact stack choices marked PROPOSE.
- `k`, `h` for CUSUM; `V_thr` and the confidence threshold for governance; simulator timing and box parameters.
- Whether and how an agent framework wraps the five agents.
- How collaborators (four teammates) are added and how branching changes once they join.

---

## 15. What to do now

**Read this entire brief and the file `README.md`, if it exists. Do not create, edit or delete any files. Do not run installers. Do not start any phase.**

Then reply with:
1. A summary of the project in **no more than 12 bullet points**, in your own words, to show you understood it.
2. The list of **rules you will follow** (section 5 honesty rules, section 11 working protocol) in one short paragraph.
3. Anything in this brief that is **ambiguous, contradictory or risky**, as a numbered list. If nothing, say "None found".
4. Any **environment problems you can already see** (for example OneDrive, shell, missing tools), found with read-only commands only (`python --version`, `node --version`, `git status`).

Then **stop and wait for the Phase 0 prompt.**


---

## Amendments v1.1 (approved 2026-10-20)

These amendments override the master brief where they differ.

A1. GIT RULE (replaces section 11, item 5 of the brief).
You must NEVER run: git add, git commit, git tag, git push, git merge, git rebase, git reset, git stash, git checkout, git switch, git restore, git clean, or any command that changes the repo, the index or its history. Read-only git commands are allowed: git status, git diff, git log, git remote -v, git branch --show-current.
After each logical step, print the exact PowerShell commands the team lead can run to commit that step: explicit "git add <paths>" lines (never "git add ." or "git add -A"), then a "git commit -m ..." line with a plain-English message. The team lead decides whether to run them. At the end of the phase also print the push command (git push -u origin main for the first push) and the optional tag commands (git tag phase-00-done, then git push origin phase-00-done). Do not put any co-author trailer in the suggested messages.

A2. Tests compare against UNROUNDED formula results. The brief's rounded numbers (AF 2.42 and 19.4; 466 h; 0.11%; 2.7%) must match when rounded to the document's own precision.

A3. CVaR testing has two layers. (a) An exact test of the CVaR function on explicit discrete loss lists; this is where the oracle values 50,000 and 10,000 are checked. (b) An approximate test of the Monte Carlo planner, with a fixed seed and a stated tolerance.

A4. Signed record fields are exactly: device_id, n, t_n, T_n, RH_n, shock_n, P_n, tau_eq_h, source, scenario_id, sw_version, key_id.

A5. Hard limits (below 0.0 C and above 40.0 C) trip quarantine only after 2 consecutive samples beyond the limit (configurable as hard_limit_consecutive_samples). A single extreme reading is marked "suspect" and excluded from decisions.

A6. MKT uses the time-weighted form: T_MKT = (Ea/R) / ( -ln( sum_i w_i * exp(-(Ea/R)/T_i) ) ) with w_i = dt_i / sum(dt). It reduces to the equal-interval form when intervals are equal.

A7. Signing library: cryptography (Ed25519). Python dependencies are pinned to exact versions that install.

A8. No title card or banner is added to the dashboard or to recordings. The Provenance drawer rule (brief section 5, rule 2) still applies.

A9. Extra Python package: shared/ (config loading and common types). Top-level Python packages are: shared, simulator, edge, planner, backend.

A10. FRONTEND_VISION.md is binding. It defines the cinematic 3D scrollytelling Story and the Control Room. It is moved to docs/01-architecture/frontend-vision.md in this phase and stays binding for all frontend phases.

A11. Revised roadmap (replaces the table in section 12 of the brief):
  Phase 0   Skeleton, toolchain, WebGL smoke test (this phase)
  Phase 1   Box simulator, scenario scripts, exported scenario recordings (JSON)
  Phase 2   Potency maths in Python, plus shared test vectors in shared/test-vectors/
  Phase 3   Thermal twin, calibration, detectors
  Phase 4   Ed25519 signing, hash chain, verify_chain, SensorSource switch
  Phase 5   Decision Planner (CVaR) and governance rules, futures export for the visuals
  Phase 6   Backend API, storage, audit log, mock SAP adapter, replay endpoints
  Phase F1  Art direction, design system, storyboard, style frames
  Phase F2  Frontend foundation: scroll rig, 3D canvas, globe, quality governor, mode adapter, TypeScript potency mirror
  Phase F3  Story chapters 1 to 3 (the pain)
  Phase F4  Story chapters 4 to 7 (the answer)
  Phase F5  Control Room
  Phase F6  Polish, accessibility, soak test, recording mode, fallback video
  Phase 8   Demo scenarios polish
  Phase 9   Evidence runs
  Phase 10  Documentation pass
  Phase 11  Raspberry Pi port
  Phase 12  One real SAP touchpoint (only after shortlist, one step at a time)
Backend phases (1 to 6) and frontend phases (F1 to F6) can run in parallel. The Round 1 slide package keeps priority over everything.

A12. Layout additions beyond the brief: docs/06-prompts/ (archive of every phase prompt), shared/test-vectors/ (JSON test vectors shared by Python and TypeScript tests), and dashboard/ as a standard Vite + React + TypeScript project.

A13. Tooling awareness. In later frontend phases, use a frontend design skill and the Playwright browser tools to look at your own screenshots, if they are available. In this phase, only REPORT what you can see. Install no plugin or MCP server yourself.

A14. The UI honesty rules in section 11 of FRONTEND_VISION.md have the same force as section 5 of the brief.
