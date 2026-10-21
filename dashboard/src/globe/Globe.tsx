// The night globe: land dots from the mask, a dark body, an atmosphere rim, stars, and the route.
// Geometry and materials are declared in JSX, so React Three Fiber disposes them on unmount.
// Nothing here uses React state per frame; the pulse time is a uniform updated in useFrame.
import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import { AdditiveBlending, BackSide, CatmullRomCurve3, Color, NormalBlending, Vector3, type ShaderMaterial } from "three";
import { useAppStore } from "../app/appStore";
import { tierSettings, type Tier } from "../quality/governor";
import { useGlobeTheme } from "./useGlobeTheme";
import type { Palette } from "../theme/palette";
import { routePoints } from "./geo";
import { sampleLandPoints, starPositions } from "./landPoints";
import {
  ATMOSPHERE_FRAGMENT,
  BODY_FRAGMENT,
  BODY_VERTEX,
  DOT_FRAGMENT,
  DOT_VERTEX,
  ROUTE_FRAGMENT,
  ROUTE_VERTEX,
} from "./shaders";
import type { GlobeProps, RouteState } from "./types";
import type { LandMask } from "./useLandMask";

const routeColor = (state: RouteState, c: Palette): string => ({ safe: c.ice400, warning: c.ember400, danger: c.ember600 })[state];
const ARC_LIFT = 0.16;
const SEGMENTS = 160;

function Stars({ count }: { count: number }) {
  const { colors } = useGlobeTheme();
  const positions = useMemo(() => starPositions(count, 30), [count]);
  if (count === 0) return null;
  return (
    <points>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial color={colors.frost} size={0.1} sizeAttenuation transparent opacity={0.5} depthWrite={false} />
    </points>
  );
}

function LandDots({ mask, samples, pixelRatio }: { mask: LandMask; samples: number; pixelRatio: number }) {
  const { theme, colors } = useGlobeTheme();
  const positions = useMemo(() => sampleLandPoints(mask.data, mask.width, mask.height, samples), [mask, samples]);
  const uniforms = useMemo(
    () => ({
      uColor: { value: new Color(colors.ice400) },
      uOpacity: { value: 0.95 },
      uSize: { value: 7.5 },
      uPixelRatio: { value: pixelRatio },
    }),
    [pixelRatio, colors],
  );
  return (
    <points key={positions.length}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <shaderMaterial
        vertexShader={DOT_VERTEX}
        fragmentShader={DOT_FRAGMENT}
        uniforms={uniforms}
        transparent
        depthWrite={false}
        blending={theme === "dark" ? AdditiveBlending : NormalBlending}
      />
    </points>
  );
}

function Body() {
  const { colors } = useGlobeTheme();
  const uniforms = useMemo(
    () => ({ uBase: { value: new Color(colors.ink900) }, uRim: { value: new Color(colors.ice700) } }),
    [colors],
  );
  return (
    <mesh>
      <sphereGeometry args={[0.985, 64, 48]} />
      <shaderMaterial vertexShader={BODY_VERTEX} fragmentShader={BODY_FRAGMENT} uniforms={uniforms} />
    </mesh>
  );
}

function Atmosphere() {
  const { theme, colors } = useGlobeTheme();
  const uniforms = useMemo(
    () => ({ uColor: { value: new Color(colors.ice400) }, uStrength: { value: theme === "dark" ? 0.7 : 0.45 } }),
    [colors, theme],
  );
  return (
    <mesh scale={1.035}>
      <sphereGeometry args={[1, 64, 48]} />
      <shaderMaterial
        vertexShader={BODY_VERTEX}
        fragmentShader={ATMOSPHERE_FRAGMENT}
        uniforms={uniforms}
        side={BackSide}
        transparent
        depthWrite={false}
        blending={theme === "dark" ? AdditiveBlending : NormalBlending}
      />
    </mesh>
  );
}

interface ArcProps {
  points: [number, number, number][];
  color: string;
  dashed: boolean;
  progress: number;
}

function Arc({ points, color, dashed, progress }: ArcProps) {
  const curve = useMemo(() => new CatmullRomCurve3(points.map((p) => new Vector3(...p))), [points]);
  const material = useRef<ShaderMaterial>(null);
  const uniforms = useMemo(
    () => ({
      uColor: { value: new Color(color) },
      uTime: { value: 0 },
      uDashed: { value: dashed ? 1 : 0 },
      uProgress: { value: progress },
    }),
    [color, dashed, progress],
  );
  useFrame((_, delta) => {
    const reduced = useAppStore.getState().reducedMotion;
    if (material.current && !reduced) material.current.uniforms.uTime.value += delta;
  });
  return (
    <mesh>
      <tubeGeometry args={[curve, SEGMENTS, dashed ? 0.003 : 0.0042, 6, false]} />
      <shaderMaterial
        ref={material}
        vertexShader={ROUTE_VERTEX}
        fragmentShader={ROUTE_FRAGMENT}
        uniforms={uniforms}
        transparent
        depthWrite={false}
      />
    </mesh>
  );
}

function Node({ position, color, radius = 0.016 }: { position: [number, number, number]; color: string; radius?: number }) {
  return (
    <mesh position={position}>
      <sphereGeometry args={[radius, 16, 12]} />
      <meshBasicMaterial color={color} />
    </mesh>
  );
}

export interface GlobeSceneContentProps extends GlobeProps {
  mask: LandMask | null;
  tier: Tier;
  pixelRatio: number;
}

export function Globe({ mask, tier, pixelRatio, routeState, showAlternative, shipmentProgress, origin, destination, alternativeVia }: GlobeSceneContentProps) {
  const { theme, colors } = useGlobeTheme();
  const settings = tierSettings(tier);
  const main = useMemo(() => routePoints(origin, destination, SEGMENTS, ARC_LIFT), [origin, destination]);
  const alt = useMemo(() => routePoints(origin, destination, SEGMENTS, ARC_LIFT * 0.8, alternativeVia), [origin, destination, alternativeVia]);
  const startPos = main[0];
  const endPos = main[main.length - 1];
  const marker = shipmentProgress === null ? null : main[Math.round(Math.min(Math.max(shipmentProgress, 0), 1) * SEGMENTS)];
  return (
    <group>
      <Stars count={theme === "dark" ? settings.stars : 0} />
      <Body />
      {mask && <LandDots mask={mask} samples={settings.dotSamples} pixelRatio={pixelRatio} />}
      <Atmosphere />
      <Arc points={main} color={routeColor(routeState, colors)} dashed={false} progress={shipmentProgress ?? 1} />
      {showAlternative && <Arc points={alt} color={colors.planner300} dashed progress={1} />}
      <Node position={startPos} color={colors.ice300} />
      <Node position={endPos} color={colors.ice300} />
      {marker && <Node position={marker} color={routeColor(routeState, colors)} radius={0.026} />}
    </group>
  );
}
