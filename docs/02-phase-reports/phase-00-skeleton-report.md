# Phase 0: Skeleton, toolchain and WebGL smoke test: Report

Date: 2026-10-20. Git commit hash: none (no commits yet; the team lead commits). Git tag: none yet (`phase-00-done` is optional).

`git status --short` at the time of writing: everything is untracked (`??`) and nothing is staged: `.gitignore`, `CLAUDE.md`, `README.md`, `backend/`, `config/`, `dashboard/`, `data/`, `docs/`, `edge/`, `planner/`, `pyproject.toml`, `requirements-dev.txt`, `scripts/`, `shared/`, `simulator/`, `tests/`.

## Pre-flight

| Check | Result |
|---|---|
| Working directory | `C:\Users\Lolaa M H\OneDrive\Desktop\potencyguard` (repo root, contains `.git`) |
| Mode | **B** (path contains "OneDrive") |
| Branch / remote | `main`; origin = `https://github.com/lolaamh06/potencyguard.git`; no commits yet |
| Stop conditions | none found (no `docs/`, no stale root files, no staged changes, no earlier "Amendments v1.1") |
| Python / Node / npm / Git | 3.13.5 / v22.17.1 / 10.9.2 / 2.52.0 |

## 1. What I was asked to do

Create the project skeleton: docs layout, amendments appended to the brief, READMEs, root files, a Python environment and config loader with tests, a checks script, and a throwaway Vite + React + TypeScript page that tests WebGL and smooth scrolling on this laptop. No feature code for later phases.

## 2. What I built

Documents
- `docs/00-project-brief/master-brief.md`: the brief (moved), with "Amendments v1.1 (approved 2026-10-20)" appended (A1 to A14).
- `docs/01-architecture/frontend-vision.md`: the frontend vision (moved).
- `docs/03-decisions/decision-0001-brief-amendments-v1-1.md`: plain-English record of A1 to A14.
- `docs/06-prompts/phase-00-prompt.md`: archive of this phase's prompt.
- `docs/02-phase-reports/phase-00-skeleton-report.md`: this report.
- A `README.md` in each of: `docs/00-project-brief`, `docs/01-architecture`, `docs/02-phase-reports`, `docs/03-decisions`, `docs/04-test-evidence`, `docs/05-demo`, `docs/06-prompts`, `config`, `shared`, `shared/test-vectors`, `simulator`, `edge`, `planner`, `backend`, `dashboard`, `scripts`, `tests`, `data`.

Root and Python
- `README.md`, `CLAUDE.md`, `.gitignore`: as specified.
- `pyproject.toml`: packaging (setuptools), ruff and pytest settings.
- `requirements-dev.txt`: pinned dev tools.
- `config/product_default.yaml`: synthetic product parameters.
- `shared/config.py`: validated loader (`ProductConfig`, `ConfigError`, `load_product_config`).
- `shared/__init__.py`, `simulator/__init__.py`, `edge/__init__.py`, `planner/__init__.py`, `backend/__init__.py`: empty.
- `tests/test_smoke.py`: 6 tests.
- `scripts/run_checks.py`: ruff, format check, pytest, then dashboard build and test.

Dashboard (throwaway smoke test)
- `dashboard/package.json`, `package-lock.json`, `tsconfig.json`, `vite.config.ts`, `index.html`.
- `dashboard/src/main.tsx`, `App.tsx` (Lenis + ScrollTrigger on one GSAP ticker, Q key), `styles.css`.
- `dashboard/src/smoke/SmokeScene.tsx` (dotted sphere, rim glow, scroll camera, bloom, context-loss guard), `PerfOverlay.tsx`, `qualityTier.ts`, `qualityTier.test.ts`, `useQualityStore.ts`.

## 3. How to run it

Fresh PowerShell window in the repo root:

```powershell
& "$env:LOCALAPPDATA\potencyguard\venv\Scripts\python.exe" scripts\run_checks.py
cd dashboard
npm run dev
```

Then open http://localhost:5173. Stop the server with Ctrl+C.

## 4. How to check it works

- Checks script: expect five `PASS:` lines (ruff check, ruff format --check, pytest, dashboard build, dashboard test) and `Summary: 5 passed, 0 failed`.
- Smoke page: a glowing dotted sphere on a dark background. Scrolling moves the camera closer. The bottom-left overlay shows FPS, Tier, DPR, WebGL version and GPU. Press Q to cycle high, medium, low.

