// Plain sentences built from the exported data (verdict, trust, route, chosen action, times). No
// figure is typed here: every number in a sentence is read from the replay file.
import type { ReplayFile } from "../data/types";
import { excursionBands } from "../controlroom/logic";
import { actionPhrase } from "./glossary";

export type StatusKind = "good" | "needs_person" | "not_trusted" | "problem";

export const STATUS_WORDS: Record<StatusKind, string> = {
  good: "All good",
  needs_person: "Needs a person",
  not_trusted: "Data not trusted",
  problem: "Problem found",
};

export const STATUS_ICON: Record<StatusKind, "ok" | "warn" | "alert" | "person"> = {
  good: "ok",
  needs_person: "person",
  not_trusted: "alert",
  problem: "warn",
};

const hours = (h: number): string => (Math.abs(h - Math.round(h)) < 0.05 ? String(Math.round(h)) : h.toFixed(1));

/** The time of the first physics check that fired, in hours, or null. */
export function firstCheckHours(replay: ReplayFile): number | null {
  const e = replay.events.find((x) => x.type === "physics_check_fired");
  return e ? e.t_s / 3600 : null;
}

export const isUntrusted = (replay: ReplayFile): boolean => replay.decision.trust_level === "untrusted";

export function totalExcursionHours(replay: ReplayFile): number {
  return excursionBands(replay.frames).reduce((sum, b) => sum + (b.toH - b.fromH), 0);
}

/** One word-and-icon status for a shipment card, from the data. */
export function statusKind(replay: ReplayFile): StatusKind {
  if (isUntrusted(replay)) return "not_trusted";
  if (replay.decision.needs_human) return "needs_person";
  if (excursionBands(replay.frames).length > 0 || replay.decision.verdict !== "ok") return "problem";
  return "good";
}

/** What happened, in one or two sentences, true to the data. */
export function whatHappened(replay: ReplayFile): string {
  const first = firstCheckHours(replay);
  if (isUntrusted(replay)) {
    return first === null
      ? "The temperature readings look wrong, so we cannot trust this data."
      : `The temperature readings look wrong: at about ${hours(first)} hours they did something a real box cannot do, so we cannot trust this data.`;
  }
  const bands = excursionBands(replay.frames);
  if (bands.length > 0) {
    const start = bands[0].fromH;
    const total = totalExcursionHours(replay);
    return `The temperature left its safe range at about ${hours(start)} hours and spent about ${hours(total)} hours outside it.`;
  }
  return "The temperature stayed in its safe range the whole way.";
}

/** The plain headline sentence for a shipment page. */
export function headline(replay: ReplayFile): string {
  const d = replay.decision;
  const parts = [whatHappened(replay)];
  if (isUntrusted(replay) && d.worst_case.bound_used) parts.push("Because of that, the plan assumes the worst case.");
  parts.push(`We recommend: ${actionPhrase(d.chosen_action)}.`);
  parts.push(d.needs_human ? "A person needs to approve this." : "This was approved automatically within the safety limits.");
  return parts.join(" ");
}

/** The reasons behind the recommendation, in plain words, from fields of the decision. */
export function plainReasons(replay: ReplayFile): string[] {
  const d = replay.decision;
  const out: string[] = [];
  if (isUntrusted(replay)) out.push("The checks do not trust the temperature readings, so the plan starts from the worst case.");
  else if (d.trust_level !== "trusted") out.push("The checks only partly trust the readings.");
  if (d.close_call) out.push("Two options were almost tied, so a person should choose.");
  const cheaper = [...d.actions].sort((a, b) => a.cvar - b.cvar)[0];
  if (cheaper) out.push(`In the worst 5% of cases, "${actionPhrase(cheaper.name)}" costs the least.`);
  if (d.needs_human && out.length === 0) out.push("This kind of decision always needs a person.");
  if (!d.needs_human) out.push("The data are trusted and the cost is within the safety limits.");
  return out;
}

export function strengthPercent(replay: ReplayFile, tS?: number): number {
  const frames = replay.frames;
  const t = tS ?? replay.meta.checkpoint_h * 3600;
  let best = frames[0];
  for (const f of frames) if (f.t_s <= t) best = f;
  return best.potency * 100;
}
