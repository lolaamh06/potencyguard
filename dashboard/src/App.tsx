import { useEffect } from "react";
import { Chrome } from "./app/Chrome";
import { Shortcuts } from "./app/Shortcuts";
import { goTo, useRoute } from "./app/route";
import { useAppStore } from "./app/appStore";
import { ControlRoom } from "./controlroom/ControlRoom";
import { currentMode, useAdapter } from "./data/useAdapter";
import { GlobeScene } from "./globe/GlobeScene";
import { PerfOverlay } from "./quality/PerfOverlay";
import { tierSettings } from "./quality/governor";
import { useQualityStore } from "./quality/qualityStore";
import { actionForKey, keyBelongsToControl, stepChapter } from "./scroll/keyboard";
import { CHAPTERS } from "./scroll/chapters";
import { scrollApi, scrollState } from "./scroll/scrollState";
import { Story } from "./story/Story";

const mode = currentMode();
const RENDERED_COUNT = CHAPTERS.filter((c) => c.rendered).length;

export function App() {
  const route = useRoute();
  const data = useAdapter(mode);
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
    const onKey = (event: KeyboardEvent) => {
      if (keyBelongsToControl((event.target as HTMLElement | null)?.tagName, event.key)) return;
      const app = useAppStore.getState();
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
      <GlobeScene />
      {grain > 0 && <div className="grain" style={{ opacity: grain }} aria-hidden="true" />}
      <Chrome route={route} />
      {route === "story" ? <Story /> : <ControlRoom mode={mode} data={data} backendReachable={data.backendReachable} />}
      <Shortcuts />
      <PerfOverlay />
      {sceneStatus === "restoring" && <p className="notice" role="status">3D paused, restoring.</p>}
    </>
  );
}
