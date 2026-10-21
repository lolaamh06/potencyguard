// Per-frame scroll values in a plain object (no React state per frame). The render loop and the
// DOM updaters read `scrollState.progress`; the rig writes it from the shared GSAP ticker.
import gsap from "gsap";
import { useEffect } from "react";

export const scrollState = {
  /** 0..1 over the scrollable height of the story. */
  progress: 0,
};

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
