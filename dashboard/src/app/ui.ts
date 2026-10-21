// Global look-and-feel choices: Simple/Technical, theme, the phone menu and the guided tour.
// Remembered with guarded storage (theme/prefs.ts); the theme is also applied by a tiny script in
// index.html before first paint so there is no flash.
import { create } from "zustand";
import { KEYS, READING_MODES, THEME_CHOICES, loadPref, resolveTheme, savePref, type ReadingMode, type ThemeChoice } from "../theme/prefs";
import type { ThemeName } from "../theme/palette";

function systemDark(): boolean {
  try {
    return typeof matchMedia === "function" && matchMedia("(prefers-color-scheme: dark)").matches;
  } catch {
    return false;
  }
}

export function applyTheme(resolved: ThemeName): void {
  if (typeof document !== "undefined") document.documentElement.dataset.theme = resolved;
}

export const TOUR_STEPS = [
  { page: "shipments", title: "1. Pick a shipment", text: "Each card is one sample journey. Press Open on the one marked Start here." },
  { page: "shipment", title: "2. Watch it play", text: "Press Play to watch the journey. The chart shows the temperature in the box." },
  { page: "shipment", title: "3. Read the recommendation", text: "The recommendation card says what we suggest and why, in plain words." },
  { page: "decisions", title: "4. Approve or choose another", text: "When a person has to decide, use Approve, Choose a different action, or Reject." },
  { page: "proof", title: "5. Check the proof", text: "See that the records are intact, and what happens if someone changes one." },
] as const;

interface UiState {
  mode: ReadingMode;
  themeChoice: ThemeChoice;
  resolved: ThemeName;
  /** True while the Story is on screen: it is a dark cinematic experience in both themes. */
  cinematic: boolean;
  menuOpen: boolean;
  tourStep: number | null;
  tourSeen: boolean;
  setMode: (m: ReadingMode) => void;
  setTheme: (t: ThemeChoice) => void;
  setCinematic: (on: boolean) => void;
  setMenu: (open: boolean) => void;
  startTour: () => void;
  stepTour: (delta: 1 | -1) => void;
  endTour: () => void;
}

const initialChoice = loadPref(KEYS.theme, THEME_CHOICES, "system");

export const useUi = create<UiState>((set, get) => ({
  mode: loadPref(KEYS.mode, READING_MODES, "simple"),
  themeChoice: initialChoice,
  resolved: resolveTheme(initialChoice, systemDark()),
  cinematic: false,
  menuOpen: false,
  tourStep: null,
  tourSeen: loadPref(KEYS.tour, ["yes", "no"] as const, "no") === "yes",

  setMode: (mode) => {
    savePref(KEYS.mode, mode);
    set({ mode });
  },
  setTheme: (themeChoice) => {
    savePref(KEYS.theme, themeChoice);
    const resolved = resolveTheme(themeChoice, systemDark());
    applyTheme(resolved);
    set({ themeChoice, resolved });
  },
  setCinematic: (cinematic) => set({ cinematic }),
  setMenu: (menuOpen) => set({ menuOpen }),
  startTour: () => set({ tourStep: 0 }),
  stepTour: (delta) => {
    const next = (get().tourStep ?? 0) + delta;
    if (next < 0) return;
    if (next >= TOUR_STEPS.length) {
      get().endTour();
      return;
    }
    set({ tourStep: next });
  },
  endTour: () => {
    savePref(KEYS.tour, "yes");
    set({ tourStep: null, tourSeen: true });
  },
}));

/** Keeps "System" in step with the operating system while the page is open. */
export function watchSystemTheme(): () => void {
  if (typeof matchMedia !== "function") return () => {};
  const query = matchMedia("(prefers-color-scheme: dark)");
  const onChange = () => {
    const s = useUi.getState();
    if (s.themeChoice !== "system") return;
    const resolved = resolveTheme("system", query.matches);
    applyTheme(resolved);
    useUi.setState({ resolved });
  };
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

export function initTheme(): void {
  applyTheme(useUi.getState().resolved);
}
