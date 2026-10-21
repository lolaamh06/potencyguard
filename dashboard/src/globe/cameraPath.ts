// The camera path, driven by scroll progress. Pure: progress in, pose out. The pose is a focus
// point on the globe (latitude, longitude) and a distance; the scene turns it into a position.
import { clamp01 } from "../scroll/chapters";
import { latLonToVec3, type LatLon } from "./geo";

export interface CameraKey {
  /** Progress 0..1 at which this key applies. */
  at: number;
  focus: LatLon;
  distance: number;
}

export interface CameraPose {
  position: [number, number, number];
  /** Where the camera looks (the globe centre, nudged toward the focus so the globe sits off-centre). */
  target: [number, number, number];
  distance: number;
}

/** Smootherstep: zero slope at both ends, so moves start and stop gently. */
export function ease(t: number): number {
  const x = clamp01(t);
  return x * x * x * (x * (x * 6 - 15) + 10);
}

/** Shortest-way interpolation of longitudes (so 170 to -170 turns 20 degrees, not 340). */
export function lerpLon(a: number, b: number, t: number): number {
  let d = (b - a) % 360;
  if (d > 180) d -= 360;
  if (d < -180) d += 360;
  return a + d * t;
}

export const CAMERA_KEYS: readonly CameraKey[] = [
  { at: 0, focus: { lat: 46, lon: 20 }, distance: 3.5 },
  { at: 0.5, focus: { lat: 28, lon: 58 }, distance: 4.0 },
  { at: 1, focus: { lat: 18, lon: 72 }, distance: 5.0 },
];

export function cameraPose(
  progress: number,
  keys: readonly CameraKey[] = CAMERA_KEYS,
  reducedMotion = false,
): CameraPose {
  // Reduced motion: no camera move at all (the scene crossfades per chapter instead).
  const p = reducedMotion ? 0.5 : clamp01(progress);
  let i = 0;
  while (i < keys.length - 2 && p > keys[i + 1].at) i++;
  const a = keys[i];
  const b = keys[Math.min(i + 1, keys.length - 1)];
  const span = b.at - a.at;
  const t = span > 0 ? ease((p - a.at) / span) : 0;
  const lat = a.focus.lat + (b.focus.lat - a.focus.lat) * t;
  const lon = lerpLon(a.focus.lon, b.focus.lon, t);
  const distance = a.distance + (b.distance - a.distance) * t;
  const dir = latLonToVec3(lat, lon);
  return {
    position: [dir[0] * distance, dir[1] * distance, dir[2] * distance],
    target: [dir[0] * 0.08, dir[1] * 0.08, dir[2] * 0.08],
    distance,
  };
}
