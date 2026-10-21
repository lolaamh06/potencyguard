import { describe, expect, it } from "vitest";
import {
  CHAPTERS,
  STORY_TOTAL_VH,
  chapterAtScroll,
  chapterLocal,
  chapterScrollY,
  chapterStartsVh,
  clamp01,
  progressFromScroll,
} from "./chapters";

const rendered = CHAPTERS.slice(0, 4);

describe("chapter table", () => {
  it("adds up to the decided 860 vh", () => {
    expect(CHAPTERS.reduce((sum, c) => sum + c.vh, 0)).toBe(STORY_TOTAL_VH);
    expect(STORY_TOTAL_VH).toBe(860);
  });

  it("has the prologue and seven chapters with unique ids", () => {
    expect(CHAPTERS).toHaveLength(8);
    expect(new Set(CHAPTERS.map((c) => c.id)).size).toBe(8);
  });

  it("renders all eight scenes", () => {
    expect(CHAPTERS.every((c) => c.rendered)).toBe(true);
    expect(CHAPTERS.map((c) => c.id)).toEqual([
      "prologue", "chapter-1", "chapter-2", "chapter-3", "chapter-4", "chapter-5", "chapter-6", "chapter-7",
    ]);
  });

  it("gives the decided length of every scene", () => {
    expect(CHAPTERS.map((c) => c.vh)).toEqual([100, 130, 130, 70, 130, 160, 100, 40]);
  });
});

describe("progress maths", () => {
  it("clamps progress to 0..1 and survives bad numbers", () => {
    expect(clamp01(-0.2)).toBe(0);
    expect(clamp01(1.7)).toBe(1);
    expect(clamp01(Number.NaN)).toBe(0);
    expect(clamp01(0.4)).toBe(0.4);
    expect(progressFromScroll(500, 1000)).toBe(0.5);
    expect(progressFromScroll(2000, 1000)).toBe(1);
    expect(progressFromScroll(-5, 1000)).toBe(0);
    expect(progressFromScroll(10, 0)).toBe(0);
  });

  it("finds chapter starts in vh", () => {
    expect(chapterStartsVh(rendered)).toEqual([0, 100, 230, 360]);
    expect(chapterStartsVh([])).toEqual([]);
  });

  it("finds the chapter on screen from the reading position", () => {
    const vh = 1000;
    const max = 3300; // 430 vh of story, one viewport less
    expect(chapterAtScroll(rendered, 0, vh, max)).toBe(0);
    expect(chapterAtScroll(rendered, 400, vh, max)).toBe(0);
    expect(chapterAtScroll(rendered, max, vh, max)).toBe(3); // the end of the page reaches the last chapter
    expect(chapterAtScroll(rendered, -50, vh, max)).toBe(0);
    expect(chapterAtScroll([], 500, vh)).toBe(0);
    expect(chapterAtScroll(rendered, 500, 0)).toBe(0);
    let prev = 0;
    for (let y = 0; y <= max; y += 50) {
      const i = chapterAtScroll(rendered, y, vh, max);
      expect(i).toBeGreaterThanOrEqual(prev);
      prev = i;
    }
  });

  it("reaches every chapter, including the short last one of the full table", () => {
    const vh = 1000;
    const max = 7600; // 860 vh minus one viewport
    const seen = new Set<number>();
    for (let y = 0; y <= max; y += 25) seen.add(chapterAtScroll(CHAPTERS, y, vh, max));
    expect([...seen].sort()).toEqual([0, 1, 2, 3, 4, 5, 6, 7]);
    expect(chapterLocal(CHAPTERS, 0, vh, max)).toEqual({ index: 0, t: 0 });
    const end = chapterLocal(CHAPTERS, max, vh, max);
    expect(end.index).toBe(7);
    expect(end.t).toBeCloseTo(1, 9);
  });

  it("maps a chapter index to a scroll position, clamped to the page and to the list", () => {
    expect(chapterScrollY(rendered, 0, 1000, 3300)).toBe(0);
    expect(chapterScrollY(rendered, 1, 1000, 3300)).toBe(1000);
    expect(chapterScrollY(rendered, 3, 1000, 3300)).toBe(3300);
    expect(chapterScrollY(rendered, 99, 1000, 3300)).toBe(3300);
    expect(chapterScrollY(rendered, -4, 1000, 3300)).toBe(0);
    expect(chapterScrollY([], 1, 1000, 3300)).toBe(0);
  });

  it("gives the position inside the chapter on screen, rising from 0 to 1", () => {
    const vh = 1000;
    const max = 7600;
    let last = { index: 0, t: 0 };
    for (let y = 0; y <= max; y += 40) {
      const at = chapterLocal(CHAPTERS, y, vh, max);
      if (at.index === last.index) expect(at.t).toBeGreaterThanOrEqual(last.t - 1e-9);
      expect(at.t).toBeGreaterThanOrEqual(0);
      expect(at.t).toBeLessThanOrEqual(1);
      last = at;
    }
    expect(chapterLocal([], 100, vh)).toEqual({ index: 0, t: 0 });
  });
});
