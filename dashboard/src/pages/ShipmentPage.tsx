// A shipment: a plain headline, playback controls, a medicine-strength gauge, the temperature chart
// (measured against expected), the recommendation with two cost bars, the approval buttons, and a
// "What happened" timeline in sentences. "Show details" adds the technical panels. Every figure is
// read from the replay data; the plain sentences come from the glossary and headline builder.
import { useEffect, useMemo } from "react";
import { useUi } from "../app/ui";
import { SCENARIO_IDS, decisionReached, frameIndexAt, journeyProgress, ringValues, routeStateFor, showAlternative, type ScenarioId, SIM_S_PER_WALL_S, type Speed } from "../controlroom/logic";
import { TimeChart } from "../controlroom/TimeChart";
import { crClock, useCr } from "../controlroom/store";
import { useReplayClock } from "../controlroom/useClock";
import { actionLabel, actionPhrase, term, trustAnswer, verdictLabel } from "../copy/glossary";
import { headline, plainReasons, statusKind, STATUS_WORDS } from "../copy/headline";
import { timelineLines } from "../copy/timeline";
import type { AdapterSnapshot, ReplayFile } from "../data/types";
import { useGlobeStore } from "../globe/globeStore";
import { PageShell } from "./PageShell";
import { DecisionActions } from "./Decide";
import { Ribbon } from "./Ribbon";
import { Chip, StatusChip, Term, fmtInt } from "./ui";
import { intactTokens } from "../controlroom/logic";
import { goTo } from "../app/route";

const SPEEDS: { label: string; speed: Speed }[] = [
  { label: "Slow", speed: 1 },
  { label: "Normal", speed: 4 },
  { label: "Fast", speed: 16 },
];

function Gauge({ replay, tS }: { replay: ReplayFile; tS: number }) {
  const mode = useUi((s) => s.mode);
  const frame = replay.frames[frameIndexAt(replay.frames, tS)];
  const r = ringValues(frame);
  const reached = decisionReached(replay, tS);
  const d = replay.decision;
  const bound = reached && (d.worst_case.bound_used || frame.trust_level !== "trusted");
  const C = 2 * Math.PI * 78;
  const C2 = 2 * Math.PI * 60;
  const trustKind = frame.trust_level === "trusted" ? "good" : frame.trust_level === "untrusted" ? "bad" : "warn";
  return (
    <section className="card gauge-card" aria-labelledby="h-gauge" data-tour="tour-play-gauge">
      <h2 id="h-gauge"><Term id="potency" /></h2>
      <div className="gauge">
        <svg viewBox="0 0 180 180" className="ring" role="img" aria-label={`${term("potency", "simple")}: ${r.potencyPercent.toFixed(1)} percent${bound ? `. Worst-case bound: ${(d.worst_case.potency * 100).toFixed(1)} percent, not an estimate` : ""}`}>
          <circle cx="90" cy="90" r="78" fill="none" stroke="var(--ink-700)" strokeWidth="12" />
          <circle cx="90" cy="90" r="78" fill="none" stroke="var(--ice-400)" strokeWidth="12" strokeLinecap="round" strokeDasharray={C} strokeDashoffset={C * (1 - Math.min(1, Math.max(0, frame.potency)))} transform="rotate(-90 90 90)" />
          {bound && (
            <>
              <circle cx="90" cy="90" r="60" fill="none" stroke="var(--ink-700)" strokeWidth="9" />
              <circle cx="90" cy="90" r="60" fill="none" stroke="var(--ember-500)" strokeWidth="9" strokeLinecap="round" strokeDasharray={C2} strokeDashoffset={C2 * (1 - d.worst_case.potency)} transform="rotate(-90 90 90)" />
            </>
          )}
        </svg>
        <div className="gauge-text">
          <strong className="big num">{r.potencyPercent.toFixed(1)}%</strong>
          <span>of full strength, as reported by the sensor feed</span>
        </div>
      </div>
      <dl className="facts">
        <div><dt><Term id="shelfLifeUsed" /></dt><dd className="num">{r.usedPercent.toFixed(1)}%</dd></div>
        <div><dt><Term id="trust" /></dt><dd><Chip icon={trustKind === "good" ? "ok" : trustKind === "bad" ? "alert" : "warn"} tone={trustKind}>{trustAnswer(frame.trust_level, mode)}</Chip></dd></div>
        {bound && (
          <div className="bound"><dt><Term id="worstCaseBound" /></dt><dd className="num">{(d.worst_case.potency * 100).toFixed(1)}% strength, {(d.worst_case.shelf_life_used_fraction * 100).toFixed(0)}% of safe life spent</dd></div>
        )}
      </dl>
      <p className="note">Illustrative product, model output.</p>
    </section>
  );
}

