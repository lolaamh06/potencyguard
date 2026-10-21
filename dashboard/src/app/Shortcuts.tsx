// The presenter "?" overlay. It lists only the keys that work in this phase.
import { useEffect, useRef } from "react";
import { useAppStore } from "./appStore";

const KEYS: [string, string][] = [
  ["?", "show or hide this list"],
  ["Space, PageDown, Right", "next chapter (Shift+Space, PageUp, Left: previous)"],
  ["Down, Up", "scroll a little"],
  ["Home, End", "start, end of the story"],
  ["G", "go to the Story"],
  ["C", "go to the Control Room"],
  ["Q", "change the picture quality (high, medium, low, 2D)"],
  ["D", "show or hide the performance numbers"],
  ["M", "turn reduced motion on or off"],
  ["F", "full screen"],
  ["Esc", "close this list"],
];

export function Shortcuts() {
  const open = useAppStore((s) => s.helpOpen);
  const setOpen = useAppStore((s) => s.setHelpOpen);
  const close = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (open) close.current?.focus();
  }, [open]);

  if (!open) return null;
  return (
    <div className="overlay-card" role="dialog" aria-modal="true" aria-label="Keyboard shortcuts" onClick={() => setOpen(false)}>
      <div onClick={(e) => e.stopPropagation()}>
        <h2>Keyboard shortcuts</h2>
        <dl>
          {KEYS.map(([key, text]) => (
            <div key={key} style={{ display: "contents" }}>
              <dt>
                <kbd>{key}</kbd>
              </dt>
              <dd>{text}</dd>
            </div>
          ))}
        </dl>
        <button className="btn" type="button" ref={close} onClick={() => setOpen(false)}>
          Close
        </button>
      </div>
    </div>
  );
}
