// Shipments: one card per sample shipment, with a plain description, a status in colour, icon and
// word, the medicine-strength figure and an Open button. One card says "Start here".
import { useEffect } from "react";
import { goTo } from "../app/route";
import { SCENARIO_IDS } from "../controlroom/logic";
import { STATUS_WORDS, statusKind, strengthPercent } from "../copy/headline";
import { SCENARIO_COPY, START_HERE } from "../copy/scenarios";
import { term } from "../copy/glossary";
import { useUi } from "../app/ui";
import type { AdapterSnapshot } from "../data/types";
import { PageShell } from "./PageShell";
import { StatusChip, HelpTip } from "./ui";

export function ShipmentsPage({ data }: { data: AdapterSnapshot }) {
  const mode = useUi((s) => s.mode);
  const loading = data.status.state === "loading";
  const failed = data.status.state === "error" ? data.status.message : null;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName)) return;
      const i = Number(e.key);
      if (Number.isInteger(i) && i >= 1 && i <= SCENARIO_IDS.length && !e.ctrlKey && !e.metaKey && !e.altKey) goTo({ page: "shipment", id: SCENARIO_IDS[i - 1] });
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <PageShell route={{ page: "shipments" }}>
      <p className="hint" role="note">Pick a shipment to begin.</p>
      {loading && <p role="status" className="muted">Loading the sample shipments…</p>}
      {failed && <p role="alert" className="error">The sample shipments could not be loaded: {failed}</p>}
      <ul className="cards">
        {SCENARIO_IDS.map((id, i) => {
          const r = data.scenarios[id];
          const copy = SCENARIO_COPY[id];
          const kind = r ? statusKind(r) : null;
          return (
            <li key={id} className={`card ship-card ${id === START_HERE ? "start" : ""}`} data-tour={id === START_HERE ? "tour-start-here" : undefined}>
              {id === START_HERE && <span className="badge-start">Start here</span>}
              <h2>{copy.title}</h2>
              <p>{copy.blurb}</p>
              {r && kind ? (
                <>
                  <p className="kv"><span><span className="term">{term("potency", mode)}<HelpTip id="potency" /></span></span><strong className="num">{strengthPercent(r).toFixed(1)}%</strong></p>
                  {kind === "not_trusted" && <p className="note">This is what the readings say. We cannot trust the readings.</p>}
                  <p><StatusChip kind={kind} text={STATUS_WORDS[kind]} /></p>
                </>
              ) : (
                <p className="muted">{loading ? "Loading…" : "No data for this shipment."}</p>
              )}
              <a className="btn primary" href={`#/shipments/${id}`} aria-label={`Open ${copy.title}`} aria-keyshortcuts={String(i + 1)}>Open</a>
            </li>
          );
        })}
      </ul>
    </PageShell>
  );
}