function CostBars({ replay }: { replay: ReplayFile }) {
  const mode = useUi((s) => s.mode);
  const d = replay.decision;
  const chosen = d.actions.find((a) => a.name === d.chosen_action)!;
  const other =
    d.chosen_action === "continue"
      ? [...d.actions].filter((a) => a.name !== "continue").sort((a, b) => a.cvar - b.cvar)[0]
      : d.actions.find((a) => a.name === "continue")!;
  const max = Math.max(chosen.cvar, other.cvar) || 1;
  const rows = [chosen, other];
  return (
    <figure className="cost-bars" aria-label="Worst-case cost comparison">
      {rows.map((a, i) => (
        <div key={a.name} className="cost-row">
          <span className="cost-label">{actionLabel(a.name, mode)}{i === 0 ? " (recommended)" : ""}</span>
          <span className="cost-bar"><i className={i === 0 ? "rec" : "alt"} style={{ width: `${(a.cvar / max) * 100}%` }} /></span>
          <span className="num cost-val">{fmtInt(a.cvar)}</span>
        </div>
      ))}
      <figcaption>
        <Term id="worstFive" />: the recommended action costs {fmtInt(chosen.cvar)} and "{actionPhrase(other.name)}" costs {fmtInt(other.cvar)}. Lower is better. Cost units are illustrative.
      </figcaption>
    </figure>
  );
}

function Recommendation({ replay, tS }: { replay: ReplayFile; tS: number }) {
  const mode = useUi((s) => s.mode);
  const reached = decisionReached(replay, tS);
  const d = replay.decision;
  return (
    <section className="card rec-card" aria-labelledby="h-rec" data-tour="tour-recommendation">
      <h2 id="h-rec">Our recommendation</h2>
      {!reached ? (
        <p className="muted">We decide at about {Math.round(replay.meta.checkpoint_h)} hours into the journey. Press Play to watch it get there.</p>
      ) : (
        <>
          <p className="rec-action">{actionLabel(d.chosen_action, mode)}</p>
          <ul className="why">
            {plainReasons(replay).slice(0, 2).map((t) => <li key={t}>{t}</li>)}
          </ul>
          <CostBars replay={replay} />
          {d.close_call && <p className="note"><Term id="closeCall" />: two options were almost tied.</p>}
        </>
      )}
      <DecisionActions replay={replay} tourId="tour-decide-inline" />
    </section>
  );
}

function Timeline({ replay, tS }: { replay: ReplayFile; tS: number }) {
  const mode = useUi((s) => s.mode);
  const human = useCr((s) => s.outcomes[replay.meta.scenario_id as ScenarioId] ?? null);
  const lines = useMemo(() => timelineLines(replay, tS, mode, human), [replay, tS, mode, human]);
  return (
    <section className="card" aria-labelledby="h-time">
      <h2 id="h-time">What happened</h2>
      <ol className="timeline" aria-live="polite">
        {lines.map((l) => (
          <li key={l.key}><span className="num t">{l.hours.toFixed(1)} h</span> {l.text}</li>
        ))}
      </ol>
    </section>
  );
}

