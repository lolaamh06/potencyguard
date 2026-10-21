# backend

- What lives here: the API, storage, audit log and the mock enterprise adapter (Phase 6). **No authentication.** Simulation on a synthetic box. The server binds to 127.0.0.1; do not expose it.
- Filled in by: Phase 6.
- Finding things:
  - `api.py`: the FastAPI app (start here); `service.py`: the logic (key registry, ingest and verification, recomputation, decisions, approvals, events).
  - `storage.py`: append-only SQLite (no update/delete function; triggers refuse them). `sap.py`: `SapAdapter`, the mock and an unimplemented sandbox stub. `replay.py`, `cli.py`: `python -m backend serve | replay | export-ledger`.
- Settings: `config/backend.yaml`. Design: `docs/03-decisions/decision-0010-backend.md`. Endpoints and PowerShell examples: `docs/01-architecture/api.md`.
- A device key must be registered before its ledgers are accepted; a public key sent with a ledger is ignored. Signing protects records after signing and does not stop a lie at the sensor, so the backend recomputes the physics checks from the signed readings.

```
$py = ".\.venv\Scripts\python.exe"   # run from the repo root after scripts\setup.ps1
& $py -m backend replay --all
& $py -m backend replay --recording data/recordings/hidden_spoilage.jsonl --at-hour 50 --tamper edit
& $py -m backend serve
```
