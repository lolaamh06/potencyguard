// The mode adapter: story (bundled data), replay (recorded scenario files) and live (the existing
// backend, read-only, same origin through the dev proxy). All three fill the same snapshot, so
// the visuals never ask which mode they are in.
import { parseJson, validateIndex, validateReplay, validateStory } from "./validate";
import type { AdapterSnapshot, Mode, ReplayFile, ReplayIndex, Result, StoryData } from "./types";

export const MODES: readonly Mode[] = ["story", "replay", "live"];
export const REPLAY_BASE = "/replay";
export const LIVE_BASE = "/api";
export const LIVE_POLL_MS = 3000;

export function parseMode(search: string): Mode {
  const value = new URLSearchParams(search).get("mode");
  return (MODES as readonly string[]).includes(value ?? "") ? (value as Mode) : "story";
}

export type Fetcher = (url: string) => Promise<{ ok: boolean; status: number; text(): Promise<string> }>;

export const EMPTY: AdapterSnapshot = {
  status: { state: "loading", mode: "story" },
  index: null,
  story: null,
  scenarios: {},
};

async function getText(fetcher: Fetcher, url: string): Promise<Result<string>> {
  try {
    const response = await fetcher(url);
    if (!response.ok) return { ok: false, error: `${url} answered ${response.status}.` };
    return { ok: true, value: await response.text() };
  } catch {
    return { ok: false, error: `${url} could not be read.` };
  }
}

export async function loadReplayIndex(fetcher: Fetcher, base = REPLAY_BASE): Promise<Result<ReplayIndex>> {
  const text = await getText(fetcher, `${base}/index.json`);
  if (!text.ok) return text;
  const json = parseJson(text.value, "The scenario list");
  if (!json.ok) return json;
  return validateIndex(json.value);
}

export async function loadReplayFile(
  fetcher: Fetcher,
  file: string,
  scenarioId: string,
  base = REPLAY_BASE,
): Promise<Result<ReplayFile>> {
  const text = await getText(fetcher, `${base}/${file}`);
  if (!text.ok) return text;
  const json = parseJson(text.value, `The file ${file}`);
  if (!json.ok) return json;
  return validateReplay(json.value, scenarioId);
}

/** Loads the index and every scenario file. A bad file is reported by name and skipped. */
export async function loadReplay(fetcher: Fetcher, mode: Mode, message: string | null = null): Promise<AdapterSnapshot> {
  const index = await loadReplayIndex(fetcher);
  if (!index.ok) return { status: { state: "error", mode, message: index.error }, index: null, story: null, scenarios: {} };
  const scenarios: Record<string, ReplayFile> = {};
  const problems: string[] = [];
  for (const entry of index.value.scenarios) {
    const file = await loadReplayFile(fetcher, entry.file, entry.scenario_id);
    if (file.ok) scenarios[entry.scenario_id] = file.value;
    else problems.push(`${entry.scenario_id}: ${file.error}`);
  }
  const count = Object.keys(scenarios).length;
  if (count === 0) {
    return { status: { state: "error", mode, message: problems.join(" ") || "No scenario could be loaded." }, index: index.value, story: null, scenarios };
  }
  const note = [message, problems.length ? `Skipped: ${problems.join(" ")}` : null].filter(Boolean).join(" ") || null;
  return { status: { state: "ready", mode, scenarios: count, message: note }, index: index.value, story: null, scenarios };
}

/** Story mode: the figures bundled into the app. */
export function loadStory(raw: unknown): AdapterSnapshot {
  const story: Result<StoryData> = validateStory(raw);
  if (!story.ok) return { status: { state: "error", mode: "story", message: story.error }, index: null, story: null, scenarios: {} };
  return { status: { state: "ready", mode: "story", scenarios: 0, message: null }, index: null, story: story.value, scenarios: {} };
}

/** Live mode: one read-only check of the backend; the caller polls. Unavailable falls back to replay. */
export async function checkLive(fetcher: Fetcher, base = LIVE_BASE): Promise<Result<{ shipments: number }>> {
  const health = await getText(fetcher, `${base}/health`);
  if (!health.ok) return { ok: false, error: "The backend is not reachable." };
  const parsed = parseJson(health.value, "The backend health answer");
  if (!parsed.ok) return { ok: false, error: "The backend answered something unexpected." };
  const list = await getText(fetcher, `${base}/shipments`);
  if (!list.ok) return { ok: false, error: "The backend did not list its shipments." };
  const shipments = parseJson(list.value, "The shipment list");
  if (!shipments.ok) return { ok: false, error: "The backend answered something unexpected." };
  const raw = shipments.value;
  const rows = Array.isArray(raw) ? raw : typeof raw === "object" && raw !== null && Array.isArray((raw as { items?: unknown }).items) ? (raw as { items: unknown[] }).items : null;
  if (rows === null) return { ok: false, error: "The backend answered something unexpected." };
  return { ok: true, value: { shipments: rows.length } };
}

export const LIVE_FALLBACK_MESSAGE =
  "The backend is not running, so recorded scenarios are shown instead. Start it with python -m backend serve.";

/** Live mode snapshot: replay data, with a calm message saying whether the backend was reached. */
export async function loadLive(fetcher: Fetcher): Promise<AdapterSnapshot> {
  const live = await checkLive(fetcher);
  if (!live.ok) return loadReplay(fetcher, "live", LIVE_FALLBACK_MESSAGE);
  return loadReplay(
    fetcher,
    "live",
    `Backend reached (${live.value.shipments} shipments listed). Recorded scenarios are shown until the live view is built.`,
  );
}

export async function loadForMode(mode: Mode, fetcher: Fetcher, storyRaw: unknown): Promise<AdapterSnapshot> {
  if (mode === "story") return loadStory(storyRaw);
  if (mode === "replay") return loadReplay(fetcher, "replay");
  return loadLive(fetcher);
}
