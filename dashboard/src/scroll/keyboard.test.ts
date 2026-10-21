import { describe, expect, it } from "vitest";
import { actionForKey, keyBelongsToControl, stepChapter, type KeyInfo } from "./keyboard";

const key = (k: string, extra: Partial<KeyInfo> = {}): KeyInfo => ({
  key: k,
  shiftKey: false,
  ctrlKey: false,
  metaKey: false,
  altKey: false,
  ...extra,
});

describe("actionForKey", () => {
  it("maps the scroll keys on the story page", () => {
    expect(actionForKey(key("ArrowDown"), true)).toEqual({ kind: "scrollBy", viewports: 0.12 });
    expect(actionForKey(key("ArrowUp"), true)).toEqual({ kind: "scrollBy", viewports: -0.12 });
    expect(actionForKey(key("PageDown"), true)).toEqual({ kind: "chapter", delta: 1 });
    expect(actionForKey(key("PageUp"), true)).toEqual({ kind: "chapter", delta: -1 });
    expect(actionForKey(key(" "), true)).toEqual({ kind: "chapter", delta: 1 });
    expect(actionForKey(key(" ", { shiftKey: true }), true)).toEqual({ kind: "chapter", delta: -1 });
    expect(actionForKey(key("Home"), true)).toEqual({ kind: "edge", where: "start" });
    expect(actionForKey(key("End"), true)).toEqual({ kind: "edge", where: "end" });
  });

  it("leaves scroll keys alone when the page does not scroll a story", () => {
    expect(actionForKey(key("ArrowDown"), false)).toBeNull();
    expect(actionForKey(key(" "), false)).toBeNull();
  });

  it("maps the app keys in any case, on every page", () => {
    expect(actionForKey(key("q"), false)).toEqual({ kind: "app", name: "tier" });
    expect(actionForKey(key("Q"), false)).toEqual({ kind: "app", name: "tier" });
    expect(actionForKey(key("d"), false)).toEqual({ kind: "app", name: "perf" });
    expect(actionForKey(key("m"), false)).toEqual({ kind: "app", name: "reduce" });
    expect(actionForKey(key("f"), false)).toEqual({ kind: "app", name: "fullscreen" });
    expect(actionForKey(key("g"), false)).toEqual({ kind: "app", name: "story" });
    expect(actionForKey(key("c"), false)).toEqual({ kind: "app", name: "controlRoom" });
    expect(actionForKey(key("?"), false)).toEqual({ kind: "app", name: "help" });
    expect(actionForKey(key("Escape"), false)).toEqual({ kind: "app", name: "close" });
  });

  it("never takes a key with a modifier (so browser shortcuts keep working)", () => {
    expect(actionForKey(key("q", { ctrlKey: true }), true)).toBeNull();
    expect(actionForKey(key("f", { metaKey: true }), true)).toBeNull();
    expect(actionForKey(key("d", { altKey: true }), true)).toBeNull();
  });

  it("ignores other keys", () => {
    expect(actionForKey(key("x"), true)).toBeNull();
    expect(actionForKey(key("Tab"), true)).toBeNull();
  });
});

describe("keyBelongsToControl", () => {
  it("leaves every key to text fields", () => {
    expect(keyBelongsToControl("INPUT", "q")).toBe(true);
    expect(keyBelongsToControl("textarea", " ")).toBe(true);
  });
  it("leaves Space and Enter to buttons and links, not the other keys", () => {
    expect(keyBelongsToControl("BUTTON", " ")).toBe(true);
    expect(keyBelongsToControl("a", "Enter")).toBe(true);
    expect(keyBelongsToControl("button", "q")).toBe(false);
    expect(keyBelongsToControl("div", " ")).toBe(false);
    expect(keyBelongsToControl(undefined, " ")).toBe(false);
  });
});

describe("stepChapter", () => {
  it("stays inside the list", () => {
    expect(stepChapter(0, -1, 4)).toBe(0);
    expect(stepChapter(3, 1, 4)).toBe(3);
    expect(stepChapter(1, 1, 4)).toBe(2);
    expect(stepChapter(0, 1, 0)).toBe(0);
  });
});
