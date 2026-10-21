// Pure geometry for the globe: latitude and longitude on a unit sphere, great-circle arcs and
// the mask lookup. No three.js, so it runs and is tested in plain Node. y is up; longitude 0
// faces +z and longitude 90 east faces +x.

export type Vec3 = readonly [number, number, number];

export interface LatLon {
  lat: number;
  lon: number;
}

const DEG = Math.PI / 180;

export function latLonToVec3(lat: number, lon: number, radius = 1): [number, number, number] {
  const phi = lat * DEG;
  const lambda = lon * DEG;
  return [
    radius * Math.cos(phi) * Math.sin(lambda),
    radius * Math.sin(phi),
    radius * Math.cos(phi) * Math.cos(lambda),
  ];
}

export function vec3ToLatLon(x: number, y: number, z: number): LatLon {
  const r = Math.hypot(x, y, z) || 1;
  return { lat: Math.asin(Math.max(-1, Math.min(1, y / r))) / DEG, lon: Math.atan2(x, z) / DEG };
}

function normalise(v: Vec3): [number, number, number] {
  const n = Math.hypot(v[0], v[1], v[2]) || 1;
  return [v[0] / n, v[1] / n, v[2] / n];
}

/** Spherical interpolation between two unit vectors (the great-circle path), t in 0..1. */
export function slerp(a: Vec3, b: Vec3, t: number): [number, number, number] {
  const na = normalise(a);
  const nb = normalise(b);
  const dot = Math.max(-1, Math.min(1, na[0] * nb[0] + na[1] * nb[1] + na[2] * nb[2]));
  const omega = Math.acos(dot);
  if (omega < 1e-9) return na;
  const s = Math.sin(omega);
  const wa = Math.sin((1 - t) * omega) / s;
  const wb = Math.sin(t * omega) / s;
  return [wa * na[0] + wb * nb[0], wa * na[1] + wb * nb[1], wa * na[2] + wb * nb[2]];
}

/** Central angle between two points, in radians. */
export function angleBetween(a: LatLon, b: LatLon): number {
  const va = latLonToVec3(a.lat, a.lon);
  const vb = latLonToVec3(b.lat, b.lon);
  return Math.acos(Math.max(-1, Math.min(1, va[0] * vb[0] + va[1] * vb[1] + va[2] * vb[2])));
}

/**
 * Points of a route arc from `from` to `to` (through `via` when given), lifted above the surface
 * by `lift * sin(pi t)` so the route reads as an arc, not a line on the ground.
 */
export function routePoints(
  from: LatLon,
  to: LatLon,
  segments: number,
  lift: number,
  via?: LatLon,
): [number, number, number][] {
  const points: [number, number, number][] = [];
  const a = latLonToVec3(from.lat, from.lon);
  const b = latLonToVec3(to.lat, to.lon);
  const m = via ? latLonToVec3(via.lat, via.lon) : null;
  for (let i = 0; i <= segments; i++) {
    const t = i / segments;
    let p: [number, number, number];
    if (m) {
      p = t < 0.5 ? slerp(a, m, t * 2) : slerp(m, b, (t - 0.5) * 2);
    } else {
      p = slerp(a, b, t);
    }
    const radius = 1 + lift * Math.sin(Math.PI * t);
    points.push([p[0] * radius, p[1] * radius, p[2] * radius]);
  }
  return points;
}

/** The mask value (0..255) at a latitude and longitude. The mask is equirectangular, row 0 north. */
export function maskValueAt(
  mask: Uint8Array | Uint8ClampedArray,
  width: number,
  height: number,
  lat: number,
  lon: number,
): number {
  const col = Math.min(width - 1, Math.max(0, Math.floor(((lon + 180) / 360) * width)));
  const row = Math.min(height - 1, Math.max(0, Math.floor(((90 - lat) / 180) * height)));
  return mask[row * width + col];
}
