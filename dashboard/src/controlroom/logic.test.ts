import { describe, expect, it } from "vitest";
import baseline from "../../public/replay/baseline_ok.json";
import hidden from "../../public/replay/hidden_spoilage.json";
import reefer from "../../public/replay/reefer_failure.json";
import type { ReplayFile } from "../data/types";
import {
  COOLDOWN_MS,
  HOLD_MS,
  REC_LENGTH_MS,
  REC_SEQUENCE,
  SCENARIO_IDS,
  SIM_S_PER_WALL_S,
  advance,
  canDecide,
  cooldownLeftMs,
  decisionReached,
  dueSteps,
  endSeconds,
  excursionBands,
  frameIndexAt,
  holdProgress,
  humanLogText,
  initialClock,
  intactTokens,
  isArmed,
  mergeLog,
  recordingRequested,
  resetClock,
  ringValues,
  routeStateFor,
  scenarioForKey,
  showAlternative,
  statusChip,
  switchAvailability,
  systemLog,
  tamperOptions,
  tamperOutcome,
  trustChip,
  validateOverride,
  validateReason,
  wallStamp,
} from "./logic";

const base = baseline as unknown as ReplayFile;
const hs = hidden as unknown as ReplayFile;
const rf = reefer as unknown as ReplayFile;

describe("scenarios", () => {
  it("has the five featured scenarios and keys 1 to 5 pick them in order", () => {
    expect([...SCENARIO_IDS]).toEqual(["baseline_ok", "door_open_excursion", "reefer_failure", "spoof_attempt", "hidden_spoilage"]);
    expect(scenarioForKey("1")).toBe("baseline_ok");
    expect(scenarioForKey("5")).toBe("hidden_spoilage");
    expect(scenarioForKey("6")).toBeNull();
    expect(scenarioForKey("0")).toBeNull();
    expect(scenarioForKey("a")).toBeNull();
  });
});

describe("replay clock", () => {
  it("runs at 1800 simulated seconds per wall second at 1x and scales with speed", () => {
    const c1 = advance(initialClock(1), 0.1, 1e9);
    expect(c1.tS).toBeCloseTo(0.1 * SIM_S_PER_WALL_S, 6);
    expect(advance(initialClock(4), 0.1, 1e9).tS).toBeCloseTo(0.4 * SIM_S_PER_WALL_S, 6);
    expect(advance(initialClock(16), 0.1, 1e9).tS).toBeCloseTo(1.6 * SIM_S_PER_WALL_S, 6);
  });

  it("does not move when paused, ignores bad steps, caps a long step and holds the final frame", () => {
    const paused = { ...initialClock(4), paused: true };
    expect(advance(paused, 1, 1e9)).toBe(paused);
    expect(advance(initialClock(), 0, 100).tS).toBe(0);
    expect(advance(initialClock(), -1, 100).tS).toBe(0);
    expect(advance(initialClock(1), 10, 1e9).tS).toBeCloseTo(0.25 * SIM_S_PER_WALL_S, 6);
    const end = endSeconds(base);
    const held = advance({ tS: end - 5, speed: 16, paused: false }, 0.2, end);
    expect(held.tS).toBe(end);
    expect(advance(held, 0.2, end)).toBe(held);
  });

  it("resets cleanly and keeps the chosen speed", () => {
    const r = resetClock({ tS: 999, speed: 16, paused: true });
    expect(r).toEqual({ tS: 0, speed: 16, paused: false });
  });

  it("finds the frame at a time", () => {
    expect(frameIndexAt(base.frames, -5)).toBe(0);
    expect(frameIndexAt(base.frames, 0)).toBe(0);
    const i = frameIndexAt(base.frames, base.frames[10].t_s + 1);
    expect(i).toBe(10);
    expect(frameIndexAt(base.frames, 1e12)).toBe(base.frames.length - 1);
    expect(frameIndexAt([], 5)).toBe(0);
  });
});

