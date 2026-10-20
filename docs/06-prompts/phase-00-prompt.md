PHASE 0: PROJECT SKELETON, TOOLCHAIN AND WEBGL SMOKE TEST

=====================================================================
PART 0. WHO YOU ARE AND HOW TO BEHAVE
=====================================================================
You are the EXECUTOR on the PotencyGuard hackathon project. A separate planning chat is the DECISION-MAKER. The team lead (a student, not an expert programmer) sits between you: they paste you prompts and carry your reports back.

Rules that apply to every line of this prompt:
- ASSUME NOTHING. If anything is unclear, ambiguous or missing, do not guess. Write numbered questions and STOP.
- Do exactly what is written here. Do not add features, files, dependencies or folders that this prompt does not list.
- Do not make decisions that belong to the decision-maker. If a choice is not specified here, list the options with pros, cons and your recommendation in your report, pick the safest minimal option only if the prompt allows it, and say so.
- Work in small steps. After each step, check your work, then print the suggested commit commands (see amendment A1), then continue.
- Plain English in all summaries. The team lead is not a programmer.

=====================================================================
PART 1. SOURCES OF TRUTH AND PRIORITY
=====================================================================
Read these two files completely, from the first line to the last, before anything else. They are in the repo root:
  1. MASTER_BRIEF.md       (the full project brief)
  2. FRONTEND_VISION.md    (the full design and frontend spec)

Priority when instructions disagree:
  1. Honesty rules (section 5 of the master brief, and section 11 of FRONTEND_VISION.md)
  2. The amendments A1 to A14 in PART 3 of this prompt
  3. FRONTEND_VISION.md (for the dashboard)
  4. MASTER_BRIEF.md (for everything else)

If either file is missing, STOP and tell the team lead which one.

=====================================================================
PART 2. PRE-FLIGHT (READ-ONLY; change nothing)
=====================================================================
Run these checks first. Print a short table of results.

2.1 Location and git (read-only commands only):
  - Print the current working directory. It must be the repo root (the folder that contains .git).
  - git status --short, git branch --show-current, git remote -v, git log --oneline -3 (the log may say there are no commits yet; that is fine).
  - Expected: branch main, remote origin = https://github.com/lolaamh06/potencyguard.git.

2.2 STOP CONDITIONS (if ANY is true, stop, report what you found, change nothing, and wait):
  a. A folder named docs/ already exists.
  b. Any of these exist in the repo root: pyproject.toml, requirements-dev.txt, package.json, .gitignore, README.md, CLAUDE.md, config/, shared/, simulator/, edge/, planner/, backend/, dashboard/, tests/, scripts/.
  c. MASTER_BRIEF.md already contains the text "Amendments v1.1".
  d. Files named PHASE_0_PROMPT.md or PHASE_00_PROMPT.md exist in the repo root (a stale prompt from another chat). Do NOT delete them; just report them.
  e. git status shows anything staged.
  If none is true, continue.

2.3 OneDrive detection:
  - If the repo path contains the text "OneDrive" (any capitalisation), set MODE = B (OneDrive-protected). Otherwise set MODE = A (plain). Print the mode.

2.4 Tool versions (read-only): python --version, node --version, npm --version, git --version. Expected: Python 3.13.x, Node 22.x, npm 10.x. If Python is older than 3.12 or Node older than 20, STOP.

2.5 Tooling awareness: list, by name only, the skills, plugins and MCP tools available in this session. Install nothing.

Print the pre-flight summary. Then continue to PART 3.

=====================================================================
PART 3. AMENDMENTS v1.1 (OFFICIAL)
=====================================================================
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

=====================================================================
PART 4. THE STEPS
=====================================================================
Before editing anything, print a short plan (files to create, steps in order, risks). Then proceed.

