// Pure logic of the Control Room: the replay clock, view-model mapping, the approval rules, the
// guarded-switch timing, the recorded tamper outcomes, the event log and the recording sequence.
// No React, no DOM, no clock of its own. Nothing here computes planner numbers: it picks and
// formats what the exporter wrote.
import type { Frame, ReplayFile, ScenarioEvent, TamperData } from "../data/types";

// ---------------------------------------------------------------- scenarios

export const SCENARIO_IDS = ["baseline_ok", "door_open_excursion", "reefer_failure", "spoof_attempt", "hidden_spoilage"] as const;
export type ScenarioId = (typeof SCENARIO_IDS)[number];

export function isScenarioId(value: string): value is ScenarioId {
  return (SCENARIO_IDS as readonly string[]).includes(value);
}

/** The number keys 1 to 5 pick the scenarios in this order (FV-A1). */
export function scenarioForKey(key: string): ScenarioId | null {
  const i = Number(key);
  return Number.isInteger(i) && i >= 1 && i <= SCENARIO_IDS.length ? SCENARIO_IDS[i - 1] : null;
}

// ---------------------------------------------------------------- replay clock

export const SPEEDS = [1, 4, 16] as const;
export type Speed = (typeof SPEEDS)[number];
/** At 1x, one wall-clock second is thirty simulated minutes. */
export const SIM_S_PER_WALL_S = 1800;
const MAX_STEP_S = 0.25;

export interface Clock {
  tS: number;
  speed: Speed;
  paused: boolean;
}

export const initialClock = (speed: Speed = 4): Clock => ({ tS: 0, speed, paused: false });

export function endSeconds(replay: ReplayFile): number {
  const last = replay.frames[replay.frames.length - 1];
  return last ? last.t_s : 0;
}

/** Moves the clock by a wall-clock step. A paused clock and a clock at the end do not move; the end holds the final frame. */
export function advance(clock: Clock, wallDtS: number, endS: number): Clock {
  if (clock.paused || clock.tS >= endS || !(wallDtS > 0)) return clock;
  const step = Math.min(wallDtS, MAX_STEP_S) * SIM_S_PER_WALL_S * clock.speed;
  return { ...clock, tS: Math.min(endS, clock.tS + step) };
}

export const atEnd = (clock: Clock, endS: number): boolean => clock.tS >= endS;
export const resetClock = (clock: Clock): Clock => ({ ...clock, tS: 0, paused: false });

/** Index of the last frame at or before tS (0 when tS is before the first frame). */
export function frameIndexAt(frames: readonly Frame[], tS: number): number {
  let lo = 0;
  let hi = frames.length - 1;
  let best = 0;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (frames[mid].t_s <= tS) {
      best = mid;
      lo = mid + 1;
    } else hi = mid - 1;
  }
  return best;
}

// ---------------------------------------------------------------- view model

export type RouteState = "safe" | "warning" | "danger";
export type Icon = "ok" | "warn" | "alert" | "person";

export interface Chip {
  icon: Icon;
  text: string;
}

/** What a person did about a needs-a-person decision (demo only; nothing leaves the browser). */
export type HumanOutcome = { kind: "approve" } | { kind: "override"; action: string; reason: string } | { kind: "reject"; reason: string };

const LABELS: Record<string, string> = {
  continue: "Continue",
  expedite: "Expedite",
  reroute_to_depot: "Reroute to depot",
  re_source: "Re-source",
  quarantine: "Quarantine",
};
export const actionLabel = (name: string): string => LABELS[name] ?? name.replace(/_/g, " ");

export const decisionReached = (replay: ReplayFile, tS: number): boolean => tS >= replay.meta.checkpoint_h * 3600;

