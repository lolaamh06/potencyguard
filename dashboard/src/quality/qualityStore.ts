// The current quality tier. A tier forced by ?tier= or chosen with Q is never changed by the
// automatic governor; otherwise the governor may step it DOWN, never up.
import { create } from "zustand";
import { cycleTier, nextTierDown, parseTier, type Tier } from "./governor";

export function webglAvailable(): boolean {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl2") ?? canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

export const hasWebgl = webglAvailable();

function initialTier(): { tier: Tier; locked: boolean } {
  const forced = parseTier(window.location.search);
  if (new URLSearchParams(window.location.search).get("rec") === "1") {
    // recording mode locks the tier so the picture does not change during a recording
    return { tier: forced ?? (hasWebgl ? "high" : "fallback2d"), locked: true };
  }
  if (forced !== null) return { tier: hasWebgl || forced === "fallback2d" ? forced : "fallback2d", locked: true };
  return { tier: hasWebgl ? "high" : "fallback2d", locked: !hasWebgl };
}

interface QualityState {
  tier: Tier;
  /** True when the tier was forced or chosen by hand: the governor leaves it alone. */
  locked: boolean;
  cycle: () => void;
  stepDown: () => void;
}

const start = initialTier();

export const useQualityStore = create<QualityState>((set) => ({
  tier: start.tier,
  locked: start.locked,
  cycle: () => set((s) => ({ tier: cycleTier(s.tier), locked: true })),
  stepDown: () =>
    set((s) => {
      if (s.locked) return s;
      const lower = nextTierDown(s.tier);
      return lower === s.tier ? s : { tier: lower };
    }),
}));
