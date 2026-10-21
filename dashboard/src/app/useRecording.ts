// Recording mode (?rec=1): V starts and stops a scripted, repeatable run through the new pages.
// It navigates and presses the same visible buttons a person would, at fixed times. No video is made.
import gsap from "gsap";
import { useEffect } from "react";
import { REC_LENGTH_MS, REC_SEQUENCE, dueSteps } from "../controlroom/logic";
import { useCr } from "../controlroom/store";

function press(text: string): boolean {
  const el = [...document.querySelectorAll<HTMLButtonElement>("button")].find((b) => b.textContent?.trim() === text && !b.disabled);
  el?.click();
  return Boolean(el);
}

export function useRecording(enabled: boolean): void {
  const recording = useCr((s) => s.recording);

  useEffect(() => {
    if (!enabled) return;
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName)) return;
      if (e.key === "v" || e.key === "V") useCr.getState().setRecording(!useCr.getState().recording);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [enabled]);

  useEffect(() => {
    if (!enabled || !recording) return;
    const t0 = performance.now();
    let prev = -1;
    const run = () => {
      const now = performance.now() - t0;
      for (const step of dueSteps(REC_SEQUENCE, prev, now)) {
        const a = step.action;
        if (a.type === "go") {
          window.location.hash = a.hash;
          if (a.speed) window.setTimeout(() => useCr.getState().setSpeed(a.speed!), 400);
        } else if (a.type === "approve") {
          if (press("Approve")) window.setTimeout(() => press("Yes, approve"), 600);
        } else if (a.type === "tamper") {
          if (press("Try to change a record")) window.setTimeout(() => press(["Early", "Middle", "Late"][Math.min(a.entryIndexInList, 2)]), 600);
        }
      }
      prev = now;
      if (now > REC_LENGTH_MS) useCr.getState().setRecording(false);
    };
    gsap.ticker.add(run);
    return () => gsap.ticker.remove(run);
  }, [enabled, recording]);
}
