// Chapter 2: "Whose data is this?" The recorded spoof_attempt scenario: the reported line, the
// thermal twin's ghost line and the residual between them. Placing the shield on the sensor
// shows when the physics checks actually fired. The copy says only what those checks catch.
import { useCallback, useRef, useState } from "react";
import { useAppStore } from "../app/appStore";
import type { ReplayFile } from "../data/types";
import { Missing, MODEL_LABEL, Scene, span, useChapterTick } from "./common";

const W = 640;
const H = 330;
const PAD = { l: 44, r: 16, t: 16 };
const TOP_H = 170;
const RES_Y = 232;
const RES_H = 70;

export function Chapter2({ data }: { data: ReplayFile | null }) {
  const svg = useRef<SVGSVGElement>(null);
  const figure = useRef<HTMLDivElement>(null);
  const [shielded, setShielded] = useState(false);
  const [drag, setDrag] = useState<{ x: number; y: number } | null>(null);
  const reduced = useAppStore((s) => s.reducedMotion);

  const frames = data?.frames.filter((f) => f.t_s <= 24 * 3600) ?? [];
  const maxH = 24;
  const x = (h: number) => PAD.l + (h / maxH) * (W - PAD.l - PAD.r);
  const temps = frames.flatMap((f) => [f.temp_c, f.twin_c]).filter((v): v is number => v !== null);
  const lo = Math.min(...temps, 0) - 1;
  const hi = Math.max(...temps, 10) + 1;
  const y = (c: number) => PAD.t + (1 - (c - lo) / (hi - lo)) * TOP_H;
  const resMax = Math.max(1, ...frames.map((f) => Math.abs(f.residual_c ?? 0)));
  const ry = (r: number) => RES_Y + RES_H / 2 - (r / resMax) * (RES_H / 2);
  const line = (pick: (f: (typeof frames)[number]) => number | null, yy: (v: number) => number) =>
    frames.reduce((d, f, i) => {
      const v = pick(f);
      return v === null ? d : `${d}${i === 0 || d === "" ? "M" : "L"}${x(f.t_s / 3600).toFixed(1)} ${yy(v).toFixed(1)} `;
    }, "");

  const alert = data?.events.find((e) => e.type === "physics_check_fired");
  const alertH = alert ? alert.t_s / 3600 : null;
  const check = alert ? String((alert.payload as { check?: string }).check ?? "a physics check").replace(/_/g, " ") : null;

  const paint = useCallback(
    (t: number) => {
      const el = svg.current;
      if (!el) return;
      const draw = reduced ? 1 : span(t, 0.05, 0.55);
      el.querySelectorAll<SVGPathElement>("[data-draw]").forEach((p) => (p.style.strokeDashoffset = String(1 - draw)));
      const copy = (id: string, from: number) => {
        const n = document.getElementById(id);
        if (n) n.style.opacity = String(reduced ? 1 : span(t, from, from + 0.12));
      };
      copy("c2-l1", 0.02);
      copy("c2-l2", 0.3);
      copy("c2-l3", 0.6);
    },
    [reduced],
  );
  useChapterTick(2, paint);

  const place = (value: boolean) => setShielded(value);
  const onPointerMove = (e: React.PointerEvent) => {
    if (!drag || !figure.current) return;
    const r = figure.current.getBoundingClientRect();
    setDrag({ x: e.clientX - r.left, y: e.clientY - r.top });
  };
  const onPointerUp = (e: React.PointerEvent) => {
    if (!drag || !figure.current) return;
    const r = figure.current.getBoundingClientRect();
    const nearSensor = e.clientX - r.left < r.width * 0.45 && e.clientY - r.top < r.height * 0.7;
    setDrag(null);
    if (nearSensor) place(true);
  };

  return (
    <Scene index={2}>
      <div className="copy">
        <h2>Whose data is this?</h2>
        <p id="c2-l1">A logger can be shielded, swapped or replayed.</p>
        <p id="c2-l2">A signature shows a record has not changed since it was signed. It does not show the sensor told the truth.</p>
        <p id="c2-l3">But a box obeys physics. Data that does not, gets caught.</p>
        <p className="quiet">The physics checks catch readings that break physics. A feed that stays plausible is not caught by them.</p>
      </div>
      <div className="figure" ref={figure} onPointerMove={onPointerMove} onPointerUp={onPointerUp}>
        {!data ? (
          <Missing what="The recorded scenario" />
        ) : (
          <>
            <svg ref={svg} viewBox={`0 0 ${W} ${H}`} role="img" aria-label="The reported temperature, the physics twin's prediction and the residual between them, for a recorded simulated scenario">
              <line x1={PAD.l} x2={PAD.l} y1={PAD.t} y2={PAD.t + TOP_H} stroke="var(--line-strong)" />
              <line x1={PAD.l} x2={W - PAD.r} y1={PAD.t + TOP_H} y2={PAD.t + TOP_H} stroke="var(--line-strong)" />
              {[0, 6, 12, 18, 24].map((h) => (
                <text key={h} x={x(h)} y={RES_Y + RES_H + 22} textAnchor="middle" fill="var(--mist-hi)" fontSize="12">{h} h</text>
              ))}
              <text x={4} y={PAD.t + 10} fill="var(--mist-hi)" fontSize="12">°C</text>
              <path data-draw d={line((f) => f.twin_c, y)} stroke="var(--mist-hi)" strokeWidth="2" strokeDasharray="1" strokeDashoffset="1" pathLength={1} fill="none" opacity="0.8" />
              <path data-draw d={line((f) => f.temp_c, y)} stroke="var(--ice-400)" strokeWidth="3" strokeDasharray="1" strokeDashoffset="1" pathLength={1} fill="none" />
              <text x={W - PAD.r} y={PAD.t + 14} textAnchor="end" fill="var(--ice-400)" fontSize="12">reported by the sensor feed</text>
              <text x={W - PAD.r} y={PAD.t + 30} textAnchor="end" fill="var(--mist-hi)" fontSize="12">twin prediction (ghost line)</text>
              <line x1={PAD.l} x2={W - PAD.r} y1={ry(0)} y2={ry(0)} stroke="var(--line-strong)" strokeDasharray="3 4" />
              <text x={4} y={RES_Y + 10} fill="var(--mist-hi)" fontSize="12">residual</text>
              <path data-draw d={line((f) => f.residual_c, ry)} stroke="var(--danger-text)" strokeWidth="2" strokeDasharray="1" strokeDashoffset="1" pathLength={1} fill="none" />
              {shielded && alertH !== null && (
                <g>
                  <line x1={x(alertH)} x2={x(alertH)} y1={PAD.t} y2={RES_Y + RES_H} stroke="var(--danger-text)" strokeDasharray="4 4" />
                  <polygon points={`${x(alertH)},${PAD.t + 4} ${x(alertH) - 7},${PAD.t - 8} ${x(alertH) + 7},${PAD.t - 8}`} fill="var(--danger-text)" />
                  <text x={x(alertH) + 8} y={PAD.t + 52} fill="var(--danger-text)" fontSize="14" fontWeight="600">Physics checks fired at {alertH.toFixed(1)} h</text>
                  <text x={x(alertH) + 8} y={PAD.t + 70} fill="var(--danger-text)" fontSize="12">{check}</text>
                </g>
              )}
            </svg>
            <div className="shield-row">
              <button
                type="button"
                className="btn shield"
                aria-pressed={shielded}
                onPointerDown={(e) => {
                  if (shielded) return;
                  (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
                  const r = figure.current!.getBoundingClientRect();
                  setDrag({ x: e.clientX - r.left, y: e.clientY - r.top });
                }}
                onClick={() => place(!shielded)}
              >
                {shielded ? "Shield on the sensor (press to remove)" : "Place the shield on the sensor (drag it onto the chart, or press)"}
              </button>
              {drag && <span className="drag-ghost" style={{ left: drag.x, top: drag.y }} aria-hidden="true">shield</span>}
            </div>
            <p className="label-model">
              Recorded scenario: {data.meta.scenario_id} (simulated). {MODEL_LABEL}. {shielded && alertH !== null ? `The physics checks fired at ${alertH.toFixed(1)} h of the recording.` : "Place the shield to see when the checks fired."}
            </p>
          </>
        )}
      </div>
    </Scene>
  );
}
