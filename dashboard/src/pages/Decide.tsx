// The three decision buttons and their confirm dialogs, used on the Shipment page and the Decisions
// page. Every action says what will happen ("This changes this screen only") before it does it, and
// reuses the tested rules: a reason of at least 10 characters, a different action for an override.
import { useState } from "react";
import { useUi } from "../app/ui";
import { actionLabel } from "../copy/glossary";
import { MIN_REASON, canDecide, decisionReached, type HumanOutcome } from "../controlroom/logic";
import { useCr } from "../controlroom/store";
import type { ReplayFile } from "../data/types";
import { Modal } from "./ui";

type Kind = "approve" | "override" | "reject";

export function DecisionActions({ replay, ignoreClock = false, tourId }: { replay: ReplayFile; ignoreClock?: boolean; tourId?: string }) {
  const mode = useUi((s) => s.mode);
  const decide = useCr((s) => s.decide);
  const tS = useCr((s) => s.tS);
  const outcome = useCr((s) => s.outcomes[replay.meta.scenario_id as keyof ReturnType<typeof useCr.getState>["outcomes"]] ?? null);
  const [kind, setKind] = useState<Kind | null>(null);
  const [action, setAction] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const d = replay.decision;
  const others = d.actions.filter((a) => a.name !== d.chosen_action);
  const when = ignoreClock ? replay.meta.checkpoint_h * 3600 : tS;
  const open = canDecide(replay, when, outcome);

  if (!d.needs_human) return <p className="calm"><strong>No decision needed.</strong> This was approved automatically within the safety limits.</p>;
  if (outcome) return <p className="calm" role="status"><strong>{label(outcome, mode)}</strong> This changed this screen only. Nothing was sent anywhere.</p>;
  if (!ignoreClock && !decisionReached(replay, tS)) return <p className="muted">The decision opens at about {Math.round(replay.meta.checkpoint_h)} hours into the journey. Press Play to get there.</p>;

  const close = () => {
    setKind(null);
    setError(null);
    setReason("");
  };
  const confirm = () => {
    const out: HumanOutcome = kind === "approve" ? { kind: "approve" } : kind === "override" ? { kind: "override", action: action || others[0].name, reason } : { kind: "reject", reason };
    const err = decide(replay, out, { ignoreClock });
    if (err) setError(err);
    else close();
  };

  return (
    <>
      <div className="btn-row" data-tour={tourId}>
        <button type="button" className="btn primary" disabled={!open} onClick={() => setKind("approve")}>Approve</button>
        <button type="button" className="btn" disabled={!open} onClick={() => { setKind("override"); setAction(others[0].name); }}>Choose a different action</button>
        <button type="button" className="btn danger" disabled={!open} onClick={() => setKind("reject")}>Reject</button>
      </div>
      {kind && (
        <Modal title={kind === "approve" ? "Approve this recommendation?" : kind === "override" ? "Choose a different action" : "Reject this recommendation?"} onClose={close}>
          <p>
            {kind === "approve" && `You are approving: ${actionLabel(d.chosen_action, mode)}.`}
            {kind === "override" && "Pick the action you prefer and say why."}
            {kind === "reject" && "You are turning the recommendation down. Say why."}
          </p>
          {kind === "override" && (
            <label className="field">
              <span>Which action?</span>
              <select value={action || others[0].name} onChange={(e) => setAction(e.target.value)}>
                {others.map((a) => <option key={a.name} value={a.name}>{actionLabel(a.name, mode)}</option>)}
              </select>
            </label>
          )}
          {kind !== "approve" && (
            <label className="field">
              <span>Reason (at least {MIN_REASON} characters)</span>
              <textarea rows={3} value={reason} onChange={(e) => setReason(e.target.value)} aria-invalid={error !== null} />
            </label>
          )}
          {error && <p className="error" role="alert">{error}</p>}
          <p className="note">This changes this screen only. Nothing is sent anywhere.</p>
          <div className="modal-actions">
            <button type="button" className={`btn ${kind === "reject" ? "danger" : "primary"}`} onClick={confirm}>
              {kind === "approve" ? "Yes, approve" : kind === "override" ? "Yes, use this action" : "Yes, reject"}
            </button>
            <button type="button" className="btn" onClick={close}>Cancel</button>
          </div>
        </Modal>
      )}
    </>
  );
}

function label(o: HumanOutcome, mode: "simple" | "technical"): string {
  if (o.kind === "approve") return "A person approved this recommendation.";
  if (o.kind === "override") return `A person chose a different action: ${actionLabel(o.action, mode)}.`;
  return "A person rejected this recommendation.";
}
