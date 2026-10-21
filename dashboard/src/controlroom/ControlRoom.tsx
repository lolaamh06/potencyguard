// The Control Room: replay-first and offline. It plays one of five recorded scenarios on a
// simulated clock, shows what the exporter wrote, and lets a presenter select scenarios with
// guarded switches, show recorded tamper results, and take demo decisions that change this screen
// only. Nothing here computes planner numbers and nothing leaves the browser.
import gsap from "gsap";
import { useCallback, useEffect, useMemo, useRef } from "react";
import { goTo } from "../app/route";
import { useAppStore } from "../app/appStore";
import type { AdapterSnapshot, Mode, ReplayFile } from "../data/types";
import { useGlobeStore } from "../globe/globeStore";
import { GuardedButton } from "./GuardedButton";
import {
  REC_LENGTH_MS,
  REC_SEQUENCE,
  SCENARIO_IDS,
  SPEEDS,
  decisionReached,
  dueSteps,
  frameIndexAt,
  journeyProgress,
  routeStateFor,
  scenarioForKey,
  showAlternative,
  switchAvailability,
  tamperOptions,
  type ScenarioId,
} from "./logic";
import { ChainPanel, EventLog, PlannerPanel, PotencyPanel, ProvenanceDrawer, ShipmentCard } from "./Panels";
import { TimeChart } from "./TimeChart";
import { useCr } from "./store";
import "./controlroom.css";

