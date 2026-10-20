import { create } from "zustand";
import { cycleTier, nextTierDown, type QualityTier } from "./qualityTier";

interface QualityState {
  tier: QualityTier;
  setTier: (tier: QualityTier) => void;
  stepDown: () => void;
  cycle: () => void;
}

export const useQualityStore = create<QualityState>((set) => ({
  tier: "high",
  setTier: (tier) => set({ tier }),
  stepDown: () => set((s) => ({ tier: nextTierDown(s.tier) })),
  cycle: () => set((s) => ({ tier: cycleTier(s.tier) })),
}));

// Mutable values written by the render loop and read by the overlay.
// Kept outside React state on purpose: no per-frame re-renders.
export const liveState = {
  scrollProgress: 0,
  fps: 0,
  webglVersion: 0,
  gpu: "unavailable",
};
