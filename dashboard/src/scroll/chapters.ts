// The chapter table and the pure scroll maths. No DOM, no React.
// Lengths are the decided story scroll (860 vh in total). F2 renders the Prologue and three
// placeholder sections only; the other chapters are built in later phases.

export interface Chapter {
  id: string;
  name: string;
  /** Scroll length in viewport heights. */
  vh: number;
  /** Rendered in this phase (the rest exist in the table only). */
  rendered: boolean;
}

export const STORY_TOTAL_VH = 860;

export const CHAPTERS: readonly Chapter[] = [
  { id: "prologue", name: "The quiet clock", vh: 100, rendered: true },
  { id: "chapter-1", name: "Two alarms, one verdict", vh: 130, rendered: true },
  { id: "chapter-2", name: "Whose data is this?", vh: 130, rendered: true },
  { id: "chapter-3", name: "Too late to matter", vh: 70, rendered: true },
  { id: "chapter-4", name: "A box that thinks", vh: 130, rendered: false },
  { id: "chapter-5", name: "Plan for the worst five percent", vh: 160, rendered: false },
  { id: "chapter-6", name: "A human decides", vh: 100, rendered: false },
  { id: "chapter-7", name: "Enter the control room", vh: 40, rendered: false },
];

export function clamp01(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.min(1, Math.max(0, value));
}

/** Scroll progress 0..1 from the scroll position and the scrollable range. */
export function progressFromScroll(scrollY: number, scrollableHeight: number): number {
  if (!(scrollableHeight > 0)) return 0;
  return clamp01(scrollY / scrollableHeight);
}

/** Start of each chapter in viewport heights (vh) from the top of the story. */
export function chapterStartsVh(chapters: readonly Chapter[]): number[] {
  let acc = 0;
  return chapters.map((c) => {
    const start = acc;
    acc += c.vh;
    return start;
  });
}

/**
 * The chapter on screen: the last chapter that has started by the middle of the viewport.
 * Using the middle keeps a short last chapter reachable, because the page cannot scroll
 * further than (total - one viewport).
 */
export function chapterAtScroll(chapters: readonly Chapter[], scrollY: number, viewportH: number): number {
  if (chapters.length === 0 || !(viewportH > 0)) return 0;
  const probe = Math.max(0, scrollY) + viewportH / 2;
  const starts = chapterStartsVh(chapters);
  let index = 0;
  for (let i = 0; i < starts.length; i++) {
    if ((starts[i] * viewportH) / 100 <= probe + 1e-6) index = i;
  }
  return index;
}

/** Scroll position (px) of the start of a chapter, never past the end of the page. */
export function chapterScrollY(
  chapters: readonly Chapter[],
  index: number,
  viewportH: number,
  maxScroll: number,
): number {
  if (chapters.length === 0) return 0;
  const starts = chapterStartsVh(chapters);
  const i = Math.min(Math.max(Math.trunc(index), 0), chapters.length - 1);
  return Math.min((starts[i] * viewportH) / 100, Math.max(maxScroll, 0));
}
