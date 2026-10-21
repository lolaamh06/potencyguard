// Drives the replay clock from the shared GSAP ticker while a shipment page is open.
import gsap from "gsap";
import { useEffect, useRef } from "react";
import type { ReplayFile } from "../data/types";
import { useCr } from "./store";

export function useReplayClock(replay: ReplayFile | undefined): void {
  const ref = useRef(replay);
  ref.current = replay;
  useEffect(() => {
    const tick = (_time: number, deltaMs: number) => {
      const r = ref.current;
      if (r) useCr.getState().tick(deltaMs / 1000, r, performance.now());
    };
    gsap.ticker.add(tick);
    return () => gsap.ticker.remove(tick);
  }, []);
}
