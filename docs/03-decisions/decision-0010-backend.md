# Decision 0010: the backend (API, storage, audit log, mock enterprise adapter)

Status: design written BEFORE the code (Phase 6). Simulation only, on a synthetic box. Signing protects records after signing and does not stop a lie at the sensor (A18): the backend therefore recomputes the physics checks from the signed readings and plans from the recomputed values, never from a signed claim alone. There is NO authentication in this phase (section 4). Every money value, probability, delay and threshold is an illustrative placeholder, not sourced [SOURCE NEEDED].

## 1. Interfaces it builds on (read from the code)

- `edge.chain`: `Entry`, `Anchor`, `verify_chain(entries, public_key, anchor, device_id)` (reused, not reimplemented), `parse_canonical` for the Phase 4 record, `key_id_of`.
- `edge.runner`/`edge.assessment`: `TrustAssessor` (potency tracker + tamper monitor + bound) gives potency, trust level and verdict from readings.
- `planner`: `PlannerConfig`, `plan()`, `build_decision()`, `build_task()`, `record_human_decision()`, `DecisionLog` / `verify_decision_log` (schema `pg-decision/1`), `build_inputs()` (the existing pipeline from a recording up to an hour). The planner code is NOT changed.
- A Phase 4 signed entry is stored unchanged: seq, canonical bytes, signature, hash, key id.

## 2. Storage

One SQLite file under `data/runs/` (git-ignored), standard `sqlite3`, no ORM. Every table is append-only: the module has no update/delete function and a trigger on every table aborts UPDATE and DELETE (as in Phase 4: a guard against mistakes in the program, not a defence against someone with file access; signatures and chains are that defence). Tables:

| table | holds |
|---|---|
| `shipments` | id, label (scenario/run), device id, origin (replay or live), scheduled duration, created time |
| `shipment_status_history` | every status as a NEW row: created, active, quarantined_pending_review, human_resolved; with a reason |
| `device_keys` | device id, key id, public key, registered time, registered by, status `active` or `revoked`; revocation is a new row |
| `ledger_submissions` | one row per ingest: result `verified` or `rejected`, first broken index, reason, detail, anchor flags, the RECOMPUTED latest potency, trust level, verdict and whether the signed claims matched |
| `entries`, `anchors` | the Phase 4 entries and anchors of every submission, unchanged |
| `decision_entries`, `decision_anchors` | the Phase 5 decision log (decisions and human decisions), unchanged format, one chain for the backend |
| `decisions` | an index of each decision (seq, shipment, chosen action, route, close-call flag) |
| `approval_tasks`, `approval_resolutions` | open human tasks (with the potency curve) and how each was resolved |
| `sap_events` | each dispatched event and its acknowledgement |
| `api_audit` | the API audit log |

## 3. Trust model for keys

- The backend never trusts a public key that arrives with a ledger. A device key must first be REGISTERED through `POST /devices/register` (demo operator; unauthenticated, see section 4). Ingest looks up the key id claimed by the entries and uses the REGISTERED public key for that device. A public key supplied in an ingest request is ignored (and said to be ignored).
- Ingest runs `verify_chain` on the whole ledger and on the anchor if present. A ledger that fails is stored as REJECTED with the first broken index and reason; it is excluded from decisions and its shipment is set to `quarantined_pending_review`. Additional backend reasons: `unregistered_key`, `key_revoked`, `mixed_keys`, `empty`, `history_conflict`.
- `history_conflict`: a later submission for a shipment must extend the last VERIFIED one (the first entries identical). A shorter or different ledger is rejected. This catches tail truncation of a previously stored ledger even without an anchor; a truncated first submission still passes without an anchor (Phase 4 limit).
- Recomputation (A18): from the verified readings the backend re-runs the potency tracker and tamper monitor (the existing edge code) and stores the recomputed potency, trust level and verdict. If the signed record claims different values, the claim is flagged `claims_consistent = false` and the next decision goes to a person with the shipment quarantined. Planning uses the recomputed values.
- Revocation. `POST /devices/{id}/revoke` appends a `revoked` row. What "after revocation" can and cannot mean: the device clock is not trusted and the record time `t_ms` is time since the start of a run, not wall-clock time, so the backend cannot tell when an entry was signed. It uses its OWN clock: a ledger RECEIVED after the revocation time is rejected as `key_revoked`; ledgers received before stay stored but are marked, and a decision on data from a revoked key always needs a person. If the key was compromised before the revocation, data stored earlier may still be forged; the backend cannot know.

## 4. No authentication (stated plainly)

This phase has no authentication or authorisation. Anyone who can reach the port can register a key, ingest, decide and resolve. Caller names (`X-Caller` header) and QA identities (`who`) are plain unauthenticated strings recorded in the audit log. The server binds to 127.0.0.1 by default. Do not expose it. Real access control, a key registry with proper enrolment, and QA identity are out of scope.

