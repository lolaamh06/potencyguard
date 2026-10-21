// Chapter 5: "Plan for the worst five percent." The 3D cloud is in the canvas (globe/Stage.tsx);
// this is the copy, the expected-versus-worst bars and the risk slider. The slider only SELECTS a
// row of the exported table; no CVaR is computed here.
import { useCallback, useEffect, useMemo, useRef } from "react";
import { useAppStore } from "../app/appStore";
import { flipAlphas, litFlags, rowForAlpha, type Chapter5Data } from "../data/story";
import { mulberry32 } from "../globe/landPoints";
import { tierSettings } from "../quality/governor";
import { useQualityStore } from "../quality/qualityStore";
import { useAlphaStore } from "../globe/Stage";
import { Missing, MODEL_LABEL, Scene, span, useChapterTick } from "./common";

const NAMES: Record<string, string> = { continue: "Continue", reroute: "Reroute" };
const fmt = (n: number) => Math.round(n).toLocaleString("en-US");

/** 2D version of the cloud for the lowest tier: the same samples, drawn flat. */
function CloudFlat({ data, alpha }: { data: Chapter5Data; alpha: number }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = ref.current;
    const ctx = c?.getContext("2d");
    if (!c || !ctx) return;
    c.width = 640;
    c.height = 260;
    ctx.clearRect(0, 0, c.width, c.height);
    const row = rowForAlpha(data.rows, alpha);
    (["continue", "reroute"] as const).forEach((name, k) => {
      const a = data.actions[name];
      const lit = litFlags(a.rank, row.tail_points);
      const rand = mulberry32(name === "continue" ? 11 : 23);
      for (let i = 0; i < data.n_points; i++) {
        const x = 40 + k * 310 + rand() * 250;
        const y = (a.failed[i] ? 50 : 200) + (rand() - 0.5) * 70;
        ctx.fillStyle = lit[i] ? "#b7aeff" : a.failed[i] ? "#ff7a3d" : "#2e9fc4";
        ctx.fillRect(x, y, 2, 2);
      }
    });
  }, [data, alpha]);
  return <canvas ref={ref} style={{ width: "100%" }} role="img" aria-label="Simulated outcomes for Continue (left) and Reroute (right); violet dots are the worst tail" />;
}

export function Chapter5({ data }: { data: Chapter5Data | null }) {
  const alpha = useAlphaStore((s) => s.alpha);
  const setAlpha = useAlphaStore((s) => s.setAlpha);
  const reduced = useAppStore((s) => s.reducedMotion);
  const root = useRef<HTMLDivElement>(null);
  const flat = !tierSettings(useQualityStore((s) => s.tier)).webgl;
  const row = useMemo(() => (data ? rowForAlpha(data.rows, alpha) : null), [data, alpha]);
  const flips = useMemo(() => (data ? flipAlphas(data.rows) : []), [data]);
  const maxBar = useMemo(() => (data ? Math.max(...data.rows.flatMap((r) => Object.values(r.actions).map((a) => Math.max(a.expected_loss, a.cvar)))) : 1), [data]);

  const paint = useCallback(
    (t: number) => {
      const el = root.current;
      if (!el) return;
      el.style.opacity = String(reduced ? 1 : span(t, 0.1, 0.25) * (1 - span(t, 0.93, 1)));
      for (const [id, from] of [["c5-l1", 0.15], ["c5-l2", 0.3], ["c5-l3", 0.5]] as const) {
        const n = document.getElementById(id);
        if (n) n.style.opacity = String(reduced ? 1 : span(t, from, from + 0.12));
      }
    },
    [reduced],
  );
  useChapterTick(5, paint);

  const worstPct = row ? Math.round((1 - row.alpha) * 100) : 5;
  return (
    <Scene index={5} className="cloud-scene">
      <div className="copy">
        <h2>Plan for the worst five percent</h2>
        <p id="c5-l1">The average says continue.</p>
        <p id="c5-l2">The worst five percent says reroute.</p>
        <p id="c5-l3">Rare, severe losses matter more than the average.</p>
        <p className="caption">Left cloud: Continue. Right cloud: Reroute. Each dot is one simulated outcome; violet dots are the worst {worstPct} percent of that action's outcomes.</p>
      </div>
      <div className="figure panel-over-3d" ref={root}>
        {!data || !row ? (
          <Missing what="The planner samples" />
        ) : (
          <>
            {flat && <CloudFlat data={data} alpha={alpha} />}
            <div className="bars" role="group" aria-label="Expected loss and worst-case average loss per action">
              {(["continue", "reroute"] as const).map((name) => {
                const a = row.actions[name];
                return (
                  <div key={name} className={row.recommended === name ? "bar-block best" : "bar-block"}>
                    <h3>{NAMES[name]} {row.recommended === name && <span className="badge">✓ lowest worst-case average</span>}</h3>
                    <div className="bar"><i style={{ width: `${(a.expected_loss / maxBar) * 100}%`, background: "var(--ice-400)" }} /><span className="num">expected {fmt(a.expected_loss)}</span></div>
                    <div className="bar"><i style={{ width: `${(a.cvar / maxBar) * 100}%`, background: "var(--planner)" }} /><span className="num">worst {worstPct}%: {fmt(a.cvar)}</span></div>
                  </div>
                );
              })}
            </div>
            <label className="handle">
              <span>Risk level (alpha {row.alpha.toFixed(2)}): average view at the left, tail view at the right</span>
              <input type="range" min={0} max={0.99} step={0.01} value={alpha} onChange={(e) => setAlpha(Number(e.target.value))} aria-valuetext={`alpha ${row.alpha.toFixed(2)}, the worst ${worstPct} percent`} />
            </label>
            <p className="verdict" role="status">By the worst {worstPct}% the lower loss is: <strong>{NAMES[row.recommended]}</strong>{flips.length > 0 && <span className="quiet"> (it changes at alpha {flips[0].toFixed(2)})</span>}</p>
            <p className="label-model">{MODEL_LABEL}. Textbook example, illustrative loss units. {fmt(data.n_points)} seeded outcomes per action (seed {data.seed}); the numbers come from the planner's own functions.</p>
          </>
        )}
      </div>
    </Scene>
  );
}