---------------------------------------------------------------------
STEP 1. DOCUMENTS AND AMENDMENTS
---------------------------------------------------------------------
1.1 Create these folders: docs/00-project-brief/, docs/01-architecture/, docs/02-phase-reports/, docs/03-decisions/, docs/04-test-evidence/, docs/05-demo/, docs/06-prompts/.
1.2 Move MASTER_BRIEF.md to docs/00-project-brief/master-brief.md and FRONTEND_VISION.md to docs/01-architecture/frontend-vision.md. Use a plain file move (PowerShell Move-Item), NOT "git mv".
1.3 Append to the very end of docs/00-project-brief/master-brief.md a new section titled exactly:
    "Amendments v1.1 (approved 2026-10-20)"
    containing amendments A1 to A14 from PART 3, verbatim. Change no other text in the brief.
1.4 Create docs/03-decisions/decision-0001-brief-amendments-v1-1.md: a short title, the date 2026-10-20, then one short plain-English paragraph per amendment (A1 to A14) saying what it decides and why.
1.5 Print the suggested commit commands for this step.

---------------------------------------------------------------------
STEP 2. FOLDERS AND READMES
---------------------------------------------------------------------
2.1 Create these folders (docs/ subfolders already exist from step 1):
    config/, shared/, shared/test-vectors/, simulator/, edge/, planner/, backend/, dashboard/, scripts/, tests/, data/
2.2 Give EVERY folder (including each docs/ subfolder) a README.md of 3 to 8 lines saying: what lives here, which phase fills it, and one plain-English sentence on how a human finds things here. Use these descriptions:
    docs/00-project-brief/   The master brief and its amendments.
    docs/01-architecture/    How the parts connect; the frontend vision; design system (filled in later).
    docs/02-phase-reports/   One report per phase, written by the executor.
    docs/03-decisions/       Decision records: what we chose and why.
    docs/04-test-evidence/   Simulation results with seeds and run lengths (Phase 9).
    docs/05-demo/            Demo script, storyboard, recording notes (Phase 8 and F6).
    docs/06-prompts/         Archive of every phase prompt, one file per phase.
    config/                  Tunable parameters in YAML (product parameters, thresholds).
    shared/                  Code used by several packages: config loader now, common types later.
    shared/test-vectors/     JSON test cases that are the single source of truth for numeric tests in Python and TypeScript.
    simulator/               The box simulator and scenario scripts (Phase 1).
    edge/                    The edge program: sensor sources, potency, thermal twin, signing and chain (Phases 2 to 4).
    planner/                 The decision planner (CVaR) and governance rules (Phase 5).
    backend/                 API, storage, audit log, mock SAP adapter (Phase 6).
    dashboard/               The cinematic Story and Control Room (Phases F1 to F6). Phase 0 holds a throwaway WebGL smoke test.
    scripts/                 Helper commands: run checks, later demo and tamper tools.
    tests/                   Automated tests; folder layout mirrors the code.
    data/                    Synthetic data only. Generated outputs are git-ignored.
2.3 Create an empty __init__.py in each of: shared/, simulator/, edge/, planner/, backend/. Also create tests/__init__.py is NOT needed; do not create it.
2.4 Print the suggested commit commands for this step.

---------------------------------------------------------------------
STEP 3. ROOT FILES
---------------------------------------------------------------------
3.1 Create README.md in the repo root with these sections, in this order:
    - Title: "PotencyGuard"
    - "What it is": 3 to 4 plain sentences. Content: PotencyGuard is a software-first entry for SAP Hackfest 2026 (Theme: Resilient Supply Chains) about cold-chain medicines. A small edge program computes how much potency a shipment has left, checks that sensor readings obey physics, and signs every record into a tamper-evident chain. A cloud layer chooses an action by minimising worst-case loss and sends risky cases to a human for approval.
    - "Status": "Phase 0: project skeleton and toolchain only. No product features yet."
    - "What is real and what is simulated": a table with columns Part | Status, rows exactly:
        Potency maths, thermal twin, detectors | Real code (from Phases 2 and 3)
        Ed25519 signing, hash chain, verification | Real code (from Phase 4)
        CVaR planner, governance rules | Real code (from Phase 5)
        Backend API, storage, audit log | Real code (from Phase 6)
        Dashboard (Story and Control Room) | Real code (from Phases F1 to F6)
        Temperature, humidity and shock feed | Simulated by a physics-based box simulator
        Shipments, forecasts, delays, attacks | Simulated (synthetic)
        SAP endpoint | Mock until a sandbox API is confirmed
        Raspberry Pi | Not yet available; Pi port is Phase 11
      followed by one line: "All data is synthetic. Potency is a model output for an imaginary product."
    - "Set up on Windows (PowerShell)": exact commands to create the venv outside the repo and install, using the paths from step 5, and how to install the dashboard dependencies (step 6). Write them as numbered steps.
    - "Run the checks": the exact command to run scripts/run_checks.py with the venv's python.
    - "Run the dashboard smoke test": npm run dev, open the printed local address, press Q to cycle quality.
    - "Folder guide": one line per top-level folder.
    - "Honesty note": 3 sentences: the dashboard is planned as a cinematic 3D experience and is not built yet; simulated parts are documented here and in phase reports; targets are never presented as results.
    Do NOT include any external statistic (no money figures, no wastage percentages). Do NOT use the words "first", "unique" or "novel".

