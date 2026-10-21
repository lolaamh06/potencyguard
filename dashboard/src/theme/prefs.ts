// Remembered preferences (theme, Simple/Technical, tour). Every read and write is guarded: storage
// can be missing, blocked or full, and the app must still work with the defaults.
export interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

export function loadPref<T extends string>(key: string, allowed: readonly T[], fallback: T, storage?: StorageLike | null): T {
  try {
    const store = storage === undefined ? window.localStorage : storage;
    const value = store?.getItem(key);
    return value !== null && value !== undefined && (allowed as readonly string[]).includes(value) ? (value as T) : fallback;
  } catch {
    return fallback;
  }
}

export function savePref(key: string, value: string, storage?: StorageLike | null): boolean {
  try {
    const store = storage === undefined ? window.localStorage : storage;
    if (!store) return false;
    store.setItem(key, value);
    return true;
  } catch {
    return false;
  }
}

export const THEME_CHOICES = ["system", "light", "dark"] as const;
export type ThemeChoice = (typeof THEME_CHOICES)[number];
export const READING_MODES = ["simple", "technical"] as const;
export type ReadingMode = (typeof READING_MODES)[number];

export const KEYS = { theme: "pg.theme", mode: "pg.mode", tour: "pg.tourSeen" } as const;

/** "system" resolves with the operating system's setting. */
export function resolveTheme(choice: ThemeChoice, systemPrefersDark: boolean): "light" | "dark" {
  if (choice === "system") return systemPrefersDark ? "dark" : "light";
  return choice;
}
