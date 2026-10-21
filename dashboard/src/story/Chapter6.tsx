// Chapter 6: "A human decides." The approval card carries content exported from the real backend
// for one needs-a-person case; the Approve press here is an illustration (nothing is sent). The
// chain ribbon shows the real result of editing a COPY of a ledger and verifying it again: the
// edited link breaks and the links after it are dimmed.
import { useCallback, useState } from "react";
import { useAppStore } from "../app/appStore";
import type { Chapter6Data } from "../data/story";
import type { ReplayFile } from "../data/types";
import { Missing, MODEL_LABEL, Scene, span, useChapterTick } from "./common";

const NAMES: Record<string, string> = { continue: "Continue", expedite: "Expedite", reroute_to_depot: "Reroute to depot", re_source: "Re-source", quarantine: "Quarantine" };
const fmt = (n: number) => Math.round(n).toLocaleString("en-US");

function Sparkline({ points }: { points: [number, number][] }) {
  const w = 200;
  const h = 46;
  const maxT = points[points.length - 1]?.[0] || 1;
  const d = points.map(([t, p], i) => `${i ? "L" : "M"}${((t / maxT) * w).toFixed(1)} ${((1 - p) * (h - 6) * 40 + 3).toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" role="img" aria-label="Reported potency over the journey so far">
      <path d={d} stroke="var(--ice-400)" strokeWidth="2" fill="none" />
    </svg>
  );
}

function Residual({ data }: { data: ReplayFile }) {
  const frames = data.frames.filter((f) => f.t_s <= data.meta.checkpoint_h * 3600);
  const max = Math.max(1, ...frames.map((f) => Math.abs(f.residual_c ?? 0)));
  const w = 200;
  const h = 46;
  const d = frames.map((f, i) => `${i ? "L" : "M"}${((f.t_s / (data.meta.checkpoint_h * 3600)) * w).toFixed(1)} ${(h / 2 - ((f.residual_c ?? 0) / max) * (h / 2 - 3)).toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" role="img" aria-label="Residual between the reported and the predicted temperature">
      <line x1="0" x2={w} y1={h / 2} y2={h / 2} stroke="var(--line-strong)" strokeDasharray="3 4" />
      <path d={d} stroke="var(--danger-text)" strokeWidth="1.8" fill="none" />
    </svg>
  );
}

export function Chapter6({ data, hidden }: { data: Chapter6Data | null; hidden: ReplayFile | null }) {
  const reduced = useAppStore((s) => s.reducedMotion);
  const [approved, setApproved] = useState(false);
  const [edited, setEdited] = useState(false);

  const paint = useCallback(
    (t: number) => {
      for (const [id, from] of [["c6-l1", 0.05], ["c6-l2", 0.45]] as const) {
        const n = document.getElementById(id);
        if (n) n.style.opacity = String(reduced ? 1 : span(t, from, from + 0.15));
      }
    },
    [reduced],
  );
  useChapterTick(6, paint);

  return (
    <Scene index={6}>
      <div className="copy">
        <h2>A human decides</h2>
        <p id="c6-l1">The system recommends. A qualified person decides.</p>
        <p id="c6-l2">Every decision is sealed into a record where any later change is detected.</p>
        {data && <p className="caption">{data.limit}</p>}
      </div>
      <div className="figure">
        {!data ? (
          <Missing what="The approval card" />
        ) : (
          <>
            <div className="card" aria-label="Approval card for a recorded simulated case">
              <div className="card-head">
                <strong>Recommendation: {NAMES[data.card.chosen_action] ?? data.card.chosen_action}</strong>
                <span className="chip warn">A person must decide</span>
              </div>
              <div className="card-grid">
                <div><span className="k">Reported potency</span><Sparkline points={data.card.potency_curve} /></div>
                <div><span className="k">Residual (reported minus predicted)</span>{hidden ? <Residual data={hidden} /> : <p className="quiet">not loaded</p>}</div>
              </div>
              <p className="k">Trust: <strong>{data.card.trust_level}</strong>. Verdict: <strong>{data.card.verdict.replace(/_/g, " ")}</strong>. Chain on the original ledger: {data.card.chain_status}.</p>
              <table className="alts">
                <thead><tr><th>Alternative</th><th>expected</th><th>worst 5%</th></tr></thead>
                <tbody>
                  {data.card.alternatives.map((a) => (
                    <tr key={a.action} className={a.action === data.card.chosen_action ? "pick" : ""}>
                      <td>{NAMES[a.action] ?? a.action}</td><td className="num">{fmt(a.expected_loss)}</td><td className="num">{fmt(a.cvar)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="why">{data.card.reason.split("; ")[0]}.</p>
              <div className="card-actions">
                <button type="button" className="btn" onClick={() => setApproved(true)} disabled={approved}>{approved ? "Approved (illustration)" : "Approve (illustration)"}</button>
                <span className="quiet">Nothing is sent: this is a demonstration press.</span>
              </div>
            </div>
            <div className="ribbon" role="img" aria-label={`Chain of signed records. ${edited ? "A copy was edited; the edited record breaks and the later ones are not verified." : "All shown records verified."}`}>
              {data.chain.ribbon.map((tok) => {
                const status = edited ? tok.status : "verified";
                return (
                  <span key={tok.index} className={`tok ${status}`} title={`entry ${tok.index}`}>
                    {status === "broken" ? "!" : status === "verified" ? "✓" : "·"}
                  </span>
                );
              })}
              {approved && <span className="seal" aria-label="Decision sealed">SEALED</span>}
            </div>
            <div className="ribbon-row">
              <button type="button" className="btn" onClick={() => setEdited((e) => !e)} aria-pressed={edited}>{edited ? "Restore the view" : "Edit a copy of the ledger and verify it again"}</button>
              <span className="quiet" role="status">{edited ? `${data.chain.tampered_result}. ${data.chain.tamper}.` : `Original ledger: ${data.chain.intact_result}.`}</span>
            </div>
            <p className="label-model">{MODEL_LABEL}. Recorded scenario {data.scenario_id} (simulated), checkpoint {data.checkpoint_h} h. The edit is made to a copy; the original is never changed.</p>
          </>
        )}
      </div>
    </Scene>
  );
}
