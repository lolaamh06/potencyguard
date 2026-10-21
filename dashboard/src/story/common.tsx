// Shared pieces of the Story chapters.
import { useCallback, useRef, type ReactNode } from "react";
import { localFor, scrollState, useScrollTicker } from "../scroll/scrollState";
import { CHAPTERS } from "../scroll/chapters";

export const MODEL_LABEL = "Illustrative product, model output";

/**
 * A scene: a tall empty section that only provides the scroll length, and a fixed full-screen layer
 * that crossfades in while this chapter is on screen. All eight layers share one fixed stage, so
 * the scroll distance (860 vh in total) is the time the viewer spends in each scene.
 */
export function Scene({ index, children, block, className }: { index: number; children: ReactNode; block?: boolean; className?: string }) {
  const chapter = CHAPTERS[index];
  const layer = useRef<HTMLDivElement>(null);
  useScrollTicker(
    useCallback(() => {
      const el = layer.current;
      if (!el) return;
      const on = scrollState.chapter === index;
      const t = scrollState.local;
      const fadeIn = index === 0 ? 1 : clamp01(t / 0.06);
      const fadeOut = index === CHAPTERS.length - 1 ? 1 : 1 - clamp01((t - 0.94) / 0.06);
      const w = on ? Math.min(fadeIn, fadeOut) : 0;
      el.style.opacity = w.toFixed(3);
      el.style.pointerEvents = w > 0.5 ? "auto" : "none";
      el.style.visibility = w > 0.001 ? "visible" : "hidden";
    }, [index]),
  );
  return (
    <section id={chapter.id} className="scene" style={{ height: `${chapter.vh}vh`, padding: 0 }} aria-label={chapter.name}>
      <div className={`${block ? "layer block" : "layer"} ${className ?? ""}`} ref={layer} style={{ opacity: 0, visibility: "hidden" }}>
        {children}
      </div>
    </section>
  );
}

/** Calls `paint(t)` on every tick with the position inside chapter `index` (0 before it, 1 after it). */
export function useChapterTick(index: number, paint: (t: number) => void): void {
  const ref = useRef(paint);
  ref.current = paint;
  const tick = useCallback(() => ref.current(localFor(index)), [index]);
  useScrollTicker(tick);
}

export function clamp01(x: number): number {
  return Math.min(1, Math.max(0, x));
}

/** 0 until `from`, 1 from `to`, linear between. */
export function span(t: number, from: number, to: number): number {
  return clamp01((t - from) / (to - from));
}

export function Missing({ what, problems }: { what: string; problems?: string[] }) {
  return (
    <p className="caption" role="status">
      {what} could not be loaded. {problems?.[0] ?? ""}
    </p>
  );
}
