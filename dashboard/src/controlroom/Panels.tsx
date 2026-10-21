// The Control Room panels: shipment, potency, chain, planner and approval, event log, provenance.
// Every figure is read from the replay file (or a frame of it); no planner number is computed here.
import gsap from "gsap";
import { useEffect, useMemo, useRef, useState } from "react";
import { useAppStore } from "../app/appStore";
import story from "../data/bundled/chapter1.json";
import type { ReplayFile, StoryData } from "../data/types";
import { GuardedButton } from "./GuardedButton";
import {
  actionLabel,
  canDecide,
  decisionReached,
  frameIndexAt,
  intactTokens,
  journeyProgress,
  mergeLog,
  ringValues,
  statusChip,
  systemLog,
  tamperOptions,
  tamperOutcome,
  trustChip,
  verdictText,
  type Availability,
  type Chip,
} from "./logic";
import { useCr } from "./store";

export const MODEL_LABEL = "Illustrative product, model output";
const fmt = (n: number) => Math.round(n).toLocaleString("en-US");

export function Icon({ kind }: { kind: Chip["icon"] }) {
  const common = { width: 14, height: 14, viewBox: "0 0 16 16", "aria-hidden": true, className: "ic" } as const;
  if (kind === "ok") return <svg {...common}><path d="M3 8.5l3 3 7-7" fill="none" stroke="currentColor" strokeWidth="2" /></svg>;
  if (kind === "warn") return <svg {...common}><path d="M8 2l7 12H1z" fill="none" stroke="currentColor" strokeWidth="1.6" /><path d="M8 6.5v3.5M8 11.7v.8" stroke="currentColor" strokeWidth="1.6" /></svg>;
  if (kind === "alert") return <svg {...common}><circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" strokeWidth="1.6" /><path d="M8 4.5v4.5M8 10.8v.8" stroke="currentColor" strokeWidth="1.6" /></svg>;
  return <svg {...common}><circle cx="8" cy="5.5" r="2.6" fill="none" stroke="currentColor" strokeWidth="1.6" /><path d="M2.5 14c.6-3 2.8-4.4 5.5-4.4s4.9 1.4 5.5 4.4" fill="none" stroke="currentColor" strokeWidth="1.6" /></svg>;
}

export function ChipView({ chip, tone }: { chip: Chip; tone: "ok" | "warn" | "alert" | "person" }) {
  return (
    <span className={`chip ${tone}`}>
      <Icon kind={chip.icon} />
      {chip.text}
    </span>
  );
}

