// A thin progress line along the top edge and chapter ticks with names along the right edge.
// The line is moved through a ref on the shared ticker, not through React state.
import { useCallback, useRef } from "react";
import { useAppStore } from "../app/appStore";
import { CHAPTERS } from "./chapters";
import { scrollApi, scrollState, useScrollTicker } from "./scrollState";

const RENDERED = CHAPTERS.filter((c) => c.rendered);

export function ProgressRail() {
  const bar = useRef<HTMLElement>(null);
  const chapter = useAppStore((s) => s.chapter);

  const paint = useCallback(() => {
    if (bar.current) bar.current.style.transform = `scaleX(${scrollState.progress.toFixed(4)})`;
  }, []);
  useScrollTicker(paint);

  return (
    <>
      <div className="rail-progress" aria-hidden="true">
        <i ref={bar} />
      </div>
      <nav className="rail" aria-label="Story chapters">
        {RENDERED.map((c, i) => (
          <button
            key={c.id}
            type="button"
            aria-current={i === chapter ? "step" : undefined}
            aria-label={`Go to ${c.name}`}
            onClick={() => scrollApi.toChapter(i)}
          >
            <span className="name">{c.name}</span>
            <span className="tick" />
          </button>
        ))}
      </nav>
    </>
  );
}
