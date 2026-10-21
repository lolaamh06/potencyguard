// The chart: reported temperature with the physics twin's prediction, the residual strip and the
// CUSUM strip on ONE shared time axis. Lines are drawn on a canvas (read straight from the replay
// clock each tick); labels, ticks and alert markers are SVG on top. Text is at least 12 px.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReplayFile } from "../data/types";
import { useScrollTicker } from "../scroll/scrollState";
import { colors } from "../theme/tokens";
import { crClock } from "./store";
import { excursionBands, frameIndexAt, SAFE_HIGH_C, SAFE_LOW_C } from "./logic";

interface Box {
  w: number;
  h: number;
  font: number;
}

const PAD_L = 0.062;
const PAD_R = 0.015;

export function TimeChart({ replay }: { replay: ReplayFile }) {
  const wrap = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [box, setBox] = useState<Box>({ w: 600, h: 300, font: 12 });
  const lastDrawn = useRef(-1);
  const frames = replay.frames;
  const durationH = replay.meta.duration_h;
  const bands = useMemo(() => excursionBands(frames), [frames]);

  const ranges = useMemo(() => {
    const t = frames.flatMap((f) => [f.temp_c, f.twin_c]).filter((v): v is number => v !== null);
    const r = frames.map((f) => Math.abs(f.residual_c ?? 0));
    const c = frames.flatMap((f) => [f.cusum_neg ?? 0, f.cusum_pos ?? 0]);
    return {
      tLo: Math.min(...t, SAFE_LOW_C) - 1,
      tHi: Math.max(...t, SAFE_HIGH_C) + 1,
      rMax: Math.max(1, ...r),
      cMax: Math.max(replay.meta.cusum_h * 1.5, ...c),
    };
  }, [frames, replay.meta.cusum_h]);

  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const measure = () => {
      const r = el.getBoundingClientRect();
      const font = Math.max(12, parseFloat(getComputedStyle(el).fontSize) || 12);
      setBox({ w: Math.max(200, r.width), h: Math.max(120, r.height), font });
      lastDrawn.current = -1;
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const geo = useMemo(() => {
    const left = box.w * PAD_L;
    const right = box.w * (1 - PAD_R);
    const axis = box.font * 1.9;
    const usable = box.h - axis - box.font * 0.4;
    const gap = box.font * 0.5;
    const hT = usable * 0.5;
    const hR = usable * 0.25 - gap;
    const hC = usable * 0.25 - gap;
    const top = box.font * 0.3;
    return { left, right, top, hT, hR, hC, yT: top, yR: top + hT + gap, yC: top + hT + hR + gap * 2, axis };
  }, [box]);

  const x = useCallback((h: number) => geo.left + (h / durationH) * (geo.right - geo.left), [geo, durationH]);
  const yTemp = useCallback((c: number) => geo.yT + (1 - (c - ranges.tLo) / (ranges.tHi - ranges.tLo)) * geo.hT, [geo, ranges]);
  const yRes = useCallback((r: number) => geo.yR + geo.hR / 2 - (r / ranges.rMax) * (geo.hR / 2), [geo, ranges]);
  const yCus = useCallback((c: number) => geo.yC + (1 - c / ranges.cMax) * geo.hC, [geo, ranges]);

  const draw = useCallback(() => {
    const el = canvas.current;
    if (!el) return;
    const idx = frameIndexAt(frames, crClock.tS);
    if (idx === lastDrawn.current) return;
    lastDrawn.current = idx;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const W = Math.round(box.w * dpr);
    const H = Math.round(box.h * dpr);
    if (el.width !== W || el.height !== H) {
      el.width = W;
      el.height = H;
    }
    const ctx = el.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, box.w, box.h);
    // excursion bands behind the temperature strip
    ctx.fillStyle = "rgba(255, 122, 61, 0.16)";
    for (const b of bands) ctx.fillRect(x(b.fromH), geo.yT, Math.max(2, x(b.toH) - x(b.fromH)), geo.hT);
    // safe range lines and CUSUM threshold
    ctx.lineWidth = 1;
    ctx.strokeStyle = "rgba(94, 120, 153, 0.7)";
    ctx.setLineDash([4, 5]);
    for (const c of [SAFE_LOW_C, SAFE_HIGH_C]) {
      ctx.beginPath();
      ctx.moveTo(geo.left, yTemp(c));
      ctx.lineTo(geo.right, yTemp(c));
      ctx.stroke();
    }
    ctx.strokeStyle = colors.ember400;
    ctx.beginPath();
    ctx.moveTo(geo.left, yCus(replay.meta.cusum_h));
    ctx.lineTo(geo.right, yCus(replay.meta.cusum_h));
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.beginPath();
    ctx.strokeStyle = "rgba(94, 120, 153, 0.7)";
    ctx.moveTo(geo.left, yRes(0));
    ctx.lineTo(geo.right, yRes(0));
    ctx.stroke();

    const line = (color: string, width: number, dash: number[], pick: (i: number) => number | null, yy: (v: number) => number) => {
      ctx.beginPath();
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.setLineDash(dash);
      let pen = false;
      for (let i = 0; i <= idx; i++) {
        const v = pick(i);
        if (v === null) continue;
        const px = x(frames[i].t_s / 3600);
        if (pen) ctx.lineTo(px, yy(v));
        else ctx.moveTo(px, yy(v));
        pen = true;
      }
      ctx.stroke();
      ctx.setLineDash([]);
    };
    line(colors.mistHi, 2, [6, 5], (i) => frames[i].twin_c, yTemp);
    line(colors.ice400, 3, [], (i) => frames[i].temp_c, yTemp);
    line(colors.dangerText, 2, [], (i) => frames[i].residual_c, yRes);
    line(colors.ember500, 2, [], (i) => Math.max(frames[i].cusum_neg ?? 0, frames[i].cusum_pos ?? 0), yCus);
    wrap.current?.querySelectorAll<SVGGElement>(".alert-mark").forEach((g) => (g.style.opacity = Number(g.dataset.t) <= crClock.tS ? "1" : "0"));
    // the clock
    const cx = x(frames[idx].t_s / 3600);
    ctx.strokeStyle = colors.frost;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(cx, geo.top);
    ctx.lineTo(cx, geo.yC + geo.hC);
    ctx.stroke();
  }, [frames, box, geo, bands, x, yTemp, yRes, yCus, replay.meta.cusum_h]);
  useScrollTicker(draw);
  useEffect(() => {
    lastDrawn.current = -1;
  }, [replay, box]);

  const alerts = useMemo(() => replay.events.filter((e) => e.type === "physics_check_fired"), [replay]);
  const ticks = useMemo(() => {
    const step = durationH > 60 ? 20 : durationH > 30 ? 10 : 6;
    return Array.from({ length: Math.floor(durationH / step) + 1 }, (_, i) => i * step);
  }, [durationH]);
  const f = box.font;

  return (
    <div className="chart-wrap" ref={wrap}>
      <canvas ref={canvas} className="chart-canvas" aria-hidden="true" />
      <svg className="chart-svg" width={box.w} height={box.h} role="img" aria-label={`Reported temperature against the physics twin's prediction, residual and CUSUM strips for the recorded scenario ${replay.meta.scenario_id}, on one time axis. Alert markers show when physics checks fired.`}>
        <g fontSize={f} fill="var(--mist-hi)">
          <text x={4} y={geo.yT + f}>°C</text>
          <text x={4} y={geo.yR + f}>residual</text>
          <text x={4} y={geo.yC + f}>CUSUM</text>
          <text x={geo.left + 6} y={yTemp(SAFE_HIGH_C) - 4} fill="var(--mist)">{SAFE_HIGH_C} °C</text>
          <text x={geo.left + 6} y={yTemp(SAFE_LOW_C) + f + 2} fill="var(--mist)">{SAFE_LOW_C} °C</text>
          <text x={geo.right - 4} y={yCus(replay.meta.cusum_h) - 4} textAnchor="end" fill="var(--ember-400)">alarm threshold h = {replay.meta.cusum_h}</text>
          {ticks.map((h) => (
            <text key={h} x={x(h)} y={box.h - f * 0.3} textAnchor="middle">{h} h</text>
          ))}
          {bands.slice(0, 3).map((b, i) => (
            <text key={i} x={x(b.fromH) + 3} y={geo.yT + f * 2.1 + i * 0} fill="var(--ember-500)">excursion</text>
          ))}
        </g>
        {alerts.slice(0, 4).map((a, i) => (
          <g key={i} transform={`translate(${x(a.t_s / 3600)} 0)`} style={{ opacity: crClock.tS >= a.t_s ? 1 : 0 }} className="alert-mark" data-t={a.t_s}>
            <line y1={geo.top} y2={geo.yC + geo.hC} stroke="var(--danger-text)" strokeDasharray="3 4" />
            <polygon points={`0,${geo.top + 2} -6,${geo.top - 6} 6,${geo.top - 6}`} fill="var(--danger-text)" />
          </g>
        ))}
      </svg>
    </div>
  );
}
