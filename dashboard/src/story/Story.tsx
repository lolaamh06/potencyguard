// The Story route. F2 renders the Prologue (real text) and three PLACEHOLDER sections that only
// prove the scroll rig and the rail. Chapters 1 to 7 are built in later phases.
import { useCallback, useRef } from "react";
import { useAppStore } from "../app/appStore";
import { CHAPTERS } from "../scroll/chapters";
import { ProgressRail } from "../scroll/ProgressRail";
import { useScrollRig } from "../scroll/useScrollRig";
import { scrollState, useScrollTicker } from "../scroll/scrollState";

const RENDERED = CHAPTERS.filter((c) => c.rendered);

export function Story() {
  const root = useRef<HTMLElement>(null);
  const second = useRef<HTMLParagraphElement>(null);
  const reduced = useAppStore((s) => s.reducedMotion);
  useScrollRig(root, reduced);

  // The second Prologue line fades in as the viewer starts to scroll (moved through a ref).
  const fade = useCallback(() => {
    if (!second.current) return;
    const p = reduced ? 1 : Math.min(Math.max((scrollState.progress - 0.01) / 0.04, 0), 1);
    second.current.style.opacity = p.toFixed(3);
  }, [reduced]);
  useScrollTicker(fade);

  return (
    <main className="story" ref={root} id="story">
      <ProgressRail />
      {RENDERED.map((chapter, index) => (
        <section
          key={chapter.id}
          id={chapter.id}
          className="scene"
          style={{ height: `${chapter.vh}vh` }}
          aria-label={chapter.name}
        >
          {index === 0 ? (
            <div style={{ alignSelf: "center", maxWidth: "min(46rem, 100%)" }}>
              <h1>
                Somewhere between the factory and the clinic, a medicine can stop being <em>medicine.</em>
              </h1>
              <p ref={second} className="caption" style={{ fontSize: "var(--t-lead)", color: "var(--frost)", opacity: reduced ? 1 : 0 }}>
                And the box carries no way to say so.
              </p>
              <p className="caption">An illustrative journey.</p>
              <span className="scroll-cue">Scroll</span>
            </div>
          ) : (
            // PLACEHOLDER (F2): proves the rig. The real chapter is built in a later phase.
            <p className="caption" style={{ alignSelf: "start", marginTop: "30vh" }}>
              {chapter.name}
            </p>
          )}
        </section>
      ))}
    </main>
  );
}
