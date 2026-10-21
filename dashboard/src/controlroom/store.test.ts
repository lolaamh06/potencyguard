import { beforeEach, describe, expect, it } from "vitest";
import baseline from "../../public/replay/baseline_ok.json";
import hidden from "../../public/replay/hidden_spoilage.json";
import type { ReplayFile } from "../data/types";
import { endSeconds } from "./logic";
import { crClock, useCr } from "./store";

const base = baseline as unknown as ReplayFile;
const hs = hidden as unknown as ReplayFile;

beforeEach(() => {
  useCr.getState().selectScenario("baseline_ok", 0);
  useCr.getState().setSpeed(4);
});

describe("scenario switching and reset", () => {
  it("switching clears the clock, the human outcome and the tamper view, and logs the selection", () => {
    const s = useCr.getState();
    s.tick(0.2, hs, 1000);
    expect(crClock.tS).toBeGreaterThan(0);
    s.selectScenario("hidden_spoilage", 5000, "armed by hold");
    const after = useCr.getState();
    expect(after.scenarioId).toBe("hidden_spoilage");
    expect(after.tS).toBe(0);
    expect(crClock.tS).toBe(0);
    expect(after.human).toBeNull();
    expect(after.tamper).toBeNull();
    expect(after.userLog).toHaveLength(1);
    expect(after.userLog[0].text).toContain("Scenario selected: hidden_spoilage");
  });

  it("reset returns to time zero, keeps the scenario and speed, and logs it", () => {
    const s = useCr.getState();
    s.setSpeed(16);
    s.tick(0.2, base, 1000);
    s.reset();
    const after = useCr.getState();
    expect(crClock.tS).toBe(0);
    expect(after.speed).toBe(16);
    expect(after.scenarioId).toBe("baseline_ok");
    expect(after.userLog[0].text).toContain("Scenario reset");
  });
});

describe("clock through the store", () => {
  it("advances by speed, pauses, and holds the final frame", () => {
    const s = useCr.getState();
    s.tick(0.1, base, 1000);
    const t1 = crClock.tS;
    expect(t1).toBeGreaterThan(0);
    s.togglePause();
    s.tick(0.1, base, 2000);
    expect(crClock.tS).toBe(t1);
    s.togglePause();
    s.setSpeed(16);
    for (let i = 0; i < 2000; i++) s.tick(0.25, base, 3000 + i * 300);
    expect(crClock.tS).toBe(endSeconds(base));
    expect(useCr.getState().tS).toBe(endSeconds(base));
  });
});

describe("demo decisions", () => {
  it("refuses a decision before the planner has decided, then accepts approval once", () => {
    const s = useCr.getState();
    s.selectScenario("hidden_spoilage", 0);
    expect(useCr.getState().decide(hs, { kind: "approve" })).toContain("not open");
    for (let i = 0; i < 600; i++) useCr.getState().tick(0.25, hs, i * 300);
    expect(useCr.getState().decide(hs, { kind: "approve" })).toBeNull();
    expect(useCr.getState().human).toEqual({ kind: "approve" });
    expect(useCr.getState().userLog.some((l) => l.text.startsWith("Event dispatched (demo adapter)"))).toBe(true);
    expect(useCr.getState().decide(hs, { kind: "approve" })).toContain("not open");
  });

  it("rejects an override with a short reason and accepts a good one", () => {
    useCr.getState().selectScenario("hidden_spoilage", 0);
    for (let i = 0; i < 600; i++) useCr.getState().tick(0.25, hs, i * 300);
    const other = hs.decision.actions.find((a) => a.name !== hs.decision.chosen_action)!.name;
    expect(useCr.getState().decide(hs, { kind: "override", action: other, reason: "short" })).toContain("10 characters");
    expect(useCr.getState().human).toBeNull();
    expect(useCr.getState().decide(hs, { kind: "override", action: other, reason: "a good enough reason" })).toBeNull();
  });
});

describe("tamper through the store", () => {
  it("applies the picked recorded result and can clear it", () => {
    const s = useCr.getState();
    s.selectScenario("hidden_spoilage", 0);
    s.pickTamper(`edit-${hs.tamper.edits[1].entry}`);
    s.applyTamper(hs);
    expect(useCr.getState().tamper).toEqual({ kind: "edit", entry: hs.tamper.edits[1].entry });
    expect(useCr.getState().userLog[useCr.getState().userLog.length - 1].text).toContain("Recorded result");
    useCr.getState().clearTamper();
    expect(useCr.getState().tamper).toBeNull();
  });
});
