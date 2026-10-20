// Throwaway 3D scene for the Phase 0 smoke test: dotted sphere, rim glow, scroll-driven camera.
import { PerformanceMonitor } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Bloom, EffectComposer } from "@react-three/postprocessing";
import { useEffect, useMemo, useRef, useState } from "react";
import { AdditiveBlending, BackSide, type Group } from "three";
import { effectiveDpr, tierSettings } from "./qualityTier";
import { liveState, useQualityStore } from "./useQualityStore";

const POINT_COLOR = "#5DD6FF";
const CAMERA_Z_FAR = 6;
const CAMERA_Z_NEAR = 2.6;
const ROTATION_RAD_PER_S = 0.05;
const FRAME_WINDOW = 60;

/** Evenly spread points on a unit sphere (Fibonacci lattice). */
function fibonacciSphere(count: number): Float32Array {
  const positions = new Float32Array(count * 3);
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < count; i++) {
    const y = 1 - (2 * (i + 0.5)) / count;
    const r = Math.sqrt(1 - y * y);
    const theta = golden * i;
    positions[i * 3] = Math.cos(theta) * r;
    positions[i * 3 + 1] = y;
    positions[i * 3 + 2] = Math.sin(theta) * r;
  }
  return positions;
}

const RIM_VERTEX = /* glsl */ `
  varying vec3 vNormal;
  varying vec3 vViewDir;
  void main() {
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    vNormal = normalize(normalMatrix * normal);
    vViewDir = normalize(-mv.xyz);
    gl_Position = projectionMatrix * mv;
  }
`;

const RIM_FRAGMENT = /* glsl */ `
  varying vec3 vNormal;
  varying vec3 vViewDir;
  void main() {
    float fresnel = pow(1.0 - abs(dot(normalize(vNormal), normalize(vViewDir))), 3.0);
    gl_FragColor = vec4(0.365, 0.839, 1.0, fresnel * 0.7);
  }
`;

function Globe({ reducedMotion }: { reducedMotion: boolean }) {
  const tier = useQualityStore((s) => s.tier);
  const count = tierSettings(tier).pointCount;
  const positions = useMemo(() => fibonacciSphere(count), [count]);
  const group = useRef<Group>(null);

  useFrame((_, delta) => {
    if (group.current && !reducedMotion) group.current.rotation.y += delta * ROTATION_RAD_PER_S;
  });

  return (
    <group ref={group}>
      <points key={count}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[positions, 3]} />
        </bufferGeometry>
        <pointsMaterial
          color={POINT_COLOR}
          size={0.012}
          sizeAttenuation
          transparent
          opacity={0.9}
          depthWrite={false}
        />
      </points>
      <mesh scale={1.08}>
        <sphereGeometry args={[1, 48, 48]} />
        <shaderMaterial
          vertexShader={RIM_VERTEX}
          fragmentShader={RIM_FRAGMENT}
          side={BackSide}
          transparent
          depthWrite={false}
          blending={AdditiveBlending}
        />
      </mesh>
    </group>
  );
}

/** Reads GPU info once, moves the camera with scroll, and keeps a 60-frame rolling FPS. */
function RenderLoopProbe({ reducedMotion }: { reducedMotion: boolean }) {
  const gl = useThree((s) => s.gl);
  const frames = useRef(new Float32Array(FRAME_WINDOW));
  const filled = useRef(0);
  const cursor = useRef(0);

  useEffect(() => {
    liveState.webglVersion = gl.capabilities.isWebGL2 ? 2 : 1;
    const ext = gl.getContext().getExtension("WEBGL_debug_renderer_info");
    liveState.gpu = ext
      ? String(gl.getContext().getParameter(ext.UNMASKED_RENDERER_WEBGL))
      : "unavailable";
  }, [gl]);

  useFrame((state, delta) => {
    frames.current[cursor.current] = delta;
    cursor.current = (cursor.current + 1) % FRAME_WINDOW;
    filled.current = Math.min(filled.current + 1, FRAME_WINDOW);
    let sum = 0;
    for (let i = 0; i < filled.current; i++) sum += frames.current[i];
    liveState.fps = sum > 0 ? filled.current / sum : 0;

    // Reduced motion: same path, but only a small zoom.
    const travel = reducedMotion ? 0.3 : 1;
    const p = liveState.scrollProgress;
    state.camera.position.z = CAMERA_Z_FAR - p * (CAMERA_Z_FAR - CAMERA_Z_NEAR) * travel;
  });
  return null;
}

/** Keeps the page alive when the browser drops the WebGL context. */
function ContextGuard({ onPaused }: { onPaused: (paused: boolean) => void }) {
  const gl = useThree((s) => s.gl);
  useEffect(() => {
    const canvas = gl.domElement;
    const lost = (e: Event) => {
      e.preventDefault();
      onPaused(true);
    };
    const restored = () => onPaused(false);
    canvas.addEventListener("webglcontextlost", lost);
    canvas.addEventListener("webglcontextrestored", restored);
    return () => {
      canvas.removeEventListener("webglcontextlost", lost);
      canvas.removeEventListener("webglcontextrestored", restored);
    };
  }, [gl, onPaused]);
  return null;
}

export function SmokeScene({ reducedMotion }: { reducedMotion: boolean }) {
  const tier = useQualityStore((s) => s.tier);
  const stepDown = useQualityStore((s) => s.stepDown);
  const [paused, setPaused] = useState(false);
  const dpr = effectiveDpr(window.devicePixelRatio, tier);

  return (
    <div className="canvas-layer">
      <Canvas
        dpr={dpr}
        camera={{ position: [0, 0, CAMERA_Z_FAR], fov: 45 }}
        gl={{ antialias: false, powerPreference: "high-performance" }}
      >
        <color attach="background" args={["#04070D"]} />
        <PerformanceMonitor onDecline={stepDown} />
        <RenderLoopProbe reducedMotion={reducedMotion} />
        <ContextGuard onPaused={setPaused} />
        <Globe reducedMotion={reducedMotion} />
        {tierSettings(tier).bloom && (
          <EffectComposer>
            <Bloom luminanceThreshold={0.2} intensity={0.6} mipmapBlur />
          </EffectComposer>
        )}
      </Canvas>
      {paused && <p className="notice">3D paused, restoring...</p>}
    </div>
  );
}