export function statusChip(replay: ReplayFile, tS: number, human: HumanOutcome | null): Chip {
  if (human) {
    if (human.kind === "approve") return { icon: "person", text: "approved by a person (demo)" };
    if (human.kind === "override") return { icon: "person", text: `overridden: ${actionLabel(human.action)} (demo)` };
    return { icon: "person", text: "rejected by a person (demo)" };
  }
  if (!decisionReached(replay, tS)) return { icon: "ok", text: "in transit, no decision yet" };
  const d = replay.decision;
  if (d.shipment_status.startsWith("quarantined")) return { icon: "warn", text: "quarantined pending review" };
  return { icon: "ok", text: d.needs_human ? "waiting for a person" : "auto-approved within thresholds" };
}

export function trustChip(frame: Frame): Chip {
  if (frame.trust_level === "trusted") return { icon: "ok", text: "Trust: trusted" };
  if (frame.trust_level === "untrusted") return { icon: "alert", text: "Trust: untrusted" };
  return { icon: "warn", text: `Trust: ${frame.trust_level.replace(/_/g, " ")}` };
}

export const verdictText = (frame: Frame): string => `Verdict: ${frame.verdict.replace(/_/g, " ")}`;

export const SAFE_LOW_C = 2;
export const SAFE_HIGH_C = 8;

export function routeStateFor(frame: Frame, replay: ReplayFile, tS: number): RouteState {
  const quarantined = decisionReached(replay, tS) && replay.decision.shipment_status.startsWith("quarantined");
  if (frame.trust_level === "untrusted" || quarantined) return "danger";
  const outside = frame.temp_c !== null && (frame.temp_c > SAFE_HIGH_C || frame.temp_c < SAFE_LOW_C);
  if (frame.trust_level !== "trusted" || outside || frame.flags.cusum || frame.flags.step || frame.flags.state) return "warning";
  return "safe";
}

/** The planned alternative is shown when the recommendation (after the decision time) is a reroute. */
export const showAlternative = (replay: ReplayFile, tS: number): boolean =>
  decisionReached(replay, tS) && replay.decision.chosen_action === "reroute_to_depot";

export const journeyProgress = (replay: ReplayFile, tS: number): number =>
  Math.min(1, Math.max(0, tS / (replay.meta.duration_h * 3600)));

export interface Ring {
  potencyPercent: number;
  usedPercent: number;
  tauH: number;
  mktC: number | null;
  tempC: number | null;
}

/** The big numbers: the frame's exported values, shown as percentages (a unit change only). */
export const ringValues = (frame: Frame): Ring => ({
  potencyPercent: frame.potency * 100,
  usedPercent: frame.shelf_life_used_fraction * 100,
  tauH: frame.tau_eq_h,
  mktC: frame.mkt_c,
  tempC: frame.temp_c,
});

export interface Band {
  fromH: number;
  toH: number;
}

/** Stretches where the reported temperature is outside the illustrative 2 to 8 C range. */
export function excursionBands(frames: readonly Frame[]): Band[] {
  const bands: Band[] = [];
  let start: number | null = null;
  for (const f of frames) {
    const out = f.temp_c !== null && (f.temp_c > SAFE_HIGH_C || f.temp_c < SAFE_LOW_C);
    if (out && start === null) start = f.t_s / 3600;
    if (!out && start !== null) {
      bands.push({ fromH: start, toH: f.t_s / 3600 });
      start = null;
    }
  }
  if (start !== null && frames.length) bands.push({ fromH: start, toH: frames[frames.length - 1].t_s / 3600 });
  return bands;
}

// ---------------------------------------------------------------- approval

export const MIN_REASON = 10;

/** A calm message if the override or reject reason is not acceptable, otherwise null. */
export function validateReason(reason: string): string | null {
  return reason.trim().length >= MIN_REASON ? null : `Give a reason of at least ${MIN_REASON} characters.`;
}

export function validateOverride(replay: ReplayFile, action: string, reason: string): string | null {
  if (!replay.decision.actions.some((a) => a.name === action)) return "Choose one of the listed actions.";
  if (action === replay.decision.chosen_action) return "Choose a different action from the recommendation.";
  return validateReason(reason);
}

export const canDecide = (replay: ReplayFile, tS: number, human: HumanOutcome | null): boolean =>
  decisionReached(replay, tS) && replay.decision.needs_human && human === null;

