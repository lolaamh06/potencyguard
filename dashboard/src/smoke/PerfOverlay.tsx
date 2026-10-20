// Small monospace overlay. Text is refreshed about 4 times per second from refs, not per frame.
import { useEffect, useRef } from "react";
import { effectiveDpr } from "./qualityTier";
import { liveState, useQualityStore } from "./useQualityStore";

const REFRESH_MS = 250;

export function PerfOverlay() {
  const box = useRef<HTMLPreElement>(null);

  useEffect(() => {
    const render = () => {
      const tier = useQualityStore.getState().tier;
      const dpr = effectiveDpr(window.devicePixelRatio, tier);
      const version = liveState.webglVersion > 0 ? String(liveState.webglVersion) : "unavailable";
      if (box.current) {
        box.current.textContent =
          `FPS:   ${liveState.fps.toFixed(0)}\n` +
          `Tier:  ${tier}\n` +
          `DPR:   ${dpr}\n` +
          `WebGL: ${version}\n` +
          `GPU:   ${liveState.gpu}`;
      }
    };
    render();
    const id = window.setInterval(render, REFRESH_MS);
    return () => window.clearInterval(id);
  }, []);

  return <pre ref={box} className="overlay" aria-label="Performance overlay" />;
}
