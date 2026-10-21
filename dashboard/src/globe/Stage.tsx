// Procedural 3D scenes that live far from the globe in the same canvas: the Prologue's vial in an
// insulated box, and Chapter 5's futures cloud. The camera flies to them (stageCamera.ts). Nothing
// is downloaded; geometry is built here. Cloud points come from the exported samples, and the
// worst-tail lighting only SELECTS by exported rank.
import { useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import { AdditiveBlending, BufferAttribute, CanvasTexture, Color, type Group, type Points } from "three";
import { create } from "zustand";
import type { Chapter5Data } from "../data/story";
import { litFlags, rowForAlpha } from "../data/story";
import { mulberry32 } from "./landPoints";
import { scrollState } from "../scroll/scrollState";
import { colors } from "../theme/tokens";
import { CLOUD_ORIGIN, VIAL_ORIGIN, sceneWeights } from "./stageCamera";
import { useAppStore } from "../app/appStore";

/** The risk level chosen on the Chapter 5 slider (changes only when the viewer moves it). */
export const useAlphaStore = create<{ alpha: number; setAlpha: (a: number) => void }>((set) => ({
  alpha: 0.95,
  setAlpha: (alpha) => set({ alpha }),
}));

/** A soft round sprite, drawn once on a canvas (no image file). */
function softDot(): CanvasTexture {
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const g = c.getContext("2d")!;
  const grad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  grad.addColorStop(0, "rgba(255,255,255,1)");
  grad.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = grad;
  g.fillRect(0, 0, 64, 64);
  return new CanvasTexture(c);
}

function Vapour({ count }: { count: number }) {
  const ref = useRef<Points>(null);
  const sprite = useMemo(softDot, []);
  const seeds = useMemo(() => {
    const rand = mulberry32(7);
    return Array.from({ length: count }, () => ({ x: (rand() - 0.5) * 1.8, z: (rand() - 0.5) * 1.2, phase: rand() * 6.28, speed: 0.04 + rand() * 0.05 }));
  }, [count]);
  const positions = useMemo(() => new Float32Array(count * 3), [count]);
  useFrame(({ clock }) => {
    const reduced = useAppStore.getState().reducedMotion;
    const t = reduced ? 0 : clock.elapsedTime;
    seeds.forEach((s, i) => {
      const rise = (t * s.speed + s.phase) % 1;
      positions[i * 3] = s.x + Math.sin(t * 0.3 + s.phase) * 0.12;
      positions[i * 3 + 1] = 0.55 + rise * 0.9;
      positions[i * 3 + 2] = s.z;
    });
    const attr = ref.current?.geometry.getAttribute("position") as BufferAttribute | undefined;
    if (attr) attr.needsUpdate = true;
  });
  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial map={sprite} color={colors.ice300} size={0.45} sizeAttenuation transparent opacity={0.16} depthWrite={false} blending={AdditiveBlending} />
    </points>
  );
}

/** The box, its lid and one vial. The glow is the shelf life remaining (1 at the start). */
function VialScene({ glow }: { glow: number }) {
  const group = useRef<Group>(null);
  const lid = useRef<Group>(null);
  const liquid = useRef<{ emissiveIntensity: number } | null>(null);
  useFrame(({ clock }) => {
    const w = sceneWeights(scrollState.chapter, scrollState.local);
    if (group.current) group.current.visible = w.vial > 0;
    const reduced = useAppStore.getState().reducedMotion;
    if (lid.current) lid.current.position.y = 0.95 + (scrollState.chapter === 0 ? scrollState.local * 1.4 : 1.4);
    if (liquid.current) liquid.current.emissiveIntensity = (0.55 + 0.35 * glow) * (reduced ? 1 : 0.92 + 0.08 * Math.sin(clock.elapsedTime * 1.6));
  });
  const wall = { color: colors.ink700, roughness: 0.95, metalness: 0 } as const;
  return (
    <group ref={group} position={VIAL_ORIGIN}>
      <ambientLight intensity={0.5} />
      <pointLight position={[1.2, 1.4, 1.6]} intensity={7} color={colors.ice300} distance={9} />
      <pointLight position={[-1.6, 0.4, -0.8]} intensity={3} color={colors.planner300} distance={8} />
      {/* foam walls and floor of the insulated box */}
      <mesh position={[0, -0.5, 0]}><boxGeometry args={[2.2, 0.12, 1.6]} /><meshStandardMaterial {...wall} /></mesh>
      <mesh position={[-1.06, 0.3, 0]}><boxGeometry args={[0.12, 1.6, 1.6]} /><meshStandardMaterial {...wall} /></mesh>
      <mesh position={[1.06, 0.3, 0]}><boxGeometry args={[0.12, 1.6, 1.6]} /><meshStandardMaterial {...wall} /></mesh>
      <mesh position={[0, 0.3, -0.76]}><boxGeometry args={[2.2, 1.6, 0.12]} /><meshStandardMaterial {...wall} /></mesh>
      {/* frosted lid that lifts as the camera pulls back */}
      <group ref={lid} position={[0, 0.95, 0]}>
        <mesh><boxGeometry args={[2.3, 0.1, 1.7]} /><meshStandardMaterial color={colors.frost} roughness={0.85} transparent opacity={0.28} depthWrite={false} /></mesh>
      </group>
      {/* the vial: glass, liquid, cap */}
      <mesh position={[0, -0.05, 0]}><cylinderGeometry args={[0.2, 0.2, 0.95, 32]} /><meshStandardMaterial color={colors.ice300} roughness={0.1} transparent opacity={0.2} depthWrite={false} /></mesh>
      <mesh position={[0, -0.2, 0]}>
        <cylinderGeometry args={[0.165, 0.165, 0.55, 32]} />
        <meshStandardMaterial ref={liquid as never} color={colors.ice400} emissive={new Color(colors.ice400)} emissiveIntensity={0.8} roughness={0.3} />
      </mesh>
      <mesh position={[0, 0.5, 0]}><cylinderGeometry args={[0.13, 0.17, 0.12, 24]} /><meshStandardMaterial color={colors.mistHi} roughness={0.5} metalness={0.4} /></mesh>
      <Vapour count={140} />
    </group>
  );
}

