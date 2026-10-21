// Quality tiers and the automatic governor. Pure functions: no React, no three.js, no clock.
// Tiers: high, medium, low, and "fallback2d" (no WebGL). The governor only ever steps DOWN.

export type Tier = "high" | "medium" | "low" | "fallback2d";

export const TIER_ORDER: readonly Tier[] = ["high", "medium", "low", "fallback2d"];

export interface TierSettings {
  /** Highest device pixel ratio the canvas may use. */
  dprCap: number;
  bloom: boolean;
  vignette: boolean;
  /** Approximate number of globe dots (sampled over the whole sphere, kept where there is land). */
  dotSamples: number;
  stars: number;
  /** Film grain opacity (0 = off). */
  grain: number;
  webgl: boolean;
}

const SETTINGS: Record<Tier, TierSettings> = {
  high: { dprCap: 2, bloom: true, vignette: true, dotSamples: 36000, stars: 1800, grain: 0.045, webgl: true },
  medium: { dprCap: 1.5, bloom: true, vignette: true, dotSamples: 20000, stars: 900, grain: 0.03, webgl: true },
  low: { dprCap: 1, bloom: false, vignette: false, dotSamples: 9000, stars: 350, grain: 0, webgl: true },
  fallback2d: { dprCap: 1, bloom: false, vignette: false, dotSamples: 5000, stars: 0, grain: 0, webgl: false },
};

export function tierSettings(tier: Tier): TierSettings {
  return SETTINGS[tier];
}

export function isTier(value: unknown): value is Tier {
  return typeof value === "string" && (TIER_ORDER as readonly string[]).includes(value);
}

/** Reads `?tier=` from a query string; anything that is not a tier name gives null. */
export function parseTier(search: string): Tier | null {
  const value = new URLSearchParams(search).get("tier");
  return isTier(value) ? value : null;
}

/** One step down for the automatic governor: high, medium, low, then it stays on low.
 *  It never chooses the 2D fallback by itself (that is for no WebGL, or a forced tier). */
export function nextTierDown(tier: Tier): Tier {
  if (tier === "high") return "medium";
  if (tier === "medium") return "low";
  return tier;
}

/** The Q key: high, medium, low, 2D, back to high. */
export function cycleTier(tier: Tier): Tier {
  return TIER_ORDER[(TIER_ORDER.indexOf(tier) + 1) % TIER_ORDER.length];
}

/** Pixel ratio actually used: at least 1, at most the tier's cap. */
export function effectiveDpr(devicePixelRatio: number, tier: Tier): number {
  return Math.min(Math.max(devicePixelRatio, 1), SETTINGS[tier].dprCap);
}

export interface GovernorConfig {
  /** Average frame time above this counts as a bad window (ms). 25 ms is 40 frames per second. */
  badFrameMs: number;
  /** Bad windows in a row before stepping down. */
  badWindows: number;
  /** Windows ignored at the start and after every change (shader compile, texture upload). */
  warmupWindows: number;
}

export const DEFAULT_GOVERNOR: GovernorConfig = { badFrameMs: 25, badWindows: 3, warmupWindows: 2 };

export interface GovernorState {
  tier: Tier;
  badStreak: number;
  warmupLeft: number;
}

export function initialGovernor(tier: Tier, config: GovernorConfig = DEFAULT_GOVERNOR): GovernorState {
  return { tier, badStreak: 0, warmupLeft: config.warmupWindows };
}

/**
 * One decision from one window of frames (the average frame time of the window).
 * Steps down after `badWindows` bad windows in a row; a good window resets the streak.
 * Never steps up. Returns the same object when nothing changes.
 */
export function stepGovernor(
  state: GovernorState,
  avgFrameMs: number,
  config: GovernorConfig = DEFAULT_GOVERNOR,
): GovernorState {
  if (!Number.isFinite(avgFrameMs) || avgFrameMs <= 0) return state;
  if (state.warmupLeft > 0) return { ...state, warmupLeft: state.warmupLeft - 1 };
  if (avgFrameMs <= config.badFrameMs) {
    return state.badStreak === 0 ? state : { ...state, badStreak: 0 };
  }
  const streak = state.badStreak + 1;
  if (streak < config.badWindows) return { ...state, badStreak: streak };
  const lower = nextTierDown(state.tier);
  if (lower === state.tier) return { ...state, badStreak: 0 };
  return { tier: lower, badStreak: 0, warmupLeft: config.warmupWindows };
}
