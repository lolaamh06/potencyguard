import { beforeEach, describe, expect, it } from "vitest";
import baseline from "../../public/replay/baseline_ok.json";
import door from "../../public/replay/door_open_excursion.json";
import hidden from "../../public/replay/hidden_spoilage.json";
import reefer from "../../public/replay/reefer_failure.json";
import spoof from "../../public/replay/spoof_attempt.json";
import { MIN_REASON } from "../controlroom/logic";
import { useCr } from "../controlroom/store";
import type { AdapterSnapshot, ReplayFile } from "../data/types";
import { decidedList, pendingQueue } from "./DecisionsPage";

const scenarios = {
  baseline_ok: baseline, door_open_excursion: door, reefer_failure: reefer, spoof_attempt: spoof, hidden_spoilage: hidden,
} as unknown as AdapterSnapshot["scenarios"];
const hs = hidden as unknown as ReplayFile;

beforeEach(() => useCr.getState().clearDecisions());

describe("the Decisions queue", () => {
  it("lists exactly the shipments that need a person, in the fixed order", () => {
    expect(pendingQueue(scenarios, {}).map((q) => q.id)).toEqual(["spoof_attempt", "hidden_spoilage"]);
    expect(decidedList(scenarios, {})).toEqual([]);
  });

  it("moves an item from waiting to decided once a person has acted", () => {
    expect(useCr.getState().decide(hs, { kind: "approve" }, { ignoreClock: true })).toBeNull();
    const out = useCr.getState().outcomes;
    expect(pendingQueue(scenarios, out).map((q) => q.id)).toEqual(["spoof_attempt"]);
    expect(decidedList(scenarios, out).map((q) => q.id)).toEqual(["hidden_spoilage"]);
  });
});

describe("the Decisions forms (reason rules reused from the tested logic)", () => {
  const other = hs.decision.actions.find((a) => a.name !== hs.decision.chosen_action)!.name;

  it("needs a reason of at least 10 characters to choose a different action", () => {
    const short = useCr.getState().decide(hs, { kind: "override", action: other, reason: "too short" }, { ignoreClock: true });
    expect(short).toContain(String(MIN_REASON));
    expect(useCr.getState().outcomes.hidden_spoilage).toBeUndefined();
    expect(useCr.getState().decide(hs, { kind: "override", action: other, reason: "this is a proper reason" }, { ignoreClock: true })).toBeNull();
    expect(useCr.getState().outcomes.hidden_spoilage).toMatchObject({ kind: "override", action: other });
  });

  it("needs a reason to reject, and refuses a different action that is the recommendation itself", () => {
    expect(useCr.getState().decide(hs, { kind: "reject", reason: "   " }, { ignoreClock: true })).toContain(String(MIN_REASON));
    expect(useCr.getState().decide(hs, { kind: "override", action: hs.decision.chosen_action, reason: "a good enough reason" }, { ignoreClock: true })).toContain("different");
    expect(useCr.getState().decide(hs, { kind: "reject", reason: "the readings look wrong to me" }, { ignoreClock: true })).toBeNull();
  });

  it("refuses a second decision for the same shipment and any decision on a shipment that needs none", () => {
    useCr.getState().decide(hs, { kind: "approve" }, { ignoreClock: true });
    expect(useCr.getState().decide(hs, { kind: "approve" }, { ignoreClock: true })).toContain("not open");
    expect(useCr.getState().decide(baseline as unknown as ReplayFile, { kind: "approve" }, { ignoreClock: true })).toContain("not open");
  });

  it("only offers the decision on a shipment page once the simulated clock reaches the decision time", () => {
    useCr.getState().selectScenario("hidden_spoilage", 0);
    expect(useCr.getState().decide(hs, { kind: "approve" })).toContain("not open");
    expect(useCr.getState().decide(hs, { kind: "approve" }, { ignoreClock: true })).toBeNull();
  });
});
