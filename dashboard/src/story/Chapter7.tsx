// Chapter 7: "Enter the control room." A clear button (and the Enter key at the end of the story)
// dives the camera toward the globe and goes to the Control Room route.
import gsap from "gsap";
import { useCallback, useEffect, useRef } from "react";
import { useAppStore } from "../app/appStore";
import { goTo } from "../app/route";
import { scrollState } from "../scroll/scrollState";
import { Scene, span, useChapterTick } from "./common";

export function enterControlRoom(reduced: boolean): void {
  if (reduced) {
    goTo("control-room");
    return;
  }
  gsap.to(scrollState, { dive: 1, duration: 0.9, ease: "power2.inOut", onComplete: () => goTo("control-room") });
}

export function Chapter7() {
  const reduced = useAppStore((s) => s.reducedMotion);
  const button = useRef<HTMLButtonElement>(null);

  useChapterTick(7, (t) => {
    if (button.current) button.current.style.opacity = String(reduced ? 1 : 0.35 + 0.65 * span(t, 0.0, 0.5));
  });

  const go = useCallback(() => enterControlRoom(reduced), [reduced]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Enter" && scrollState.chapter === 7 && !(e.target instanceof HTMLButtonElement)) go();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go]);

  // leaving the story resets the dive so coming back starts from rest
  useEffect(() => () => void (scrollState.dive = 0), []);

  return (
    <Scene index={7}>
      <div className="copy">
        <h2>Enter the control room</h2>
        <p>The story ends here and the product begins.</p>
        <button ref={button} type="button" className="btn enter" onClick={go}>
          Enter the Control Room
        </button>
        <p className="caption">Press <kbd>Enter</kbd> here, or <kbd>C</kbd> at any time.</p>
      </div>
      <div className="figure" />
    </Scene>
  );
}
