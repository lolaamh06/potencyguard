import { describe, expect, it } from "vitest";
import { CAMERA_KEYS, cameraPose, ease, lerpLon } from "./cameraPath";
import { angleBetween, latLonToVec3, maskValueAt, routePoints, slerp, vec3ToLatLon } from "./geo";
import { mulberry32, sampleLandPoints, starPositions } from "./landPoints";

describe("geo", () => {
  it("puts the poles and the equator where they belong", () => {
    expect(latLonToVec3(90, 0)[1]).toBeCloseTo(1, 12);
    expect(latLonToVec3(0, 0)).toEqual([0, 0, 1]);
    const east = latLonToVec3(0, 90);
    expect(east[0]).toBeCloseTo(1, 12);
    expect(east[2]).toBeCloseTo(0, 12);
  });

  it("round-trips latitude and longitude", () => {
    for (const [lat, lon] of [
      [50.11, 8.68],
      [-33.9, 151.2],
      [1.35, 103.82],
      [0, -179],
    ]) {
      const v = latLonToVec3(lat, lon);
      const back = vec3ToLatLon(v[0], v[1], v[2]);
      expect(back.lat).toBeCloseTo(lat, 9);
      expect(back.lon).toBeCloseTo(lon, 9);
    }
  });

  it("slerp stays on the sphere and hits both ends", () => {
    const a = latLonToVec3(50, 8);
    const b = latLonToVec3(1, 103);
    expect(slerp(a, b, 0)[0]).toBeCloseTo(a[0], 12);
    expect(slerp(a, b, 1)[2]).toBeCloseTo(b[2], 12);
    const m = slerp(a, b, 0.37);
    expect(Math.hypot(m[0], m[1], m[2])).toBeCloseTo(1, 12);
    expect(slerp(a, a, 0.5)[1]).toBeCloseTo(a[1], 12);
  });

  it("measures a quarter turn along the equator", () => {
    expect(angleBetween({ lat: 0, lon: 0 }, { lat: 0, lon: 90 })).toBeCloseTo(Math.PI / 2, 12);
  });

  it("builds an arc that leaves and arrives at the surface and rises in between", () => {
    const pts = routePoints({ lat: 50, lon: 8 }, { lat: 1, lon: 103 }, 64, 0.2);
    expect(pts).toHaveLength(65);
    const r = (p: number[]) => Math.hypot(p[0], p[1], p[2]);
    expect(r(pts[0])).toBeCloseTo(1, 12);
    expect(r(pts[64])).toBeCloseTo(1, 12);
    expect(r(pts[32])).toBeCloseTo(1.2, 6);
  });

  it("routes through a waypoint when asked", () => {
    const via = { lat: 25, lon: 55 };
    const pts = routePoints({ lat: 50, lon: 8 }, { lat: 1, lon: 103 }, 64, 0, via);
    const mid = vec3ToLatLon(pts[32][0], pts[32][1], pts[32][2]);
    expect(mid.lat).toBeCloseTo(25, 6);
    expect(mid.lon).toBeCloseTo(55, 6);
  });

  it("reads the mask at a latitude and longitude, clamping the edges", () => {
    const mask = new Uint8Array(4 * 2);
    mask[0] = 255; // top-left: lat > 0, lon < 0
    expect(maskValueAt(mask, 4, 2, 45, -135)).toBe(255);
    expect(maskValueAt(mask, 4, 2, -45, 135)).toBe(0);
    expect(maskValueAt(mask, 4, 2, 90, -180)).toBe(255);
    expect(maskValueAt(mask, 4, 2, -90, 180)).toBe(0);
  });
});

describe("land points and stars", () => {
  it("keeps points only where there is land", () => {
    const w = 64;
    const h = 32;
    const mask = new Uint8Array(w * h);
    for (let row = 0; row < h / 2; row++) for (let col = 0; col < w; col++) mask[row * w + col] = 255; // north
    const pts = sampleLandPoints(mask, w, h, 2000);
    expect(pts.length % 3).toBe(0);
    expect(pts.length / 3).toBeGreaterThan(900);
    expect(pts.length / 3).toBeLessThan(1100);
    for (let i = 0; i < pts.length; i += 3) {
      expect(pts[i + 1]).toBeGreaterThanOrEqual(-1e-6);
      expect(Math.hypot(pts[i], pts[i + 1], pts[i + 2])).toBeCloseTo(1, 5);
    }
  });

  it("gives nothing for an all-sea mask", () => {
    expect(sampleLandPoints(new Uint8Array(16 * 8), 16, 8, 500)).toHaveLength(0);
  });

  it("makes the same stars every time, on a shell", () => {
    const a = starPositions(100, 30);
    const b = starPositions(100, 30);
    expect(Array.from(a)).toEqual(Array.from(b));
    for (let i = 0; i < a.length; i += 3) {
      const r = Math.hypot(a[i], a[i + 1], a[i + 2]);
      expect(r).toBeGreaterThanOrEqual(27 - 1e-3);
      expect(r).toBeLessThanOrEqual(33 + 1e-3);
    }
    const rand = mulberry32(1);
    const v = rand();
    expect(v).toBeGreaterThanOrEqual(0);
    expect(v).toBeLessThan(1);
  });
});

describe("camera path", () => {
  it("eases with zero slope at the ends and is monotone", () => {
    expect(ease(0)).toBe(0);
    expect(ease(1)).toBe(1);
    expect(ease(0.5)).toBeCloseTo(0.5, 12);
    expect(ease(-1)).toBe(0);
    expect(ease(2)).toBe(1);
    expect(ease(0.05)).toBeLessThan(0.05);
    let prev = -1;
    for (let i = 0; i <= 20; i++) {
      const v = ease(i / 20);
      expect(v).toBeGreaterThanOrEqual(prev);
      prev = v;
    }
  });

  it("turns the short way round the globe", () => {
    expect(lerpLon(170, -170, 0.5)).toBeCloseTo(180, 9);
    expect(lerpLon(-170, 170, 0.5)).toBeCloseTo(-180, 9);
    expect(lerpLon(10, 50, 0.25)).toBeCloseTo(20, 9);
  });

  it("starts close, ends far, and moves smoothly", () => {
    const start = cameraPose(0);
    const end = cameraPose(1);
    expect(start.distance).toBeCloseTo(CAMERA_KEYS[0].distance, 9);
    expect(end.distance).toBeCloseTo(CAMERA_KEYS[2].distance, 9);
    expect(Math.hypot(...start.position)).toBeCloseTo(start.distance, 9);
    let prev = cameraPose(0).distance;
    for (let i = 1; i <= 100; i++) {
      const d = cameraPose(i / 100).distance;
      expect(d).toBeGreaterThanOrEqual(prev - 1e-9);
      expect(Math.abs(d - prev)).toBeLessThan(0.1);
      prev = d;
    }
  });

  it("clamps progress and does not move at all under reduced motion", () => {
    expect(cameraPose(-3).distance).toBeCloseTo(cameraPose(0).distance, 12);
    expect(cameraPose(9).distance).toBeCloseTo(cameraPose(1).distance, 12);
    expect(cameraPose(0, CAMERA_KEYS, true).position).toEqual(cameraPose(1, CAMERA_KEYS, true).position);
  });
});
