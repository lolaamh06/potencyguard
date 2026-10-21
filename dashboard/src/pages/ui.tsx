// Small shared building blocks of the pages: icons, status chips, the "?" help popover, the modal
// dialog, and a term label that follows the Simple/Technical switch.
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { useUi } from "../app/ui";
import { explain, hiddenIn, term, type TermId } from "../copy/glossary";
import { STATUS_ICON, STATUS_WORDS, type StatusKind } from "../copy/headline";

export type IconKind = "ok" | "warn" | "alert" | "person";

export function Icon({ kind }: { kind: IconKind }) {
  const common = { width: 16, height: 16, viewBox: "0 0 16 16", "aria-hidden": true, className: "ic" } as const;
  if (kind === "ok") return <svg {...common}><path d="M3 8.5l3 3 7-7" fill="none" stroke="currentColor" strokeWidth="2" /></svg>;
  if (kind === "warn") return <svg {...common}><path d="M8 2l7 12H1z" fill="none" stroke="currentColor" strokeWidth="1.6" /><path d="M8 6.5v3.5M8 11.7v.8" stroke="currentColor" strokeWidth="1.6" /></svg>;
  if (kind === "alert") return <svg {...common}><circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" strokeWidth="1.6" /><path d="M8 4.5v4.5M8 10.8v.8" stroke="currentColor" strokeWidth="1.6" /></svg>;
  return <svg {...common}><circle cx="8" cy="5.5" r="2.6" fill="none" stroke="currentColor" strokeWidth="1.6" /><path d="M2.5 14c.6-3 2.8-4.4 5.5-4.4s4.9 1.4 5.5 4.4" fill="none" stroke="currentColor" strokeWidth="1.6" /></svg>;
}

const TONE: Record<StatusKind, string> = { good: "good", needs_person: "person", not_trusted: "bad", problem: "warn" };

/** A status in colour, icon and word together (never colour alone). */
export function StatusChip({ kind, text }: { kind: StatusKind; text?: string }) {
  return (
    <span className={`status ${TONE[kind]}`}>
      <Icon kind={STATUS_ICON[kind]} />
      {text ?? STATUS_WORDS[kind]}
    </span>
  );
}

export function Chip({ icon, tone, children }: { icon: IconKind; tone: "good" | "warn" | "bad" | "person" | "plain"; children: ReactNode }) {
  return (
    <span className={`status ${tone}`}>
      <Icon kind={icon} />
      {children}
    </span>
  );
}

/** A small "?" button with a keyboard-accessible popover that explains a term in one sentence. */
export function HelpTip({ id }: { id: TermId }) {
  const mode = useUi((s) => s.mode);
  const [open, setOpen] = useState(false);
  const uid = useId();
  const root = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    const away = (e: MouseEvent) => root.current && !root.current.contains(e.target as Node) && setOpen(false);
    window.addEventListener("keydown", close);
    window.addEventListener("mousedown", away);
    return () => {
      window.removeEventListener("keydown", close);
      window.removeEventListener("mousedown", away);
    };
  }, [open]);
  return (
    <span className="tip" ref={root}>
      <button type="button" className="tip-btn" aria-expanded={open} aria-controls={uid} aria-label={`What does “${term(id, mode)}” mean?`} onClick={() => setOpen((o) => !o)}>
        ?
      </button>
      {open && (
        <span id={uid} role="tooltip" className="tip-pop">
          {explain(id, mode)}
        </span>
      )}
    </span>
  );
}

/** A term's label in the current reading mode, with its "?" help. Renders nothing for a term hidden in Simple mode. */
export function Term({ id, help = true }: { id: TermId; help?: boolean }) {
  const mode = useUi((s) => s.mode);
  if (hiddenIn(id, mode)) return null;
  return (
    <span className="term">
      {term(id, mode)}
      {help && <HelpTip id={id} />}
    </span>
  );
}

/** A modal dialog: focus moves in, Esc and the backdrop close it. */
export function Modal({ title, children, onClose, wide = false }: { title: string; children: ReactNode; onClose: () => void; wide?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const titleId = useId();
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const first = ref.current?.querySelector<HTMLElement>("input, select, textarea, button");
    first?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "Tab" && ref.current) {
        const items = [...ref.current.querySelectorAll<HTMLElement>("button, input, select, textarea, a[href], summary")].filter((x) => !x.hasAttribute("disabled"));
        if (items.length === 0) return;
        const firstEl = items[0];
        const lastEl = items[items.length - 1];
        if (e.shiftKey && document.activeElement === firstEl) {
          e.preventDefault();
          lastEl.focus();
        } else if (!e.shiftKey && document.activeElement === lastEl) {
          e.preventDefault();
          firstEl.focus();
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      previous?.focus?.();
    };
  }, [onClose]);
  return (
    <div className="modal-back" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal ${wide ? "wide" : ""}`} role="dialog" aria-modal="true" aria-labelledby={titleId} ref={ref}>
        <h2 id={titleId}>{title}</h2>
        {children}
      </div>
    </div>
  );
}

export const fmtInt = (n: number): string => Math.round(n).toLocaleString("en-US");
