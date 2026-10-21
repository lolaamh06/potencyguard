"""The HTTP API (Phase 6): FastAPI, JSON only, strict request models, no stack traces.

NO AUTHENTICATION in this phase. Anyone who can reach the port can register a key, ingest, decide
and resolve; the caller name (`X-Caller` header) and the QA identity (`who`) are plain strings that
are written to the audit log. The server binds to 127.0.0.1 by default. Do not expose it.

Signing protects records after signing and does not stop a lie at the sensor (A18). Simulation on
a synthetic box. The planner recommends; QA decides.
"""
# ruff: noqa: E501  (long literal lines)

from __future__ import annotations

import re
from typing import Any, Literal

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from backend.config import BackendConfig, load_backend_config
from backend.service import SOFTWARE_VERSION, ApiError, Service
from backend.storage import Store
from edge.chain import Anchor, Entry, load_or_create_signer
from planner.config import load_planner_config
from shared.config import load_box_config, load_product_config

ID_PATTERN = r"^[A-Za-z0-9_.-]{1,64}$"
HEX64 = r"^[0-9a-fA-F]{64}$"
HEX128 = r"^[0-9a-fA-F]{128}$"
HEX16 = r"^[0-9a-fA-F]{16}$"
MAX_ENTRIES = 50_000
MAX_RECORD_HEX = 20_000


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class RegisterRequest(Strict):
    device_id: str = Field(pattern=ID_PATTERN)
    public_key_hex: str = Field(pattern=HEX64)
    registered_by: str = Field(min_length=3, max_length=64)
    note: str = Field(default="", max_length=300)


class RevokeRequest(Strict):
    key_id: str = Field(pattern=HEX16)
    revoked_by: str = Field(min_length=3, max_length=64)
    reason: str = Field(min_length=3, max_length=300)


class ShipmentRequest(Strict):
    shipment_id: str = Field(pattern=ID_PATTERN)
    label: str = Field(min_length=1, max_length=100)
    device_id: str = Field(pattern=ID_PATTERN)
    origin: Literal["replay", "live"]
    scheduled_duration_h: float | None = Field(default=None, gt=0, le=10_000)


class EntryIn(Strict):
    seq: int = Field(ge=0)
    record_hex: str = Field(min_length=2, max_length=MAX_RECORD_HEX, pattern=r"^[0-9a-fA-F]+$")
    signature_hex: str = Field(pattern=HEX128)
    hash_hex: str = Field(pattern=HEX64)
    key_id: str = Field(pattern=HEX16)


class AnchorIn(Strict):
    seq: int = Field(ge=0)
    head_hex: str = Field(pattern=HEX64)
    statement_hex: str = Field(min_length=2, max_length=2000, pattern=r"^[0-9a-fA-F]+$")
    signature_hex: str = Field(pattern=HEX128)
    key_id: str = Field(pattern=HEX16)


class LedgerRequest(Strict):
    entries: list[EntryIn] = Field(min_length=1, max_length=MAX_ENTRIES)
    anchor: AnchorIn | None = None
    public_key_hex: str | None = Field(
        default=None, description="IGNORED. The backend only uses keys registered through /devices."
    )


class DecideRequest(Strict):
    remaining_hours: float | None = Field(default=None, gt=0, le=10_000)
    seed: int | None = Field(default=None, ge=0)


class ResolveRequest(Strict):
    who: str = Field(min_length=2, max_length=64)
    action: Literal["approve", "override", "reject"]
    final_action: (
        Literal["continue", "expedite", "reroute_to_depot", "re_source", "quarantine"] | None
    ) = None
    reason: str = Field(min_length=10, max_length=500)


class IngestResponse(BaseModel):
    shipment_id: str
    chain_status: Literal["verified", "rejected"]
    reason: str
    first_bad_index: int | None
    detail: str
    entries: int
    anchor_present: bool
    anchor_checked: bool
    claims_consistent: bool | None
    claims_detail: str
    public_key_in_request: str
    submission_id: int


