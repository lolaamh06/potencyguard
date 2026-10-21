# Backend API (Phase 6)

Simulation on a synthetic box. **There is no authentication.** Anyone who can reach the port can register a key, ingest, decide and resolve; caller names and QA identities are plain strings that go into the audit log. The server binds to 127.0.0.1 by default (`config/backend.yaml`). Do not expose it. Signing protects records after signing and does not stop a lie at the sensor (A18), so the backend recomputes the physics checks from the signed readings and plans from the recomputed values. The planner recommends; QA decides. Design: `docs/03-decisions/decision-0010-backend.md`.

JSON only. Errors look like `{"error": "<code>", "message": "..."}` (422 adds a `detail` list of where the request was wrong). No stack traces. Send an optional `X-Caller` header to label the caller in the audit log. Every POST is audited, including refused and invalid ones; reads are not.

## Endpoints

| method and path | purpose | notes |
|---|---|---|
| `POST /devices/register` | register a device public key | demo operator; 201; 409 if already registered or used by another device |
| `POST /devices/{id}/revoke` | revoke a registered key | appends a row; ledgers received afterwards are rejected |
| `GET /devices` | list keys and their status | |
| `POST /shipments` | create a shipment | `origin` is `replay` or `live`; optional `scheduled_duration_h` |
| `GET /shipments` | list | |
| `GET /shipments/{id}` | latest recomputed potency, trust level, verdict, chain status, latest decision, status history | |
| `POST /shipments/{id}/ledger` | ingest entries and an optional anchor | always 200 when stored; read `chain_status` (`verified` or `rejected`) |
| `GET /shipments/{id}/readings?offset=&limit=` | decoded readings of the latest verified ledger | paged, `limit` 1 to 1000 |
| `GET /shipments/{id}/verify` | re-verify the stored chain now | reports the key's current status |
| `POST /shipments/{id}/decide` | run the planner on the latest verified data | 409 if the latest ledger was rejected or missing; body `{"remaining_hours": h, "seed": n}` both optional |
| `GET /shipments/{id}/decisions` | decisions and human decisions, and whether the decision log verifies | |
| `GET /approvals` | open human tasks (alternatives, potency curve, chain status, reason) | |
| `POST /approvals/{task}/resolve` | `approve`, `override` (with `final_action`) or `reject` | `reason` of at least 10 characters; appended as a NEW record that refers to the original |
| `GET /audit?offset=&limit=` | the API audit log | paged |
| `GET /provenance/{id}` | source, scenario id, adapter mode, software version, replay or live | |
| `GET /health` | liveness; says `authentication: none` | |

## How a ledger is trusted

1. A device key must be registered first. A public key sent with a ledger is ignored.
2. The whole chain (and the anchor, if sent) is checked with `verify_chain` against the REGISTERED key. A failure is stored as `rejected` with the first broken entry and the reason, the shipment is quarantined, and no decision can come from it. Extra reasons: `unregistered_key`, `key_revoked`, `mixed_keys`, `history_conflict` (a later ledger must extend the stored one), `unusable_readings`.
3. Without an anchor, removing entries from the END of a first submission cannot be detected (the Phase 4 limit). With an anchor it is reported as `truncated`.
4. The backend re-runs the potency and tamper checks on the signed readings. If the values the device signed differ, the ledger is stored but flagged (`claims_consistent: false`) and the next decision needs a person.

## PowerShell examples

Start a server (leave it running in its own window), then in another window:

```
$py = "$env:LOCALAPPDATA\potencyguard\venv\Scripts\python.exe"
& $py -m backend serve                       # http://127.0.0.1:8765, no authentication
```

```
$py = "$env:LOCALAPPDATA\potencyguard\venv\Scripts\python.exe"
$u  = "http://127.0.0.1:8765"
$h  = @{ "X-Caller" = "my-demo" }

# 1. a signed ledger from a recording (the device id must match what you register)
& $py -m edge run --recording data/recordings/reefer_failure.jsonl --device-id pg-live-1
$ledger = (Get-ChildItem data\runs\*reefer_failure.sqlite | Sort-Object LastWriteTime | Select-Object -Last 1).FullName
$pub    = (Get-Content ($ledger -replace '\.sqlite$', '.pubkey')).Trim()
& $py -m backend export-ledger --ledger $ledger --out body.json

# 2. register the key, create the shipment, post the ledger
Invoke-RestMethod -Method Post -Uri "$u/devices/register" -Headers $h -ContentType "application/json" `
  -Body (@{ device_id = "pg-live-1"; public_key_hex = $pub; registered_by = "demo-operator" } | ConvertTo-Json)
Invoke-RestMethod -Method Post -Uri "$u/shipments" -Headers $h -ContentType "application/json" `
  -Body (@{ shipment_id = "S-1"; label = "reefer_failure"; device_id = "pg-live-1"; origin = "replay"; scheduled_duration_h = 36 } | ConvertTo-Json)
Invoke-RestMethod -Method Post -Uri "$u/shipments/S-1/ledger" -Headers $h -ContentType "application/json" -InFile body.json

# 3. a recommendation (QA decides), then look at the shipment
Invoke-RestMethod -Method Post -Uri "$u/shipments/S-1/decide" -Headers $h -ContentType "application/json" -Body '{"remaining_hours": 16}'
Invoke-RestMethod "$u/shipments/S-1"
Invoke-RestMethod "$u/approvals"
Invoke-RestMethod "$u/audit?limit=10"
```

When a task is open, resolve it (the reason needs at least 10 characters):

```
Invoke-RestMethod -Method Post -Uri "$u/approvals/0/resolve" -Headers $h -ContentType "application/json" `
  -Body (@{ who = "QA lead"; action = "override"; final_action = "quarantine"; reason = "hold it for the review" } | ConvertTo-Json)
```

The decision is made at the LAST ingested reading. For realistic checkpoints use the headless replay, which posts the first H hours:

```
& $py -m backend replay --recording data/recordings/reefer_failure.jsonl --at-hour 20
& $py -m backend replay --recording data/recordings/hidden_spoilage.jsonl --at-hour 50 --tamper edit
& $py -m backend replay --all
```

## Events for the enterprise system

A decision that is auto-approved, or a task that a person resolves, produces one event through the `SapAdapter` interface. The default adapter is a mock: it stores the event and returns an acknowledgement whose `provenance` is `mock`. The other mode, `sandbox`, is an unimplemented stub (HTTP 501); it holds no address or credential, because no real interface has been chosen.
