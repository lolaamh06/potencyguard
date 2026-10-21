// Pure mapping from a key press to a scroll or app action. Kept free of the DOM so it can be tested.

export type KeyAction =
  | { kind: "scrollBy"; viewports: number }
  | { kind: "chapter"; delta: 1 | -1 }
  | { kind: "edge"; where: "start" | "end" }
  | { kind: "app"; name: "tier" | "perf" | "help" | "reduce" | "fullscreen" | "story" | "controlRoom" | "close" };

export interface KeyInfo {
  key: string;
  shiftKey: boolean;
  ctrlKey: boolean;
  metaKey: boolean;
  altKey: boolean;
}

/** Keys that are left to a focused control (a button, a link, a field). */
export function keyBelongsToControl(tag: string | undefined, key: string): boolean {
  const t = (tag ?? "").toLowerCase();
  if (t === "input" || t === "textarea" || t === "select") return true;
  return (t === "button" || t === "a") && (key === " " || key === "Enter");
}

/** The action for a key, or null when the key is not ours (so the browser keeps it). */
export function actionForKey(info: KeyInfo, scrollKeys: boolean): KeyAction | null {
  if (info.ctrlKey || info.metaKey || info.altKey) return null;
  const key = info.key;
  switch (key) {
    case "?":
      return { kind: "app", name: "help" };
    case "Escape":
      return { kind: "app", name: "close" };
    case "q":
    case "Q":
      return { kind: "app", name: "tier" };
    case "d":
    case "D":
      return { kind: "app", name: "perf" };
    case "m":
    case "M":
      return { kind: "app", name: "reduce" };
    case "f":
    case "F":
      return { kind: "app", name: "fullscreen" };
    case "g":
    case "G":
      return { kind: "app", name: "story" };
    case "c":
    case "C":
      return { kind: "app", name: "controlRoom" };
    default:
      break;
  }
  if (!scrollKeys) return null;
  switch (key) {
    case "ArrowDown":
      return { kind: "scrollBy", viewports: 0.12 };
    case "ArrowUp":
      return { kind: "scrollBy", viewports: -0.12 };
    case "ArrowRight":
    case "PageDown":
      return { kind: "chapter", delta: 1 };
    case "ArrowLeft":
    case "PageUp":
      return { kind: "chapter", delta: -1 };
    case " ":
      return { kind: "chapter", delta: info.shiftKey ? -1 : 1 };
    case "Home":
      return { kind: "edge", where: "start" };
    case "End":
      return { kind: "edge", where: "end" };
    default:
      return null;
  }
}

/** Next chapter index after a chapter step, kept inside the list. */
export function stepChapter(current: number, delta: 1 | -1, count: number): number {
  return Math.min(Math.max(current + delta, 0), Math.max(count - 1, 0));
}