## 5. Test results

- `run_checks.py`: 5 passed, 0 failed.
- pytest: 6 passed, 0 failed, 0 skipped.
- Vitest: 5 passed, 0 failed, 0 skipped.
- Dev server: served the page with HTTP 200 and the correct title on port 5173; stopped afterwards, port is free.
- Not tested: the page was not opened in a browser by me (the Playwright browser tools failed to connect in this session), so FPS, smoothness and the visual look are **unverified** until the team lead looks at it.

## 6. What is real and what is simulated in this phase

Real: the config loader and its tests, the checks script, the tier logic and its tests, the 3D page code. Nothing in this phase is simulated product behaviour; there is no sensor, potency, signing, planner or SAP code yet. The sphere is a stylised procedural object, not a model of anything.

## 7. Decisions I made and why

1. **Junction target.** The prompt says the junction points at `%LOCALAPPDATA%\potencyguard\dashboard-node_modules`. That did not work: Node follows the junction to its real folder and then looks for packages in a folder named `node_modules` above it, so `tsc` and `vitest` failed. I made the target `%LOCALAPPDATA%\potencyguard\dashboard-node_modules\node_modules` instead. CLAUDE.md rule 10 and README step 4 still name the shorter path; I left them as the prompt said "exactly" (see open question 1).
2. **Installing around the junction.** `npm install` replaces a junction with a real folder (it logged "Removing non-directory"). For a moment a real `node_modules` existed inside the OneDrive folder. I installed into a real folder, moved it to the external location and re-created the junction. Future installs need the same steps (written in `dashboard/README.md`).
3. **Dependencies of the dev tools.** `requirements-dev.txt` pins the three requested packages plus their five mandatory dependencies (colorama, iniconfig, packaging, pluggy, Pygments), as the prompt allowed.
4. **Template packages.** I wrote the Vite files by hand and added `vite`, `@vitejs/plugin-react`, `@types/react` and `@types/react-dom` (the contents of a react-ts template) because the page cannot build without them. `react-dom` is needed with React. `postprocessing` is a required peer of `@react-three/postprocessing`.
5. **Build script.** `npm run build` runs `tsc --noEmit` (strict) and then `vite build`.
6. **Governor.** drei `PerformanceMonitor` with only `onDecline` wired, so the tier never steps up by itself. It could step down early during the initial load; Q cycles tiers manually.
7. **Reduced motion.** Lenis is not created and the sphere does not rotate; the camera moves only 30% of the normal distance.
8. No PROPOSE items were needed in this phase.

## 8. Assumptions introduced

- `config/product_default.yaml` carries ASSUMPTION comments on T_ref_c, P_min, both hard limits, `hard_limit_consecutive_samples`, `alpha` and `monte_carlo_n`. `Ea_over_R` and `tau_max_h` cite their sources as the prompt asked.
- All product parameters are for an imaginary product.
- Point size 0.012, rim glow strength 0.7, bloom threshold 0.2 and intensity 0.6 are unverified visual guesses for the throwaway page.

## 9. Problems and surprises

- npm replaced the junction (decision 2) and the first install into the junction was incomplete (missing `std-env` and a TypeScript platform package). A clean install fixed it.
- The Node module resolution issue with the junction (decision 1).
- `pip` prints a notice that a newer pip exists (25.1.1 to 26.2.1); I did not upgrade it.
- Vite warns that the JS chunk is over 500 kB (three.js and friends); not addressed in a throwaway page.
- `ruff format` reformatted one line in `shared/config.py`.
- The Playwright MCP server failed to connect ("Connection closed"); I did not try to fix or install it.
- Git Bash/PowerShell: `npm` writes some progress text to stderr, which PowerShell shows as an error banner even when the command succeeds.

## 10. Versions pinned and bundle size

Python (venv at `%LOCALAPPDATA%\potencyguard\venv`, Python 3.13.5; pins in `requirements-dev.txt`): pytest 9.1.1, ruff 0.17.1, PyYAML 6.0.3, colorama 0.4.6, iniconfig 2.3.1, packaging 26.3, pluggy 1.7.0, Pygments 2.21.0. The project itself is installed in editable mode (`potencyguard` 0.0.0).

