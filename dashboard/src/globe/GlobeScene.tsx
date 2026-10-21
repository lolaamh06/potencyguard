// The canvas around the globe: camera rig driven by scroll progress, the quality governor probe,
// WebGL context loss and restore, and light post-processing on the higher tiers.
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Bloom, EffectComposer, Vignette } from "@react-three/postprocessing";
import { useEffect, useRef } from "react";
import { Component, type ReactNode } from "react";
import { Vector3 } from "three";
import { useAppStore } from "../app/appStore";
import { useUi } from "../app/ui";
import {
  DEFAULT_GOVERNOR,
  effectiveDpr,
  initialGovernor,
  stepGovernor,
  tierSettings,
  type GovernorState,
} from "../quality/governor";
import { perf } from "../quality/perf";
import { useQualityStore } from "../quality/qualityStore";
import { scrollState } from "../scroll/scrollState";
import { cameraPose } from "./cameraPath";
import { stageCamera } from "./stageCamera";
import { Stage } from "./Stage";
import { useStoryBundle } from "../data/useStoryData";
import { useGlobeStore } from "./globeStore";
import { useGlobeTheme } from "./useGlobeTheme";
import { Fallback2D } from "./Fallback2D";
import { Globe } from "./Globe";
import { DEFAULT_GLOBE_PROPS, type GlobeProps } from "./types";
import { useLandMask } from "./useLandMask";

const WINDOW_FRAMES = 60;
const _target = new Vector3();
const _goal = new Vector3();

/** Moves the camera along the scroll path. Reads a ref-like plain object, never React state. */
function CameraRig() {
  const camera = useThree((s) => s.camera);
  const size = useThree((s) => s.size);
  const set = useThree((s) => s.set);
  const first = useRef(true);
  const layout = useGlobeStore((s) => s.layout);

  useEffect(() => {
    // Wide screens: shift the globe right so the story text has the left side. Tall screens:
    // shift it down so the text has the top.
    const control = layout === "control";
    const shiftX = !control && size.width / size.height > 1.2 ? size.width * 0.2 : 0;
    const shiftY = !control && size.width / size.height < 1 ? size.height * 0.2 : 0;
    const persp = camera as typeof camera & { setViewOffset?: (...a: number[]) => void; clearViewOffset?: () => void };
    if (shiftX > 0 || shiftY > 0) persp.setViewOffset?.(size.width, size.height, -shiftX, -shiftY, size.width, size.height);
    else persp.clearViewOffset?.();
    camera.updateProjectionMatrix();
    set({});
  }, [camera, size, set, layout]);


  useFrame((_, delta) => {
    const reduced = useAppStore.getState().reducedMotion;
    const portrait = layout !== "control" && size.width / size.height < 1;
    const globePose = cameraPose(layout === "control" ? 0.5 : scrollState.progress, undefined, reduced);
    const pose = layout === "control" ? globePose : stageCamera(scrollState.chapter, scrollState.local, globePose, reduced);
    const k = portrait ? 1.45 : 1;
    const dive = 1 - 0.5 * scrollState.dive;
    _target.set(...pose.target);
    _goal.set(
      _target.x + (pose.position[0] * k - _target.x) * dive,
      _target.y + (pose.position[1] * k - _target.y) * dive,
      _target.z + (pose.position[2] * k - _target.z) * dive,
    );
    if (first.current || reduced) {
      camera.position.copy(_goal);
      first.current = false;
    } else {
      camera.position.lerp(_goal, 1 - Math.exp(-7 * delta));
    }
    camera.lookAt(_target);
  });
  return null;
}

/** Writes the render numbers and feeds the governor one window of frames at a time. */
function GovernorProbe() {
  const gl = useThree((s) => s.gl);
  const tier = useQualityStore((s) => s.tier);
  const stepDown = useQualityStore((s) => s.stepDown);
  const state = useRef<GovernorState>(initialGovernor(tier));
  const sum = useRef(0);
  const count = useRef(0);

  useEffect(() => {
    gl.info.autoReset = false;
    const ctx = gl.getContext();
    const ext = ctx.getExtension("WEBGL_debug_renderer_info");
    perf.renderer = ext ? String(ctx.getParameter(ext.UNMASKED_RENDERER_WEBGL)) : "unavailable";
    perf.webgl = gl.capabilities.isWebGL2 ? "2" : "1";
    return () => {
      gl.info.autoReset = true;
    };
  }, [gl]);

  useEffect(() => {
    state.current = initialGovernor(tier);
    sum.current = 0;
    count.current = 0;
  }, [tier]);

  // priority -1 runs before the render of this frame, so the counters hold the whole previous frame
  useFrame((_, delta) => {
    perf.calls = gl.info.render.calls;
    perf.triangles = gl.info.render.triangles;
    gl.info.reset();
    const ms = delta * 1000;
    perf.frameMs = perf.frameMs === 0 ? ms : perf.frameMs * 0.9 + ms * 0.1;
    perf.fps = perf.frameMs > 0 ? 1000 / perf.frameMs : 0;
    sum.current += ms;
    count.current += 1;
    if (count.current >= WINDOW_FRAMES) {
      const next = stepGovernor(state.current, sum.current / count.current, DEFAULT_GOVERNOR);
      const changed = next.tier !== state.current.tier;
      state.current = next;
      sum.current = 0;
      count.current = 0;
      if (changed) stepDown();
    }
  }, -1);
  return null;
}

