// Chapter 4: "A box that thinks." A stylised, procedurally drawn cutaway that explodes along its
// axis; each part lights up in turn with a generic label. It describes a DESIGN, not installed hardware.
import { useCallback, useRef } from "react";
import { useAppStore } from "../app/appStore";
import { Scene, span, useChapterTick } from "./common";

const PARTS = [
  { id: "shell", label: "Insulated shell", dy: -150, color: "var(--mist)" },
  { id: "rack", label: "Vial rack", dy: -50, color: "var(--ice-700)" },
  { id: "sensor", label: "Sensors", dy: 40, color: "var(--ice-400)" },
  { id: "board", label: "Edge computer", dy: 125, color: "var(--planner)" },
  { id: "log", label: "Signed log", dy: 205, color: "var(--verify)" },
] as const;

const NOTES = ["Thermal twin", "Potency estimator"] as const;

export function Chapter4() {
  const root = useRef<SVGSVGElement>(null);
  const reduced = useAppStore((s) => s.reducedMotion);

  const paint = useCallback(
    (t: number) => {
      const el = root.current;
      if (!el) return;
      const open = reduced ? 1 : span(t, 0.08, 0.55);
      PARTS.forEach((p, i) => {
        const g = el.querySelector<SVGGElement>(`#part-${p.id}`);
        if (g) g.setAttribute("transform", `translate(0 ${(p.dy * open).toFixed(1)})`);
        const lit = reduced ? 1 : span(t, 0.3 + i * 0.1, 0.4 + i * 0.1);
        const label = el.querySelector<SVGGElement>(`#label-${p.id}`);
        if (label) label.style.opacity = String(lit);
      });
      const rings = el.querySelector<SVGGElement>("#rings");
      if (rings) rings.style.opacity = String(reduced ? 1 : span(t, 0.72, 0.9));
      for (const [id, from] of [["c4-l1", 0.05], ["c4-l2", 0.55]] as const) {
        const n = document.getElementById(id);
        if (n) n.style.opacity = String(reduced ? 1 : span(t, from, from + 0.15));
      }
    },
    [reduced],
  );
  useChapterTick(4, paint);

  return (
    <Scene index={4}>
      <div className="copy">
        <h2>A box that thinks</h2>
        <p id="c4-l1">Potency, physics and proof, computed where the medicine is.</p>
        <p id="c4-l2">It works even when the network does not.</p>
        <p className="caption">A stylised model of the design. The labels describe the design, not installed hardware.</p>
      </div>
      <div className="figure">
        <svg ref={root} viewBox="0 0 640 520" role="img" aria-label="A stylised exploded view of an insulated shipping box with sensors, an edge computer and a signed log">
          <g transform="translate(150 150)">
            <g id="part-shell"><polygon points="0,40 120,0 240,40 120,80" fill="var(--ink-700)" stroke="var(--mist)" strokeWidth="2" /><polygon points="0,40 0,90 120,130 120,80" fill="var(--ink-800)" stroke="var(--mist)" strokeWidth="2" /><polygon points="240,40 240,90 120,130 120,80" fill="var(--ink-900)" stroke="var(--mist)" strokeWidth="2" /></g>
            <g id="part-rack"><polygon points="40,50 120,20 200,50 120,80" fill="none" stroke="var(--ice-400)" strokeWidth="2" strokeDasharray="5 4" />{[70, 100, 130, 160].map((cx) => (<rect key={cx} x={cx - 6} y={32} width="12" height="26" rx="4" fill="var(--ice-700)" stroke="var(--ice-300)" />))}</g>
            <g id="part-sensor"><circle cx="120" cy="50" r="14" fill="var(--ice-400)" opacity="0.25" /><circle cx="120" cy="50" r="6" fill="var(--ice-400)" /><line x1="120" y1="50" x2="170" y2="30" stroke="var(--ice-400)" strokeWidth="2" /></g>
            <g id="part-board"><rect x="70" y="35" width="100" height="30" rx="4" fill="var(--ink-800)" stroke="var(--planner-300)" strokeWidth="2" /><rect x="84" y="44" width="22" height="12" fill="var(--planner)" opacity="0.7" /><rect x="114" y="44" width="40" height="3" fill="var(--planner-300)" /><rect x="114" y="52" width="28" height="3" fill="var(--planner-300)" /></g>
            <g id="part-log">{[0, 1, 2, 3].map((i) => (<rect key={i} x={90 + i * 18} y={40} width="12" height="22" rx="3" fill="none" stroke="var(--verify)" strokeWidth="2" />))}<line x1="96" x2="150" y1="51" y2="51" stroke="var(--verify)" /></g>
          </g>
          {PARTS.map((p) => (
            <g id={`label-${p.id}`} key={p.id} opacity="0">
              <text x={430} y={198 + p.dy} fill={p.color} fontSize="15" fontWeight="600">{p.label}</text>
              <line x1="395" x2="425" y1={192 + p.dy} y2={192 + p.dy} stroke={p.color} />
            </g>
          ))}
          <g id="rings" opacity="0">
            <circle cx="320" cy="355" r="62" fill="none" stroke="var(--ice-400)" strokeWidth="2" />
            <circle cx="320" cy="355" r="48" fill="none" stroke="var(--planner)" strokeWidth="2" />
            <circle cx="320" cy="355" r="34" fill="none" stroke="var(--verify)" strokeWidth="2" />
            <text x="320" y="440" textAnchor="middle" fill="var(--mist-hi)" fontSize="13">potency · physics · proof</text>
            <text x="60" y="470" fill="var(--mist-hi)" fontSize="13">{NOTES[0]}, {NOTES[1]}</text>
          </g>
        </svg>
      </div>
    </Scene>
  );
}
