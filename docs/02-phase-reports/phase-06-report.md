# Phase 6: backend API, storage, audit log, mock enterprise adapter: Report

Date: 2026-10-21. Git commit hash and tag: none yet (the team lead commits). Simulation on a synthetic box. Not real-world evidence. **There is no authentication in this phase.** Signing protects records after signing and does not stop a lie at the sensor (A18). All money values, probabilities and thresholds are illustrative placeholders, not sourced [SOURCE NEEDED].

## 1. What I was asked to do

Build the backend: an API that registers device keys, ingests signed ledgers, verifies them against the REGISTERED key, stores everything append-only, runs the Phase 5 planner on verified data, handles human approvals, keeps an API audit log, and talks to an enterprise system only through a mock adapter. Plus a headless replay flow and a tamper demonstration through the API.

## 2. What I built

- `backend/storage.py`: one SQLite file, 13 append-only tables, triggers refuse UPDATE and DELETE, no update/delete function.
- `backend/service.py`: key registry, ingest and verification, recomputation of the physics checks, decisions, approvals, events, provenance.
- `backend/api.py`: the FastAPI app (strict pydantic models, clean errors, an audit middleware). `backend/sap.py`: `SapAdapter`, `MockSapAdapter`, `SandboxSapAdapter`. `backend/replay.py`, `backend/cli.py`: `python -m backend serve | replay | export-ledger`.
- `config/backend.yaml`, `scripts/check_phase6.py` (the eighth check), `tests/test_backend.py`.
- Docs: decision 0010 (written before the code), `docs/01-architecture/api.md`, this report, READMEs, the prompt archive.
- Nothing in `edge/`, `planner/`, `shared/` or `simulator/` was changed, and no existing test was edited.

**Installed versions (pinned in `requirements-dev.txt`; fastapi, uvicorn, httpx also in `pyproject.toml`):** fastapi 0.156.4, uvicorn 0.54.0, httpx 0.28.1; mandatory dependencies starlette 1.9.0, annotated-doc 0.0.5, anyio 4.15.1, certifi 2026.10.19, click 8.5.0, h11 0.16.0, httpcore 1.0.9, idna 3.20, opentelemetry-api 1.45.1. No `npm` command was run.

## 3. How to run it

```
$py = "$env:LOCALAPPDATA\potencyguard\venv\Scripts\python.exe"
& $py -m backend replay --recording data/recordings/reefer_failure.jsonl --at-hour 20
& $py -m backend replay --recording data/recordings/hidden_spoilage.jsonl --at-hour 50 --tamper edit
& $py -m backend replay --all
& $py -m backend serve            # http://127.0.0.1:8765, no authentication
```

An `Invoke-RestMethod` walk-through against the running server is in `docs/01-architecture/api.md` (I ran it against a live server on a spare port: register, create, ingest, decide, shipment view, audit, provenance all worked).

## 4. How to check it works

`& $py scripts\run_checks.py` prints `Summary: 8 passed, 0 failed`. The eighth check registers a throw-away key, posts a good ledger (auto-approved, one mock event) and a tampered one (rejected, quarantined, decision refused), checks that the database refuses a DELETE and that the sandbox adapter is a stub, and compares the golden hashes.

## 5. Test results

Baseline before the phase: 7 of 7 checks, 683 tests. Now: **8 of 8 checks, 739 tests** (56 new, all in `tests/test_backend.py`). They cover: registration, duplicates, a key used by two devices, revocation as a new row, a ledger received after revocation rejected; a good ledger verified; edit, delete, reorder, re-sign, and a copied key id each rejected at the right entry and reason; a ledger signed by an unregistered key rejected although internally consistent; a public key shipped with the ledger ignored; truncation passing without an anchor and caught with one; a later shorter or different ledger rejected as a history conflict; signed values that differ from the recomputation flagged and sent to a person; trusted recordings auto-approved where Phase 5 did; untrusted data never auto-approved even with thresholds of 10^12; close-call routing (and its relative-difference rule, including a zero CVaR); human resolution as a new record with the original bytes untouched, short or inconsistent reasons rejected, double resolution refused; events only on auto-approval or human resolution; no update/delete function and the database refusing UPDATE and DELETE on every one of the 13 tables; status history kept in order; an audit row for every state-changing call including 409, 404 and 422; a plain 500 with no internal detail; clean errors for 12 kinds of bad input; paging; provenance and health; adapter selection (mock by default, sandbox answers 501, source scan: no "http", no address, no credential, no false wording); config validation; binding to 127.0.0.1; golden files and chain vectors unchanged; no key file or PEM block in the repo; replay for three recordings, for each of the five tamper options and for `--all`; the export command.

**Tests changed:** none (no existing test was edited).

## 6. What is real and what is simulated

The API, storage, verification and audit log are real code. All data are simulated recordings; `source` stays "sim". The enterprise adapter is a mock; nothing is sent anywhere. There is no authentication.

