// UI state of the Control Room. The replay clock itself is the plain object `crClock`, moved by
// the shared GSAP ticker and read directly by the canvas chart (no React state per frame); the
// store gets a copy of its time about ten times a second for the text panels.
import { create } from "zustand";
import type { ReplayFile } from "../data/types";
import {
  SCENARIO_IDS,
  advance,
  atEnd,
  canDecide,
  endSeconds,
  humanLogText,
  initialClock,
  resetClock,
  tamperOptions,
  tamperOutcome,
  validateOverride,
  validateReason,
  wallStamp,
  type Clock,
  type HumanOutcome,
  type LogLine,
  type ScenarioId,
  type Speed,
  type TamperChoice,
} from "./logic";

export const crClock: Clock = initialClock(4);

interface CrState {
  scenarioId: ScenarioId;
  tS: number;
  speed: Speed;
  paused: boolean;
  human: HumanOutcome | null;
  /** What a person did for each shipment (demo only; kept when the scenario changes). */
  outcomes: Partial<Record<ScenarioId, HumanOutcome>>;
  tamper: TamperChoice | null;
  tamperPick: string;
  userLog: LogLine[];
  provenanceOpen: boolean;
  lastUseMs: number | null;
  recording: boolean;
  message: string | null;
  selectScenario: (id: ScenarioId, nowMs: number, how?: string) => void;
  setSpeed: (speed: Speed) => void;
  togglePause: () => void;
  reset: () => void;
  tick: (wallDtS: number, replay: ReplayFile, nowMs: number) => void;
  decide: (replay: ReplayFile, outcome: HumanOutcome, opts?: { ignoreClock?: boolean }) => string | null;
  clearDecisions: () => void;
  pickTamper: (key: string) => void;
  applyTamper: (replay: ReplayFile) => void;
  clearTamper: () => void;
  setProvenance: (open: boolean) => void;
  setRecording: (on: boolean) => void;
}

let lastPublishMs = 0;
let keyCounter = 0;

const line = (text: string, tS: number): LogLine => ({ key: `u${++keyCounter}`, tS, wall: wallStamp(new Date()), text });

function syncClock(next: Clock): void {
  crClock.tS = next.tS;
  crClock.speed = next.speed;
  crClock.paused = next.paused;
}

export const useCr = create<CrState>((set, get) => ({
  scenarioId: SCENARIO_IDS[0],
  tS: 0,
  speed: crClock.speed,
  paused: false,
  human: null,
  outcomes: {},
  tamper: null,
  tamperPick: "",
  userLog: [],
  provenanceOpen: false,
  lastUseMs: null,
  recording: false,
  message: null,

  selectScenario: (id, nowMs, how = "armed by hold") => {
    syncClock(resetClock(crClock));
    set({
      scenarioId: id,
      tS: 0,
      paused: false,
      human: get().outcomes[id] ?? null,
      tamper: null,
      tamperPick: "",
      lastUseMs: nowMs,
      message: null,
      userLog: [line(`Scenario selected: ${id} (${how}).`, 0)],
    });
  },

  setSpeed: (speed) => {
    syncClock({ ...crClock, speed });
    set({ speed });
  },

  togglePause: () => {
    syncClock({ ...crClock, paused: !crClock.paused });
    set({ paused: crClock.paused });
  },

  reset: () => {
    syncClock(resetClock(crClock));
    set((s) => ({ tS: 0, paused: false, tamper: null, userLog: [line(`Scenario reset: ${s.scenarioId}.`, 0)] }));
  },

  tick: (wallDtS, replay, nowMs) => {
    const end = endSeconds(replay);
    const next = advance(crClock, wallDtS, end);
    if (next === crClock) return;
    syncClock(next);
    if (nowMs - lastPublishMs >= 100 || atEnd(next, end)) {
      lastPublishMs = nowMs;
      set({ tS: next.tS });
    }
  },

  decide: (replay, outcome, opts) => {
    const s = get();
    const id = replay.meta.scenario_id as ScenarioId;
    const when = opts?.ignoreClock ? replay.meta.checkpoint_h * 3600 : crClock.tS;
    if (!canDecide(replay, when, s.outcomes[id] ?? null)) return "A decision is not open right now.";
    const error =
      outcome.kind === "override" ? validateOverride(replay, outcome.action, outcome.reason) : outcome.kind === "reject" ? validateReason(outcome.reason) : null;
    if (error) return error;
    set({
      outcomes: { ...s.outcomes, [id]: outcome },
      human: id === s.scenarioId ? outcome : s.human,
      tS: crClock.tS,
      userLog: [...s.userLog, line(humanLogText(outcome), crClock.tS)],
    });
    return null;
  },

  clearDecisions: () => set({ outcomes: {}, human: null }),

  pickTamper: (key) => set({ tamperPick: key }),

  applyTamper: (replay) => {
    const s = get();
    const option = tamperOptions(replay.tamper).find((o) => o.key === s.tamperPick) ?? tamperOptions(replay.tamper)[0];
    const outcome = tamperOutcome(replay.tamper, option.choice);
    if (!outcome) return;
    set({
      tamper: option.choice,
      tamperPick: option.key,
      userLog: [...s.userLog, line(`Tamper on a ledger copy: ${option.label}. Recorded result: ${outcome.lines[outcome.lines.length - 1]}`, crClock.tS)],
    });
  },

  clearTamper: () => set({ tamper: null }),
  setProvenance: (open) => set({ provenanceOpen: open }),
  setRecording: (on) => set({ recording: on }),
}));
