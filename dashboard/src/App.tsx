import { Suspense, lazy, useEffect } from "react";
import { Chrome } from "./app/Chrome";
import { Shortcuts } from "./app/Shortcuts";
import { goTo, useRoute } from "./app/route";
import { useAppStore } from "./app/appStore";
import { ControlRoom } from "./controlroom/ControlRoom";
import { currentMode, useAdapter } from "./data/useAdapter";
import { PerfOverlay } from "./quality/PerfOverlay";
import { tierSettings } from "./quality/governor";
import { useQualityStore } from "./quality/qualityStore";
import { actionForKey, keyBelongsToControl, stepChapter } from "./scroll/keyboard";
import { CHAPTERS } from "./scroll/chapters";
import { scrollApi, scrollState } from "./scroll/scrollState";
import { recordingRequested } from "./controlroom/logic";

const GlobeScene = lazy(() => import("./globe/GlobeScene").then((m) => ({ default: m.GlobeScene })));
const Story = lazy(() => import("./story/Story").then((m) => ({ default: m.Story })));

const mode = currentMode();
const recMode = recordingRequested(window.location.search);
const RENDERED_COUNT = CHAPTERS.filter((c) => c.rendered).length;

export function App() {
  const route = useRoute();
  const data = useAdapter(mode === "live" ? "live" : "replay");
  const sceneStatus = useAppStore((s) => s.sceneStatus);
  const reduced = useAppStore((s) => s.reducedMotion);
  const tier = useQualityStore((s) => s.tier);
  const grain = tierSettings(tier).grain;

  // The Control Room has no scroll: the globe holds its last pose.
  useEffect(() => {
    if (route === "control-room") scrollState.progress = 1;
    else window.scrollTo(0, 0);
  }, [route]);

  useEffect(() => {
    document.documentElement.dataset.reducedMotion = String(reduced);
  }, [reduced]);
  useEffect(() => {
    if (recMode) document.documentElement.dataset.rec = "1";
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (keyBelongsToControl((event.target as HTMLElement | null)?.tagName, event.key)) return;
      const app = useAppStore.getState();
      if (recMode && (event.key === "?" || event.key === "d" || event.key === "D" || event.key === "q" || event.key === "Q")) return;
      const action = actionForKey(event, route === "story" && !app.helpOpen);
      if (!action) return;
      event.preventDefault();
      switch (action.kind) {
        case "scrollBy":
          scrollApi.by(action.viewports);
          break;
        case "chapter":
          scrollApi.toChapter(stepChapter(app.chapter, action.delta, RENDERED_COUNT));
          break;
        case "edge":
          scrollApi.toEdge(action.where);
          break;
        case "app":
          if (action.name === "tier") useQualityStore.getState().cycle();
          else if (action.name === "perf") app.togglePerf();
          else if (action.name === "help") app.setHelpOpen(!app.helpOpen);
          else if (action.name === "reduce") app.toggleReducedMotion();
          else if (action.name === "close") app.setHelpOpen(false);
          else if (action.name === "story") goTo("story");
          else if (action.name === "controlRoom") goTo("control-room");
          else if (action.name === "fullscreen") {
            if (document.fullscreenElement) void document.exitFullscreen();
            else void document.documentElement.requestFullscreen?.().catch(() => {});
          }
          break;
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [route]);

  return (
    <>
      <Suspense fallback={null}>
        <GlobeScene />
      </Suspense>
      {grain > 0 && route === "story" && <div className="grain" style={{ opacity: grain }} aria-hidden="true" />}
      {route === "story" && <Chrome route={route} />}
      {route === "story" ? (
        <Suspense fallback={null}>
          <Story />
        </Suspense>
      ) : (
        <ControlRoom mode={mode} data={data} backendReachable={data.backendReachable} recMode={recMode} />
      )}
      {!recMode && <Shortcuts />}
      {!recMode && <PerfOverlay />}
      {sceneStatus === "restoring" && <p className="notice" role="status">3D paused, restoring.</p>}
    </>
  );
}