## 7. Decisions and PROPOSE items

Decision note 0010 was written before the code. Choices to confirm:
- **P1** An ingest that verified or failed always returns 200 with `chain_status`; the rejected ledger is stored (not a transport error).
- **P2** Revocation: ledgers RECEIVED after the revocation are rejected; earlier data stay but are marked and any decision on them needs a person. The device clock is not trusted and a record's `t_ms` is time since the start of a run, so "signed after revocation" cannot be known; the backend uses its own receipt time. If the key was compromised before it was revoked, data stored earlier may still be forged.
- **P3** The backend recomputes the physics checks from the signed readings and plans from the recomputed values; the signed derived values are only compared (A18).
- **P4** After a person resolves a quarantined shipment the status becomes `human_resolved`; nothing is released automatically.
- **P5** (found while building) If the latest submission is rejected, decisions are refused until a valid ledger that extends the stored one arrives; a rejected tail cannot be bypassed by deciding on the older verified ledger.
- **Near-tie rule (Step 6):** done in the BACKEND layer. The planner code is unchanged, so no planner change, no decision-note change to the planner and no brief amendment were needed. The same layer adds two further stricter-only rules (claims differ from the recomputation; key revoked).

## 8. Assumptions and unverified claims introduced

Placeholders, not sourced [SOURCE NEEDED]: `close_call_percent` 5.0; the page sizes; the port 8765. Nothing numeric about the world was added.

## 9. Problems, surprises, omissions

- Starlette's test client prints a deprecation warning that recommends another package (`httpx2`). Only fastapi, uvicorn and httpx were allowed, so the warning is filtered in code; it is harmless.
- fastapi 0.156.4 has `opentelemetry-api` as a mandatory dependency, so it is pinned too.
- A first live-server try returned `wrong_device`: the ledger was signed for the default device id `pg-sim-001` but registered as `pg-live-1`. That is the backend working (the device id in every record must match the shipment's device); the example now passes `--device-id`.
- A replay with `--at-hour` posts a prefix of the ledger without its anchor (the anchor names the last entry).
- Omitted: authentication and roles; a key enrolment process; a real enterprise-system call (and any chosen interface); a long-running scheduler; rate limiting; a user interface (Phase F1); database migrations. `GET` calls are not audited. The server keeps one connection behind a lock, which is enough for a demo, not for load.

## 10. Numbers measured

`replay --all` (seed 20261021, as in Phase 5): baseline_ok, door_open_excursion, reefer_failure and heatwave_transit are verified and auto-approved (continue, continue, reroute_to_depot, reroute_to_depot; four mock events); spoof_attempt and hidden_spoilage are verified (the chain is intact) but untrusted by the physics checks, so the shipment is `quarantined_pending_review` and the decision needs a person (hidden_spoilage is also flagged as a close call: continue and re_source differ by 1,710 in CVaR, 3.4 percent of the best). `replay --tamper edit` on `hidden_spoilage`: rejected (bad_signature at entry 288), shipment quarantined, decision refused with 409, zero events. Tests: 739 passed.

## 11. Can say / must not say (slides)

Can say (simulation, synthetic data):
1. Device keys are registered first; a ledger is only accepted if its whole chain verifies against the registered key.
2. A tampered ledger (edit, deletion, reorder, another key) is rejected, stored as rejected with the first broken entry, the shipment is quarantined and no decision is made from it.
3. The backend does not take the device's word for its own results: it recomputes the potency and tamper checks from the signed readings.
4. Every decision and every human decision is signed and chained; a person's decision is a new record, never an edit.
5. Every state-changing API call is written to an audit log, including refused ones.
6. Events go to the enterprise system only for an auto-approved or human-resolved decision, through one adapter interface; today that adapter is a mock.
7. The planner's near-ties go to a person.

Must NOT say: that it is connected to an enterprise system or that any real interface was chosen; that the API is secure or has access control (there is none); that a signed record is true because it is signed; that the backend can tell when an entry was signed; that removing the end of a first-submitted ledger is always detected; that a revoked key's earlier data are known to be good or bad; that these results describe real shipments.

## 12. Open questions for the decision-maker

1. P1: is "200 with a stored `rejected`" the status code you want for a tampered ledger (alternative: 409)?
2. P2: should revoking a key quarantine everything it ever signed (safer, more disruptive), instead of marking earlier data?
3. P5: is it right that a rejected latest ledger blocks decisions until a valid extension arrives?
4. The registration endpoint is unauthenticated: when should real enrolment (and QA identity) be added, before the frontend or after?
5. Should `GET` calls be audited too?
6. The database default is `data/runs/backend.sqlite`; keep a single file for the long-running server, or one per day?

## 13. Suggested next phase (not started)

Phase F1 (the frontend) can read everything through this API. Before any exposure beyond localhost: authentication, a real key enrolment process, and a decision on the enterprise interface.