3.2 Create CLAUDE.md in the repo root with EXACTLY this content (you may fix typos only):
    # CLAUDE.md: rules for every session in this repo
    1. At the start of every session, read docs/00-project-brief/master-brief.md and docs/01-architecture/frontend-vision.md completely.
    2. You are the executor. The decision-maker is a separate planning chat. Never decide PROPOSE items silently; put options, pros, cons and a recommendation in the phase report.
    3. Assume nothing. If anything is unclear, ask numbered questions and stop.
    4. Plan first, build in small steps, stay inside the current phase, stop at the end of the phase.
    5. GIT RULE: never run git add, commit, tag, push, merge, rebase, reset, stash, checkout, switch, restore or clean. Read-only git (status, diff, log, remote -v, branch --show-current) is fine. After each logical step, print explicit-path "git add" lines and a "git commit -m" line for the team lead to run if they choose.
    6. Honesty rules (master brief section 5, frontend vision section 11): no false statements in UI, code, docs or reports; neutral wording for simulated parts; provenance always recorded and reachable; "simulation results" wording; targets are not findings; potency is a model output; synthetic data only.
    7. Never write the words "first", "unique" or "novel" about a component. Never put external statistics in code, docs or UI; write [SOURCE NEEDED] instead.
    8. All maths is deterministic code. An LLM never computes or changes a number.
    9. Environment (Windows, PowerShell): use the venv's python by full path: %LOCALAPPDATA%\potencyguard\venv\Scripts\python.exe. Do not change the PowerShell execution policy. Write helper scripts in Python or PowerShell-compatible commands.
    10. OneDrive: the repo may sit inside OneDrive. Never create a venv inside the repo. dashboard/node_modules must be a junction to %LOCALAPPDATA%\potencyguard\dashboard-node_modules when the repo is inside OneDrive. Report any "file in use" or sync problem.
    11. Never commit secrets. Keys, tokens and .env files are git-ignored. If you find a secret in the repo, stop and report.
    12. Every phase ends with a report in docs/02-phase-reports/ (template in master brief section 11.1) and a plain-English summary in the final message. Then stop and wait for the next phase prompt.
    13. Archive each phase prompt text in docs/06-prompts/ at the end of the phase.

3.3 Create .gitignore in the repo root with EXACTLY these entries (plus short comment headers):
    # Python
    __pycache__/
    *.py[cod]
    .pytest_cache/
    .ruff_cache/
    *.egg-info/
    build/
    dist/
    # Virtual environments
    .venv/
    venv/
    env/
    # Node
    node_modules/
    dashboard/node_modules
    dashboard/dist/
    dashboard/.vite/
    # OS and editors
    Thumbs.db
    desktop.ini
    .DS_Store
    .vscode/
    .idea/
    # Secrets and keys
    .env
    *.env
    *.pem
    *.key
    keys/
    # Generated data and logs
    data/generated/
    data/runs/
    assets-raw/
    *.log
    *.db
    *.sqlite
    # Claude Code local settings
    .claude/settings.local.json
    (Note: "dashboard/node_modules" without a trailing slash is deliberate, so it also matches a junction.)

