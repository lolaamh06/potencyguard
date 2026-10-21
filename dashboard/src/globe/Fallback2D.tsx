// The 2D view for the lowest tier and for devices without WebGL: the same land dots and route,
// drawn orthographically on a 2D canvas. It redraws when the picture changes enough, not per frame.
import { useCallback, useEffect, useRef } from "react";
import { useAppStore } from "../app/appStore";
import { tierSettings } from "../quality/governor";
import { scrollState, useScrollTicker } from "../scroll/scrollState";
import { useGlobeTheme } from "./useGlobeTheme";
import { cameraPose } from "./cameraPath";
import { routePoints } from "./geo";
import { sampleLandPoints } from "./landPoints";
import type { GlobeProps } from "./types";
import { useLandMask } from "./useLandMask";
import { useGlobeStore } from "./globeStore";

type V = [number, number, number];

const cross = (a: V, b: V): V => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const dot = (a: V, b: V) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const unit = (a: V): V => {
  const n = Math.hypot(...a) || 1;
  return [a[0] / n, a[1] / n, a[2] / n];
};

export function Fallback2D(props: GlobeProps) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const mask = useLandMask();
  const reduced = useAppStore((s) => s.reducedMotion);
  const lastDrawn = useRef(-1);
  const layoutNow = useGlobeStore((s) => s.layout);
  const { colors } = useGlobeTheme();
  const points = useRef<Float32Array | null>(null);

  useEffect(() => {
    points.current = mask ? sampleLandPoints(mask.data, mask.width, mask.height, tierSettings("fallback2d").dotSamples) : null;
    lastDrawn.current = -1;
  }, [mask]);

  const draw = useCallback(() => {
    const el = canvas.current;
    if (!el) return;
    const w = el.clientWidth;
    const h = el.clientHeight;
    if (el.width !== w || el.height !== h) {
      el.width = w;
      el.height = h;
      lastDrawn.current = -1;
    }
    const progress = reduced || layoutNow === "control" ? 0.5 : scrollState.progress;
    if (Math.abs(progress - lastDrawn.current) < 0.004 && lastDrawn.current >= 0) return;
    lastDrawn.current = progress;
    const ctx = el.getContext("2d");
    if (!ctx) return;
    ctx.fillStyle = colors.void;
    ctx.fillRect(0, 0, w, h);
    const radius = Math.min(w, h) * (w / h > 1.2 ? 0.36 : 0.42);
    const cx = layoutNow !== "control" && w / h > 1.2 ? w * 0.62 : w / 2;
    const cy = h * 0.5;
    const glow = ctx.createRadialGradient(cx, cy, radius * 0.9, cx, cy, radius * 1.18);
    glow.addColorStop(0, "rgba(93, 214, 255, 0.35)");
    glow.addColorStop(1, "rgba(93, 214, 255, 0)");
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(cx, cy, radius * 1.18, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = colors.ink900;
    ctx.beginPath();
    ctx.arc(cx, cy, radius, 0, Math.PI * 2);
    ctx.fill();

    const pose = cameraPose(progress, undefined, reduced);
    const f = unit(pose.position);
    const r = unit(cross([0, 1, 0], f));
    const u = cross(f, r);
    const project = (p: V): { x: number; y: number; depth: number } => ({
      x: cx + dot(p, r) * radius,
      y: cy - dot(p, u) * radius,
      depth: dot(p, f),
    });

    const pts = points.current;
    if (pts) {
      ctx.fillStyle = colors.ice400;
      for (let i = 0; i < pts.length; i += 3) {
        const q = project([pts[i], pts[i + 1], pts[i + 2]]);
        if (q.depth <= 0.02) continue;
        ctx.globalAlpha = Math.min(1, q.depth * 1.6) * 0.9;
        ctx.fillRect(q.x - 1, q.y - 1, 2, 2);
      }
      ctx.globalAlpha = 1;
    }
    const arc = (pointsOnArc: V[], color: string, dashed: boolean) => {
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.setLineDash(dashed ? [6, 6] : []);
      ctx.beginPath();
      let pen = false;
      for (const p of pointsOnArc) {
        const q = project(p);
        if (q.depth <= 0) {
          pen = false;
          continue;
        }
        if (pen) ctx.lineTo(q.x, q.y);
        else ctx.moveTo(q.x, q.y);
        pen = true;
      }
      ctx.stroke();
      ctx.setLineDash([]);
    };
    const route = routePoints(props.origin, props.destination, 120, 0.16);
    const stateColor = { safe: colors.ice400, warning: colors.ember400, danger: colors.ember600 }[props.routeState];
    arc(route, stateColor, false);
    if (props.showAlternative) arc(routePoints(props.origin, props.destination, 120, 0.13, props.alternativeVia), colors.planner300, true);
    for (const p of [route[0], route[route.length - 1]]) {
      const q = project(p);
      if (q.depth > 0) {
        ctx.fillStyle = colors.ice300;
        ctx.beginPath();
        ctx.arc(q.x, q.y, 4, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }, [props.origin, props.destination, props.routeState, props.showAlternative, props.alternativeVia, reduced, layoutNow, colors]);

  useScrollTicker(draw);
  useEffect(() => {
    draw();
    const onResize = () => {
      lastDrawn.current = -1;
      draw();
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [draw, mask]);

  return (
    <div className={`canvas-layer ${layoutNow === "control" ? "control" : ""}`} data-testid="globe-2d">
      <canvas
        ref={canvas}
        style={{ width: "100%", height: "100%", display: "block" }}
        role="img"
        aria-label="A 2D view of a night globe with an illustrative shipping route"
      />
      <div className="vignette-2d" />
    </div>
  );
}