export function humanLogText(h: HumanOutcome): string {
  if (h.kind === "approve") return "Event dispatched (demo adapter): recommendation approved by a person.";
  if (h.kind === "override") return `Event dispatched (demo adapter): action changed to ${actionLabel(h.action)} by a person. Reason: ${h.reason.trim()}`;
  return `Event dispatched (demo adapter): recommendation rejected by a person. Reason: ${h.reason.trim()}`;
}

// ---------------------------------------------------------------- guarded switch

export const HOLD_MS = 600;
export const COOLDOWN_MS = 2000;

export const holdProgress = (startMs: number | null, nowMs: number): number =>
  startMs === null ? 0 : Math.min(1, Math.max(0, (nowMs - startMs) / HOLD_MS));
export const isArmed = (startMs: number | null, nowMs: number): boolean => holdProgress(startMs, nowMs) >= 1;
export const cooldownLeftMs = (lastUseMs: number | null, nowMs: number): number =>
  lastUseMs === null ? 0 : Math.max(0, COOLDOWN_MS - (nowMs - lastUseMs));

export interface Availability {
  enabled: boolean;
  reason: string | null;
}

export function switchAvailability(opts: { id: string; activeId: string | null; nowMs: number; lastUseMs: number | null; loading: boolean }): Availability {
  if (opts.loading) return { enabled: false, reason: "Data are still loading." };
  if (opts.id === opts.activeId) return { enabled: false, reason: "This scenario is already running." };
  const left = cooldownLeftMs(opts.lastUseMs, opts.nowMs);
  if (left > 0) return { enabled: false, reason: `Cooling down: ${Math.ceil(left / 1000)} s.` };
  return { enabled: true, reason: null };
}

// ---------------------------------------------------------------- tamper (recorded results)

export type TamperChoice = { kind: "edit"; entry: number } | { kind: "truncate" };

export interface Token {
  index: number;
  status: "verified" | "broken" | "after_break" | "removed";
}

export interface TamperOutcome {
  label: string;
  lines: string[];
  tokens: Token[];
  firstBroken: number | null;
}

export const TOKEN_WINDOW = 17;

function windowAround(center: number, length: number): [number, number] {
  const from = Math.max(0, Math.min(center - Math.floor(TOKEN_WINDOW / 2), length - TOKEN_WINDOW));
  return [from, Math.min(length, from + TOKEN_WINDOW)];
}

/** The untouched ribbon: a stretch of verified tokens around an entry. */
export function intactTokens(length: number, center: number): Token[] {
  const [from, to] = windowAround(center, length);
  return Array.from({ length: to - from }, (_, i) => ({ index: from + i, status: "verified" as const }));
}

export function tamperOptions(t: TamperData): { key: string; label: string; choice: TamperChoice }[] {
  return [
    ...t.edits.map((e) => ({ key: `edit-${e.entry}`, label: `Edit the temperature of entry ${e.entry}`, choice: { kind: "edit", entry: e.entry } as TamperChoice })),
    { key: "truncate", label: `Remove the last ${t.truncation.removed} entries`, choice: { kind: "truncate" } as TamperChoice },
  ];
}

/** The genuine recorded outcome for a choice (nothing is verified in the browser). */
export function tamperOutcome(t: TamperData, choice: TamperChoice): TamperOutcome | null {
  if (choice.kind === "edit") {
    const e = t.edits.find((x) => x.entry === choice.entry);
    if (!e) return null;
    const [from, to] = windowAround(e.first_broken_index, t.ledger_length);
    const tokens: Token[] = [];
    for (let i = from; i < to; i++) tokens.push({ index: i, status: i < e.first_broken_index ? "verified" : i === e.first_broken_index ? "broken" : "after_break" });
    return { label: t.label, lines: [`${e.action}.`, `Verify again: ${e.text}`], tokens, firstBroken: e.first_broken_index };
  }
  const n = t.ledger_length - t.truncation.removed;
  const [from, to] = windowAround(n - 1, n);
  const tokens: Token[] = Array.from({ length: to - from }, (_, i) => ({ index: from + i, status: "verified" as const }));
  for (let i = 0; i < Math.min(t.truncation.removed, 5); i++) tokens.push({ index: n + i, status: "removed" });
  return {
    label: t.label,
    lines: [`${t.truncation.action}.`, `Without an anchor: ${t.truncation.without_anchor.text}`, `With the anchor: ${t.truncation.with_anchor.text}`],
    tokens,
    firstBroken: t.truncation.with_anchor.ok ? null : n,
  };
}