npm (exact versions in `dashboard/package.json`, lock file `package-lock.json`):
- Runtime: react 19.3.1, react-dom 19.3.1, three 0.186.1, @react-three/fiber 9.8.2, @react-three/drei 10.7.9, @react-three/postprocessing 3.2.1, postprocessing 6.39.5, gsap 3.15.0, lenis 1.3.27, zustand 5.0.15, d3-scale 4.0.2, d3-shape 3.2.0.
- Dev: typescript 7.0.2, vitest 5.0.5, vite 8.3.4, @vitejs/plugin-react 6.1.2, @types/react 19.3.0, @types/react-dom 19.3.0, @types/three 0.186.0, @types/d3-scale 4.0.9, @types/d3-shape 3.2.0.
- Why these: fiber 9.8.2 needs react `>=19 <19.4` and three `>=0.156`; drei 10.7.9 needs react `^19`, fiber `^9`, three `>=0.159`; postprocessing 3.2.1 needs react `^19`, fiber `>=9.7.0`, postprocessing `^6.36`; vite 8.3.4 needs Node `^20.19 || >=22.12` (we have 22.17.1); plugin-react 6.1.2 needs vite `^8`. All are the latest stable at install time. No `--force` or `--legacy-peer-deps`.

Production build (`npm run build`): `dist/index.html` 0.43 kB (gzip 0.29); `dist/assets/index-*.css` 0.64 kB (gzip 0.34); `dist/assets/index-*.js` 1,354.30 kB (gzip 384.48).

Junction (MODE B): `dashboard\node_modules` is a Junction to `%LOCALAPPDATA%\potencyguard\dashboard-node_modules\node_modules`. Real files in `dashboard\` excluding `node_modules` and `dist`: 14 (before `dist` is built). `git status` lists no `node_modules` and no `dist`; `git check-ignore` confirms both are ignored.

## 11. Tooling I can see (names only; nothing installed)

Skills: frontend-design:frontend-design, dataviz, artifact-design, artifact-diagramming, artifact-capabilities, update-config, keybindings-help, code-review, simplify, fewer-permission-prompts, loop, schedule, claude-api, run, plugin-authoring, init, security-review, anthropic-skills:built-in-browser, anthropic-skills:chrome-browser, anthropic-skills:computer-use, anthropic-skills:deep-research, anthropic-skills:docs, anthropic-skills:docx, anthropic-skills:google-workspace, anthropic-skills:import-memory, anthropic-skills:morning, anthropic-skills:pdf, anthropic-skills:pptx, anthropic-skills:skill-creator, anthropic-skills:xlsx.

MCP tools: claude_ai_Claude_Docs (batch, guide, update, create, delete, export, query, read), claude-vscode (getDiagnostics). Configured but **failed to connect**: plugin:playwright:playwright.

Other tools in the session: Agent, Artifact, AskUserQuestion, Bash, Edit, Glob, Grep, PowerShell, Read, Write, WebFetch, WebSearch and scheduling/notification tools.

## What I did NOT do

- Did not open the smoke page in a browser or take screenshots (Playwright failed to connect). FPS and visual quality are unverified.
- Did not run any state-changing git command.
- Did not update CLAUDE.md or README step 4 for the junction target change (the prompt said exact content).
- Did not upgrade pip.
- Did not check a 30-minute memory soak or context-loss restore behaviour (code written, not exercised).

## 12. Extra files beyond the prompt, and why

- `dashboard/package.json`, `package-lock.json`, `tsconfig.json`, `vite.config.ts`, `index.html`: required for a Vite project; the prompt named `vite.config`-style needs only implicitly (step 6.2).
- No other extra files in the repo. One working file (`amendments.md`) was written to the session scratchpad outside the repo.
- `.claude/` already existed before this phase and is untouched.

## 13. Open questions for the decision-maker

1. Should CLAUDE.md rule 10 and README step 4 be updated to the working junction target (`...\dashboard-node_modules\node_modules`) and to mention that `npm install` breaks the junction?
2. Is a 1.35 MB (384 kB gzip) JS bundle acceptable for later phases, or should code-splitting be planned in F2?
3. Should the Playwright MCP connection be fixed before F1, since the vision's review loop depends on screenshots?
4. The prompt sets `requires-python = ">=3.12"` and ruff `target-version = "py312"` while the environment is 3.13.5; is that intended? (I followed the prompt.)

## 14. Suggested next phase

Phase 1 (box simulator and scenario recordings) and Phase F1 (art direction) can start in parallel. Before them, the team lead should run the smoke page and report FPS, tier and GPU string, so the decision-maker knows whether 3D quality targets are realistic on this laptop. Not started.
