import { describe, expect, it } from "vitest";
import { KEYS, READING_MODES, THEME_CHOICES, loadPref, resolveTheme, savePref, type StorageLike } from "./prefs";

const memory = (): StorageLike & { data: Record<string, string> } => {
  const data: Record<string, string> = {};
  return { data, getItem: (k) => (k in data ? data[k] : null), setItem: (k, v) => void (data[k] = v) };
};

describe("preference storage", () => {
  it("saves and reads back an allowed value", () => {
    const s = memory();
    expect(savePref(KEYS.theme, "light", s)).toBe(true);
    expect(loadPref(KEYS.theme, THEME_CHOICES, "system", s)).toBe("light");
    savePref(KEYS.mode, "technical", s);
    expect(loadPref(KEYS.mode, READING_MODES, "simple", s)).toBe("technical");
  });

  it("falls back to the default for a missing or unknown value", () => {
    const s = memory();
    expect(loadPref(KEYS.theme, THEME_CHOICES, "system", s)).toBe("system");
    s.data[KEYS.theme] = "purple";
    expect(loadPref(KEYS.theme, THEME_CHOICES, "system", s)).toBe("system");
    expect(loadPref(KEYS.mode, READING_MODES, "simple", s)).toBe("simple");
  });

  it("survives storage that throws or is missing", () => {
    const broken: StorageLike = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("full");
      },
    };
    expect(loadPref(KEYS.theme, THEME_CHOICES, "system", broken)).toBe("system");
    expect(savePref(KEYS.theme, "dark", broken)).toBe(false);
    expect(loadPref(KEYS.theme, THEME_CHOICES, "dark", null)).toBe("dark");
    expect(savePref(KEYS.theme, "dark", null)).toBe(false);
  });

  it("defaults the reading mode to simple", () => {
    expect(loadPref(KEYS.mode, READING_MODES, "simple", memory())).toBe("simple");
  });

  it("resolves System with the operating system setting", () => {
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
    expect(resolveTheme("light", true)).toBe("light");
    expect(resolveTheme("dark", false)).toBe("dark");
  });
});
