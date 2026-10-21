// Chapter 3: "Too late to matter." A timeline of a recorded simulated journey. A clock hand sweeps
// along it; the decision marker sits at the end; the early dot is where the physics checks first fired.
import { useCallback, useRef, useState } from "react";
import { useAppStore } from "../app/appStore";
import type { ReplayFile } from "../data/types";
import { Missing, Scene, span, useChapterTick } from "./common";

const W = 760;
const H = 220;
const L = 40;
const R = 40;

export function Chapter3({ data }: { data: ReplayFile | null }) {
  const hand = useRef<SVGGElement>(null);
  const [open, setOpen] = useState(false);
  const reduced = useAppStore((s) => s.reducedMotion);
  const duration = data?.meta.duration_h ?? 36;
  const x = (h: number) => L + (h / duration) * (W - L - R);
  const early = data?.events.find((e) => e.type === "physics_check_fired");
  const earlyH = early ? early.t_s / 3600 : null;

  const paint = useCallback(
    (t: number) => {
      const p = reduced ? 1 : span(t, 0.1, 0.85);
      if (hand.current) hand.current.setAttribute("transform", `translate(${x(p * duration)} 0)`);
      for (const [id, from] of [["c3-l1", 0.05], ["c3-l2", 0.35]] as const) {
        const n = document.getElementById(id);
        if (n) n.style.opacity = String(reduced ? 1 : span(t, from, from + 0.15));
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [reduced, duration],
  );
  useChapterTick(3, paint);

  return (
    <Scene index={3}>
      <div className="copy">
        <h2>Too late to matter</h2>
        <p id="c3-l1">By the time anyone decides, the journey is already over.</p>
        <p id="c3-l2">Every hour between the excursion and the decision is a rescue that never happened.</p>
        <p className="caption">An illustrative journey.</p>
      </div>
      <div className="figure">
        {!data ? (
          <Missing what="The recorded journey" />
        ) : (
          <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`A timeline of ${duration} hours. The physics checks first fired at ${earlyH?.toFixed(1)} hours; the decision comes at the end.`}>
            <line x1={L} x2={W - R} y1={110} y2={110} stroke="var(--line-strong)" strokeWidth="3" />
            {[0, 0.25, 0.5, 0.75, 1].map((f) => (
              <g key={f}>
                <line x1={x(f * duration)} x2={x(f * duration)} y1={104} y2={116} stroke="var(--line-strong)" />
                <text x={x(f * duration)} y={140} textAnchor="middle" fill="var(--mist-hi)" fontSize="12">{Math.round(f * duration)} h</text>
              </g>
            ))}
            {earlyH !== null && (
              <g
                tabIndex={0}
                role="button"
                aria-label="Where the physics checks first fired. Press for details."
                onMouseEnter={() => setOpen(true)}
                onMouseLeave={() => setOpen(false)}
                onFocus={() => setOpen(true)}
                onBlur={() => setOpen(false)}
                onClick={() => setOpen((o) => !o)}
                style={{ cursor: "pointer" }}
              >
                <circle cx={x(earlyH)} cy={110} r={18} fill="var(--danger-text)" opacity="0.18" />
                <circle cx={x(earlyH)} cy={110} r={8} fill="var(--danger-text)" />
                <text x={x(earlyH)} y={84} textAnchor="middle" fill="var(--danger-text)" fontSize="13">{earlyH.toFixed(1)} h</text>
              </g>
            )}
            <g>
              <line x1={x(duration)} x2={x(duration)} y1={70} y2={110} stroke="var(--frost)" />
              <rect x={x(duration) - 150} y={44} width="150" height="28" rx="6" fill="none" stroke="var(--frost)" />
              <text x={x(duration) - 75} y={63} textAnchor="middle" fill="var(--frost)" fontSize="13">decision at delivery</text>
            </g>
            <g ref={hand}>
              <line x1="0" x2="0" y1={96} y2={124} stroke="var(--ice-300)" strokeWidth="3" />
              <circle cx="0" cy={110} r="5" fill="var(--ice-300)" />
            </g>
            {open && earlyH !== null && (
              <g>
                <rect x={Math.max(10, x(earlyH) - 130)} y={150} width="260" height="52" rx="8" fill="var(--ink-800)" stroke="var(--line-strong)" />
                <text x={Math.max(10, x(earlyH) - 130) + 12} y={171} fill="var(--frost)" fontSize="13">Here the physics checks first fired.</text>
                <text x={Math.max(10, x(earlyH) - 130) + 12} y={190} fill="var(--mist-hi)" fontSize="12">A person could have been told here.</text>
              </g>
            )}
          </svg>
        )}
        <p className="label-model">Recorded scenario: {data?.meta.scenario_id ?? "reefer_failure"} (simulated).</p>
      </div>
    </Scene>
  );
}
