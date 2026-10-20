// Smoke-test page: Lenis + GSAP ScrollTrigger on one shared ticker drive a scroll-scrubbed camera.
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import Lenis from "lenis";
import { useEffect, useRef } from "react";
import { PerfOverlay } from "./smoke/PerfOverlay";
import { SmokeScene } from "./smoke/SmokeScene";
import { liveState, useQualityStore } from "./smoke/useQualityStore";

gsap.registerPlugin(ScrollTrigger);

const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function webglAvailable(): boolean {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl2") ?? canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

const hasWebgl = webglAvailable();

export function App() {
  const spacer = useRef<HTMLDivElement>(null);

  // Everything is created here and fully cleaned up, because StrictMode mounts effects twice in dev.
  useEffect(() => {
    const lenis = reducedMotion ? null : new Lenis({ autoRaf: false });
    const tick = (time: number) => lenis?.raf(time * 1000);
    gsap.ticker.add(tick);
    gsap.ticker.lagSmoothing(0);
    lenis?.on("scroll", ScrollTrigger.update);

    const trigger = ScrollTrigger.create({
      trigger: spacer.current,
      start: "top top",
      end: "bottom bottom",
      scrub: true,
      onUpdate: (self) => {
        liveState.scrollProgress = self.progress;
      },
    });

    return () => {
      trigger.kill();
      gsap.ticker.remove(tick);
      gsap.ticker.lagSmoothing(500, 33);
      lenis?.destroy();
    };
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() === "q") useQualityStore.getState().cycle();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <>
      {hasWebgl ? (
        <SmokeScene reducedMotion={reducedMotion} />
      ) : (
        <p className="notice">3D is unavailable on this device</p>
      )}
      <main ref={spacer} className="spacer" aria-label="Scroll to move the camera">
        <p className="hint">Scroll. Press Q to change quality.</p>
      </main>
      <PerfOverlay />
    </>
  );
}
