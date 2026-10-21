// "What happened" as plain sentences, from the recorded events up to the replay time. Nothing is
// typed by hand except the words around the data.
import type { ReplayFile } from "../data/types";
import type { HumanOutcome } from "../controlroom/logic";
import { actionLabel, actionPhrase, trustAnswer, verdictLabel, type ReadingMode } from "./glossary";

export interface TimelineLine {
  key: string;
  hours: number;
  text: string;
}

const CHECK_WORDS: Record<string, string> = {
  cusum_neg: "the temperature drifted away from what we expected",
  cusum_pos: "the temperature drifted away from what we expected",
  impossible_step: "the temperature jumped in a way a real box cannot",
  impossible_state: "the temperature reading was physically impossible",
  flat_line: "the readings went suspiciously flat",
};

const h = (tS: number): string => {
  const v = tS / 3600;
  return Math.abs(v - Math.round(v)) < 0.05 ? String(Math.round(v)) : v.toFixed(1);
};

export function checkWords(check: string): string {
  return CHECK_WORDS[check] ?? check.replace(/_/g, " ");
}

export function timelineLines(replay: ReplayFile, tS: number, mode: ReadingMode, human: HumanOutcome | null): TimelineLine[] {
  const lines: TimelineLine[] = [{ key: "start", hours: 0, text: "The journey began." }];
  replay.events.forEach((e, i) => {
    if (e.t_s > tS) return;
    const p = e.payload as Record<string, unknown>;
    if (e.type === "physics_check_fired") {
      lines.push({ key: `e${i}`, hours: e.t_s / 3600, text: `At ${h(e.t_s)} hours a safety check fired: ${checkWords(String(p.check ?? ""))}.` });
    } else if (e.type === "verdict_changed" && p.from) {
      lines.push({ key: `e${i}`, hours: e.t_s / 3600, text: `At ${h(e.t_s)} hours the verdict changed: ${verdictLabel(String(p.to), mode).toLowerCase()}.` });
    } else if (e.type === "decision_proposed") {
      const trust = trustAnswer(replay.decision.trust_level, "simple");
      lines.push({
        key: `e${i}`,
        hours: e.t_s / 3600,
        text: `At ${h(e.t_s)} hours the system recommended: ${actionPhrase(String(p.chosen_action))}. Can we trust this data? ${trust}.`,
      });
    }
  });
  if (human) {
    const text =
      human.kind === "approve"
        ? "A person approved the recommendation (demo: this changed this screen only)."
        : human.kind === "override"
          ? `A person chose a different action: ${actionLabel(human.action, "simple").toLowerCase()} (demo: this changed this screen only).`
          : "A person rejected the recommendation (demo: this changed this screen only).";
    lines.push({ key: "human", hours: tS / 3600, text });
  }
  return lines;
}
