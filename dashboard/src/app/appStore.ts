// App-wide state that changes rarely (never per frame). Per-frame values live in scroll/scrollState.ts.
import { create } from "zustand";

function systemPrefersReducedMotion(): boolean {
  try {
    return typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch {
    return false;
  }
}

export type SceneStatus = "ok" | "restoring";

interface AppState {
  reducedMotion: boolean;
  helpOpen: boolean;
  perfOpen: boolean;
  /** Index of the chapter on screen (changes a few times per scroll, not per frame). */
  chapter: number;
  sceneStatus: SceneStatus;
  setReducedMotion: (value: boolean) => void;
  toggleReducedMotion: () => void;
  setHelpOpen: (value: boolean) => void;
  togglePerf: () => void;
  setChapter: (index: number) => void;
  setSceneStatus: (status: SceneStatus) => void;
}

export const useAppStore = create<AppState>((set) => ({
  reducedMotion: systemPrefersReducedMotion(),
  helpOpen: false,
  perfOpen: false,
  chapter: 0,
  sceneStatus: "ok",
  setReducedMotion: (value) => set({ reducedMotion: value }),
  toggleReducedMotion: () => set((s) => ({ reducedMotion: !s.reducedMotion })),
  setHelpOpen: (value) => set({ helpOpen: value }),
  togglePerf: () => set((s) => ({ perfOpen: !s.perfOpen })),
  setChapter: (index) => set((s) => (s.chapter === index ? s : { chapter: index })),
  setSceneStatus: (status) => set({ sceneStatus: status }),
}));