describe("view model (frames in, display values out; no planner maths)", () => {
  it("maps the status by time and by what a person did", () => {
    expect(statusChip(hs, 0, null).text).toContain("no decision yet");
    const after = hs.meta.checkpoint_h * 3600;
    expect(statusChip(hs, after, null)).toEqual({ icon: "warn", text: "quarantined pending review" });
    expect(statusChip(base, base.meta.checkpoint_h * 3600, null).text).toBe("auto-approved within thresholds");
    expect(statusChip(hs, after, { kind: "approve" }).text).toContain("approved by a person");
    expect(statusChip(hs, after, { kind: "reject", reason: "not convinced" }).text).toContain("rejected");
  });

  it("marks untrusted data as danger and a normal run as safe", () => {
    const late = hs.frames[hs.frames.length - 1];
    expect(routeStateFor(late, hs, late.t_s)).toBe("danger");
    expect(trustChip(late).icon).toBe("alert");
    const first = base.frames[0];
    expect(routeStateFor(first, base, 0)).toBe("safe");
    expect(trustChip(first).text).toBe("Trust: trusted");
  });

  it("shows the alternative route only for a reroute recommendation after the decision", () => {
    expect(showAlternative(rf, 0)).toBe(false);
    expect(showAlternative(rf, rf.meta.checkpoint_h * 3600)).toBe(rf.decision.chosen_action === "reroute_to_depot");
    expect(showAlternative(base, 1e9)).toBe(false);
  });

  it("passes the exported values through as the big numbers", () => {
    const f = base.frames[5];
    const r = ringValues(f);
    expect(r.potencyPercent).toBeCloseTo(f.potency * 100, 9);
    expect(r.usedPercent).toBeCloseTo(f.shelf_life_used_fraction * 100, 9);
    expect(r.tauH).toBe(f.tau_eq_h);
    expect(r.tempC).toBe(f.temp_c);
  });

  it("finds excursion bands where the reported temperature leaves 2 to 8 C", () => {
    const frames = [2, 5, 9, 10, 5, 3, 1].map((t, i) => ({ ...base.frames[0], t_s: i * 3600, temp_c: t }));
    expect(excursionBands(frames)).toEqual([
      { fromH: 2, toH: 4 },
      { fromH: 6, toH: 6 },
    ]);
    expect(excursionBands([])).toEqual([]);
  });

  it("knows when the decision has been reached", () => {
    expect(decisionReached(hs, 0)).toBe(false);
    expect(decisionReached(hs, hs.meta.checkpoint_h * 3600)).toBe(true);
  });
});

describe("approval and override rules", () => {
  it("needs a reason of at least 10 characters (trimmed)", () => {
    expect(validateReason("short")).not.toBeNull();
    expect(validateReason("   a b c    ")).not.toBeNull();
    expect(validateReason("ten chars!")).toBeNull();
    expect(validateReason("a perfectly good reason")).toBeNull();
  });

  it("overrides need a different, listed action and a reason", () => {
    const chosen = hs.decision.chosen_action;
    expect(validateOverride(hs, "no_such_action", "a perfectly good reason")).not.toBeNull();
    expect(validateOverride(hs, chosen, "a perfectly good reason")).toContain("different");
    const other = hs.decision.actions.find((a) => a.name !== chosen)!.name;
    expect(validateOverride(hs, other, "too short")).not.toBeNull();
    expect(validateOverride(hs, other, "quality assurance prefers this")).toBeNull();
  });

  it("only offers a human decision for a needs-a-person case after the decision, once", () => {
    const after = hs.meta.checkpoint_h * 3600;
    expect(canDecide(hs, 0, null)).toBe(false);
    expect(canDecide(hs, after, null)).toBe(true);
    expect(canDecide(hs, after, { kind: "approve" })).toBe(false);
    expect(canDecide(base, 1e9, null)).toBe(false);
  });

  it("words the log line as a demo adapter event", () => {
    expect(humanLogText({ kind: "approve" })).toMatch(/^Event dispatched \(demo adapter\)/);
    expect(humanLogText({ kind: "override", action: "quarantine", reason: " because we say so " })).toContain("Quarantine");
    expect(humanLogText({ kind: "reject", reason: "no good reason" })).toContain("rejected");
  });
});

describe("hold-to-arm and cooldown (pure)", () => {
  it("fills over 600 ms and arms at the end", () => {
    expect(holdProgress(null, 1000)).toBe(0);
    expect(holdProgress(1000, 1000)).toBe(0);
    expect(holdProgress(1000, 1000 + HOLD_MS / 2)).toBeCloseTo(0.5, 9);
    expect(holdProgress(1000, 1000 + HOLD_MS * 3)).toBe(1);
    expect(isArmed(1000, 1000 + HOLD_MS - 1)).toBe(false);
    expect(isArmed(1000, 1000 + HOLD_MS)).toBe(true);
    expect(holdProgress(1000, 500)).toBe(0);
  });

  it("cools down for 2 seconds after use", () => {
    expect(cooldownLeftMs(null, 5000)).toBe(0);
    expect(cooldownLeftMs(5000, 5000)).toBe(COOLDOWN_MS);
    expect(cooldownLeftMs(5000, 5000 + COOLDOWN_MS)).toBe(0);
    expect(cooldownLeftMs(5000, 9999)).toBe(0);
  });

  it("gives a reason whenever a switch is disabled", () => {
    const ok = { id: "a", activeId: "b", nowMs: 10_000, lastUseMs: null, loading: false };
    expect(switchAvailability(ok)).toEqual({ enabled: true, reason: null });
    expect(switchAvailability({ ...ok, loading: true }).reason).toContain("loading");
    expect(switchAvailability({ ...ok, activeId: "a" }).reason).toContain("already running");
    const cooling = switchAvailability({ ...ok, lastUseMs: 9_500 });
    expect(cooling.enabled).toBe(false);
    expect(cooling.reason).toContain("Cooling down");
  });
});

