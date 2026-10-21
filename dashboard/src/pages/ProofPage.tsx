// Proof: what signed records are, the recorded result of checking them, what happens when a record
// is changed (a real edit on a copy, recorded), the missing-records case, and the honest limit.
import { useMemo, useState } from "react";
import { useUi } from "../app/ui";
import { intactTokens, tamperOutcome, type TamperChoice } from "../controlroom/logic";
import { term } from "../copy/glossary";
import { SCENARIO_COPY } from "../copy/scenarios";
import { SCENARIO_IDS } from "../controlroom/logic";
import type { AdapterSnapshot } from "../data/types";
import { PageShell } from "./PageShell";
import { Ribbon } from "./Ribbon";
import { HelpTip } from "./ui";

export function ProofPage({ data }: { data: AdapterSnapshot }) {
  const mode = useUi((s) => s.mode);
  const available = SCENARIO_IDS.filter((id) => data.scenarios[id]);
  const [id, setId] = useState<(typeof SCENARIO_IDS)[number]>("hidden_spoilage");
  const [checked, setChecked] = useState(false);
  const [trying, setTrying] = useState(false);
  const [pick, setPick] = useState<"early" | "middle" | "late" | null>(null);
  const replay = data.scenarios[id] ?? data.scenarios[available[0]];
  const edits = replay?.tamper.edits ?? [];
  const chosen = replay && pick ? edits[pick === "early" ? 0 : pick === "middle" ? Math.floor(edits.length / 2) : edits.length - 1] : null;
  const outcome = useMemo(() => (replay && chosen ? tamperOutcome(replay.tamper, { kind: "edit", entry: chosen.entry } as TamperChoice) : null), [replay, chosen]);

  return (
    <PageShell route={{ page: "proof" }}>
      {!replay ? (
        <p role="status" className="muted">{data.status.state === "loading" ? "Loading…" : "No records are available to check."}</p>
      ) : (
        <>
          <section className="card" aria-labelledby="h-what">
            <h2 id="h-what">What are signed records?</h2>
            <p>Every temperature reading is saved together with a digital stamp, called a <span className="term">signed record<HelpTip id="signedRecord" /></span>. Each record is also linked to the one before it, like links in a <span className="term">chain<HelpTip id="chain" /></span>, so changing any record breaks every link after it.</p>
            <label className="field inline">
              <span>Sample shipment</span>
              <select value={id} onChange={(e) => { setId(e.target.value as typeof id); setChecked(false); setTrying(false); setPick(null); }}>
                {available.map((s) => <option key={s} value={s}>{SCENARIO_COPY[s].title}</option>)}
              </select>
            </label>
          </section>

          <section className="card" aria-labelledby="h-check" data-tour="tour-proof">
            <h2 id="h-check">1. Check the records</h2>
            <button type="button" className="btn primary" onClick={() => setChecked(true)}>Check the records</button>
            {checked && (
              <div role="status" className="result good">
                <Ribbon tokens={intactTokens(replay.tamper.ledger_length, Math.floor(replay.tamper.ledger_length / 2))} label="Records, all verified" />
                <p><strong>{replay.chain.ok ? `All ${replay.chain.entries_total} records check out.` : "The check found a problem."}</strong> {replay.chain.ok ? "None has been changed since it was signed." : replay.chain.result}</p>
                <p className="note">This is the recorded result of checking this shipment's records. {mode === "technical" ? replay.chain.result + "." : ""}</p>
              </div>
            )}
          </section>

          <section className="card" aria-labelledby="h-try">
            <h2 id="h-try">2. Try to change a record</h2>
            <p>We made a real change to a <em>copy</em> of the records and checked them again. The original is never touched. Press the button, then pick when in the journey the change happens.</p>
            <button type="button" className="btn" aria-expanded={trying} onClick={() => setTrying((t) => !t)}>Try to change a record</button>
            {trying && (
              <>
                <div className="btn-row" role="group" aria-label="When the change happens">
                  {(["early", "middle", "late"] as const).map((p) => (
                    <button key={p} type="button" className="btn seg-btn" aria-pressed={pick === p} onClick={() => setPick(p)}>
                      {p === "early" ? "Early" : p === "middle" ? "Middle" : "Late"}
                    </button>
                  ))}
                </div>
                {chosen && outcome && (
                  <div role="status" className="result bad">
                    <Ribbon tokens={outcome.tokens} label={`Records after a change to record ${chosen.entry}: the check fails at record ${chosen.first_broken_index}`} />
                    <p><strong>Record {chosen.entry} was changed, so the check fails at record {chosen.first_broken_index}.</strong> Every record after it can no longer be trusted.</p>
                    <p className="note">{replay.tamper.label}. {mode === "technical" ? chosen.text + "." : ""}</p>
                  </div>
                )}
              </>
            )}
          </section>

          <section className="card" aria-labelledby="h-trunc">
            <h2 id="h-trunc">3. What if records are deleted from the end?</h2>
            <p>We also deleted the last {replay.tamper.truncation.removed} records from a copy.</p>
            <ul className="why">
              <li><strong>Without the <span className="term">end-marker<HelpTip id="anchor" /></span>:</strong> {replay.tamper.truncation.without_anchor.ok ? "the check still passes, because it cannot tell that records are missing." : "the check fails."}</li>
              <li><strong>With the end-marker:</strong> {replay.tamper.truncation.with_anchor.ok ? "the check passes." : "the check fails, because the end-marker says there should be more records."}</li>
            </ul>
          </section>

          <section className="card limit" aria-labelledby="h-limit">
            <h2 id="h-limit">The honest limit</h2>
            <p><strong>Signing protects records after they are signed. It does not stop a wrong sensor reading from being signed.</strong></p>
            <p>That is why the system also checks the readings against the laws of physics. {term("trust", mode)} answers that second question.</p>
          </section>
        </>
      )}
    </PageShell>
  );
}
