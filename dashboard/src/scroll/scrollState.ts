// Per-frame scroll values in a plain object (no React state per frame). The render loop and the
// DOM updaters read `scrollState.progress`; the rig writes it from the shared GSAP ticker.
import gsap from "gsap";
import { useEffect } from "react";

export const scrollState = {
  /** 0..1 over the scrollable height of the story. */
  progress: 0,
  /** Index of the chapter on screen and the position inside it (0 to 1). */
  chapter: 0,
  local: 0,
  /** Chapter 7 dive: 0 at rest, 1 when the camera has dived toward the globe. */
  dive: 0,
};

/** The position inside chapter `index` as seen by that chapter's own graphics: 0 before it, 1 after it. */
export function localFor(index: number): number {
  if (scrollState.chapter < index) return 0;
  if (scrollState.chapter > index) return 1;
  return scrollState.local;
}

/** The rig fills these in so the keyboard, the rail and the shortcuts can move the page. */
export const scrollApi = {
  toChapter: (_index: number): void => {},
  by: (_viewports: number): void => {},
  toEdge: (_where: "start" | "end"): void => {},
};

/** Runs `callback` on every tick of the shared GSAP clock (the same clock as Lenis and the 3D loop). */
export function useScrollTicker(callback: () => void): void {
  useEffect(() => {
    gsap.ticker.add(callback);
    return () => gsap.ticker.remove(callback);
  }, [callback]);
}