3.4 Print the suggested commit commands for this step.

---------------------------------------------------------------------
STEP 4. PYTHON ENVIRONMENT, PACKAGING, CONFIG, SHARED LOADER
---------------------------------------------------------------------
4.1 Create the virtual environment OUTSIDE the repo:
      Path: %LOCALAPPDATA%\potencyguard\venv   (in PowerShell: $env:LOCALAPPDATA\potencyguard\venv)
      Use Python 3.13.x from PATH.
    Always call the venv's python.exe by full path. Never activate scripts; never change the execution policy.
4.2 Check that pip can reach PyPI (for example, pip download of a tiny package into a temp folder outside the repo, or pip index). If not, STOP and report.
4.3 Install exactly: pytest, ruff, pyyaml. Then write requirements-dev.txt in the repo root listing the exact installed versions (== pins) of those three and nothing else (use pip freeze output filtered to those three plus any of their mandatory dependencies, and say which in a comment line).
4.4 Create pyproject.toml in the repo root with:
      [build-system]  requires = ["setuptools>=68"], build-backend = "setuptools.build_meta"
      [project]  name = "potencyguard", version = "0.0.0", description = "PotencyGuard prototype (SAP Hackfest 2026)", requires-python = ">=3.12"
      [tool.setuptools]  packages = ["shared", "simulator", "edge", "planner", "backend"]
      [tool.ruff]  line-length = 100, target-version = "py312", extend-exclude = ["dashboard"]
      [tool.ruff.lint]  select = ["E", "F", "I", "B", "UP"]
      [tool.pytest.ini_options]  testpaths = ["tests"]
    Then install the project in editable mode into the venv (pip install -e .). Do NOT install FastAPI, numpy, cryptography or pydantic yet.
4.5 Create config/product_default.yaml with EXACTLY these keys and values, with a header comment "Synthetic product parameters for an imaginary 2 to 8 C vaccine. Not real product data." and an "ASSUMPTION" comment on every value except Ea_over_R (source: USP default Ea 83.144 kJ/mol) and tau_max_h (source: 24 months at the reference temperature, from the project document):
      Ea_over_R: 10000
      T_ref_c: 5.0
      tau_max_h: 17520
      P_min: 0.90
      hard_limit_low_c: 0.0
      hard_limit_high_c: 40.0
      hard_limit_consecutive_samples: 2
      alpha: 0.95
      monte_carlo_n: 5000
4.6 Create shared/config.py:
      - class ConfigError(ValueError)
      - @dataclass(frozen=True) class ProductConfig with fields: Ea_over_R: float, T_ref_c: float, tau_max_h: float, P_min: float, hard_limit_low_c: float, hard_limit_high_c: float, hard_limit_consecutive_samples: int, alpha: float, monte_carlo_n: int
      - properties: k_ref_per_h = ln(1 / P_min) / tau_max_h ; T_ref_k = T_ref_c + 273.15
      - function load_product_config(path: Path | str | None = None) -> ProductConfig. With path None it loads config/product_default.yaml found relative to the repo root (locate the repo root from the file location, not from the current working directory).
      - Validation, each failure raising ConfigError with a message that names the key and the bad value, for example "P_min must be strictly between 0 and 1 (got 1.5)":
          * every key present (message lists the missing keys)
          * all numeric values are numbers (not strings or booleans)
          * 0 < P_min < 1
          * Ea_over_R > 0
          * tau_max_h > 0
          * hard_limit_low_c < T_ref_c < hard_limit_high_c
          * hard_limit_consecutive_samples is an integer >= 1
          * 0 < alpha < 1
          * monte_carlo_n is an integer >= 100
      - Type hints and a short docstring on each public item. No other behaviour.
4.7 Print the suggested commit commands for this step.

