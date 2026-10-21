import { describe, expect, it } from "vitest";
import {
  CHAPTERS,
  STORY_TOTAL_VH,
  chapterAtScroll,
  chapterScrollY,
  chapterStartsVh,
  clamp01,
  progressFromScroll,
} from "./chapters";

const rendered = CHAPTERS.filter((c) => c.rendered);

describe("chapter table", () => {
  it("adds up to the decided 860 vh", () => {
    expect(CHAPTERS.reduce((sum, c) => sum + c.vh, 0)).toBe(STORY_TOTAL_VH);
    expect(STORY_TOTAL_VH).toBe(860);
  });

  it("has the prologue and seven chapters with unique ids", () => {
    expect(CHAPTERS).toHaveLength(8);
    expect(new Set(CHAPTERS.map((c) => c.id)).size).toBe(8);
  });

  it("renders the prologue and three placeholders in this phase", () => {
    expect(rendered.map((c) => c.id)).toEqual(["prologue", "chapter-1", "chapter-2", "chapter-3"]);
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

  it("finds the chapter on screen from the scroll position (the middle of the viewport decides)", () => {
    const vh = 1000;
    expect(chapterAtScroll(rendered, 0, vh)).toBe(0);
    expect(chapterAtScroll(rendered, 400, vh)).toBe(0);
    expect(chapterAtScroll(rendered, 500, vh)).toBe(1);
    expect(chapterAtScroll(rendered, 1700, vh)).toBe(1);
    expect(chapterAtScroll(rendered, 1900, vh)).toBe(2);
    expect(chapterAtScroll(rendered, 3300, vh)).toBe(3); // the end of the page: 430 - 100 = 330 vh
    expect(chapterAtScroll(rendered, -50, vh)).toBe(0);
    expect(chapterAtScroll([], 500, vh)).toBe(0);
    expect(chapterAtScroll(rendered, 500, 0)).toBe(0);
  });

  it("maps a chapter index to a scroll position, clamped to the page and to the list", () => {
    expect(chapterScrollY(rendered, 0, 1000, 3300)).toBe(0);
    expect(chapterScrollY(rendered, 1, 1000, 3300)).toBe(1000);
    expect(chapterScrollY(rendered, 3, 1000, 3300)).toBe(3300);
    expect(chapterScrollY(rendered, 99, 1000, 3300)).toBe(3300);
    expect(chapterScrollY(rendered, -4, 1000, 3300)).toBe(0);
    expect(chapterScrollY([], 1, 1000, 3300)).toBe(0);
  });
});
