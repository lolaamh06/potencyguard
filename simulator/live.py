"""LiveSimulator: one run of the box, one sample per step(), with faults injectable while it runs.

Random streams (all derived from one seed with numpy SeedSequence.spawn):
  0 sensor noise            used only inside BoxEngine, three draws per sample, always
  1 scenario parameters     draws every range once at construction
  2 free-run faults         used only by the free-run planner
The seed is always available as .seed (and .seed_mode is "fixed" or "random"), so any run,
even a random one, can be reproduced.
"""

from __future__ import annotations

import copy
import secrets
from typing import Any

import numpy as np
from pydantic import BaseModel, ValidationError

from edge.sensor_reading import SensorReading
from shared.config import BoxConfig
from simulator.engine import BoxEngine
from simulator.events import (
    INJECTABLE_MODELS,
    KIND_AMBIENT,
    KIND_COOLING,
    KIND_GLITCH,
    KIND_HEAT,
    KIND_SHOCK,
    KIND_SPOOF,
    ORIGIN_INJECTED,
    ORIGIN_SCHEDULED,
    EventRecord,
    InjectionResult,
    ScheduledEvent,
)
from simulator.freerun import FreeRun, FreeRunPlanner
from simulator.scenario import ResolvedScenario, Scenario, resolve_scenario
from simulator.truth import TruthSample

SEED_BITS = 32
FREERUN_ID = "freerun"


def _scheduled_record(
    index: int, event: ScheduledEvent, interval_s: float, n_samples: int
) -> EventRecord:
    """Turn a resolved scenario event into a history record (times in seconds)."""
    data = event.model_dump()
    kind_by_type = {
        "heat_load": KIND_HEAT,
        "cooling_factor": KIND_COOLING,
        "ambient_offset": KIND_AMBIENT,
        "spoof": KIND_SPOOF,
        "glitch": KIND_GLITCH,
        "shock": KIND_SHOCK,
    }
    type_ = data.pop("type")
    kind = kind_by_type[type_]
    event_id = f"sch-{index:03d}-{type_}"
    if "at_h" in data:
        sample = min(max(round(data.pop("at_h") * 3600.0 / interval_s), 0), n_samples - 1)
        start_s = sample * interval_s
        return EventRecord(
            event_id, type_, kind, ORIGIN_SCHEDULED, start_s, start_s + interval_s, data
        )
    start_s = data.pop("start_h") * 3600.0
    end_s = data.pop("end_h") * 3600.0
    if kind == KIND_SPOOF:
        data["add_noise"] = event.noise_enabled  # type: ignore[union-attr]
    return EventRecord(event_id, type_, kind, ORIGIN_SCHEDULED, start_s, end_s, data)


def _error_text(exc: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(p) for p in err['loc']) or 'event'}: {err['msg']}" for err in exc.errors()
    )