/** Keeps the page alive when the browser drops the WebGL context, and shows a calm notice. */
function ContextGuard() {
  const gl = useThree((s) => s.gl);
  const setStatus = useAppStore((s) => s.setSceneStatus);
  useEffect(() => {
    const canvas = gl.domElement;
    const lost = (event: Event) => {
      event.preventDefault();
      perf.contextLost = true;
      setStatus("restoring");
    };
    const restored = () => {
      perf.contextLost = false;
      setStatus("ok");
    };
    canvas.addEventListener("webglcontextlost", lost);
    canvas.addEventListener("webglcontextrestored", restored);
    return () => {
      canvas.removeEventListener("webglcontextlost", lost);
      canvas.removeEventListener("webglcontextrestored", restored);
      perf.contextLost = false;
    };
  }, [gl, setStatus]);
  return null;
}

class SceneBoundary extends Component<{ children: ReactNode; props: GlobeProps }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(error: unknown) {
    console.warn("3D scene failed; showing the 2D view instead.", error instanceof Error ? error.message : "");
  }
  render() {
    return this.state.failed ? <Fallback2D {...this.props.props} /> : this.props.children;
  }
}

export function GlobeScene(props: Partial<GlobeProps>) {
  const { theme, colors } = useGlobeTheme();
  const cinematic = useUi((st) => st.cinematic);
  const storeProps = useGlobeStore((s) => s.props);
  const layoutNow = useGlobeStore((s) => s.layout);
  const globeProps: GlobeProps = { ...DEFAULT_GLOBE_PROPS, ...storeProps, ...props };
  const tier = useQualityStore((s) => s.tier);
  const settings = tierSettings(tier);
  const mask = useLandMask();
  const dpr = effectiveDpr(window.devicePixelRatio, tier);
  const chapter = useAppStore((s) => s.chapter);
  const reduced = useAppStore((s) => s.reducedMotion);
  const layer = useRef<HTMLDivElement>(null);
  const story = useStoryBundle();

  // Behind the chart chapters the globe is dimmed so the figures read clearly.
  useEffect(() => {
    layer.current?.classList.toggle("dim", cinematic ? [1, 2, 3, 4, 6].includes(chapter) : true);
  }, [chapter, cinematic]);

  // Reduced motion: the camera stays still, so each chapter change crossfades the picture instead.
  useEffect(() => {
    const el = layer.current;
    if (!el || !reduced) return;
    el.classList.add("fading");
    const id = window.setTimeout(() => el.classList.remove("fading"), 450);
    return () => window.clearTimeout(id);
  }, [chapter, reduced]);

  if (!settings.webgl) return <Fallback2D {...globeProps} />;

  return (
    <div className={`canvas-layer ${layoutNow === "control" ? "control" : ""}`} ref={layer} data-testid="globe-canvas">
      <SceneBoundary props={globeProps}>
        <Canvas
          dpr={dpr}
          camera={{ position: [0, -39.5, 1.6], fov: 40, near: 0.05, far: 250 }}
          gl={{ antialias: false, powerPreference: "high-performance", alpha: false }}
          aria-label="A night globe with an illustrative shipping route"
        >
          <color attach="background" args={[colors.void]} />
          <CameraRig />
          <GovernorProbe />
          <ContextGuard />
          <Globe {...globeProps} mask={mask} tier={tier} pixelRatio={dpr} />
          <Stage cloud={story?.ch5 ?? null} glow={story?.hidden?.frames[0]?.potency ?? 1} />
          {settings.bloom && theme === "dark" && (
            <EffectComposer multisampling={0}>
              <Bloom luminanceThreshold={0.35} intensity={0.55} mipmapBlur />
              <Vignette eskil={false} offset={0.25} darkness={0.7} />
            </EffectComposer>
          )}
        </Canvas>
      </SceneBoundary>
    </div>
  );
}
