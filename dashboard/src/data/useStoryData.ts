// Loads the files the chapters need (once, cached). A missing or malformed file gives null and a
// calm message on the page, never an exception.
import { useEffect, useState } from "react";
import chapter1 from "./bundled/chapter1.json";
import { loadReplayFile, type Fetcher } from "./adapter";
import { parseJson, validateStory } from "./validate";
import { validateChapter5, validateChapter6, type Chapter5Data, type Chapter6Data } from "./story";
import type { ReplayFile, StoryData } from "./types";

const browserFetch: Fetcher = (url) => fetch(url);

export interface StoryBundle {
  ch1: StoryData | null;
  ch2: ReplayFile | null;
  ch3: ReplayFile | null;
  ch5: Chapter5Data | null;
  ch6: Chapter6Data | null;
  hidden: ReplayFile | null;
  problems: string[];
}

async function fetchJson<T>(url: string, validate: (raw: unknown) => { ok: true; value: T } | { ok: false; error: string }): Promise<{ value: T | null; problem: string | null }> {
  try {
    const response = await fetch(url);
    if (!response.ok) return { value: null, problem: `${url} answered ${response.status}.` };
    const json = parseJson(await response.text(), url);
    if (!json.ok) return { value: null, problem: json.error };
    const result = validate(json.value);
    return result.ok ? { value: result.value, problem: null } : { value: null, problem: result.error };
  } catch {
    return { value: null, problem: `${url} could not be read.` };
  }
}

let cached: Promise<StoryBundle> | null = null;

export function loadStoryBundle(): Promise<StoryBundle> {
  cached ??= (async () => {
    const problems: string[] = [];
    const take = <T,>(r: { value: T | null; problem: string | null }): T | null => {
      if (r.problem) problems.push(r.problem);
      return r.value;
    };
    const story = validateStory(chapter1);
    const replay = async (file: string, id: string): Promise<ReplayFile | null> => {
      const r = await loadReplayFile(browserFetch, file, id);
      if (!r.ok) problems.push(r.error);
      return r.ok ? r.value : null;
    };
    const [ch2, ch3, hidden, ch5, ch6] = await Promise.all([
      replay("spoof_attempt.json", "spoof_attempt"),
      replay("reefer_failure.json", "reefer_failure"),
      replay("hidden_spoilage.json", "hidden_spoilage"),
      fetchJson("/story/chapter5.json", validateChapter5).then(take),
      fetchJson("/story/chapter6.json", validateChapter6).then(take),
    ]);
    return { ch1: story.ok ? story.value : null, ch2, ch3, ch5, ch6, hidden, problems };
  })();
  return cached;
}

export function useStoryBundle(): StoryBundle | null {
  const [bundle, setBundle] = useState<StoryBundle | null>(null);
  useEffect(() => {
    let alive = true;
    void loadStoryBundle().then((b) => alive && setBundle(b));
    return () => {
      alive = false;
    };
  }, []);
  return bundle;
}
