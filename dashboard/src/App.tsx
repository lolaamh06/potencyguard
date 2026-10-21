import { Suspense, lazy, useEffect } from "react";
import { Help } from "./app/Help";
import { Nav } from "./app/Nav";
import { Tour } from "./app/Tour";
import { useAppStore } from "./app/appStore";
import { goTo, useRoute } from "./app/route";
import { initTheme, useUi, watchSystemTheme } from "./app/ui";
import { useRecording } from "./app/useRecording";
import { recordingRequested } from "./controlroom/logic";
import { currentMode, useAdapter } from "./data/useAdapter";
import { useGlobeStore } from "./globe/globeStore";
import { AboutPage } from "./pages/AboutPage";
import { DecisionsPage } from "./pages/DecisionsPage";
import { HomePage } from "./pages/HomePage";
import { ProofPage } from "./pages/ProofPage";
import { ShipmentPage } from "./pages/ShipmentPage";
import { ShipmentsPage } from "./pages/ShipmentsPage";
import { PerfOverlay } from "./quality/PerfOverlay";
import { tierSettings } from "./quality/governor";
import { useQualityStore } from "./quality/qualityStore";
import { CHAPTERS } from "./scroll/chapters";
import { actionForKey, keyBelongsToControl, stepChapter } from "./scroll/keyboard";
import { scrollApi, scrollState } from "./scroll/scrollState";

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
  const story = route.page === "story";
  useRecording(recMode);

  useEffect(() => {
    initTheme();
    return watchSystemTheme();
  }, []);

  // the globe is a calm background on every page except the Story, which drives it by scrolling
  useEffect(() => {
    useUi.getState().setCinematic(story);
    useUi.getState().setMenu(false);
    useGlobeStore.getState().setLayout("story");
    if (!story) {
      scrollState.chapter = 3;
      scrollState.local = 0.5;
      scrollState.progress = 0.5;
      window.scrollTo(0, 0);
    } else window.scrollTo(0, 0);
  }, [story, route.page, route.id]);

  useEffect(() => {
    document.documentElement.dataset.reducedMotion = String(reduced);
  }, [reduced]);
  useEffect(() => {
    if (recMode) document.documentElement.dataset.rec = "1";
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (keyBelongsToControl((event.target as HTMLElement | null)?.tagName, event.key)) return;
      const t = event.target as HTMLElement | null;
      if (t && ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName)) return;
      const app = useAppStore.getState();
      if (recMode && ["?", "d", "D", "q", "Q"].includes(event.key)) return;
      if ((event.key === "h" || event.key === "H") && !event.ctrlKey && !event.metaKey && !event.altKey) {
        goTo({ page: "home" });
        return;
      }
      const action = actionForKey(event, story && !app.helpOpen);
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
          else if (action.name === "story") goTo({ page: "story" });
          else if (action.name === "controlRoom") goTo({ page: "shipments" });
          else if (action.name === "fullscreen") {
            if (document.fullscreenElement) void document.exitFullscreen();
            else void document.documentElement.requestFullscreen?.().catch(() => {});
          }
          break;
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [story]);

  return (
    <>
      <a className="skip-link" href="#content" onClick={(e) => { e.preventDefault(); document.getElementById("content")?.focus(); }}>Skip to content</a>
      <Suspense fallback={null}>
        <GlobeScene />
      </Suspense>
      {grain > 0 && story && <div className="grain" style={{ opacity: grain }} aria-hidden="true" />}
      <Nav route={route} />
      {story ? (
        <div data-theme="dark" className="cinematic">
          <Suspense fallback={<main id="content" className="page"><p role="status" className="muted">Loading the story…</p></main>}>
            <Story />
          </Suspense>
        </div>
      ) : (
        <>
          {route.page === "home" && <HomePage />}
          {route.page === "shipments" && <ShipmentsPage data={data} />}
          {route.page === "shipment" && route.id && <ShipmentPage id={route.id} data={data} />}
          {route.page === "decisions" && <DecisionsPage data={data} />}
          {route.page === "proof" && <ProofPage data={data} />}
          {route.page === "about" && <AboutPage data={data} />}
          <footer className="foot">
            <span>Sample data from a simulation. Actions on screen change the screen only.</span>
            <a href="#/about">About this data</a>
          </footer>
        </>
      )}
      <Help />
      <Tour />
      {!recMode && <PerfOverlay />}
      {mode === "live" && data.backendReachable === false && <p className="notice" role="status">The backend is not reachable, so the recorded shipments are shown.</p>}
      {sceneStatus === "restoring" && <p className="notice" role="status">3D paused, restoring.</p>}
    </>
  );
}