---------------------------------------------------------------------
STEP 5. PYTHON TESTS AND THE CHECKS SCRIPT
---------------------------------------------------------------------
5.1 Create tests/test_smoke.py with these tests (use pytest, tmp_path for temporary YAML files):
      - test_packages_import: import shared, simulator, edge, planner, backend.
      - test_default_config_loads: load_product_config() returns the nine values above; k_ref_per_h is approx 6.0137e-06 (pytest.approx with rel=1e-4); T_ref_k is approx 278.15.
      - test_invalid_p_min_raises: write a copy of the default YAML with P_min: 1.5 into tmp_path; ConfigError is raised and the message contains "P_min".
      - test_missing_key_raises: remove Ea_over_R from a copy; ConfigError message contains "Ea_over_R".
      - test_t_ref_outside_limits_raises: set T_ref_c: 45.0 in a copy; ConfigError is raised.
      - test_boolean_is_not_a_number: set alpha: true in a copy; ConfigError is raised.
5.2 Create scripts/run_checks.py:
      - Runs, in order, using the same python that runs the script (sys.executable -m ...): "ruff check .", "ruff format --check .", "pytest -q".
      - If dashboard/package.json exists AND dashboard/node_modules exists, also runs "npm run build" and "npm test" inside dashboard/ (find npm with shutil.which; on Windows it is npm.cmd).
      - Prints a clear PASS or FAIL line for each check and an overall summary; returns exit code 0 only if everything passed. Shows the tail of the output for any failing check.
      - Works when run from the repo root in PowerShell.
5.3 Run it with the venv python. Fix everything until it passes. (Dashboard checks will be skipped or run after step 6; say which.)
5.4 Print the suggested commit commands for this step.

---------------------------------------------------------------------
STEP 6. DASHBOARD SCAFFOLD AND WEBGL SMOKE TEST
---------------------------------------------------------------------
Purpose: prove this laptop can run smooth 3D with smooth scrolling before we invest in the cinematic frontend. The page is THROWAWAY: plain styling, no polish.

6.1 If MODE = B (repo inside OneDrive), do this FIRST, before creating any dashboard files:
    a. Create the folder $env:LOCALAPPDATA\potencyguard\dashboard-node_modules
    b. Make sure the repo's dashboard\ folder exists and contains no node_modules folder.
    c. Create a directory junction: dashboard\node_modules  ->  %LOCALAPPDATA%\potencyguard\dashboard-node_modules  (cmd /c mklink /J "<repo>\dashboard\node_modules" "%LOCALAPPDATA%\potencyguard\dashboard-node_modules").
    d. Confirm with (Get-Item dashboard\node_modules).LinkType that it says Junction.
    If MODE = A, skip 6.1.
    If anything in 6.1 fails, make at most 2 fix attempts, then SKIP the rest of step 6, write exactly what happened into the report, and continue to step 7. Never install node_modules as a real folder inside OneDrive.

6.2 Create a Vite + React + TypeScript project inside dashboard/ (use the official Vite react-ts template or write the minimal files yourself; do not overwrite dashboard/README.md, merge into it). npm scripts required: dev, build, test (vitest run). Add lint only if the template provides it.

6.3 Install dependencies with exact versions (npm install --save-exact). Before installing, check peer-dependency compatibility between React, three, @react-three/fiber, @react-three/drei and @react-three/postprocessing (for example with "npm view <pkg> peerDependencies") and choose mutually compatible latest-stable versions. Never use --force or --legacy-peer-deps; if you cannot resolve a conflict, STOP the step and report the conflict.
      runtime: three, @react-three/fiber, @react-three/drei, @react-three/postprocessing, gsap, lenis, zustand, d3-scale, d3-shape
      dev: typescript, vitest, @types/three, @types/d3-scale, @types/d3-shape
    Do NOT install Playwright, any UI kit, any chart library, any font package or any CSS framework.
    If MODE = B, after installing verify: (1) the packages are in the external folder; (2) count of real files inside the repo's dashboard folder excluding node_modules; (3) git status does not list node_modules. Report the numbers.

