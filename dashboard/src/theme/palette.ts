// The two palettes as hex, for the 3D scene, the canvas charts and the contrast test. The CSS
// variables in tokens.css (dark) and tokens-light.css (light) must hold the same values; a test checks.
export type ThemeName = "dark" | "light";

export interface Palette {
  void: string;
  ink900: string;
  ink800: string;
  ink700: string;
  line: string;
  lineStrong: string;
  frost: string;
  mistHi: string;
  mist: string;
  ice400: string;
  ice300: string;
  ice700: string;
  ember400: string;
  ember500: string;
  ember600: string;
  dangerText: string;
  verify: string;
  planner: string;
  planner300: string;
}

export const DARK: Palette = {
  void: "#04070d", ink900: "#070c16", ink800: "#0b1220", ink700: "#111b2e", line: "#1b2a44", lineStrong: "#5e7899",
  frost: "#e8f4ff", mistHi: "#a9bad1", mist: "#8fa3bf", ice400: "#5dd6ff", ice300: "#9be7ff", ice700: "#14506b",
  ember400: "#ffb347", ember500: "#ff7a3d", ember600: "#ff3d2e", dangerText: "#ff8a7a", verify: "#3df2b1", planner: "#8b7cff", planner300: "#b7aeff",
};

/** Light: surfaces are pale, text and accents are dark enough for the contrast rules (see palette.test.ts). */
export const LIGHT: Palette = {
  void: "#eef3f9", ink900: "#ffffff", ink800: "#f7fafd", ink700: "#e4ecf6", line: "#cdd8e6", lineStrong: "#5b6f8a",
  frost: "#0b1b2e", mistHi: "#33445b", mist: "#4a5d75", ice400: "#0a6fa0", ice300: "#0b5c86", ice700: "#cfe6f3",
  ember400: "#8a5100", ember500: "#a84400", ember600: "#c0281a", dangerText: "#b3261e", verify: "#0b7a55", planner: "#5545d0", planner300: "#4535b8",
};

export const PALETTES: Record<ThemeName, Palette> = { dark: DARK, light: LIGHT };

/** CSS variable name for each palette key (the same names in both themes). */
export const CSS_VARS: Record<keyof Palette, string> = {
  void: "--void", ink900: "--ink-900", ink800: "--ink-800", ink700: "--ink-700", line: "--line", lineStrong: "--line-strong",
  frost: "--frost", mistHi: "--mist-hi", mist: "--mist", ice400: "--ice-400", ice300: "--ice-300", ice700: "--ice-700",
  ember400: "--ember-400", ember500: "--ember-500", ember600: "--ember-600", dangerText: "--danger-text", verify: "--verify",
  planner: "--planner", planner300: "--planner-300",
};

function lin(c: number): number {
  const v = c / 255;
  return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
}

export function luminance(hex: string): number {
  const h = hex.replace("#", "");
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

/** WCAG 2.x contrast ratio between two hex colours. */
export function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

export interface Pair {
  fg: keyof Palette;
  bg: keyof Palette;
  min: number;
  role: string;
}

const SURFACES: (keyof Palette)[] = ["void", "ink900", "ink800", "ink700"];

/** Every text/background pair the app uses, with the rule it must meet (7 for body text, 4.5 for large text and status colours). */
export const PAIRS: Pair[] = [
  ...SURFACES.flatMap((bg): Pair[] => [
    { fg: "frost", bg, min: 7, role: "primary text" },
    { fg: "mistHi", bg, min: 7, role: "secondary text" },
  ]),
  ...(["void", "ink900", "ink800"] as const).flatMap((bg): Pair[] => [
    { fg: "mist", bg, min: 4.5, role: "tertiary and large text" },
    { fg: "ice400", bg, min: 4.5, role: "accent text" },
    { fg: "ember400", bg, min: 4.5, role: "warning text" },
    { fg: "dangerText", bg, min: 4.5, role: "danger text" },
    { fg: "verify", bg, min: 4.5, role: "good text" },
    { fg: "planner300", bg, min: 4.5, role: "recommendation text" },
  ]),
  { fg: "lineStrong", bg: "ink900", min: 3, role: "control borders" },
];
