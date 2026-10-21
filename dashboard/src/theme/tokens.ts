// The palette from tokens.css, for the 3D scene and canvas code. Keep the two files in step:
// tokens.test.ts checks that every value here appears in tokens.css.
export const colors = {
  void: "#04070d",
  ink900: "#070c16",
  ink800: "#0b1220",
  ink700: "#111b2e",
  line: "#1b2a44",
  lineStrong: "#5e7899",
  frost: "#e8f4ff",
  mistHi: "#a9bad1",
  mist: "#8fa3bf",
  ice400: "#5dd6ff",
  ice300: "#9be7ff",
  ice700: "#14506b",
  ember400: "#ffb347",
  ember500: "#ff7a3d",
  ember600: "#ff3d2e",
  dangerText: "#ff8a7a",
  verify: "#3df2b1",
  planner: "#8b7cff",
  planner300: "#b7aeff",
} as const;

export type ColorName = keyof typeof colors;
