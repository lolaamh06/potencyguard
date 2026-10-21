// Camera poses for every scene, as a pure function of the chapter on screen and the position
// inside it. The globe keeps its own scroll path (cameraPath.ts); the vial and the futures cloud
// sit in far-away regions of the same canvas and the camera flies there and back.
import { ease } from "./cameraPath";
import type { CameraPose } from "./cameraPath";

export type Vec = [number, number, number];

/** Fixed regions of the stage. The globe is at the origin. */
export const VIAL_ORIGIN: Vec = [0, -40, 0];
export const CLOUD_ORIGIN: Vec = [0, 0, -90];

const VIAL_POSE: CameraPose = {
  position: [0.9, -39.45, 4.4],
  target: [-0.6, -39.95, 0],
  distance: 4.5,
};
const CLOUD_POSE: CameraPose = {
  position: [0.2, 2.2, -90 + 11],
  target: [0.2, 2.5, -90],
  distance: 11,
};

export const POSES = { vial: VIAL_POSE, cloud: CLOUD_POSE } as const;

function mix(a: Vec, b: Vec, t: number): Vec {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
}

export function mixPose(a: CameraPose, b: CameraPose, t: number): CameraPose {
  const k = ease(t);
  return {
    position: mix(a.position, b.position, k),
    target: mix(a.target, b.target, k),
    distance: a.distance + (b.distance - a.distance) * k,
  };
}

/** Which far scene is in view and how much (0 to 1), by chapter index and position inside it. */
export function sceneWeights(chapter: number, t: number): { vial: number; cloud: number } {
  const clamp = (x: number) => Math.min(1, Math.max(0, x));
  let vial = 0;
  let cloud = 0;
  if (chapter === 0) vial = 1 - clamp((t - 0.35) / 0.65);
  if (chapter === 5) cloud = t < 0.12 ? clamp(t / 0.12) : t > 0.92 ? 1 - clamp((t - 0.92) / 0.08) : 1;
  return { vial, cloud };
}

/** The camera pose: from the far scenes to the globe pose given for this moment. */
export function stageCamera(chapter: number, t: number, globePose: CameraPose, reduced: boolean): CameraPose {
  const w = sceneWeights(chapter, t);
  if (reduced) {
    // no flight: a still pose per scene (the picture crossfades instead)
    if (w.cloud > 0.5) return CLOUD_POSE;
    if (w.vial > 0.5) return VIAL_POSE;
    return globePose;
  }
  if (w.vial > 0) return mixPose(globePose, VIAL_POSE, w.vial);
  if (w.cloud > 0) return mixPose(globePose, CLOUD_POSE, w.cloud);
  return globePose;
}
