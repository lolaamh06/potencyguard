import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { CSS_VARS, DARK, LIGHT, PAIRS, PALETTES, contrast, type ThemeName } from "./palette";

const dark = readFileSync(new URL("./tokens.css", import.meta.url), "utf-8").toLowerCase();
const light = readFileSync(new URL("./tokens-light.css", import.meta.url), "utf-8").toLowerCase();

describe.each([["dark", DARK], ["light", LIGHT]] as const)("contrast in the %s theme (WCAG 2.x)", (name, palette) => {
  for (const pair of PAIRS) {
    it(`${pair.role}: ${pair.fg} on ${pair.bg} is at least ${pair.min}:1`, () => {
      const ratio = contrast(palette[pair.fg], palette[pair.bg]);
      expect(ratio, `${name} ${pair.fg} on ${pair.bg} = ${ratio.toFixed(2)}`).toBeGreaterThanOrEqual(pair.min);
    });
  }
});

describe("the CSS holds the same values as the palettes", () => {
  it.each(["dark", "light"] as ThemeName[])("%s", (name) => {
    const css = name === "dark" ? dark : light;
    for (const key of Object.keys(CSS_VARS) as (keyof typeof DARK)[]) {
      const line = new RegExp(`${CSS_VARS[key]}: *(#[0-9a-f]{6})`).exec(css);
      expect(line, `${name} ${CSS_VARS[key]}`).not.toBeNull();
      expect(line![1]).toBe(PALETTES[name][key].toLowerCase());
    }
  });

  it("covers every status colour with a label rule: status colours are never the only signal", () => {
    // enforced in the components (icon plus word); here: each status colour exists in both themes
    for (const k of ["ember400", "dangerText", "verify", "planner300"] as const) {
      expect(DARK[k]).toMatch(/^#/);
      expect(LIGHT[k]).toMatch(/^#/);
    }
  });
});
