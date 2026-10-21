import { describe, expect, it } from "vitest";
import chapter1 from "./bundled/chapter1.json";
import chapter5 from "../../public/story/chapter5.json";
import chapter6 from "../../public/story/chapter6.json";
import type { StoryData } from "./types";
import { constantsFor, flipAlphas, litFlags, rowForAlpha, scrubJourney, validateChapter5, validateChapter6, type Ch5Row } from "./story";

const story = chapter1 as unknown as StoryData;

describe("chapter 1 scrub (potency mirror) against the exported figures", () => {
  it("matches the exported end-of-journey figures for both profiles and both journeys", () => {
    for (const profile of ["active", "reference"] as const) {
      const c = constantsFor(story, profile);
      for (const key of ["A", "B"]) {
        const j = story.journeys[key];
        const wanted = story.profiles[profile].journeys[key];
        const got = scrubJourney(j.temp_c, j.hours, 1, c);
        expect(got.shelfLifeUsedPercent).toBeCloseTo(wanted.shelf_life_used_percent, 9);
        expect(got.potency).toBeCloseTo(wanted.potency, 12);
      }
    }
  });

  it("starts at full potency, falls steadily, and clamps the handle", () => {
    const c = constantsFor(story, "active");
    const { temp_c, hours } = story.journeys.B;
    expect(scrubJourney(temp_c, hours, 0, c).potency).toBe(1);
    let prev = 1;
    for (let i = 1; i <= 20; i++) {
      const p = scrubJourney(temp_c, hours, i / 20, c).potency;
      expect(p).toBeLessThan(prev);
      prev = p;
    }
    expect(scrubJourney(temp_c, hours, 9, c).hours).toBe(hours);
    expect(scrubJourney(temp_c, hours, -1, c).hours).toBe(0);
  });

  it("matches the hourly exported curve", () => {
    const c = constantsFor(story, "active");
    const curve = (story.profiles.active as unknown as { curves: Record<string, { h: number; potency: number }[]> }).curves.B;
    for (const point of curve) {
      const got = scrubJourney(story.journeys.B.temp_c, story.journeys.B.hours, point.h / story.journeys.B.hours, c);
      expect(got.potency).toBeCloseTo(point.potency, 10);
    }
  });
});

describe("chapter 5 row selection (no planner maths in the page)", () => {
  const rows = (chapter5 as unknown as { rows: Ch5Row[] }).rows;

  it("selects the nearest exported alpha and returns the exported numbers", () => {
    const row = rowForAlpha(rows, 0.95);
    expect(row.alpha).toBe(0.95);
    expect(row.actions.continue.expected_loss).toBeCloseTo(4000, 6);
    expect(row.actions.continue.cvar).toBeCloseTo(50000, 6);
    expect(row.actions.reroute.cvar).toBeCloseTo(10000, 6);
    expect(row.recommended).toBe("reroute");
    expect(rowForAlpha(rows, 0.951).alpha).toBe(0.95);
    expect(rowForAlpha(rows, -3).alpha).toBe(0);
    expect(rowForAlpha(rows, 7).alpha).toBe(0.99);
  });

  it("flips the recommendation where the exported data flip", () => {
    expect(rowForAlpha(rows, 0).recommended).toBe("continue");
    const flips = flipAlphas(rows);
    expect(flips).toHaveLength(1);
    expect(rowForAlpha(rows, flips[0] - 0.01).recommended).toBe("continue");
    expect(rowForAlpha(rows, flips[0]).recommended).toBe("reroute");
  });

  it("lights exactly the exported number of tail points", () => {
    const c = (chapter5 as unknown as { actions: Record<string, { rank: number[] }> }).actions.continue;
    const lit = litFlags(c.rank, rowForAlpha(rows, 0.95).tail_points);
    expect(lit.reduce((a, b) => a + b, 0)).toBe(250);
    expect(litFlags([2, 0, 1], 1)).toEqual(new Uint8Array([0, 1, 0]));
    expect(litFlags([], 5)).toHaveLength(0);
  });
});

describe("validation of the new files", () => {
  it("accepts the real files", () => {
    expect(validateChapter5(chapter5).ok).toBe(true);
    expect(validateChapter6(chapter6).ok).toBe(true);
  });

  it("rejects malformed and empty input calmly", () => {
    for (const bad of [null, {}, [], "x", { actions: {}, rows: [] }]) {
      expect(validateChapter5(bad).ok).toBe(false);
      expect(validateChapter6(bad).ok).toBe(false);
    }
    const short = JSON.parse(JSON.stringify(chapter5));
    short.actions.continue.rank = [1, 2];
    expect(validateChapter5(short).ok).toBe(false);
    const noRibbon = JSON.parse(JSON.stringify(chapter6));
    noRibbon.chain.ribbon = [];
    expect(validateChapter6(noRibbon).ok).toBe(false);
  });

  it("chapter 6 holds a real broken link and says what the signature does not show", () => {
    const c6 = chapter6 as unknown as { chain: { tampered_result: string; ribbon: { status: string }[] }; limit: string };
    expect(c6.chain.tampered_result).toContain("BROKEN");
    expect(c6.chain.ribbon.some((t) => t.status === "broken")).toBe(true);
    expect(c6.limit).toContain("does not show the sensor told the truth");
  });
});
