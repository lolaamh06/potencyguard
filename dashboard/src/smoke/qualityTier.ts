// Pure quality-tier logic (no React, no three.js). Tiers: see FRONTEND_VISION.md section 9.

export type QualityTier = "high" | "medium" | "low";

export interface TierSettings {
  dprCap: number;
  pointCount: number;
  bloom: boolean;
}

const SETTINGS: Record<QualityTier, TierSettings> = {
  high: { dprCap: 2, pointCount: 40000, bloom: true },
  medium: { dprCap: 1.5, pointCount: 20000, bloom: true },
  low: { dprCap: 1, pointCount: 8000, bloom: false },
};

export function tierSettings(tier: QualityTier): TierSettings {
  return SETTINGS[tier];
}

/** One step down; "low" stays "low". The governor never steps up on its own. */
export function nextTierDown(tier: QualityTier): QualityTier {
  if (tier === "high") return "medium";
  return "low";
}

/** Manual cycle used by the Q key: high -> medium -> low -> high. */
export function cycleTier(tier: QualityTier): QualityTier {
  if (tier === "high") return "medium";
  if (tier === "medium") return "low";
  return "high";
}

/** Device pixel ratio actually used: at least 1, at most the tier cap. */
export function effectiveDpr(devicePixelRatio: number, tier: QualityTier): number {
  return Math.min(Math.max(devicePixelRatio, 1), SETTINGS[tier].dprCap);
}
