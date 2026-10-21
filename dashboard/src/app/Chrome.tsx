// The top bar: brand, a skip link to the Control Room, the visible reduce-motion control,
// the quality tier and the shortcuts button.
import { goTo, type Route } from "./route";
import { useAppStore } from "./appStore";
import { useQualityStore } from "../quality/qualityStore";

const TIER_LABEL = { high: "High", medium: "Medium", low: "Low", fallback2d: "2D" } as const;

export function Chrome({ route }: { route: Route }) {
  const reduced = useAppStore((s) => s.reducedMotion);
  const toggleReduced = useAppStore((s) => s.toggleReducedMotion);
  const setHelp = useAppStore((s) => s.setHelpOpen);
  const tier = useQualityStore((s) => s.tier);
  const cycle = useQualityStore((s) => s.cycle);

  return (
    <header className="chrome">
      <a className="brand" href="#/story">
        PotencyGuard<small>SIMULATION</small>
      </a>
      {route === "story" ? (
        <button className="btn" type="button" onClick={() => goTo("control-room")}>
          Skip to Control Room
        </button>
      ) : (
        <button className="btn" type="button" onClick={() => goTo("story")}>
          Back to the story
        </button>
      )}
      <button className="btn" type="button" aria-pressed={reduced} onClick={toggleReduced} title="Reduce motion (M)">
        Reduce motion
      </button>
      <button className="btn" type="button" onClick={cycle} title="Change picture quality (Q)">
        Quality: {TIER_LABEL[tier]}
      </button>
      <button className="btn" type="button" onClick={() => setHelp(true)} aria-label="Keyboard shortcuts" title="Shortcuts (?)">
        ?
      </button>
    </header>
  );
}
