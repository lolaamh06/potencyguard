import { describe, expect, it } from "vitest";
import { cycleTier, effectiveDpr, nextTierDown, tierSettings } from "./qualityTier";

describe("quality tiers", () => {
  it("steps down one tier at a time and stops at low", () => {
    expect(nextTierDown("low")).toBe("low");
    expect(nextTierDown("high")).toBe("medium");
    expect(nextTierDown("medium")).toBe("low");
  });

  it("cycles high -> medium -> low -> high", () => {
    expect(cycleTier("high")).toBe("medium");
    expect(cycleTier("medium")).toBe("low");
    expect(cycleTier("low")).toBe("high");
  });

  it("turns bloom off only on low", () => {
    expect(tierSettings("low").bloom).toBe(false);
    expect(tierSettings("high").bloom).toBe(true);
  });

  it("has strictly decreasing point counts from high to low", () => {
    expect(tierSettings("high").pointCount).toBeGreaterThan(tierSettings("medium").pointCount);
    expect(tierSettings("medium").pointCount).toBeGreaterThan(tierSettings("low").pointCount);
  });

  it("keeps the effective pixel ratio between 1 and the tier cap", () => {
    expect(effectiveDpr(3, "high")).toBe(2);
    expect(effectiveDpr(3, "medium")).toBe(1.5);
    expect(effectiveDpr(3, "low")).toBe(1);
    expect(effectiveDpr(0.5, "high")).toBe(1);
    expect(effectiveDpr(1.25, "high")).toBe(1.25);
  });
});