class LiveSimulator:
    """Advance one sample at a time; inject faults between steps."""

    def __init__(
        self,
        source: Scenario | FreeRun,
        box: BoxConfig,
        seed: int | None = None,
    ) -> None:
        self.seed_mode = "random" if seed is None else "fixed"
        self.seed = secrets.randbits(SEED_BITS) if seed is None else int(seed)
        noise_ss, params_ss, free_ss = np.random.SeedSequence(self.seed).spawn(3)
        self._box = box
        self._events: list[EventRecord] = []
        self._injected_count = 0
        self.resolved: ResolvedScenario | None = None
        self._planner: FreeRunPlanner | None = None

        if isinstance(source, Scenario):
            self.scenario_id = source.id
            self.sample_interval_s = source.sample_interval_s
            self.n_total: int | None = source.n_samples
            self.duration_h: float | None = source.duration_h
            rh_base = source.rh_base_pct
            self.resolved = resolve_scenario(
                source, np.random.Generator(np.random.PCG64(params_ss))
            )
            ambient_fn = self.resolved.ambient_function()
            for i, event in enumerate(self.resolved.events, start=1):
                record = _scheduled_record(i, event, self.sample_interval_s, source.n_samples)
                self._events.append(record)
        else:
            cfg = source.config
            self.scenario_id = FREERUN_ID
            self.sample_interval_s = cfg.sample_interval_s
            self.duration_h = source.hours
            self.n_total = (
                None
                if source.hours is None
                else round(source.hours * 3600.0 / cfg.sample_interval_s) + 1
            )
            rh_base = cfg.rh_base_pct
            self._planner = FreeRunPlanner(
                source, box, np.random.Generator(np.random.PCG64(free_ss))
            )
            ambient_fn = self._planner.ambient_function()

        self.engine = BoxEngine(
            box,
            self.sample_interval_s,
            ambient_fn,
            rh_base,
            np.random.Generator(np.random.PCG64(noise_ss)),
            self._events,
        )
        self._last_truth: TruthSample | None = None

    # ------------------------------------------------------------------ stepping

    @property
    def finished(self) -> bool:
        return self.n_total is not None and self.engine.n >= self.n_total

    def step(self) -> tuple[SensorReading | None, TruthSample | None]:
        """Next sample, or (None, None) when the scenario has ended."""
        if self.finished:
            return None, None
        if self._planner is not None:
            lookahead_s = self.engine.next_sample_s + 2 * self.sample_interval_s
            self._events.extend(self._planner.plan_through(lookahead_s, self.sample_interval_s))
        reading, truth = self.engine.step()
        self._last_truth = truth
        return reading, truth

    # ------------------------------------------------------------------ history

    def events(self) -> list[EventRecord]:
        """Copies of every event so far (scheduled, freerun, injected), ordered by start time."""
        return sorted(copy.deepcopy(self._events), key=lambda e: (e.start_s, e.id))

    def snapshot(self) -> dict[str, Any]:
        """Plain data describing the current state, for a future API."""
        truth = self._last_truth
        return {
            "scenario_id": self.scenario_id,
            "seed": self.seed,
            "seed_mode": self.seed_mode,
            "sim_time_s": self.engine.now_s,
            "finished": self.finished,
            "true_temp_c": None if truth is None else truth.true_temp_c,
            "reported_temp_c": None if truth is None else truth.reported_temp_c,
            "compressor_on": self.engine.compressor_on,
            "cooling_factor": None if truth is None else truth.cooling_factor,
            "spoof_mode": None if truth is None else truth.spoof_mode,
            "active_events": [
                {"id": e.id, "type": e.type, "origin": e.origin}
                for e in self._events
                if truth is not None and e.id in truth.active_event_ids
            ],
        }

    # ------------------------------------------------------------------ injection

    def _new_record(
        self, type_: str, kind: str, start_s: float, end_s, params: dict
    ) -> EventRecord:
        self._injected_count += 1
        event_id = f"inj-{self._injected_count:03d}-{type_}"
        return EventRecord(event_id, type_, kind, ORIGIN_INJECTED, start_s, end_s, params)

    def _end_open(self, kind: str, now_s: float, when=lambda e: True) -> list[EventRecord]:
        """End every still-running event of this kind (that passes `when`) at now_s."""
        ended = []
        for event in self._events:
            if event.kind != kind or not when(event):
                continue
            still_running = event.end_s is None or event.end_s > now_s
            if still_running and event.start_s <= now_s:
                event.end_s = now_s
                ended.append(event)
        return ended

    def inject(self, event: dict | BaseModel) -> InjectionResult:
        """Apply a fault from the current simulated time. A rejected fault changes nothing."""
        data = event.model_dump() if isinstance(event, BaseModel) else event
        if not isinstance(data, dict):
            return InjectionResult(False, error="an event must be a mapping with a 'type'")
        type_ = data.get("type")
        model = INJECTABLE_MODELS.get(type_)  # type: ignore[arg-type]
        if model is None:
            known = ", ".join(INJECTABLE_MODELS)
            return InjectionResult(False, error=f"unknown event type {type_!r}; known: {known}")
        try:
            parsed = model.model_validate(data)
        except ValidationError as exc:
            return InjectionResult(False, error=f"{type_}: {_error_text(exc)}")
        return self._apply(parsed)

    def _apply(self, parsed: Any) -> InjectionResult:
        type_ = parsed.type
        now_s = self.engine.now_s
        next_s = self.engine.next_sample_s
        interval = self.sample_interval_s

        if type_ in ("kill_cooling", "derate_cooling"):
            self._end_open(KIND_COOLING, now_s, lambda e: e.origin == ORIGIN_INJECTED)
            factor = 0.0 if type_ == "kill_cooling" else parsed.factor
            record = self._new_record(type_, KIND_COOLING, now_s, None, {"factor": factor})
        elif type_ == "restore_cooling":
            ended = self._end_open(KIND_COOLING, now_s, lambda e: e.params["factor"] < 1.0)
            if not ended:
                return InjectionResult(True, None, "restore_cooling: nothing to restore")
            for event in ended:
                event.params["ended_by"] = "restore_cooling"
            return InjectionResult(True, ended[-1].id, f"cooling restored from t={now_s:.0f} s")
        elif type_ == "open_door":
            power = parsed.power_w if parsed.power_w is not None else self._box.door_default_power_w
            params = {"power_w": power, "rh_delta_pct": 0.0}
            record = self._new_record(
                type_, KIND_HEAT, now_s, now_s + parsed.duration_min * 60.0, params
            )
        elif type_ in ("heat_soak", "cold_snap"):
            params = {"delta_c": parsed.delta_c, "ramp_h": parsed.ramp_h}
            end_s = now_s + parsed.duration_h * 3600.0
            record = self._new_record(type_, KIND_AMBIENT, now_s, end_s, params)
        elif type_ == "spoof_sensor":
            if parsed.mode == "replay" and (
                parsed.replay_from_h + parsed.replay_len_h > now_s / 3600.0
            ):
                return InjectionResult(
                    False, error="spoof_sensor: the replayed period must lie in the past"
                )
            self._end_open(KIND_SPOOF, now_s)
            params = {"mode": parsed.mode}
            for name in ("reported_c", "delta_c", "replay_from_h", "replay_len_h"):
                if getattr(parsed, name) is not None:
                    params[name] = getattr(parsed, name)
            params["add_noise"] = (
                parsed.add_noise if parsed.add_noise is not None else parsed.mode != "replay"
            )
            end_s = None if parsed.duration_min is None else now_s + parsed.duration_min * 60.0
            record = self._new_record(type_, KIND_SPOOF, now_s, end_s, params)
        elif type_ == "stop_spoof":
            ended = self._end_open(KIND_SPOOF, now_s)
            if not ended:
                return InjectionResult(True, None, "stop_spoof: nothing to stop")
            return InjectionResult(True, ended[-1].id, f"spoof stopped at t={now_s:.0f} s")
        elif type_ == "glitch_spike":
            params = {"value_c": parsed.value_c, "injected_at_s": now_s}
            record = self._new_record(type_, KIND_GLITCH, next_s, next_s + interval, params)
        else:  # shock
            params = {"peak_g": parsed.peak_g, "injected_at_s": now_s}
            record = self._new_record(type_, KIND_SHOCK, next_s, next_s + interval, params)

        self._events.append(record)
        return InjectionResult(True, record.id, f"{type_} applied from t={record.start_s:.0f} s")