describe("tamper selection (recorded results)", () => {
  const t = hs.tamper;

  it("offers every recorded edit position and the truncation", () => {
    const options = tamperOptions(t);
    expect(options).toHaveLength(t.edits.length + 1);
    expect(options[options.length - 1].choice.kind).toBe("truncate");
    expect(options[0].label).toContain(String(t.edits[0].entry));
  });

  it("shows the genuine recorded outcome: link cracks at the first broken entry, later links dim", () => {
    for (const e of t.edits) {
      const out = tamperOutcome(t, { kind: "edit", entry: e.entry })!;
      expect(out.firstBroken).toBe(e.first_broken_index);
      expect(out.lines.join(" ")).toContain(e.text);
      const broken = out.tokens.filter((x) => x.status === "broken");
      expect(broken).toHaveLength(1);
      expect(broken[0].index).toBe(e.first_broken_index);
      for (const tok of out.tokens) {
        if (tok.index < e.first_broken_index) expect(tok.status).toBe("verified");
        if (tok.index > e.first_broken_index) expect(tok.status).toBe("after_break");
      }
    }
    expect(tamperOutcome(t, { kind: "edit", entry: -7 })).toBeNull();
  });

  it("truncation: passes without an anchor, is caught with it", () => {
    const out = tamperOutcome(t, { kind: "truncate" })!;
    expect(out.lines.join(" ")).toContain("Without an anchor");
    expect(out.lines.join(" ")).toContain("With the anchor");
    expect(out.tokens.filter((x) => x.status === "removed").length).toBeGreaterThan(0);
    expect(t.truncation.without_anchor.ok).toBe(true);
    expect(t.truncation.with_anchor.ok).toBe(false);
  });

  it("keeps the window inside the ledger and labels the result honestly", () => {
    const tokens = intactTokens(t.ledger_length, 0);
    expect(tokens[0].index).toBe(0);
    expect(tokens.length).toBeLessThanOrEqual(17);
    const end = intactTokens(t.ledger_length, t.ledger_length - 1);
    expect(end[end.length - 1].index).toBe(t.ledger_length - 1);
    expect(t.label).toBe("Result of a real edit on a ledger copy (recorded)");
  });
});

describe("event log", () => {
  it("starts with the scenario, then lists recorded events up to the clock, oldest first", () => {
    const early = systemLog(hs, 0);
    expect(early).toHaveLength(1);
    expect(early[0].text).toContain("hidden_spoilage");
    const later = systemLog(hs, endSeconds(hs));
    expect(later.length).toBeGreaterThan(2);
    expect(later.some((l) => l.text.startsWith("Physics check fired"))).toBe(true);
    expect(later.some((l) => l.text.startsWith("Decision proposed"))).toBe(true);
    const times = later.map((l) => l.tS);
    expect([...times].sort((a, b) => a - b)).toEqual(times);
  });

  it("merges user lines in time order and keeps neutral wording", () => {
    const sys = systemLog(hs, endSeconds(hs));
    const merged = mergeLog(sys, [{ key: "u1", tS: 100, wall: "10:00:00", text: "Event dispatched (demo adapter): x" }]);
    expect(merged).toHaveLength(sys.length + 1);
    expect(merged.every((l, i) => i === 0 || merged[i - 1].tS <= l.tS)).toBe(true);
    for (const l of merged) expect(l.text).not.toMatch(/SAP|connected to/i);
    expect(wallStamp(new Date(2026, 9, 21, 7, 5, 9))).toBe("07:05:09");
  });
});

describe("recording sequence", () => {
  it("is ordered, starts at 0 and ends before its stated length", () => {
    const times = REC_SEQUENCE.map((s) => s.atMs);
    expect([...times].sort((a, b) => a - b)).toEqual(times);
    expect(times[0]).toBe(0);
    expect(times[times.length - 1]).toBeLessThan(REC_LENGTH_MS);
  });

  it("fires each step once as time passes, including the one at 0", () => {
    const fired: number[] = [];
    let prev = -1;
    for (let now = 0; now <= REC_LENGTH_MS; now += 250) {
      for (const s of dueSteps(REC_SEQUENCE, prev, now)) fired.push(s.atMs);
      prev = now;
    }
    expect(fired).toEqual(REC_SEQUENCE.map((s) => s.atMs));
    expect(dueSteps(REC_SEQUENCE, 100, 100)).toEqual([]);
  });

  it("picks the demo scenarios in order, tampers, then approves", () => {
    const kinds = REC_SEQUENCE.map((s) => s.action.type);
    expect(kinds).toEqual(["scenario", "scenario", "tamper", "approve", "provenance", "provenance"]);
  });

  it("is requested by ?rec=1 only", () => {
    expect(recordingRequested("?rec=1")).toBe(true);
    expect(recordingRequested("?rec=0")).toBe(false);
    expect(recordingRequested("")).toBe(false);
  });
});