## 5. API

JSON only, strict pydantic models (extra fields forbidden), no stack traces in responses (errors: `{"error": code, "message": text}`).

| method and path | purpose |
|---|---|
| `POST /devices/register`, `POST /devices/{id}/revoke`, `GET /devices` | key registry |
| `POST /shipments`, `GET /shipments`, `GET /shipments/{id}` | shipments; the view has the latest recomputed potency, trust, verdict, chain status, latest decision, status history |
| `POST /shipments/{id}/ledger` | ingest entries (+ optional anchor), verify, store; always 200 with the stored result (accepted or rejected) |
| `GET /shipments/{id}/readings` (paged), `GET /shipments/{id}/verify` | readings of the latest verified ledger; re-verify the stored chain now |
| `POST /shipments/{id}/decide` | run the Phase 5 planner on the latest verified data; sign and store; refuse (409) on a rejected or missing ledger |
| `GET /shipments/{id}/decisions`, `GET /approvals`, `POST /approvals/{task}/resolve` | decisions; open human tasks; approve / override / reject (reason of at least 10 characters), appended as a NEW record referencing the original |
| `GET /audit` (paged), `GET /provenance/{id}`, `GET /health` | audit log; where the data came from; liveness |

Every POST writes an audit row (time, endpoint, caller label, shipment id, outcome), including refused and invalid calls (a middleware does this, so validation failures are included). Reads are not audited.

## 6. Decisions and the near-tie rule

`decide` rebuilds the planner inputs with the existing `planner.pipeline.build_inputs` (the verified readings are written to a temporary recording; nothing is duplicated), replaces the chain status by the real ingest result, runs `plan()` and `build_decision()`. Then, in the BACKEND layer (planner code unchanged), three additional rules can only make a decision stricter: (a) CLOSE CALL: if the best two actions' CVaR differ by less than `close_call_percent` (default 5 percent of the best CVaR, illustrative) the route becomes `needs_human` with a reason; (b) the signed claims did not match the recomputation; (c) the signing key was revoked. The result is signed and appended to the decision log by the unchanged Phase 5 `DecisionLog`. No amendment to the planner or the brief is needed for this. Dispatch: an event goes to the enterprise adapter only when a decision is auto-approved or a person resolves a task.

## 7. Enterprise adapter contract

`SapAdapter` (abstract): `dispatch(event) -> acknowledgement` and `lookup_acknowledgement(id)`; typed pydantic models. `MockSapAdapter` writes the event to `sap_events`, returns a fake acknowledgement whose `provenance` field says `mock`. `SandboxSapAdapter` raises `NotImplementedError` and contains no address, endpoint or credential: this project does not know which interface a real adapter would call and does not guess. Selection by `config/backend.yaml` (`sap_adapter: mock`); the mode is stored in the provenance. Event description wording: "Event dispatched".

## 8. Replay and live

`python -m backend replay --recording FILE [--at-hour H] [--tamper ACTION]` creates an in-process app with a new database, registers a device, creates a shipment (origin `replay`), runs the recording through the real edge runner, posts the ledger through the app (test client), triggers a decision, resolves nothing automatically, and prints a summary. `--all` runs the six demo checkpoints of Phase 5. `python -m backend serve` runs uvicorn on 127.0.0.1. `python -m backend export-ledger` writes an ingest body from a ledger so a live server can be exercised by hand. With `--at-hour` a prefix of the ledger is posted without its anchor (the anchor names the last entry).

## 9. PROPOSE items

**P1. Always 200 for an ingest that verified or failed.** (a) 200 with `chain_status` accepted/rejected (chosen); (b) 409 for a rejected ledger. (a) means a client must read the field; (b) makes a tampered ledger look like a transport error although the rejection is the system working and is stored. Recommendation: (a).

**P2. Revocation effect.** (a) only ledgers received after revocation are rejected, earlier data are marked and need a person (chosen); (b) quarantine everything the key ever signed; (c) accept an operator-supplied effective time. (b) is safest and disruptive; (c) invents a trust in the operator's timestamp. Recommendation: (a) now, (b) as an operator option later.

**P3. Where the signed claims are checked.** (a) recompute from the signed readings and compare (chosen); (b) trust the signed derived values. (b) would treat a signature as proof of truth, which A18 forbids. Recommendation: (a).

**P4. Shipment status after a human resolves a quarantined shipment.** New status `human_resolved` (chosen) rather than silently releasing it. A release workflow is out of scope.

## 10. Out of scope

Authentication and roles; a real enterprise-system call; a database server or migrations; multiple planners; web sockets; the dashboard (Phase F1); key enrolment ceremonies and hardware keys; reading real sensors; any statement that the system is connected to a real enterprise system.
