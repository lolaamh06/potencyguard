// Validation of everything the adapter reads. A malformed or empty file gives a calm message,
// never an exception, so a bad file cannot take the screen down.
import type { ReplayFile, ReplayIndex, Result, StoryData } from "./types";

const SUPPORTED_SCHEMA = "1";
const FRAME_NUMBERS = ["t_s", "potency", "tau_eq_h", "shelf_life_used_fraction"] as const;
const FRAME_NULLABLE = ["temp_c", "ambient_c", "twin_c", "residual_c", "cusum_neg", "cusum_pos", "mkt_c"] as const;

type Obj = Record<string, unknown>;

const isObj = (v: unknown): v is Obj => typeof v === "object" && v !== null && !Array.isArray(v);
const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const isStr = (v: unknown): v is string => typeof v === "string";

function fail<T>(error: string): Result<T> {
  return { ok: false, error };
}

export function parseJson(text: string, what: string): Result<unknown> {
  if (text.trim() === "") return fail(`${what} is empty.`);
  try {
    return { ok: true, value: JSON.parse(text) as unknown };
  } catch {
    return fail(`${what} is not valid JSON.`);
  }
}

export function validateIndex(raw: unknown): Result<ReplayIndex> {
  if (!isObj(raw)) return fail("The scenario list is not an object.");
  if (raw.schema_version !== SUPPORTED_SCHEMA) {
    return fail(`The scenario list has schema version ${String(raw.schema_version)}; this app reads version ${SUPPORTED_SCHEMA}.`);
  }
  if (!Array.isArray(raw.scenarios) || raw.scenarios.length === 0) return fail("The scenario list is empty.");
  for (const entry of raw.scenarios) {
    if (!isObj(entry) || !isStr(entry.scenario_id) || !isStr(entry.label) || !isStr(entry.file) || !isNum(entry.checkpoint_h)) {
      return fail("A scenario entry is missing a field (scenario_id, label, file or checkpoint_h).");
    }
    if (!/^[a-z0-9_]+\.json$/.test(entry.file)) return fail(`A scenario file name is not allowed: ${entry.file}`);
  }
  return { ok: true, value: raw as unknown as ReplayIndex };
}

export function validateReplay(raw: unknown, expectedId?: string): Result<ReplayFile> {
  if (!isObj(raw)) return fail("The scenario file is not an object.");
  const { meta, frames, events, decision, chain } = raw;
  if (!isObj(meta)) return fail("The scenario file has no meta block.");
  if (meta.schema_version !== SUPPORTED_SCHEMA) {
    return fail(`The scenario file has schema version ${String(meta.schema_version)}; this app reads version ${SUPPORTED_SCHEMA}.`);
  }
  if (!isStr(meta.scenario_id)) return fail("The scenario file has no scenario id.");
  if (expectedId !== undefined && meta.scenario_id !== expectedId) {
    return fail(`The file holds scenario ${meta.scenario_id}, not ${expectedId}.`);
  }
  if (!isObj(meta.labels) || !isStr(meta.labels.product) || !isStr(meta.labels.data)) {
    return fail("The scenario file has no product and data labels.");
  }
  if (!isObj(meta.route) || !isObj(meta.route.origin) || !isObj(meta.route.destination)) {
    return fail("The scenario file has no route.");
  }
  if (!Array.isArray(frames) || frames.length === 0) return fail("The scenario file has no frames.");
  let lastT = -Infinity;
  for (let i = 0; i < frames.length; i++) {
    const f = frames[i];
    if (!isObj(f)) return fail(`Frame ${i} is not an object.`);
    for (const key of FRAME_NUMBERS) if (!isNum(f[key])) return fail(`Frame ${i} has no number for ${key}.`);
    for (const key of FRAME_NULLABLE) if (!(f[key] === null || isNum(f[key]))) return fail(`Frame ${i} has a bad value for ${key}.`);
    if (!isStr(f.trust_level) || !isStr(f.verdict) || !isObj(f.flags)) return fail(`Frame ${i} is missing its trust, verdict or flags.`);
    if ((f.t_s as number) < lastT) return fail(`Frame ${i} goes back in time.`);
    lastT = f.t_s as number;
    if ((f.potency as number) < 0 || (f.potency as number) > 1) return fail(`Frame ${i} has a potency outside 0 to 1.`);
  }
  if (!Array.isArray(events)) return fail("The scenario file has no event list.");
  for (let i = 0; i < events.length; i++) {
    const e = events[i];
    if (!isObj(e) || !isNum(e.t_s) || !isStr(e.type) || !isObj(e.payload)) return fail(`Event ${i} is malformed.`);
  }
  if (!isObj(decision) || !Array.isArray(decision.actions) || decision.actions.length === 0 || !isStr(decision.chosen_action)) {
    return fail("The scenario file has no decision.");
  }
  if (!isObj(chain) || typeof chain.ok !== "boolean" || !isNum(chain.entries_total)) return fail("The scenario file has no chain summary.");
  return { ok: true, value: raw as unknown as ReplayFile };
}

export function validateStory(raw: unknown): Result<StoryData> {
  if (!isObj(raw) || !isObj(raw.profiles) || !isObj(raw.journeys)) return fail("The bundled story data is malformed.");
  const active = (raw.profiles as Obj).active;
  if (!isObj(active) || !isObj(active.journeys)) return fail("The bundled story data has no active profile.");
  for (const key of ["A", "B"]) {
    const j = (active.journeys as Obj)[key];
    if (!isObj(j) || !isNum(j.shelf_life_used_percent) || !isNum(j.potency)) return fail(`The bundled story data has no figures for journey ${key}.`);
  }
  return { ok: true, value: raw as unknown as StoryData };
}