export function ControlRoom({ mode, data, backendReachable, recMode }: { mode: Mode; data: AdapterSnapshot; backendReachable: boolean | null; recMode: boolean }) {
  const scenarioId = useCr((s) => s.scenarioId);
  const tS = useCr((s) => s.tS);
  const speed = useCr((s) => s.speed);
  const paused = useCr((s) => s.paused);
  const lastUse = useCr((s) => s.lastUseMs);
  const provenanceOpen = useCr((s) => s.provenanceOpen);
  const recording = useCr((s) => s.recording);
  const cr = useCr;
  const setHelp = useAppStore((s) => s.setHelpOpen);
  const replay: ReplayFile | undefined = data.scenarios[scenarioId];
  const loading = data.status.state === "loading";
  const replayRef = useRef<ReplayFile | undefined>(replay);
  replayRef.current = replay;

  // the globe lives in a window of this screen
  useEffect(() => {
    useGlobeStore.getState().setLayout("control");
    return () => useGlobeStore.getState().setLayout("story");
  }, []);

  // the replay clock follows the shared ticker; reaching the end holds the final frame
  useEffect(() => {
    const tick = (_time: number, deltaMs: number) => {
      const r = replayRef.current;
      if (r) cr.getState().tick(deltaMs / 1000, r, performance.now());
    };
    gsap.ticker.add(tick);
    return () => gsap.ticker.remove(tick);
  }, [cr]);

  // route state, alternative and marker on the globe (progress in 1 percent steps)
  const frame = replay ? replay.frames[frameIndexAt(replay.frames, tS)] : null;
  const routeState = replay && frame ? routeStateFor(frame, replay, tS) : "safe";
  const alt = replay ? showAlternative(replay, tS) : false;
  const prog = replay ? Math.round(journeyProgress(replay, tS) * 100) / 100 : 0;
  useEffect(() => {
    if (!replay) return;
    const r = replay.meta.route;
    useGlobeStore.getState().setProps({ routeState, showAlternative: alt, shipmentProgress: prog, origin: r.origin, destination: r.destination, alternativeVia: r.alternative[0] ?? undefined });
  }, [replay, routeState, alt, prog]);

  const select = useCallback((id: ScenarioId, how?: string) => {
    const s = cr.getState();
    if (!switchAvailability({ id, activeId: s.scenarioId, nowMs: performance.now(), lastUseMs: s.lastUseMs, loading }).enabled && how !== "recording") return;
    s.selectScenario(id, performance.now(), how);
  }, [cr, loading]);

  const tamperNow = useCallback(() => {
    const r = replayRef.current;
    if (!r || mode === "live") return;
    cr.getState().applyTamper(r);
  }, [cr, mode]);

  // presenter shortcuts
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName)) return;
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const k = e.key;
      const id = scenarioForKey(k);
      const s = cr.getState();
      if (id) {
        e.preventDefault();
        select(id, "shortcut");
      } else if (k === " ") {
        if (t instanceof HTMLButtonElement) return;
        e.preventDefault();
        s.togglePause();
      } else if (k === "r" || k === "R") s.reset();
      else if (k === "t" || k === "T") tamperNow();
      else if (k === "a" || k === "A") {
        const r = replayRef.current;
        if (r) s.decide(r, { kind: "approve" });
      } else if (k === "p" || k === "P") s.setProvenance(!s.provenanceOpen);
      else if ((k === "v" || k === "V") && recMode) s.setRecording(!s.recording);
      else if (k === "Escape") s.setProvenance(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [cr, select, tamperNow, recMode]);

  // recording mode: a scripted, repeatable sequence at fixed timing
  useEffect(() => {
    if (!recording) return;
    const t0 = performance.now();
    let prev = -1;
    const run = () => {
      const now = performance.now() - t0;
      for (const step of dueSteps(REC_SEQUENCE, prev, now)) {
        const a = step.action;
        const s = cr.getState();
        const r = replayRef.current;
        if (a.type === "scenario") {
          s.selectScenario(a.id, performance.now(), "recording");
          s.setSpeed(a.speed);
        } else if (a.type === "tamper" && r) {
          const opts = tamperOptions(r.tamper);
          s.pickTamper(opts[Math.min(a.entryIndexInList, opts.length - 1)].key);
          s.applyTamper(r);
        } else if (a.type === "approve" && r) s.decide(r, { kind: "approve" });
        else if (a.type === "provenance") s.setProvenance(a.open);
      }
      prev = now;
      if (now > REC_LENGTH_MS) cr.getState().setRecording(false);
    };
    gsap.ticker.add(run);
    return () => gsap.ticker.remove(run);
  }, [recording, cr]);

  const options = useMemo(() => (replay ? tamperOptions(replay.tamper) : []), [replay]);
  void options;

  if (data.status.state === "error") {
    return (
      <main className="cr-state" aria-label="Control Room">
        <h1>Control Room</h1>
        <p role="alert">The recorded scenarios could not be read: {data.status.message}</p>
        <p>Run <span className="num">python scripts/export_replay.py</span> to write them again.</p>
      </main>
    );
  }
  if (loading) {
    return (
      <main className="cr-state" aria-label="Control Room">
        <h1>Control Room</h1>
        <p role="status">Loading the recorded scenarios.</p>
      </main>
    );
  }
  if (!replay || !frame) {
    return (
      <main className="cr-state" aria-label="Control Room">
        <h1>Control Room</h1>
        <p role="status">There are no data for the scenario {scenarioId}. Pick another one.</p>
      </main>
    );
  }

  const nowMs = performance.now();
  return (
    <main className="cr" aria-label="Control Room, a simulation on synthetic data">
      <header className="topbar">
        <a className="brand-cr" href="#/story">PotencyGuard<small>SIMULATION</small></a>
        <div className="scen-row" role="group" aria-label="Scenarios (hold to select)">
          {SCENARIO_IDS.map((id, i) => (
            <GuardedButton
              key={id}
              ariaLabel={`Select the scenario ${id} (hold to arm). Shortcut ${i + 1}.`}
              availability={switchAvailability({ id, activeId: scenarioId, nowMs, lastUseMs: lastUse, loading })}
              active={id === scenarioId}
              onFire={() => select(id)}
            >
              <span className="num">{i + 1}</span> {id}
            </GuardedButton>
          ))}
        </div>
        <span className="spacer" />
        <div className="seg" role="group" aria-label="Replay speed">
          {SPEEDS.map((s) => (
            <button key={s} type="button" className="btn" aria-pressed={speed === s} onClick={() => cr.getState().setSpeed(s)}>{s}×</button>
          ))}
        </div>
        <button type="button" className="btn" aria-pressed={paused} onClick={() => cr.getState().togglePause()} aria-keyshortcuts="Space">{paused ? "Resume" : "Pause"}</button>
        <button type="button" className="btn" onClick={() => cr.getState().reset()} aria-keyshortcuts="R">Reset</button>
        <button type="button" className="btn" aria-expanded={provenanceOpen} onClick={() => cr.getState().setProvenance(!provenanceOpen)} aria-keyshortcuts="P">Provenance</button>
        {!recMode && <button type="button" className="btn" onClick={() => goTo("story")}>Story</button>}
        {!recMode && <button type="button" className="btn" aria-label="Keyboard shortcuts" onClick={() => setHelp(true)}>?</button>}
      </header>

      <ShipmentCard replay={replay} tS={tS} />
      <div className="globe-window" aria-hidden="true" />
      <PotencyPanel replay={replay} tS={tS} />

      <section className="panel chart-panel" aria-labelledby="h-chart">
        <h2 id="h-chart" className="eyebrow">Reported against the physics twin <small>{replay.meta.scenario_id}.jsonl, simulated sensor feed</small></h2>
        <TimeChart replay={replay} />
        <div className="legend-row">
          <span style={{ "--c": "var(--ice-400)" } as React.CSSProperties}>reported by the sensor feed</span>
          <span style={{ "--c": "var(--mist-hi)" } as React.CSSProperties}>twin prediction, one step ahead</span>
          <span style={{ "--c": "var(--ember-400)" } as React.CSSProperties}>alarm threshold</span>
          <span>▲ physics check fired</span>
        </div>
      </section>
      <ChainPanel replay={replay} tS={tS} live={mode === "live"} />

      <PlannerPanel replay={replay} tS={tS} />
      <EventLog replay={replay} tS={tS} />

      <ProvenanceDrawer replay={replay} mode={mode} />
      {mode === "live" && backendReachable === false && <p className="notice" role="status">The backend is not reachable, so the recorded scenarios are shown.</p>}
      {data.status.state === "ready" && data.status.message && mode === "live" && backendReachable !== false && <p className="notice" role="status">{data.status.message}</p>}
      {decisionReached(replay, tS) && <span className="sr-only" role="status">Decision reached: {replay.decision.chosen_action}</span>}
    </main>
  );
}
