import { describe, expect, it } from "vitest";
import { cameraPose } from "./cameraPath";
import { POSES, sceneWeights, stageCamera } from "./stageCamera";

const globe = cameraPose(0.3);
const near = (a: number[], b: number[]) => a.forEach((v, i) => expect(v).toBeCloseTo(b[i], 9));

describe("stage camera", () => {
  it("starts on the vial, leaves it by 35 percent of the Prologue and is on the globe after", () => {
    expect(sceneWeights(0, 0).vial).toBe(1);
    expect(sceneWeights(0, 0.35).vial).toBe(1);
    expect(sceneWeights(0, 1).vial).toBe(0);
    near(stageCamera(0, 0, globe, false).position, POSES.vial.position);
    near(stageCamera(0, 1, globe, false).position, globe.position);
  });

  it("is at the futures cloud during Chapter 5 and on the globe elsewhere", () => {
    expect(sceneWeights(5, 0.5).cloud).toBe(1);
    expect(sceneWeights(5, 0).cloud).toBeCloseTo(0, 9);
    expect(sceneWeights(5, 1).cloud).toBeCloseTo(0, 9);
    for (const chapter of [1, 2, 3, 4, 6, 7]) {
      near(stageCamera(chapter, 0.5, globe, false).position, globe.position);
    }
    near(stageCamera(5, 0.5, globe, false).position, POSES.cloud.position);
  });

  it("moves smoothly between poses", () => {
    let prev = stageCamera(0, 0.35, globe, false).position;
    for (let i = 1; i <= 50; i++) {
      const p = stageCamera(0, 0.35 + (0.65 * i) / 50, globe, false).position;
      expect(Math.hypot(p[0] - prev[0], p[1] - prev[1], p[2] - prev[2])).toBeLessThan(6);
      prev = p;
    }
  });

  it("does not fly under reduced motion", () => {
    near(stageCamera(0, 0.5, globe, true).position, POSES.vial.position);
    near(stageCamera(0, 0.9, globe, true).position, globe.position);
    near(stageCamera(5, 0.5, globe, true).position, POSES.cloud.position);
  });
});