/** A number that eases to its new value (instantly under reduced motion). */
export function Num({ value, decimals = 1, unit = "" }: { value: number | null; decimals?: number; unit?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const shown = useRef<{ v: number }>({ v: value ?? 0 });
  const reduced = useAppStore((s) => s.reducedMotion);
  useEffect(() => {
    if (value === null) return;
    const write = () => {
      if (ref.current) ref.current.textContent = shown.current.v.toFixed(decimals);
    };
    if (reduced) {
      shown.current.v = value;
      write();
      return;
    }
    const tween = gsap.to(shown.current, { v: value, duration: 0.45, ease: "power2.out", onUpdate: write });
    return () => void tween.kill();
  }, [value, decimals, reduced]);
  return (
    <span className="num">
      <span ref={ref}>{value === null ? "n/a" : value.toFixed(decimals)}</span>
      {value !== null && unit && <small>{unit}</small>}
    </span>
  );
}

// ---------------------------------------------------------------- shipment

export function ShipmentCard({ replay, tS }: { replay: ReplayFile; tS: number }) {
  const human = useCr((s) => s.human);
  const frame = replay.frames[frameIndexAt(replay.frames, tS)];
  const status = statusChip(replay, tS, human);
  const tone = status.icon === "person" ? "person" : status.icon;
  const trust = trustChip(frame);
  const p = journeyProgress(replay, tS);
  return (
    <section className="panel" aria-labelledby="h-ship">
      <h2 id="h-ship" className="eyebrow">Shipment</h2>
      <p className="ship-name">{replay.meta.scenario_id}</p>
      <p className="muted">{replay.meta.label}</p>
      <p className="muted">{replay.meta.route.origin.label} to {replay.meta.route.destination.label}</p>
      <div className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(p * 100)} aria-label="Illustrative journey progress">
        <i style={{ width: `${p * 100}%` }} />
      </div>
      <p className="num small">{(tS / 3600).toFixed(1)} of {replay.meta.duration_h.toFixed(1)} h</p>
      <div className="chips">
        <ChipView chip={status} tone={tone} />
        <ChipView chip={trust} tone={trust.icon === "person" ? "ok" : trust.icon} />
        <span className="chip plain"><Icon kind="ok" />{verdictText(frame)}</span>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------- potency

export function PotencyPanel({ replay, tS }: { replay: ReplayFile; tS: number }) {
  const frame = replay.frames[frameIndexAt(replay.frames, tS)];
  const r = ringValues(frame);
  const reached = decisionReached(replay, tS);
  const d = replay.decision;
  const bound = reached && (d.worst_case.bound_used || frame.trust_level !== "trusted");
  const C = 2 * Math.PI * 78;
  const C2 = 2 * Math.PI * 60;
  return (
    <section className="panel" aria-labelledby="h-pot">
      <h2 id="h-pot" className="eyebrow">Potency <small>{MODEL_LABEL}</small></h2>
      <div className="potency">
        <svg viewBox="0 0 180 180" className="ring-big" role="img" aria-label={`Reported potency ${r.potencyPercent.toFixed(2)} percent${bound ? `; worst-case bound ${(d.worst_case.potency * 100).toFixed(1)} percent, not an estimate` : ""}`}>
          <circle cx="90" cy="90" r="78" fill="none" stroke="var(--ink-700)" strokeWidth="11" />
          <circle cx="90" cy="90" r="78" fill="none" stroke="var(--ice-400)" strokeWidth="11" strokeLinecap="round" strokeDasharray={C} strokeDashoffset={C * (1 - Math.min(1, Math.max(0, frame.potency)))} transform="rotate(-90 90 90)" />
          {bound && (
            <>
              <circle cx="90" cy="90" r="60" fill="none" stroke="var(--ink-700)" strokeWidth="8" />
              <circle cx="90" cy="90" r="60" fill="none" stroke="var(--ember-500)" strokeWidth="8" strokeLinecap="round" strokeDasharray={C2} strokeDashoffset={C2 * (1 - d.worst_case.potency)} transform="rotate(-90 90 90)" />
            </>
          )}
        </svg>
        <div className="ring-text">
          <b className="big"><Num value={r.potencyPercent} decimals={2} unit="%" /></b>
          <span>potency, reported by the sensor feed</span>
          {frame.trust_level !== "trusted" && <span className="warn-text">data not trusted</span>}
        </div>
      </div>
      <dl className="figs">
        <div><dt>Shelf life used</dt><dd><Num value={r.usedPercent} decimals={2} unit="%" /></dd></div>
        <div><dt>Equivalent time at reference temperature</dt><dd><Num value={r.tauH} decimals={1} unit=" h" /></dd></div>
        <div><dt>Mean kinetic temperature</dt><dd><Num value={r.mktC} decimals={2} unit=" °C" /></dd></div>
        <div><dt>Box temperature now</dt><dd><Num value={r.tempC} decimals={2} unit=" °C" /></dd></div>
        <div><dt>Recomputed by the backend (at {d.recomputed.t_h} h)</dt><dd>{reached ? <Num value={d.recomputed.potency * 100} decimals={2} unit="%" /> : <span className="num muted">not yet</span>}</dd></div>
        <div className={bound ? "bound" : ""}><dt>Worst-case bound, not an estimate</dt><dd>{bound ? <><Num value={d.worst_case.potency * 100} decimals={1} unit="%" /><small className="num"> / used {(d.worst_case.shelf_life_used_fraction * 100).toFixed(0)}%</small></> : <span className="num muted">not in use</span>}</dd></div>
      </dl>
      <p className="note">Reported: from the signed sensor feed. Recomputed: the backend's own calculation from the same readings.</p>
    </section>
  );
}

// ---------------------------------------------------------------- chain

export function ChainPanel({ replay, tS, live }: { replay: ReplayFile; tS: number; live: boolean }) {
  const tamper = useCr((s) => s.tamper);
  const pick = useCr((s) => s.tamperPick);
  const pickTamper = useCr((s) => s.pickTamper);
  const applyTamper = useCr((s) => s.applyTamper);
  const clearTamper = useCr((s) => s.clearTamper);
  const lastUse = useCr((s) => s.lastUseMs);
  const options = useMemo(() => tamperOptions(replay.tamper), [replay]);
  const outcome = tamper ? tamperOutcome(replay.tamper, tamper) : null;
  const n = replay.tamper.ledger_length;
  const tokens = outcome ? outcome.tokens : intactTokens(n, Math.round(journeyProgress(replay, tS) * (n - 1)));
  const availability: Availability = live
    ? { enabled: false, reason: "Tamper is not available in live mode: it shows recorded results, and live mode reads the backend read-only." }
    : lastUse !== null && performance.now() - lastUse < 0
      ? { enabled: false, reason: "Cooling down." }
      : { enabled: true, reason: null };
  return (
    <section className={`panel ${outcome ? "has-result" : ""}`} aria-labelledby="h-chain">
      <h2 id="h-chain" className="eyebrow">Signed record chain <small className="num">{n} entries, key {replay.provenance.signing_key_id}</small></h2>
      <div className="ribbon" role="img" aria-label={outcome ? `Chain after an edit to a copy: first broken entry ${outcome.firstBroken ?? "none"}` : "Chain of signed records, all verified"}>
        {tokens.map((t) => (
          <span key={t.index} className={`tok ${t.status}`} title={`entry ${t.index}`}>
            {t.status === "verified" ? "✓" : t.status === "broken" ? "!" : t.status === "removed" ? "–" : "·"}
          </span>
        ))}
      </div>
      <div className="entry-labels num small"><span>entry {tokens[0]?.index}</span><span>entry {tokens[tokens.length - 1]?.index}</span></div>
      <div className="results" role="status" aria-live="polite">
        {outcome ? (
          <>
            <p className="tag">{outcome.label}</p>
            {outcome.lines.map((l, i) => <p key={i} className={i === 0 ? "" : "bad"}>{l}</p>)}
          </>
        ) : (
          <p><Icon kind="ok" /> Original ledger: {replay.chain.result}.</p>
        )}
      </div>
      <div className="tamper-row">
        <label>
          <span className="sr-only">Which edit to show</span>
          <select value={pick || options[0].key} onChange={(e) => pickTamper(e.target.value)} disabled={live} aria-label="Which recorded edit to show">
            {options.map((o) => <option key={o.key} value={o.key}>{o.label}</option>)}
          </select>
        </label>
        <GuardedButton ariaLabel="Tamper with a copy of the ledger (hold to arm)" availability={availability} onFire={() => applyTamper(replay)} className="tamper">Hold to tamper with a copy</GuardedButton>
        {tamper && <button type="button" className="btn small-btn" onClick={clearTamper}>Restore the view</button>}
      </div>
      <p className="note">Edits a COPY of the ledger and shows the recorded result of a real verification (not done in the browser). The original is never changed. Signing protects records after signing. It does not stop a false sensor value.</p>
    </section>
  );
}

// ---------------------------------------------------------------- planner and approval

export function PlannerPanel({ replay, tS }: { replay: ReplayFile; tS: number }) {
  const d = replay.decision;
  const human = useCr((s) => s.human);
  const decide = useCr((s) => s.decide);
  const [overriding, setOverriding] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [action, setAction] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const reached = decisionReached(replay, tS);
  const open = canDecide(replay, tS, human);
  const maxV = Math.max(...d.actions.flatMap((a) => [a.expected_loss, a.cvar]));
  const lowestExpected = d.actions.reduce((m, a) => (a.expected_loss < m.expected_loss ? a : m)).name;
  const others = d.actions.filter((a) => a.name !== d.chosen_action);
  const frame = replay.frames[frameIndexAt(replay.frames, tS)];

  useEffect(() => {
    setOverriding(false);
    setRejecting(false);
    setError(null);
    setReason("");
  }, [replay.meta.scenario_id]);

  const submit = (kind: "override" | "reject") => {
    const err = decide(replay, kind === "override" ? { kind, action: action || others[0].name, reason } : { kind, reason });
    setError(err);
    if (!err) {
      setOverriding(false);
      setRejecting(false);
    }
  };

  return (
    <section className="panel planner" aria-labelledby="h-plan">
      <h2 id="h-plan" className="eyebrow">Planner: expected loss and worst-5% loss <small>{d.n_scenarios.toLocaleString("en-US")} scenarios, alpha {d.alpha}</small></h2>
      {!reached ? (
        <p className="muted pending">The planner decides at {replay.meta.checkpoint_h} h of this recording. Waiting for the simulated clock.</p>
      ) : (
        <div className="plan-grid">
          <table className="atable">
            <thead><tr><th>Action</th><th>Loss (bars)</th><th className="r">expected</th><th className="r">worst 5%</th></tr></thead>
            <tbody>
              {d.actions.map((a) => (
                <tr key={a.name} className={a.name === d.chosen_action ? "pick" : ""}>
                  <td>{a.name === d.chosen_action ? "✓ " : a.name === lowestExpected ? "◆ " : ""}{actionLabel(a.name)}</td>
                  <td className="barcell"><i className="b1" style={{ width: `${(a.expected_loss / maxV) * 100}%` }} /><i className="b2" style={{ width: `${(a.cvar / maxV) * 100}%` }} /></td>
                  <td className="num r">{fmt(a.expected_loss)}</td>
                  <td className="num r">{fmt(a.cvar)}</td>
                </tr>
              ))}
            </tbody>
            <caption className="legend">✓ recommended · ◆ lowest expected · bars: <span className="k1">expected</span>, <span className="k2">worst 5%</span></caption>
          </table>
          <div className="why">
            <h3>Why this {d.needs_human ? "needs a person" : "can be auto-approved"}</h3>
            <ul>
              {d.reasons.slice(0, 1).map((r, i) => <li key={i}>{r}</li>)}
              {d.reasons.length > 1 && <li className="muted">+ {d.reasons.length - 1} more in the decision record</li>}
            </ul>
            {d.close_call && <p className="callout"><Icon kind="warn" /> Close call flagged: the leading actions are almost tied.</p>}
            {frame.trust_level !== "trusted" && <p className="callout"><Icon kind="alert" /> Data not trusted: the plan starts from the worst-case bound, not an estimate.</p>}
          </div>
          <div className="decide">
            <p className="rec">Recommended: <b>{actionLabel(d.chosen_action)}</b></p>
            {human ? (
              <p className="done" role="status"><Icon kind="person" /> {statusChip(replay, tS, human).text}. Event dispatched (demo adapter).</p>
            ) : d.needs_human ? (
              <>
                <p className="chip warn"><Icon kind="person" /> A person must decide</p>
                {!overriding && !rejecting ? (
                  <div className="btns">
                    <button type="button" className="btn" onClick={() => decide(replay, { kind: "approve" })} disabled={!open} aria-keyshortcuts="A">Approve</button>
                    <button type="button" className="btn" onClick={() => { setOverriding(true); setAction(others[0].name); }} disabled={!open}>Override</button>
                    <button type="button" className="btn" onClick={() => setRejecting(true)} disabled={!open}>Reject</button>
                  </div>
                ) : (
                  <form className="override" onSubmit={(e) => { e.preventDefault(); submit(overriding ? "override" : "reject"); }}>
                    {overriding && (
                      <label>Choose another action
                        <select value={action} onChange={(e) => setAction(e.target.value)}>
                          {others.map((a) => <option key={a.name} value={a.name}>{actionLabel(a.name)}</option>)}
                        </select>
                      </label>
                    )}
                    <label>Reason (at least 10 characters)
                      <textarea rows={2} value={reason} onChange={(e) => setReason(e.target.value)} aria-invalid={error !== null} />
                    </label>
                    {error && <p className="err" role="alert">{error}</p>}
                    <div className="btns">
                      <button type="submit" className="btn">{overriding ? "Record the override" : "Record the rejection"}</button>
                      <button type="button" className="btn" onClick={() => { setOverriding(false); setRejecting(false); setError(null); }}>Cancel</button>
                    </div>
                  </form>
                )}
              </>
            ) : (
              <p className="chip ok"><Icon kind="ok" /> Auto-approved within thresholds</p>
            )}
            <p className="note">Demo actions change this screen only. Nothing leaves the browser.</p>
          </div>
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------- event log

export function EventLog({ replay, tS }: { replay: ReplayFile; tS: number }) {
  const user = useCr((s) => s.userLog);
  const lines = useMemo(() => mergeLog(systemLog(replay, tS), user), [replay, tS, user]);
  const end = useRef<HTMLLIElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView({ block: "nearest" });
  }, [lines.length]);
  return (
    <section className="panel log" aria-labelledby="h-log">
      <h2 id="h-log" className="eyebrow">Event log</h2>
      <ol role="log" aria-live="polite" aria-label="Event log, newest last">
        {lines.map((l) => (
          <li key={l.key}><span className="num t">{l.wall ? `${l.wall} ` : ""}T+{(l.tS / 3600).toFixed(1)} h</span> {l.text}</li>
        ))}
        <li ref={end} aria-hidden="true" />
      </ol>
    </section>
  );
}

// ---------------------------------------------------------------- provenance

export function ProvenanceDrawer({ replay, mode }: { replay: ReplayFile; mode: string }) {
  const open = useCr((s) => s.provenanceOpen);
  const set = useCr((s) => s.setProvenance);
  const ref = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (open) ref.current?.focus();
  }, [open]);
  if (!open) return null;
  const pv = replay.provenance;
  const ref2 = (story as unknown as StoryData).profiles.reference;
  const rows: [string, string][] = [
    ["Source", `${pv.source} (Sensor feed, synthetic)`],
    ["Scenario id", pv.scenario_id],
    ["Recording seed", String(pv.recording_seed)],
    ["Planner seed", String(pv.planner_seed)],
    ["Enterprise adapter", `${pv.sap_adapter_mode} (Enterprise system, simulated)`],
    ["Software", `${pv.software_version}; dashboard Phase F4`],
    ["Signing key id", pv.signing_key_id],
    ["Profile in use", `active illustrative profile (Ea/R ${replay.meta.product.Ea_over_R}, reference ${replay.meta.product.T_ref_c} °C, shelf life ${replay.meta.product.tau_max_h} h at reference)`],
    ["Reference-profile figures", `journey A ${ref2.journeys.A.shelf_life_used_percent.toFixed(2)}% and journey B ${ref2.journeys.B.shelf_life_used_percent.toFixed(2)}% of shelf life used (model output)`],
    ["Data", pv.from_replay ? `a replay of a recording${mode === "live" ? " (live mode reads the backend status only)" : ""}` : "live"],
  ];
  return (
    <aside className="drawer" role="dialog" aria-label="Provenance" aria-modal="false">
      <h2>Where this comes from</h2>
      <dl>
        {rows.map(([k, v]) => (
          <div key={k}><dt>{k}</dt><dd>{v}</dd></div>
        ))}
      </dl>
      <p className="note">Signing protects records after signing. It does not stop a false sensor value.</p>
      <button type="button" className="btn" ref={ref} onClick={() => set(false)}>Close</button>
    </aside>
  );
}
