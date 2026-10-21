import { describe, expect, it } from "vitest";
import story from "./bundled/chapter1.json";
import baseline from "../../public/replay/baseline_ok.json";
import doorOpen from "../../public/replay/door_open_excursion.json";
import hidden from "../../public/replay/hidden_spoilage.json";
import reefer from "../../public/replay/reefer_failure.json";
import spoof from "../../public/replay/spoof_attempt.json";
import index from "../../public/replay/index.json";
import {
  LIVE_FALLBACK_MESSAGE,
  checkLive,
  loadForMode,
  loadReplay,
  loadStory,
  parseMode,
  type Fetcher,
} from "./adapter";
import { parseJson, validateIndex, validateReplay, validateStory } from "./validate";

const files: Record<string, unknown> = {
  "/replay/index.json": index,
  "/replay/baseline_ok.json": baseline,
  "/replay/door_open_excursion.json": doorOpen,
  "/replay/reefer_failure.json": reefer,
  "/replay/spoof_attempt.json": spoof,
  "/replay/hidden_spoilage.json": hidden,
};

function serve(overrides: Record<string, string | number> = {}): Fetcher {
  return async (url) => {
    const override = overrides[url];
    if (typeof override === "number") return { ok: false, status: override, text: async () => "" };
    if (typeof override === "string") return { ok: true, status: 200, text: async () => override };
    if (url in files) return { ok: true, status: 200, text: async () => JSON.stringify(files[url]) };
    return { ok: false, status: 404, text: async () => "" };
  };
}

const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T;

describe("mode selection", () => {
  it("defaults to story and accepts the three modes", () => {
    expect(parseMode("")).toBe("story");
    expect(parseMode("?mode=replay")).toBe("replay");
    expect(parseMode("?mode=live&tier=low")).toBe("live");
    expect(parseMode("?mode=story")).toBe("story");
  });
  it("falls back to story for anything else", () => {
    expect(parseMode("?mode=demo")).toBe("story");
    expect(parseMode("?mode=")).toBe("story");
    expect(parseMode("?MODE=live")).toBe("story");
  });
});

describe("validation of the real files", () => {
  it("accepts the five exported scenarios and the index", () => {
    expect(validateIndex(index).ok).toBe(true);
    for (const [id, doc] of [
      ["baseline_ok", baseline],
      ["door_open_excursion", doorOpen],
      ["reefer_failure", reefer],
      ["spoof_attempt", spoof],
      ["hidden_spoilage", hidden],
    ] as const) {
      const result = validateReplay(doc, id);
      expect(result.ok, id).toBe(true);
    }
  });

  it("accepts the bundled story figures", () => {
    expect(validateStory(story).ok).toBe(true);
  });
});

describe("malformed and empty input", () => {
  it("reports empty text and invalid JSON calmly", () => {
    expect(parseJson("", "x")).toEqual({ ok: false, error: "x is empty." });
    expect(parseJson("   ", "x").ok).toBe(false);
    expect(parseJson("{not json", "x")).toEqual({ ok: false, error: "x is not valid JSON." });
  });

  it("rejects things that are not scenario files", () => {
    for (const bad of [null, 5, "text", [], {}, { meta: {} }]) {
      expect(validateReplay(bad).ok).toBe(false);
    }
    expect(validateIndex({ schema_version: "1", scenarios: [] }).ok).toBe(false);
    expect(validateIndex({ schema_version: "9", scenarios: [] }).ok).toBe(false);
    expect(validateIndex(null).ok).toBe(false);
    expect(validateStory({}).ok).toBe(false);
  });

  it("rejects a file with no frames, a bad frame, time going back or a potency out of range", () => {
    const noFrames = clone(baseline);
    noFrames.frames = [];
    expect(validateReplay(noFrames).ok).toBe(false);

    const badField = clone(baseline) as { frames: Record<string, unknown>[] };
    badField.frames[3].potency = "high";
    expect(validateReplay(badField).ok).toBe(false);

    const backwards = clone(baseline) as { frames: { t_s: number }[] };
    backwards.frames[5].t_s = -1;
    const result = validateReplay(backwards);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toContain("back in time");

    const outOfRange = clone(baseline) as { frames: { potency: number }[] };
    outOfRange.frames[2].potency = 1.5;
    expect(validateReplay(outOfRange).ok).toBe(false);
  });

  it("rejects a file for the wrong scenario, a wrong schema version, or without labels", () => {
    const wrongId = validateReplay(baseline, "hidden_spoilage");
    expect(wrongId.ok).toBe(false);
    const wrongVersion = clone(baseline);
    wrongVersion.meta.schema_version = "2";
    expect(validateReplay(wrongVersion).ok).toBe(false);
    const noLabels = clone(baseline) as { meta: Record<string, unknown> };
    delete noLabels.meta.labels;
    expect(validateReplay(noLabels).ok).toBe(false);
  });

  it("rejects a scenario file name that could point elsewhere", () => {
    const sneaky = { schema_version: "1", scenarios: [{ scenario_id: "x", label: "x", file: "../secret.json", checkpoint_h: 1 }] };
    expect(validateIndex(sneaky).ok).toBe(false);
  });
});

