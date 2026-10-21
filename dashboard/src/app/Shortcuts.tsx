// The presenter "?" overlay. It lists only the keys that work in this phase.
import { useEffect, useRef } from "react";
import { useAppStore } from "./appStore";

const KEYS: [string, string][] = [
  ["?", "show or hide this list"],
  ["Space, PageDown, Right", "Story: next chapter (Shift+Space, PageUp, Left: previous)"],
  ["Down, Up", "scroll a little"],
  ["Home, End", "start, end of the story"],
  ["Enter", "enter the Control Room (at the last chapter)"],
  ["1 to 5", "Control Room: pick a scenario"],
  ["Space", "Control Room: pause or resume the replay"],
  ["R", "Control Room: reset the scenario"],
  ["T", "Control Room: show a recorded tamper result"],
  ["A", "Control Room: approve (demo, a decision must be open)"],
  ["P", "Control Room: provenance drawer"],
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
