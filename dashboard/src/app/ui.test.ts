import { beforeEach, describe, expect, it } from "vitest";
import { term } from "../copy/glossary";
import { TOUR_STEPS, useUi } from "./ui";

beforeEach(() => {
  useUi.setState({ mode: "simple", themeChoice: "system", tourStep: null, tourSeen: false, menuOpen: false });
});

describe("the Simple / Technical switch", () => {
  it("defaults to Simple", () => {
    expect(useUi.getState().mode).toBe("simple");
  });

  it("switches globally and the glossary follows it", () => {
    const pick = () => term("worstFive", useUi.getState().mode);
    expect(pick()).toBe("Cost in the worst 5% of cases");
    useUi.getState().setMode("technical");
    expect(useUi.getState().mode).toBe("technical");
    expect(pick()).toContain("CVaR");
    useUi.getState().setMode("simple");
    expect(pick()).toBe("Cost in the worst 5% of cases");
  });
});

describe("theme choice", () => {
  it("remembers the choice and resolves light and dark directly", () => {
    useUi.getState().setTheme("light");
    expect(useUi.getState().themeChoice).toBe("light");
    expect(useUi.getState().resolved).toBe("light");
    useUi.getState().setTheme("dark");
    expect(useUi.getState().resolved).toBe("dark");
  });
});

describe("the guided tour", () => {
  it("has the five steps the product promises, in order", () => {
    expect(TOUR_STEPS).toHaveLength(5);
    expect(TOUR_STEPS.map((s) => s.title.replace(/^\d\. /, ""))).toEqual([
      "Pick a shipment", "Watch it play", "Read the recommendation", "Approve or choose another", "Check the proof",
    ]);
  });

  it("starts, steps forward and back, never below the first step, and ends after the last", () => {
    const u = useUi.getState();
    u.startTour();
    expect(useUi.getState().tourStep).toBe(0);
    useUi.getState().stepTour(-1);
    expect(useUi.getState().tourStep).toBe(0);
    for (let i = 0; i < 4; i++) useUi.getState().stepTour(1);
    expect(useUi.getState().tourStep).toBe(4);
    useUi.getState().stepTour(1);
    expect(useUi.getState().tourStep).toBeNull();
    expect(useUi.getState().tourSeen).toBe(true);
  });

  it("can be skipped at any step", () => {
    useUi.getState().startTour();
    useUi.getState().stepTour(1);
    useUi.getState().endTour();
    expect(useUi.getState().tourStep).toBeNull();
    expect(useUi.getState().tourSeen).toBe(true);
  });
});