describe("loading", () => {
  it("loads all five scenarios in replay mode", async () => {
    const snap = await loadReplay(serve(), "replay");
    expect(snap.status).toEqual({ state: "ready", mode: "replay", scenarios: 5, message: null });
    expect(Object.keys(snap.scenarios).sort()).toEqual([
      "baseline_ok",
      "door_open_excursion",
      "hidden_spoilage",
      "reefer_failure",
      "spoof_attempt",
    ]);
  });

  it("shows a calm error, not a crash, for a malformed index", async () => {
    const snap = await loadReplay(serve({ "/replay/index.json": "{oops" }), "replay");
    expect(snap.status.state).toBe("error");
    if (snap.status.state === "error") expect(snap.status.message).toContain("not valid JSON");
  });

  it("shows a calm error for an empty or missing index", async () => {
    expect((await loadReplay(serve({ "/replay/index.json": "" }), "replay")).status.state).toBe("error");
    expect((await loadReplay(serve({ "/replay/index.json": 404 }), "replay")).status.state).toBe("error");
  });

  it("skips one bad scenario file, names it, and loads the rest", async () => {
    const snap = await loadReplay(serve({ "/replay/reefer_failure.json": "{}" }), "replay");
    expect(snap.status.state).toBe("ready");
    expect(Object.keys(snap.scenarios)).toHaveLength(4);
    if (snap.status.state === "ready") expect(snap.status.message).toContain("reefer_failure");
  });

  it("reports an error when every scenario file is bad", async () => {
    const bad = Object.fromEntries(Object.keys(files).filter((k) => k !== "/replay/index.json").map((k) => [k, "[]"]));
    expect((await loadReplay(serve(bad), "replay")).status.state).toBe("error");
  });

  it("story mode uses the bundled figures and makes no request", async () => {
    let calls = 0;
    const counting: Fetcher = async () => {
      calls += 1;
      return { ok: false, status: 500, text: async () => "" };
    };
    const snap = await loadForMode("story", counting, story);
    expect(calls).toBe(0);
    expect(snap.status).toMatchObject({ state: "ready", mode: "story" });
    expect(snap.story?.profiles.active.journeys.A.shelf_life_used_percent).toBeGreaterThan(0);
    expect(loadStory({}).status.state).toBe("error");
  });
});

describe("live mode", () => {
  const live = (shipments: unknown): Fetcher => {
    const base = serve();
    return async (url) => {
      if (url === "/api/health") return { ok: true, status: 200, text: async () => '{"status":"ok","authentication":"none"}' };
      if (url === "/api/shipments") return { ok: true, status: 200, text: async () => JSON.stringify(shipments) };
      return base(url);
    };
  };

  it("counts shipments read-only when the backend answers", async () => {
    const result = await checkLive(live([{ id: "a" }, { id: "b" }]));
    expect(result).toEqual({ ok: true, value: { shipments: 2 } });
    const wrapped = await checkLive(live({ items: [{ id: "a" }] }));
    expect(wrapped).toEqual({ ok: true, value: { shipments: 1 } });
  });

  it("falls back to replay with a calm message when the backend is down", async () => {
    const snap = await loadForMode("live", serve(), story);
    expect(snap.status.mode).toBe("live");
    expect(snap.status.state).toBe("ready");
    if (snap.status.state === "ready") {
      expect(snap.status.message).toBe(LIVE_FALLBACK_MESSAGE);
      expect(snap.status.scenarios).toBe(5);
    }
  });

  it("treats an unexpected answer as unavailable", async () => {
    expect((await checkLive(live("nonsense"))).ok).toBe(false);
    expect((await checkLive(async () => { throw new Error("offline"); })).ok).toBe(false);
  });

  it("only ever reads from the same-origin proxy path", async () => {
    const seen: string[] = [];
    const spy: Fetcher = async (url) => {
      seen.push(url);
      return { ok: false, status: 502, text: async () => "" };
    };
    await checkLive(spy);
    expect(seen.every((u) => u.startsWith("/api/"))).toBe(true);
  });
});
