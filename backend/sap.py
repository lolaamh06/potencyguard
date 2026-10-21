"""Enterprise-system adapter interface, a mock and an unimplemented sandbox stub (Phase 6).

Everything the backend sends to an enterprise system goes through `SapAdapter`. The mock adapter logs
the event and returns a made-up acknowledgement whose `provenance` field says "mock". The sandbox
adapter is a stub: it raises NotImplementedError and holds no address, endpoint or credential,
because this project does not know which interface a real adapter would call and does not guess.

Events are dispatched only when a decision is auto-approved or a person resolves a task. The
description wording is neutral: "Event dispatched".
"""
# ruff: noqa: E501  (long literal lines)

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EVENT_DESCRIPTION = "Event dispatched"
MOCK_PROVENANCE = "mock"


class DecisionReference(BaseModel):
    """Points at the signed decision (and human decision) the event is about."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    decision_seq: int = Field(ge=0)
    decision_hash_hex: str = Field(min_length=64, max_length=64)
    human_seq: int | None = None


class SapEvent(BaseModel):
    """An event for the enterprise system. Immutable."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    shipment_id: str = Field(min_length=1)
    action: str | None = Field(
        description="The action to carry out, or None when a person rejected"
    )
    route: str = Field(description="auto_approved or human_resolved")
    resolution: Literal["auto_approved", "human_approve", "human_override", "human_reject"]
    reference: DecisionReference
    description: str = EVENT_DESCRIPTION


class SapAcknowledgement(BaseModel):
    """What the adapter returns. Immutable."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ack_id: str = Field(min_length=1)
    provenance: str = Field(min_length=1)
    status: str = "accepted"


class SapAdapter(ABC):
    """The only way the backend talks to an enterprise system."""

    mode: str

    @abstractmethod
    def dispatch(self, event: SapEvent) -> SapAcknowledgement:
        """Send one event and return its acknowledgement."""

    @abstractmethod
    def lookup_acknowledgement(self, ack_id: str) -> SapAcknowledgement | None:
        """Look an earlier acknowledgement up (None if unknown)."""


class MockSapAdapter(SapAdapter):
    """Logs the event (through `log`) and returns a made-up acknowledgement marked as a mock."""

    mode = "mock"

    def __init__(self, log, count_events) -> None:
        self._log = log  # callable(event, ack) that stores the event
        self._count = count_events  # callable() -> number of events stored so far
        self._acks: dict[str, SapAcknowledgement] = {}

    def dispatch(self, event: SapEvent) -> SapAcknowledgement:
        ack = SapAcknowledgement(
            ack_id=f"mock-{self._count() + 1:06d}", provenance=MOCK_PROVENANCE, status="accepted"
        )
        self._log(event, ack)
        self._acks[ack.ack_id] = ack
        return ack

    def lookup_acknowledgement(self, ack_id: str) -> SapAcknowledgement | None:
        return self._acks.get(ack_id)


class SandboxSapAdapter(SapAdapter):
    """A stub for a future adapter. It cannot send anything."""

    mode = "sandbox"
    MESSAGE = (
        "The sandbox adapter is not implemented in this project: it has no address, endpoint or "
        "credential, and no real enterprise interface has been chosen. Use sap_adapter: mock."
    )

    def dispatch(self, event: SapEvent) -> SapAcknowledgement:
        raise NotImplementedError(self.MESSAGE)

    def lookup_acknowledgement(self, ack_id: str) -> SapAcknowledgement | None:
        raise NotImplementedError(self.MESSAGE)


def make_adapter(mode: str, log, count_events) -> SapAdapter:
    """Pick the adapter by configuration. Only `mock` and `sandbox` exist."""
    if mode == "mock":
        return MockSapAdapter(log, count_events)
    if mode == "sandbox":
        return SandboxSapAdapter()
    raise ValueError(f"unknown adapter mode {mode!r}; use mock or sandbox")
