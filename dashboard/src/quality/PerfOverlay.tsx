// Small performance overlay, hidden by default (D key). Reads the plain `perf` object four times
// a second; it never touches the render loop.
import { useEffect, useState } from "react";
import { useAppStore } from "../app/appStore";
import { perf } from "./perf";
import { tierSettings } from "./governor";
import { useQualityStore } from "./qualityStore";

export function PerfOverlay() {
  const open = useAppStore((s) => s.perfOpen);
  const tier = useQualityStore((s) => s.tier);
  const locked = useQualityStore((s) => s.locked);
  const [, tick] = useState(0);

  useEffect(() => {
    if (!open) return;
    const id = window.setInterval(() => tick((n) => n + 1), 250);
    return () => window.clearInterval(id);
  }, [open]);

  if (!open) return null;
  const settings = tierSettings(tier);
  return (
    <div className="perf" role="status" aria-label="Performance overlay" data-testid="perf-overlay">
      {[
        `tier        ${tier}${locked ? " (fixed)" : " (auto)"}`,
        `fps         ${perf.fps.toFixed(1)}`,
        `frame time  ${perf.frameMs.toFixed(1)} ms`,
        `draw calls  ${perf.calls}`,
        `triangles   ${perf.triangles}`,
        `pixel ratio <= ${settings.dprCap}`,
        `webgl       ${perf.webgl}`,
        `renderer    ${perf.renderer}`,
        perf.contextLost ? "context     LOST (restoring)" : "context     ok",
      ].join("\n")}
    </div>
  );
}
