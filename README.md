# PotencyGuard

PotencyGuard is a software prototype for SAP Hackfest 2026 (theme: resilient supply chains) about medicines that must stay cold on their way to a clinic. Sensors in a shipping box report the temperature; the system works out how much strength the medicine still has, checks that the readings obey the laws of physics, signs every record so later changes are detected, and recommends an action (carry on, send to the nearest depot, hold for review and so on). A person makes the final decision when the data cannot be trusted. The front end lets you watch five sample journeys, read the recommendation in plain words, try the approval buttons and see what happens when a signed record is changed.

**Honest limits.** Everything is a simulation on a synthetic box: the temperature readings come from a simulator, the medicine and its costs are imaginary, and no real shipment, patient or company is involved. The enterprise (SAP) system is a demo stand-in that sends nothing anywhere, the backend has no authentication, and signing protects records after they are signed but does not stop a false sensor reading from being signed.

## Requirements

- Windows 10 or 11 with PowerShell (the one that comes with Windows is fine).
- Git for Windows.
- Python 3.11 or newer (python.org, "Windows installer"; tick "Add python.exe to PATH").
- Node.js 22.12 or newer (nodejs.org, the LTS version; it includes npm).

## Quick start

Open PowerShell in the folder where you want the project, then:

```powershell
git clone <the repository address you were given>
cd potencyguard
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
powershell -ExecutionPolicy Bypass -File scripts\run-demo.ps1
```

Open http://127.0.0.1:4173 in your browser. `setup.ps1` takes a few minutes the first time and is safe to run again. `run-demo.ps1` builds the dashboard if needed and serves it on your own computer only; press Ctrl+C to stop. Add `-Dev` for the development server (port 5173) or `-Backend` to also start the backend API.

**What to click first**
1. On Home, press "Try the demo", then open the card marked "Start here".
2. Press Play (or Fast) and watch the chart, the strength gauge and the sentences under "What happened".
3. Follow the "Next step" buttons: Decisions, then Proof, then About this data.
4. Try the Simple / Technical and Light / Dark switches at the top, and Help for a short tour.

## Checks and commands

Run these from the repo root. `$py` is the Python in the project's own environment.

```powershell
$py = ".\.venv\Scripts\python.exe"
powershell -ExecutionPolicy Bypass -File scripts\check.ps1   # all checks (a few minutes)
& $py -m backend serve                                       # the backend API on http://127.0.0.1:8765
& $py -m backend replay --all                                # drive the API with the sample recordings
& $py -m edge run --recording data/recordings/hidden_spoilage.jsonl   # edge runner: writes a signed ledger to data/runs
& $py -m planner demo                                        # the decision planner on the demo checkpoints
& $py scripts\tamper_demo.py <ledger file> all               # change a COPY of a ledger and verify it
& $py -m simulator generate --all                            # regenerate the golden recordings
```

`scripts\run_checks.py` is what `check.ps1` runs: ruff, the format check, the Python tests, three project checks and the dashboard build and tests.

## Project map

| Folder | What it holds |
|---|---|
| `simulator/` | The box simulator that makes the sample temperature data. |
| `edge/` | The edge program: potency maths, the thermal model and detectors, signed records and the hash chain. |
| `planner/` | The decision planner (worst-case cost) and the rules that send cases to a person. |
| `backend/` | The API, append-only storage, audit log and the demo stand-in for the enterprise system. |
| `dashboard/` | The front end (React, three.js): product pages and the scroll Story. |
| `shared/` | Shared code and `test-vectors/`, the numeric test cases used by both Python and TypeScript. |
| `config/` | Tunable parameters in YAML. |
| `data/` | Synthetic data only: golden recordings and calibration recordings. |
| `scripts/` | Setup, run and check scripts, exporters and evaluation tools. |
| `tests/` | The automated tests. |
| `docs/` | The brief, architecture notes, phase reports, decision notes and screenshots. See `docs/README.md`. |

## Troubleshooting

- **"Running scripts is disabled on this system."** Use the commands above with `-ExecutionPolicy Bypass`, or allow scripts for this window only: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`. This changes nothing permanent.
- **"Python was not found" (or the Microsoft Store opens).** Install Python from python.org and tick "Add python.exe to PATH", then open a new PowerShell window. If the Store opens, turn off the "python.exe" app execution alias in Windows Settings, Apps, Advanced app settings, App execution aliases.
- **Node is too old or missing.** Install the current LTS from nodejs.org (22.12 or newer), then open a new PowerShell window. Check with `node --version`.
- **"Port 4173 is already in use."** An earlier run is still going. Close its window (Ctrl+C), or choose another port: `scripts\run-demo.ps1 -Port 4200`.
- **The project folder is inside OneDrive and things are slow or fail.** OneDrive tries to sync the large `node_modules` and `.venv` folders. Clone the repo outside OneDrive (for example `C:\dev\potencyguard`), or pause syncing while you run `scripts\setup.ps1`.

## Rules for teammates

- Work on a branch and make small commits. Run `scripts\check.ps1` before you push.
- Never commit `data/runs/`, keys, `.venv`, `node_modules` or `dist` (they are git-ignored; keep it that way).
- Private signing keys live outside the repo, under `%LOCALAPPDATA%\potencyguard\keys`. Never copy one into the repo.
- Do not edit the golden recordings in `data/recordings/` or the files in `shared/test-vectors/`; a test checks them byte for byte.
- Install dashboard packages with `npm ci`, never `npm install` (it can change `package-lock.json`). `scripts\setup.ps1` already does this.
- Keep the honesty rules: everything on screen is simulated or sample data, figures come from the project's own code, and no outside statistics go in code or docs.

## Where to read more

- `docs/00-project-brief/master-brief.md`: what we are building and why, and the honesty rules.
- `docs/01-architecture/frontend-vision.md`: the front-end vision (with amendments) and `design-system.md`.
- `docs/01-architecture/api.md`: the backend endpoints with PowerShell examples.
- `docs/01-architecture/signed-record-format.md`: the exact rules for signed records.
- `docs/02-phase-reports/`: one report per phase, newest last.
