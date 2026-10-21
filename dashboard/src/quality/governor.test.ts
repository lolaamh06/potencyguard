import { describe, expect, it } from "vitest";
import {
  DEFAULT_GOVERNOR,
  cycleTier,
  effectiveDpr,
  initialGovernor,
  nextTierDown,
  parseTier,
  stepGovernor,
  tierSettings,
  type GovernorState,
} from "./governor";

const run = (state: GovernorState, windows: number[]): GovernorState =>
  windows.reduce((s, ms) => stepGovernor(s, ms), state);

describe("tier helpers", () => {
  it("steps down one tier at a time and stays on low", () => {
    expect(nextTierDown("high")).toBe("medium");
    expect(nextTierDown("medium")).toBe("low");
    expect(nextTierDown("low")).toBe("low");
    expect(nextTierDown("fallback2d")).toBe("fallback2d");
  });

  it("cycles high, medium, low, 2D, high", () => {
    expect(cycleTier("high")).toBe("medium");
    expect(cycleTier("medium")).toBe("low");
    expect(cycleTier("low")).toBe("fallback2d");
    expect(cycleTier("fallback2d")).toBe("high");
  });

  it("parses ?tier= and ignores anything else", () => {
    expect(parseTier("?tier=low")).toBe("low");
    expect(parseTier("?mode=replay&tier=fallback2d")).toBe("fallback2d");
    expect(parseTier("?tier=ultra")).toBeNull();
    expect(parseTier("")).toBeNull();
  });

  it("caps the pixel ratio by tier and never goes below 1", () => {
    expect(effectiveDpr(3, "high")).toBe(2);
    expect(effectiveDpr(3, "medium")).toBe(1.5);
    expect(effectiveDpr(3, "low")).toBe(1);
    expect(effectiveDpr(0.5, "high")).toBe(1);
  });

  it("only high and medium have post-processing; 2D has no WebGL", () => {
    expect(tierSettings("high").bloom && tierSettings("high").vignette).toBe(true);
    expect(tierSettings("medium").bloom).toBe(true);
    expect(tierSettings("low").bloom).toBe(false);
    expect(tierSettings("low").vignette).toBe(false);
    expect(tierSettings("fallback2d").webgl).toBe(false);
    expect(tierSettings("high").dotSamples).toBeGreaterThan(tierSettings("medium").dotSamples);
    expect(tierSettings("medium").dotSamples).toBeGreaterThan(tierSettings("low").dotSamples);
  });
});

describe("governor", () => {
  const warm = { ...initialGovernor("high"), warmupLeft: 0 };

  it("ignores the warm-up windows", () => {
    const state = run(initialGovernor("high"), [90, 90]);
    expect(state.tier).toBe("high");
    expect(state.warmupLeft).toBe(0);
  });

  it("steps down only after several bad windows in a row", () => {
    expect(run(warm, [40, 40]).tier).toBe("high");
    expect(run(warm, [40, 40, 40]).tier).toBe("medium");
  });

  it("a good window resets the streak", () => {
    expect(run(warm, [40, 40, 10, 40, 40]).tier).toBe("high");
  });

  it("waits again after a change, then can step down again", () => {
    let state = run(warm, [40, 40, 40]);
    expect(state.tier).toBe("medium");
    expect(state.warmupLeft).toBe(DEFAULT_GOVERNOR.warmupWindows);
    state = run(state, [40, 40]);
    expect(state.tier).toBe("medium");
    state = run(state, [40, 40, 40]);
    expect(state.tier).toBe("low");
  });

  it("never steps up, however good the frames are", () => {
    const low = { tier: "low" as const, badStreak: 0, warmupLeft: 0 };
    expect(run(low, Array(50).fill(4)).tier).toBe("low");
    const medium = { tier: "medium" as const, badStreak: 0, warmupLeft: 0 };
    expect(run(medium, Array(50).fill(4)).tier).toBe("medium");
  });

  it("never goes below low, and never to the 2D fallback on its own", () => {
    const low = { tier: "low" as const, badStreak: 0, warmupLeft: 0 };
    expect(run(low, Array(30).fill(200)).tier).toBe("low");
  });

  it("ignores impossible frame times", () => {
    expect(stepGovernor(warm, Number.NaN)).toBe(warm);
    expect(stepGovernor(warm, 0)).toBe(warm);
    expect(stepGovernor(warm, -5)).toBe(warm);
  });
});