// ---------------------------------------------------------------- event log

export interface LogLine {
  key: string;
  tS: number;
  wall: string | null;
  text: string;
}

export const formatSimTime = (tS: number): string => `T+${(tS / 3600).toFixed(1)} h`;

function describe(e: ScenarioEvent, replay: ReplayFile): string | null {
  const p = e.payload as Record<string, unknown>;
  if (e.type === "physics_check_fired") return `Physics check fired: ${String(p.check ?? "").replace(/_/g, " ")}.`;
  if (e.type === "verdict_changed") {
    if (!p.from) return null; // the first verdict of a run is not news
    return `Verdict changed: ${String(p.from).replace(/_/g, " ")} to ${String(p.to).replace(/_/g, " ")}.`;
  }
  if (e.type === "decision_proposed") {
    const how = replay.decision.needs_human ? "a person must decide" : "auto-approved within thresholds";
    return `Decision proposed: ${actionLabel(String(p.chosen_action))} (${how}).`;
  }
  return null;
}

/** The recorded events up to tS, plus the scenario start, oldest first (newest last). */
export function systemLog(replay: ReplayFile, tS: number): LogLine[] {
  const lines: LogLine[] = [{ key: "start", tS: 0, wall: null, text: `Scenario started: ${replay.meta.scenario_id} (replay of a recording, simulated).` }];
  replay.events.forEach((e, i) => {
    if (e.t_s > tS) return;
    const text = describe(e, replay);
    if (text) lines.push({ key: `e${i}`, tS: e.t_s, wall: null, text });
  });
  return lines;
}

export function mergeLog(system: readonly LogLine[], user: readonly LogLine[]): LogLine[] {
  return [...system, ...user].map((l, i) => ({ l, i })).sort((a, b) => a.l.tS - b.l.tS || a.i - b.i).map((x) => x.l);
}

export function wallStamp(date: Date): string {
  const two = (n: number) => String(n).padStart(2, "0");
  return `${two(date.getHours())}:${two(date.getMinutes())}:${two(date.getSeconds())}`;
}

// ---------------------------------------------------------------- recording mode

export type RecAction =
  | { type: "go"; hash: string; speed?: Speed }
  | { type: "tamper"; entryIndexInList: number }
  | { type: "approve" };

export interface RecStep {
  atMs: number;
  action: RecAction;
}

/** The scripted, repeatable demo sequence on the new pages (fixed timing; at 16x a simulated hour takes 0.125 s). */
export const REC_SEQUENCE: readonly RecStep[] = [
  { atMs: 0, action: { type: "go", hash: "#/shipments/baseline_ok", speed: 16 } },
  { atMs: 7000, action: { type: "go", hash: "#/shipments/hidden_spoilage", speed: 16 } },
  { atMs: 15000, action: { type: "approve" } },
  { atMs: 19000, action: { type: "go", hash: "#/proof" } },
  { atMs: 21000, action: { type: "tamper", entryIndexInList: 1 } },
  { atMs: 27000, action: { type: "go", hash: "#/about" } },
];
export const REC_LENGTH_MS = 31000;

/** Steps that fall in (prevMs, nowMs]; the first call uses prevMs = -1 so a step at 0 fires. */
export function dueSteps(steps: readonly RecStep[], prevMs: number, nowMs: number): RecStep[] {
  return steps.filter((s) => s.atMs > prevMs && s.atMs <= nowMs);
}

export const recordingRequested = (search: string): boolean => new URLSearchParams(search).get("rec") === "1";
