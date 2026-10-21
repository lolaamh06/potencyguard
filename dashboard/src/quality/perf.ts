// Live render numbers, written by the render loop and read by the overlay. A plain object, so
// nothing re-renders per frame.
export const perf = {
  fps: 0,
  frameMs: 0,
  calls: 0,
  triangles: 0,
  renderer: "unknown",
  webgl: "none" as string,
  contextLost: false,
};
