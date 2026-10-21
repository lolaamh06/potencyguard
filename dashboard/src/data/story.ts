// Data for the Story chapters, as written by scripts/export_story.py. The page only SELECTS and
// DISPLAYS these numbers: it never computes planner figures. (The Chapter 1 scrub uses the tested
// potency mirror, and is checked against the exported figures in story.test.ts.)
import { equivalentReferenceTimeH, potencyFromTauEq, shelfLifeUsedFraction, type ProductConstants } from "../potency/mirror";
import type { Result, StoryData } from "./types";

export interface Ch5Action {
  cost: number;
  failure_probability: number;
  failed: number[];
  rank: number[];
}

export interface Ch5ActionRow {
  expected_loss: number;
  cvar: number;
  var_sample: number;
  cvar_sample: number;
}

export interface Ch5Row {
  alpha: number;
  tail_points: number;
  actions: Record<string, Ch5ActionRow>;
  recommended: string;
}

export interface Chapter5Data {
  label: string;
  seed: number;
  n_points: number;
  V: number;
  actions: Record<string, Ch5Action>;
  rows: Ch5Row[];
}

export interface RibbonToken {
  index: number;
  hash_prefix: string;
  status: "verified" | "broken" | "after_break";
}

export interface Chapter6Data {
  label: string;
  scenario_id: string;
  checkpoint_h: number;
  card: {
    potency_curve: [number, number][];
    alternatives: { action: string; cost: number; failure_probability: number; expected_loss: number; cvar: number }[];
    chosen_action: string;
    chain_status: string;
    reason: string;
    explanation: string;
    trust_level: string;
    verdict: string;
    route: string;
  };
  chain: {
    device_id: string;
    key_id: string;
    entries_total: number;
    intact_result: string;
    tampered_result: string;
    tamper: string;
    first_broken_index: number;
    reason: string;
    ribbon: RibbonToken[];
  };
  backend_check: { chain_status: string; reason: string | null; first_bad_index: number | null; decision_refused: string | null };
  limit: string;
}

type Obj = Record<string, unknown>;
const isObj = (v: unknown): v is Obj => typeof v === "object" && v !== null && !Array.isArray(v);
const fail = <T>(error: string): Result<T> => ({ ok: false, error });

export function validateChapter5(raw: unknown): Result<Chapter5Data> {
  if (!isObj(raw) || !isObj(raw.actions) || !Array.isArray(raw.rows)) return fail("The Chapter 5 data is malformed.");
  const n = raw.n_points;
  if (typeof n !== "number" || n <= 0) return fail("The Chapter 5 data has no point count.");
  for (const name of ["continue", "reroute"]) {
    const a = (raw.actions as Obj)[name];
    if (!isObj(a) || !Array.isArray(a.failed) || !Array.isArray(a.rank) || a.failed.length !== n || a.rank.length !== n) {
      return fail(`The Chapter 5 data has no ${name} points.`);
    }
  }
  if (raw.rows.length === 0) return fail("The Chapter 5 data has no alpha rows.");
  for (const row of raw.rows) {
    if (!isObj(row) || typeof row.alpha !== "number" || typeof row.tail_points !== "number" || !isObj(row.actions) || typeof row.recommended !== "string") {
      return fail("A Chapter 5 row is malformed.");
    }
  }
  return { ok: true, value: raw as unknown as Chapter5Data };
}

export function validateChapter6(raw: unknown): Result<Chapter6Data> {
  if (!isObj(raw) || !isObj(raw.card) || !isObj(raw.chain)) return fail("The Chapter 6 data is malformed.");
  const ribbon = (raw.chain as Obj).ribbon;
  if (!Array.isArray(ribbon) || ribbon.length === 0) return fail("The Chapter 6 data has no chain ribbon.");
  for (const t of ribbon) {
    if (!isObj(t) || typeof t.index !== "number" || !["verified", "broken", "after_break"].includes(String(t.status))) {
      return fail("A chain token is malformed.");
    }
  }
  if (!Array.isArray((raw.card as Obj).potency_curve) || !Array.isArray((raw.card as Obj).alternatives)) return fail("The approval card data is incomplete.");
  return { ok: true, value: raw as unknown as Chapter6Data };
}

/** The row for a slider value: the nearest alpha in the exported grid (a selection, no maths). */
export function rowForAlpha(rows: readonly Ch5Row[], alpha: number): Ch5Row {
  let best = rows[0];
  for (const row of rows) if (Math.abs(row.alpha - alpha) < Math.abs(best.alpha - alpha)) best = row;
  return best;
}

/** Which points are lit as "worst": the first `tailPoints` by exported rank. */
export function litFlags(rank: readonly number[], tailPoints: number): Uint8Array {
  const out = new Uint8Array(rank.length);
  for (let i = 0; i < rank.length; i++) out[i] = rank[i] < tailPoints ? 1 : 0;
  return out;
}

/** The alpha values at which the exported recommendation changes (for the slider's tick). */
export function flipAlphas(rows: readonly Ch5Row[]): number[] {
  const out: number[] = [];
  for (let i = 1; i < rows.length; i++) if (rows[i].recommended !== rows[i - 1].recommended) out.push(rows[i].alpha);
  return out;
}

/** Chapter 1 scrub: potency and shelf life used after a fraction of a constant-temperature journey. */
export function scrubJourney(
  tempC: number,
  hours: number,
  fraction: number,
  constants: ProductConstants,
): { hours: number; potency: number; shelfLifeUsedPercent: number } {
  const h = hours * Math.min(1, Math.max(0, fraction));
  const tau = equivalentReferenceTimeH([tempC], [h], constants);
  return { hours: h, potency: potencyFromTauEq(tau, constants), shelfLifeUsedPercent: shelfLifeUsedFraction(tau, constants) * 100 };
}

/** Product constants for the mirror from the exported profile (hard limits are the product defaults). */
export function constantsFor(story: StoryData, profile: "active" | "reference"): ProductConstants {
  const p = story.profiles[profile];
  return {
    Ea_over_R: p.Ea_over_R,
    T_ref_c: p.T_ref_c,
    tau_max_h: p.tau_max_h,
    P_min: p.P_min,
    hard_limit_low_c: 0,
    hard_limit_high_c: 40,
    hard_limit_consecutive_samples: 2,
  };
}
