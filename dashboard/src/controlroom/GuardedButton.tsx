// A guarded switch: a flip-up cover, hold to arm (about 600 ms with a progress ring), a keyboard
// path (hold Enter or Space), and a visible reason whenever it is disabled. The timing rules are
// the pure functions in logic.ts.
import { useCallback, useRef, type ReactNode } from "react";
import { useScrollTicker } from "../scroll/scrollState";
import { HOLD_MS, holdProgress, isArmed, type Availability } from "./logic";

const R = 9;
const C = 2 * Math.PI * R;

export function GuardedButton({
  children,
  onFire,
  availability,
  active = false,
  className = "",
  ariaLabel,
}: {
  children: ReactNode;
  onFire: () => void;
  availability: Availability;
  active?: boolean;
  className?: string;
  ariaLabel: string;
}) {
  const start = useRef<number | null>(null);
  const ring = useRef<SVGCircleElement>(null);
  const shell = useRef<HTMLSpanElement>(null);

  const paint = useCallback(() => {
    if (start.current === null) return;
    const now = performance.now();
    const p = holdProgress(start.current, now);
    ring.current?.setAttribute("stroke-dashoffset", String(C * (1 - p)));
    if (isArmed(start.current, now)) {
      cancel();
      onFire();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onFire]);
  useScrollTicker(paint);

  function cancel() {
    start.current = null;
    ring.current?.setAttribute("stroke-dashoffset", String(C));
    shell.current?.removeAttribute("data-holding");
  }
  function begin() {
    if (!availability.enabled || start.current !== null) return;
    start.current = performance.now();
    shell.current?.setAttribute("data-holding", "true");
  }

  const described = availability.reason ?? `Hold for ${(HOLD_MS / 1000).toFixed(1)} seconds to arm.`;
  return (
    <span className={`guard ${className}`} ref={shell} data-active={active || undefined}>
      <span className="cover" aria-hidden="true" />
      <button
        type="button"
        className="gbtn"
        aria-label={ariaLabel}
        aria-disabled={!availability.enabled}
        aria-pressed={active}
        title={described}
        onPointerDown={(e) => {
          e.currentTarget.setPointerCapture?.(e.pointerId);
          begin();
        }}
        onPointerUp={cancel}
        onPointerCancel={cancel}
        onPointerLeave={cancel}
        onKeyDown={(e) => {
          if ((e.key === "Enter" || e.key === " ") && !e.repeat) {
            e.preventDefault();
            begin();
          }
        }}
        onKeyUp={(e) => {
          if (e.key === "Enter" || e.key === " ") cancel();
        }}
        onBlur={cancel}
      >
        <svg className="ring" viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="12" r={R} fill="none" stroke="var(--line-strong)" strokeWidth="2" />
          <circle ref={ring} cx="12" cy="12" r={R} fill="none" stroke="var(--ice-300)" strokeWidth="2.5" strokeDasharray={C} strokeDashoffset={C} transform="rotate(-90 12 12)" />
        </svg>
        <span>{children}</span>
      </button>
      {!availability.enabled && availability.reason && <span className="why-off">{availability.reason}</span>}
    </span>
  );
}