class HealthResponse(BaseModel):
    status: str
    software_version: str
    authentication: str
    sap_adapter_mode: str
    bound_host: str
    planner_key_id: str


class DeviceOut(BaseModel):
    device_id: str
    key_id: str
    status: str


def _decode_entries(model: LedgerRequest) -> tuple[list[Entry], Anchor | None]:
    entries = [
        Entry(e.seq, bytes.fromhex(e.record_hex), bytes.fromhex(e.signature_hex), bytes.fromhex(e.hash_hex), e.key_id.lower())
        for e in model.entries
    ]  # fmt: skip
    a = model.anchor
    anchor = None
    if a is not None:
        anchor = Anchor(
            a.seq,
            bytes.fromhex(a.head_hex),
            bytes.fromhex(a.statement_hex),
            bytes.fromhex(a.signature_hex),
            a.key_id.lower(),
        )
    return entries, anchor


def create_app(
    cfg: BackendConfig | None = None,
    store: Store | None = None,
    key_dir: str | None = None,
    clock=None,
    planner_cfg=None,
) -> FastAPI:
    cfg = cfg or load_backend_config()
    if store is None:
        store = Store(cfg.database_path(), clock) if clock else Store(cfg.database_path())
    signer = load_or_create_signer(key_dir or cfg.planner_key_dir or _default_planner_key_dir())
    service = Service(
        store,
        cfg,
        planner_cfg or load_planner_config(),
        load_product_config(),
        load_box_config(),
        signer,
    )
    app = FastAPI(
        title="PotencyGuard backend (simulation)",
        version=SOFTWARE_VERSION,
        description="Simulation on a synthetic box. No authentication. Bind to 127.0.0.1 only.",
    )
    app.state.service = service
    app.state.config = cfg

    # ----------------------------------------------------------- errors and audit

    @app.exception_handler(ApiError)
    async def _api_error(_request: Request, exc: ApiError):
        return JSONResponse(
            status_code=exc.status, content={"error": exc.code, "message": exc.message}
        )

    @app.exception_handler(RequestValidationError)
    async def _invalid(_request: Request, exc: RequestValidationError):
        detail = [
            {"loc": [str(p) for p in e.get("loc", [])], "msg": str(e.get("msg", ""))}
            for e in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error": "invalid_request",
                "message": "The request did not match the expected format.",
                "detail": detail,
            },
        )

    @app.exception_handler(404)
    async def _not_found(_request: Request, _exc):
        return JSONResponse(
            status_code=404, content={"error": "not_found", "message": "No such endpoint."}
        )

    @app.middleware("http")
    async def audit(request: Request, call_next):
        request.state.shipment_id = None
        request.state.outcome = None
        try:
            response = await call_next(request)
        except Exception:  # never show a stack trace; the failure is audited
            response = JSONResponse(
                status_code=500,
                content={"error": "internal_error", "message": "An internal error occurred."},
            )
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            match = re.match(r"^/shipments/([^/]+)", request.url.path)
            shipment_id = request.state.shipment_id or (match.group(1) if match else None)
            code = response.status_code
            outcome = request.state.outcome or (
                "ok" if code < 400 else "refused" if code < 500 else "error"
            )
            store.add_audit(
                request.method,
                request.url.path[:200],
                request.headers.get("x-caller", "anonymous")[:64],
                None if shipment_id is None else str(shipment_id)[:64],
                outcome,
                code,
                "",
            )
        return response

    def page(offset: int, limit: int) -> tuple[int, int]:
        return offset, min(limit, cfg.max_page_size)

    # ----------------------------------------------------------- devices

    @app.post("/devices/register", status_code=201, response_model=DeviceOut)
    def register(body: RegisterRequest):
        return service.register_device(
            body.device_id, body.public_key_hex.lower(), body.registered_by, body.note
        )

    @app.post("/devices/{device_id}/revoke", response_model=DeviceOut)
    def revoke(device_id: str, body: RevokeRequest):
        return service.revoke_key(device_id, body.key_id.lower(), body.revoked_by, body.reason)

    @app.get("/devices")
    def devices() -> dict[str, Any]:
        return {"items": service.list_devices(), "note": "unauthenticated demo registry"}

    # ----------------------------------------------------------- shipments

    @app.post("/shipments", status_code=201)
    def create_shipment(body: ShipmentRequest, request: Request) -> dict[str, Any]:
        request.state.shipment_id = body.shipment_id
        return service.create_shipment(
            body.shipment_id, body.label, body.device_id, body.origin, body.scheduled_duration_h
        )

    @app.get("/shipments")
    def shipments() -> dict[str, Any]:
        return {"items": service.list_shipments()}

    @app.get("/shipments/{shipment_id}")
    def shipment(shipment_id: str) -> dict[str, Any]:
        return service.shipment_view(shipment_id)

    @app.post("/shipments/{shipment_id}/ledger", response_model=IngestResponse)
    def ingest(shipment_id: str, body: LedgerRequest, request: Request):
        entries, anchor = _decode_entries(body)
        result = service.ingest(shipment_id, entries, anchor, body.public_key_hex is not None)
        request.state.outcome = "ok" if result.result == "verified" else "ledger_rejected"
        return IngestResponse(
            shipment_id=shipment_id, chain_status=result.result, reason=result.reason,
            first_bad_index=result.first_bad_index, detail=result.detail, entries=result.entry_count,
            anchor_present=result.anchor_present, anchor_checked=result.anchor_checked,
            claims_consistent=result.claims_consistent, claims_detail=result.claims_detail,
            public_key_in_request=result.public_key_in_request, submission_id=result.submission_id,
        )  # fmt: skip

    @app.get("/shipments/{shipment_id}/readings")
    def readings(
        shipment_id: str, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000)
    ) -> dict[str, Any]:
        offset, limit = page(offset, limit)
        return service.readings_page(shipment_id, offset, limit)

    @app.get("/shipments/{shipment_id}/verify")
    def verify(shipment_id: str) -> dict[str, Any]:
        return service.verify_now(shipment_id)

    @app.post("/shipments/{shipment_id}/decide", status_code=201)
    def decide(
        shipment_id: str, request: Request, body: DecideRequest | None = None
    ) -> dict[str, Any]:
        body = body or DecideRequest()
        result = service.decide(shipment_id, body.remaining_hours, body.seed)
        request.state.outcome = f"decision_{result['route']}"
        return result

    @app.get("/shipments/{shipment_id}/decisions")
    def decisions(shipment_id: str) -> dict[str, Any]:
        return service.decisions_view(shipment_id)

    # ----------------------------------------------------------- approvals

    @app.get("/approvals")
    def approvals() -> dict[str, Any]:
        return {"items": service.open_approvals()}

    @app.post("/approvals/{task_id}/resolve")
    def resolve(task_id: int, body: ResolveRequest, request: Request) -> dict[str, Any]:
        result = service.resolve(task_id, body.who, body.action, body.final_action, body.reason)
        request.state.shipment_id = result["shipment_id"]
        return result

    # ----------------------------------------------------------- audit, provenance, health

    @app.get("/audit")
    def audit_log(
        offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000)
    ) -> dict[str, Any]:
        offset, limit = page(offset, limit)
        return service.audit_page(offset, limit)

    @app.get("/provenance/{shipment_id}")
    def provenance(shipment_id: str) -> dict[str, Any]:
        return service.provenance(shipment_id)

    @app.get("/health", response_model=HealthResponse)
    def health():
        return HealthResponse(
            status="ok", software_version=SOFTWARE_VERSION, authentication="none",
            sap_adapter_mode=service.adapter.mode, bound_host=cfg.host,
            planner_key_id=signer.key_id,
        )  # fmt: skip

    return app


def _default_planner_key_dir() -> str:
    from edge.chain import default_key_dir

    return str(default_key_dir() / "backend-planner")