6.4 Build the smoke page. Required behaviour:
    Files (under dashboard/src/): main.tsx, App.tsx, smoke/SmokeScene.tsx, smoke/PerfOverlay.tsx, smoke/qualityTier.ts, smoke/qualityTier.test.ts, smoke/useQualityStore.ts, styles.css. Keep each file small and commented.
    Page and style:
      - Page title: "PotencyGuard: WebGL smoke test (scaffold only)".
      - Body background #04070D, no margin. The 3D canvas is fixed, full screen, behind everything. A transparent scroll spacer makes the page about 400vh tall.
    3D:
      - A procedural dotted sphere: points on a sphere using a Fibonacci distribution (no external assets), point colour #5DD6FF, small size with size attenuation, transparent, depthWrite off.
      - A slightly larger back-face sphere with a simple fresnel-style shader for a soft rim glow.
      - The sphere rotates slowly about the vertical axis (0.05 rad/s).
      - The camera moves from z = 6 (far) to z = 2.6 (near) as the page scrolls, driven by GSAP ScrollTrigger scrub through a plain progress value that the render loop reads.
    Smooth scroll:
      - Lenis smooth scrolling driven from GSAP's ticker (gsap.ticker.add with lenis.raf, gsap.ticker.lagSmoothing(0), lenis.on("scroll", ScrollTrigger.update)) so DOM scroll and the 3D camera stay in sync.
      - React StrictMode mounts effects twice in development: create everything in an effect and clean it up completely (destroy Lenis, kill ScrollTriggers, remove ticker callbacks).
    Quality tiers (qualityTier.ts, pure functions, no React):
      - export type QualityTier = "high" | "medium" | "low"
      - export interface TierSettings { dprCap: number; pointCount: number; bloom: boolean }
      - export function tierSettings(tier: QualityTier): TierSettings
            high:   dprCap 2,   pointCount 40000, bloom true
            medium: dprCap 1.5, pointCount 20000, bloom true
            low:    dprCap 1,   pointCount 8000,  bloom false
      - export function nextTierDown(tier): QualityTier   high -> medium -> low -> low
      - export function cycleTier(tier): QualityTier      high -> medium -> low -> high
      - export function effectiveDpr(devicePixelRatio: number, tier: QualityTier): number  = min(max(devicePixelRatio, 1), dprCap of the tier)
    Quality behaviour:
      - Zustand store (useQualityStore.ts) holds the tier (start at "high") with setTier, stepDown and cycle.
      - Use drei's PerformanceMonitor: when it reports a decline, step the tier down. NEVER step the tier up automatically. Key "Q" cycles tiers manually.
      - Bloom (from @react-three/postprocessing: EffectComposer and Bloom, luminanceThreshold about 0.2, intensity about 0.6) is mounted only when the tier's bloom is true.
    Overlay (bottom-left, small monospace text, colour #8FA3BF on a dark translucent box) showing: rolling-average FPS over the last 60 frames, the current tier, effective device pixel ratio, WebGL version, and the GPU renderer string read from the standard WEBGL_debug_renderer_info extension (show "unavailable" if absent). Update the overlay about 4 times per second from refs; do not trigger React state updates every frame.
    Resilience and accessibility:
      - If "prefers-reduced-motion: reduce" is set, turn off Lenis smoothing and the sphere rotation and keep the camera scroll movement simple.
      - Handle WebGL context loss: on "webglcontextlost" call preventDefault and show a calm message "3D paused, restoring..."; on "webglcontextrestored" resume. The page must never go blank.
      - If WebGL is unavailable, show a plain message "3D is unavailable on this device" and keep the overlay text.
      - No network calls of any kind: no CDN, no font download, no analytics, no remote textures.

6.5 Tests and build:
      - qualityTier.test.ts (Vitest) with these cases: nextTierDown("low") is "low"; nextTierDown("high") is "medium"; cycleTier goes high -> medium -> low -> high; tierSettings("low").bloom is false and tierSettings("high").bloom is true; pointCount is strictly decreasing from high to low; effectiveDpr never exceeds the tier cap, never goes below 1, and effectiveDpr(3, "high") equals 2.
      - Run npm test and npm run build until they pass. Report the production bundle sizes (the numbers Vite prints). Do not leave any dev server running when you finish.
      - Re-run scripts/run_checks.py with the venv python; it should now include the dashboard build and test.
6.6 Print the suggested commit commands for this step. (Reminder: node_modules is ignored and must not appear in any "git add" line; list package.json and package-lock.json explicitly.)

---------------------------------------------------------------------
STEP 7. REPORTS
---------------------------------------------------------------------
7.1 Write docs/02-phase-reports/phase-00-skeleton-report.md using the template in section 11.1 of the master brief (all 12 headings). It must also contain:
      - The pre-flight table from PART 2 (mode A or B, tool versions).
      - The exact commands to run the checks and to start the dashboard, written for a fresh PowerShell window.
      - Locations of the venv and of node_modules, versions of every installed package (Python and npm), and how they are pinned.
      - If MODE = B: the junction result and the file counts.
      - Production bundle sizes.
      - A section "Tooling I can see": names only of the skills, plugins and MCP tools available in this session.
      - A section "What I did NOT do" listing anything in this prompt you skipped or could not do, with the reason.
      - No placeholder statistics anywhere.
7.2 Print the suggested commit commands for this step.

---------------------------------------------------------------------
STEP 8. ARCHIVE THIS PROMPT (LAST FILE OPERATION)
---------------------------------------------------------------------
Write the full text of THIS prompt, exactly as you received it, to docs/06-prompts/phase-00-prompt.md. Print the suggested commit commands for this step, then the optional push and tag commands from amendment A1.

=====================================================================
PART 5. WHAT YOU MUST NOT DO
=====================================================================
- Do not run any state-changing git command (A1).
- Do not delete, rename or overwrite any file this prompt does not mention. If you find stray files, report them.
- Do not install anything not listed. Do not install global tools. Do not install plugins or MCP servers.
- Do not change the PowerShell execution policy or any system setting.
- Do not create a venv inside the repo. Do not create node_modules as a real folder inside OneDrive.
- Do not write feature code for later phases (no simulator, potency maths, signing, planner, API).
- Do not add external statistics, the words "first", "unique" or "novel", or any claim that simulated parts are real.
- Do not leave background processes running.
- Do not continue past a STOP condition. Report and wait.

=====================================================================
PART 6. ACCEPTANCE CRITERIA (check each one in the report)
=====================================================================
[ ] Pre-flight ran and found no STOP condition (or you stopped and reported).
[ ] docs/ layout exists; every folder has a README.md; the five Python packages have __init__.py.
[ ] The brief lives at docs/00-project-brief/master-brief.md with "Amendments v1.1 (approved 2026-10-20)" appended; the vision lives at docs/01-architecture/frontend-vision.md; no stray copies remain in the repo root.
[ ] README.md, CLAUDE.md and .gitignore exist with the specified content.
[ ] The venv is at %LOCALAPPDATA%\potencyguard\venv; requirements-dev.txt and pyproject.toml exist; the project is installed editable.
[ ] scripts/run_checks.py passes in a fresh PowerShell window (ruff, format check, pytest, and the dashboard build and test).
[ ] dashboard/ builds; npm test passes; the smoke page code exists as specified; no dev server left running.
[ ] If MODE = B: dashboard/node_modules is a junction to an external folder (or step 6 was stopped and reported).
[ ] git status (read-only) shows only the files this prompt created or moved; nothing is staged; nothing was committed.
[ ] The phase report exists and the prompt is archived in docs/06-prompts/.

=====================================================================
PART 7. FINAL MESSAGE FORMAT
=====================================================================
End with exactly these four items, in plain English:
1. SUMMARY: what exists now, how to see it, anything to worry about (no jargon).
2. COMMIT COMMANDS: every suggested commit block, in order, in the A1 format; then the optional push and tag commands.
3. HOW TO RUN: the exact PowerShell commands to run the checks and to start the dashboard smoke page (npm run dev), and what to look at in the overlay (FPS, tier, GPU string) and what to scroll.
4. OPEN QUESTIONS: numbered, or "None".
Then STOP. Do not start Phase 1.
