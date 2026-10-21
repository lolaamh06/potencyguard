// The Story route: the Prologue and Chapters 1 to 7. All text is real DOM text. Chapter graphics
// are DOM and SVG, except the Prologue's vial and Chapter 5's cloud, which are in the 3D canvas
// (with 2D versions below for the lowest tier).
import { useCallback, useRef } from "react";
import { useAppStore } from "../app/appStore";
import { useStoryBundle } from "../data/useStoryData";
import { tierSettings } from "../quality/governor";
import { useQualityStore } from "../quality/qualityStore";
import { ProgressRail } from "../scroll/ProgressRail";
import { useScrollRig } from "../scroll/useScrollRig";
import { scrollState, useScrollTicker } from "../scroll/scrollState";
import { Chapter1 } from "./Chapter1";
import { Chapter2 } from "./Chapter2";
import { Chapter3 } from "./Chapter3";
import { Chapter4 } from "./Chapter4";
import { Chapter5 } from "./Chapter5";
import { Chapter6 } from "./Chapter6";
import { Chapter7 } from "./Chapter7";
import { Scene } from "./common";

function VialStill() {
  return (
    <svg viewBox="0 0 120 180" width="140" role="img" aria-label="A vial in an insulated box">
      <rect x="10" y="150" width="100" height="10" rx="3" fill="var(--ink-700)" />
      <rect x="40" y="30" width="40" height="120" rx="10" fill="none" stroke="var(--mist-hi)" strokeWidth="2" />
      <rect x="45" y="70" width="30" height="76" rx="6" fill="var(--ice-400)" opacity="0.8" />
      <rect x="46" y="14" width="28" height="16" rx="3" fill="var(--mist)" />
    </svg>
  );
}

export function Story() {
  const root = useRef<HTMLElement>(null);
  const second = useRef<HTMLParagraphElement>(null);
  const reduced = useAppStore((s) => s.reducedMotion);
  const tier = useQualityStore((s) => s.tier);
  const bundle = useStoryBundle();
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
      <Scene index={0} block>
        <div style={{ paddingTop: "22vh", maxWidth: "min(46rem, 100%)" }}>
          <h1>
            Somewhere between the factory and the clinic, a medicine can stop being <em>medicine.</em>
          </h1>
          <p ref={second} className="caption lead" style={{ opacity: reduced ? 1 : 0 }}>
            And the box carries no way to say so.
          </p>
          <p className="caption">An illustrative journey.</p>
          {!tierSettings(tier).webgl && <VialStill />}
        </div>
        <span className="scroll-cue">Scroll</span>
      </Scene>
      <Chapter1 story={bundle?.ch1 ?? null} />
      <Chapter2 data={bundle?.ch2 ?? null} />
      <Chapter3 data={bundle?.ch3 ?? null} />
      <Chapter4 />
      <Chapter5 data={bundle?.ch5 ?? null} />
      <Chapter6 data={bundle?.ch6 ?? null} hidden={bundle?.hidden ?? null} />
      <Chapter7 />
    </main>
  );
}
