import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { colors } from "./tokens";

const css = readFileSync(new URL("./tokens.css", import.meta.url), "utf-8");

describe("design tokens", () => {
  it("every colour exported to TypeScript is defined in tokens.css", () => {
    const lower = css.toLowerCase();
    for (const [name, value] of Object.entries(colors)) {
      expect(lower.includes(value.toLowerCase()), `${name} ${value}`).toBe(true);
    }
  });

  it("uses the three decided font families and no external font host", () => {
    expect(css).toContain('"Fraunces"');
    expect(css).toContain('"Inter"');
    expect(css).toContain('"JetBrains Mono"');
    expect(css).not.toMatch(/https?:\/\//);
  });
});