function Details({ replay, tS }: { replay: ReplayFile; tS: number }) {
  const mode = useUi((s) => s.mode);
  const d = replay.decision;
  const frame = replay.frames[frameIndexAt(replay.frames, tS)];
  const reached = decisionReached(replay, tS);
  const n = replay.tamper.ledger_length;
  return (
    <details className="details">
      <summary>Show details</summary>
      <div className="details-body">
        {mode === "technical" && (
          <section aria-labelledby="h-full-chart">
            <h3 id="h-full-chart">Measured against expected, with the difference and alarm strips</h3>
            <p className="caption">Top: measured temperature (solid) and the physics model's expectation (dashed). Middle: the <Term id="difference" help={false} /> strip. Bottom: the <Term id="alarmStrip" help={false} />; a check fires when it passes the dotted line.</p>
            <div className="chart-box tall"><TimeChart replay={replay} /></div>
          </section>
        )}
        <section aria-labelledby="h-figs">
          <h3 id="h-figs">Reported and recomputed figures</h3>
          <dl className="facts wide">
            <div><dt><Term id="potency" /> (reported by the sensor feed)</dt><dd className="num">{(frame.potency * 100).toFixed(2)}%</dd></div>
            <div><dt><Term id="potency" /> (recomputed by the backend at {d.recomputed.t_h} h)</dt><dd className="num">{reached ? `${(d.recomputed.potency * 100).toFixed(2)}%` : "not yet"}</dd></div>
            <div><dt><Term id="shelfLifeUsed" /></dt><dd className="num">{(frame.shelf_life_used_fraction * 100).toFixed(2)}%</dd></div>
            <div><dt><Term id="mkt" /></dt><dd className="num">{frame.mkt_c === null ? "n/a" : `${frame.mkt_c.toFixed(2)} °C`}</dd></div>
            <div><dt>Equivalent time at the reference temperature</dt><dd className="num">{frame.tau_eq_h.toFixed(1)} h</dd></div>
            <div><dt>Verdict</dt><dd>{verdictLabel(frame.verdict, mode)}</dd></div>
          </dl>
        </section>
        {reached && (
          <section aria-labelledby="h-table">
            <h3 id="h-table">All the actions compared</h3>
            <table className="table">
              <thead><tr><th>Action</th><th className="r"><Term id="expectedLoss" /></th><th className="r"><Term id="worstFive" /></th></tr></thead>
              <tbody>
                {d.actions.map((a) => (
                  <tr key={a.name} className={a.name === d.chosen_action ? "pick" : ""}>
                    <td>{a.name === d.chosen_action ? "✓ " : ""}{actionLabel(a.name, mode)}</td>
                    <td className="num r">{fmtInt(a.expected_loss)}</td>
                    <td className="num r">{fmtInt(a.cvar)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="caption">Cost units are illustrative. {d.n_scenarios.toLocaleString("en-US")} simulated outcomes per action, seed {d.planner_seed}.</p>
            <h3>The full reasons</h3>
            <ul className="why">{d.reasons.map((t, i) => <li key={i}>{t}</li>)}</ul>
          </section>
        )}
        <section aria-labelledby="h-chain">
          <h3 id="h-chain">The chain of records</h3>
          <Ribbon tokens={intactTokens(n, Math.round(journeyProgress(replay, tS) * (n - 1)))} label="Chain of signed records, all verified" />
          <p className="caption">{n} records. {replay.chain.result}. To see what happens when one is changed, go to the <a href="#/proof">Proof page</a>.</p>
        </section>
      </div>
    </details>
  );
}

export function ShipmentPage({ id, data }: { id: ScenarioId; data: AdapterSnapshot }) {
  const replay = data.scenarios[id];
  const scenarioId = useCr((s) => s.scenarioId);
  const tS = useCr((s) => s.tS);
  const speed = useCr((s) => s.speed);
  const paused = useCr((s) => s.paused);
  const human = useCr((s) => s.outcomes[id] ?? null);
  useReplayClock(replay);

  // opening a shipment starts it from the beginning at Normal speed
  useEffect(() => {
    const s = useCr.getState();
    s.selectScenario(id, performance.now(), "opened");
    s.setSpeed(4);
  }, [id]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && ["INPUT", "TEXTAREA", "SELECT", "BUTTON", "A", "SUMMARY"].includes(t.tagName)) return;
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.key === " ") {
        e.preventDefault();
        useCr.getState().togglePause();
      } else if (e.key === "r" || e.key === "R") useCr.getState().reset();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // the globe shows where the shipment is, in the colour of its state
  const frame = replay ? replay.frames[frameIndexAt(replay.frames, tS)] : null;
  const routeState = replay && frame ? routeStateFor(frame, replay, tS) : "safe";
  const alt = replay ? showAlternative(replay, tS) : false;
  const prog = replay ? Math.round(journeyProgress(replay, tS) * 100) / 100 : 0;
  useEffect(() => {
    if (!replay) return;
    const r = replay.meta.route;
    useGlobeStore.getState().setProps({ routeState, showAlternative: alt, shipmentProgress: prog, origin: r.origin, destination: r.destination, alternativeVia: r.alternative[0] });
    return () => useGlobeStore.getState().setProps({ shipmentProgress: null, showAlternative: false, routeState: "safe" });
  }, [replay, routeState, alt, prog]);

  const route = { page: "shipment" as const, id };
  if (!SCENARIO_IDS.includes(id)) return null;
  if (data.status.state === "loading") return <PageShell route={route}><p role="status" className="muted">Loading this shipment…</p></PageShell>;
  if (!replay || !frame || scenarioId !== id) {
    return (
      <PageShell route={route}>
        {data.status.state === "error" || !replay ? (
          <p role="alert" className="error">We could not load this shipment. <a href="#/shipments">Go back to the list</a> and try another.</p>
        ) : (
          <p role="status" className="muted">Getting the journey ready…</p>
        )}
      </PageShell>
    );
  }

  const kind = statusKind(replay);
  const hoursNow = tS / 3600;
  const ended = tS >= (replay.frames[replay.frames.length - 1]?.t_s ?? 0);

  return (
    <PageShell route={route} endActions={<a className="btn" href="#/decisions">See all decisions</a>}>
      <section className="headline-card" aria-live="polite">
        <StatusChip kind={human ? "needs_person" : kind} text={human ? "A person has decided" : STATUS_WORDS[kind]} />
        <p className="headline">{headline(replay)}</p>
      </section>

      <section className="playback" aria-label="Playback" data-tour="tour-play">
        <button type="button" className="btn primary" onClick={() => (ended ? useCr.getState().reset() : useCr.getState().togglePause())}>
          {ended ? "Play again" : paused ? "Play" : "Pause"}
        </button>
        <button type="button" className="btn" onClick={() => useCr.getState().reset()}>Restart</button>
        <div className="seg" role="group" aria-label="Playback speed">
          {SPEEDS.map((s) => (
            <button key={s.label} type="button" className="btn seg-btn" aria-pressed={speed === s.speed} onClick={() => useCr.getState().setSpeed(s.speed)} title={`${s.label}: ${(SIM_S_PER_WALL_S * s.speed) / 3600} hours of the journey per second`}>
              {s.label}
            </button>
          ))}
        </div>
        <span className="num clock" role="timer" aria-label="Time into the journey">{hoursNow.toFixed(1)} of {replay.meta.duration_h.toFixed(0)} hours</span>
      </section>

      <div className="grid-2">
        <Gauge replay={replay} tS={tS} />
        <section className="card chart-card" aria-labelledby="h-chart">
          <h2 id="h-chart">Temperature in the box</h2>
          <p className="caption">This line is the temperature inside the box. The dotted line is what we expected. Triangles mark when a safety check fired.</p>
          <div className="chart-box"><TimeChart replay={replay} simple /></div>
          <ul className="legend" aria-label="Chart legend">
            <li><span className="sw solid" /> Measured temperature</li>
            <li><span className="sw dotted" /> Expected temperature</li>
            <li><span className="sw band" /> Outside the safe range (2 to 8 °C, illustrative)</li>
            <li><span className="sw tri" aria-hidden="true">▲</span> A safety check fired</li>
          </ul>
        </section>
      </div>

      <div className="grid-2">
        <Recommendation replay={replay} tS={tS} />
        <Timeline replay={replay} tS={tS} />
      </div>
      <Details replay={replay} tS={tS} />
    </PageShell>
  );
}

export { crClock, goTo };