/** Futures cloud: two clusters, the worst tail in the planner colour. Colours are rewritten only when the slider moves. */
function CloudCluster({ data, name, x }: { data: Chapter5Data; name: "continue" | "reroute"; x: number }) {
  const action = data.actions[name];
  const n = data.n_points;
  const ref = useRef<Points>(null);
  const layout = useMemo(() => {
    const rand = mulberry32(name === "continue" ? 11 : 23);
    const pos = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) {
      const failed = action.failed[i] === 1;
      pos[i * 3] = (rand() - 0.5) * 3.0;
      pos[i * 3 + 1] = (failed ? 1.5 : -1.2 + action.cost / data.V) + (rand() - 0.5) * 0.9;
      pos[i * 3 + 2] = (rand() - 0.5) * 0.8;
    }
    return pos;
  }, [action, n, data.V, name]);
  const colorsArr = useMemo(() => new Float32Array(n * 3), [n]);
  const alpha = useAlphaStore((s) => s.alpha);
  useEffect(() => {
    const row = rowForAlpha(data.rows, alpha);
    const lit = litFlags(action.rank, row.tail_points);
    const dim = new Color(colors.ice700);
    const base = new Color(colors.ice400).multiplyScalar(0.55);
    const tail = new Color(colors.planner300);
    for (let i = 0; i < n; i++) {
      const c = lit[i] ? tail : action.failed[i] ? dim.clone().lerp(new Color(colors.ember500), 0.35) : base;
      colorsArr[i * 3] = c.r;
      colorsArr[i * 3 + 1] = c.g;
      colorsArr[i * 3 + 2] = c.b;
    }
    const attr = ref.current?.geometry.getAttribute("color") as BufferAttribute | undefined;
    if (attr) attr.needsUpdate = true;
  }, [alpha, action, data.rows, n, colorsArr]);
  return (
    <points ref={ref} position={[x, 0, 0]}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[layout, 3]} />
        <bufferAttribute attach="attributes-color" args={[colorsArr, 3]} />
      </bufferGeometry>
      <pointsMaterial vertexColors size={0.07} sizeAttenuation transparent opacity={0.95} depthWrite={false} blending={AdditiveBlending} />
    </points>
  );
}

function FuturesCloud({ data }: { data: Chapter5Data }) {
  const group = useRef<Group>(null);
  useFrame(() => {
    if (group.current) group.current.visible = sceneWeights(scrollState.chapter, scrollState.local).cloud > 0;
  });
  return (
    <group ref={group} position={CLOUD_ORIGIN}>
      <CloudCluster data={data} name="continue" x={-2.4} />
      <CloudCluster data={data} name="reroute" x={2.4} />
    </group>
  );
}

export function Stage({ cloud, glow }: { cloud: Chapter5Data | null; glow: number }) {
  return (
    <>
      <VialScene glow={glow} />
      {cloud && <FuturesCloud data={cloud} />}
    </>
  );
}
