// Loads the data for the current mode once, and (in live mode) re-checks the backend every few
// seconds, read-only. The result is plain state that changes rarely.
import { useEffect, useState } from "react";
import story from "./bundled/chapter1.json";
import { EMPTY, LIVE_POLL_MS, checkLive, loadForMode, parseMode, type Fetcher } from "./adapter";
import type { AdapterSnapshot, Mode } from "./types";

const browserFetch: Fetcher = (url) => fetch(url);

export function currentMode(): Mode {
  return parseMode(window.location.search);
}

export function useAdapter(mode: Mode): AdapterSnapshot & { backendReachable: boolean | null } {
  const [snapshot, setSnapshot] = useState<AdapterSnapshot>({ ...EMPTY, status: { state: "loading", mode } });
  const [reachable, setReachable] = useState<boolean | null>(null);

  useEffect(() => {
    let alive = true;
    loadForMode(mode, browserFetch, story)
      .then((s) => alive && setSnapshot(s))
      .catch(() => alive && setSnapshot({ ...EMPTY, status: { state: "error", mode, message: "The data could not be loaded." } }));
    return () => {
      alive = false;
    };
  }, [mode]);

  useEffect(() => {
    if (mode !== "live") return;
    let alive = true;
    const poll = () => checkLive(browserFetch).then((r) => alive && setReachable(r.ok));
    void poll();
    const id = window.setInterval(poll, LIVE_POLL_MS);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, [mode]);

  return { ...snapshot, backendReachable: reachable };
}
