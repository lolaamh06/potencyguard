// Dot-matrix globe: evenly spread points over the sphere (a Fibonacci lattice), kept where the
// land mask says land. Pure, so it is tested without a GPU. The sphere has the same dot density
// everywhere; there is no per-frame work.
import { maskValueAt, vec3ToLatLon } from "./geo";

/** Seeded pseudo-random numbers (mulberry32), so the stars are the same on every load. */
export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Land dot positions (x, y, z on the unit sphere) from `samples` lattice points. */
export function sampleLandPoints(
  mask: Uint8Array | Uint8ClampedArray,
  width: number,
  height: number,
  samples: number,
  threshold = 128,
): Float32Array {
  const golden = Math.PI * (3 - Math.sqrt(5));
  const out: number[] = [];
  for (let i = 0; i < samples; i++) {
    const y = 1 - (2 * (i + 0.5)) / samples;
    const r = Math.sqrt(1 - y * y);
    const theta = golden * i;
    const x = Math.sin(theta) * r;
    const z = Math.cos(theta) * r;
    const { lat, lon } = vec3ToLatLon(x, y, z);
    if (maskValueAt(mask, width, height, lat, lon) >= threshold) out.push(x, y, z);
  }
  return new Float32Array(out);
}

/** Star positions on a large shell, seeded. */
export function starPositions(count: number, radius: number, seed = 20261021): Float32Array {
  const rand = mulberry32(seed);
  const out = new Float32Array(count * 3);
  for (let i = 0; i < count; i++) {
    const u = rand() * 2 - 1;
    const phi = rand() * Math.PI * 2;
    const s = Math.sqrt(1 - u * u);
    const r = radius * (0.9 + rand() * 0.2);
    out[i * 3] = Math.cos(phi) * s * r;
    out[i * 3 + 1] = u * r;
    out[i * 3 + 2] = Math.sin(phi) * s * r;
  }
  return out;
}
