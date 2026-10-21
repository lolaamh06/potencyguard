// Decisions: the queue of shipments waiting for a person, built from the replay data. Each item has
// the recommendation, the reasons in plain words, and the three decision buttons (with confirm).
import { useUi } from "../app/ui";
import { SCENARIO_IDS, type HumanOutcome, type ScenarioId } from "../controlroom/logic";
import { useCr } from "../controlroom/store";
import { actionLabel } from "../copy/glossary";
import { headline, plainReasons } from "../copy/headline";
import { SCENARIO_COPY } from "../copy/scenarios";
import type { AdapterSnapshot, ReplayFile } from "../data/types";
import { DecisionActions } from "./Decide";
import { PageShell } from "./PageShell";

export interface QueueItem {
  id: ScenarioId;
  replay: ReplayFile;
}

/** Shipments whose recommendation needs a person and has not been decided yet, in the fixed shipment order. */
export function pendingQueue(scenarios: AdapterSnapshot["scenarios"], outcomes: Partial<Record<ScenarioId, HumanOutcome>>): QueueItem[] {
  return SCENARIO_IDS.filter((id) => scenarios[id]?.decision.needs_human && !outcomes[id]).map((id) => ({ id, replay: scenarios[id] }));
}

export function decidedList(scenarios: AdapterSnapshot["scenarios"], outcomes: Partial<Record<ScenarioId, HumanOutcome>>): QueueItem[] {
  return SCENARIO_IDS.filter((id) => scenarios[id] && outcomes[id]).map((id) => ({ id, replay: scenarios[id] }));
}

export function DecisionsPage({ data }: { data: AdapterSnapshot }) {
  const mode = useUi((s) => s.mode);
  const outcomes = useCr((s) => s.outcomes);
  const clear = useCr((s) => s.clearDecisions);
  const pending = pendingQueue(data.scenarios, outcomes);
  const done = decidedList(data.scenarios, outcomes);
  const loading = data.status.state === "loading";
  return (
    <PageShell route={{ page: "decisions" }}>
      {loading && <p role="status" className="muted">Loading…</p>}
      {data.status.state === "error" && <p role="alert" className="error">The shipments could not be loaded: {data.status.message}</p>}
      {!loading && pending.length === 0 && (
        <section className="card empty" role="status">
          <h2>Nothing is waiting for a person</h2>
          <p>{done.length > 0 ? "You have decided every open item. " : ""}Open a shipment that needs a person, for example “{SCENARIO_COPY.hidden_spoilage.title}”, to see how a decision works.</p>
          <p className="btn-row"><a className="btn primary" href="#/shipments/hidden_spoilage">Open “{SCENARIO_COPY.hidden_spoilage.title}”</a><a className="btn" href="#/shipments">See all shipments</a></p>
        </section>
      )}
      <ul className="cards decide-list">
        {pending.map(({ id, replay }, i) => (
          <li key={id} className="card decide-card">
            <h2>{SCENARIO_COPY[id].title}</h2>
            <p className="headline small">{headline(replay)}</p>
            <p className="rec-action">{actionLabel(replay.decision.chosen_action, mode)}</p>
            <ul className="why">{plainReasons(replay).map((t) => <li key={t}>{t}</li>)}</ul>
            <DecisionActions replay={replay} ignoreClock tourId={i === 0 ? "tour-decide" : undefined} />
            <p className="note"><a href={`#/shipments/${id}`}>Open this shipment</a> to watch what led to it.</p>
          </li>
        ))}
      </ul>
      {done.length > 0 && (
        <section aria-labelledby="h-done">
          <h2 id="h-done">Already decided</h2>
          <ul className="cards">
            {done.map(({ id, replay }) => (
              <li key={id} className="card">
                <h3>{SCENARIO_COPY[id].title}</h3>
                <DecisionActions replay={replay} ignoreClock />
              </li>
            ))}
          </ul>
          <button type="button" className="btn" onClick={clear}>Start over (undo these demo decisions)</button>
        </section>
      )}
    </PageShell>
  );
}
