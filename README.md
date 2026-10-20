# PotencyGuard

## What it is

PotencyGuard is a software-first entry for SAP Hackfest 2026 (Theme: Resilient Supply Chains) about cold-chain medicines. A small edge program computes how much potency a shipment has left, checks that sensor readings obey physics, and signs every record into a tamper-evident chain. A cloud layer chooses an action by minimising worst-case loss and sends risky cases to a human for approval.

## Status

Phase 0: project skeleton and toolchain only. No product features yet.

## What is real and what is simulated

| Part | Status |
|---|---|
| Potency maths, thermal twin, detectors | Real code (from Phases 2 and 3) |
| Ed25519 signing, hash chain, verification | Real code (from Phase 4) |
| CVaR planner, governance rules | Real code (from Phase 5) |
| Backend API, storage, audit log | Real code (from Phase 6) |
| Dashboard (Story and Control Room) | Real code (from Phases F1 to F6) |
| Temperature, humidity and shock feed | Simulated by a physics-based box simulator |
| Shipments, forecasts, delays, attacks | Simulated (synthetic) |
| SAP endpoint | Mock until a sandbox API is confirmed |
| Raspberry Pi | Not yet available; Pi port is Phase 11 |

All data is synthetic. Potency is a model output for an imaginary product.

## Set up on Windows (PowerShell)

Open a fresh PowerShell window in the repo root.

1. Create the Python environment outside the repo (it lives under your local app data folder):
   `python -m venv "$env:LOCALAPPDATA\potencyguard\venv"`
2. Install the Python tools:
   `& "$env:LOCALAPPDATA\potencyguard\venv\Scripts\python.exe" -m pip install -r requirements-dev.txt`
3. Install the project itself in editable mode:
   `& "$env:LOCALAPPDATA\potencyguard\venv\Scripts\python.exe" -m pip install -e .`
4. Dashboard dependencies. If the repo is inside OneDrive, first make `dashboard\node_modules` a junction to `%LOCALAPPDATA%\potencyguard\dashboard-node_modules` (see CLAUDE.md, rule 10), then:
   `cd dashboard`
   `npm install`

## Run the checks

`& "$env:LOCALAPPDATA\potencyguard\venv\Scripts\python.exe" scripts\run_checks.py`

## Run the dashboard smoke test

`cd dashboard` then `npm run dev`. Open the printed local address (http://localhost:5173), scroll, and press Q to cycle the quality tier.

## Folder guide

- `config/`: tunable parameters (YAML)
- `shared/`: shared code (config loader) and `test-vectors/` for numeric tests
- `simulator/`: box simulator (Phase 1)
- `edge/`: edge program (Phases 2 to 4)
- `planner/`: decision planner and governance (Phase 5)
- `backend/`: API, storage, mock SAP adapter (Phase 6)
- `dashboard/`: Story and Control Room (Phase 0 smoke test; F1 to F6)
- `scripts/`: helper commands
- `tests/`: automated tests
- `data/`: synthetic data only
- `docs/`: brief, architecture, phase reports, decisions, evidence, demo notes, prompt archive

## Honesty note

The dashboard is planned as a cinematic 3D experience and is not built yet; only a throwaway WebGL test page exists. Simulated parts are documented here and in the phase reports. Targets are never presented as results.
