// What the globe shows, set by the screen that owns it (the Control Room sets the route state,
// the alternative and the shipment marker; the Story leaves it at the defaults).
import { create } from "zustand";
import { DEFAULT_GLOBE_PROPS, type GlobeProps } from "./types";

interface GlobeStore {
  props: GlobeProps;
  /** "story": full-screen backdrop, globe shifted off-centre. "control": a window in the Control Room. */
  layout: "story" | "control";
  setProps: (p: Partial<GlobeProps>) => void;
  setLayout: (layout: "story" | "control") => void;
}

export const useGlobeStore = create<GlobeStore>((set) => ({
  props: DEFAULT_GLOBE_PROPS,
  layout: "story",
  setProps: (p) => set((s) => ({ props: { ...s.props, ...p } })),
  setLayout: (layout) => set((s) => ({ layout, props: layout === "story" ? DEFAULT_GLOBE_PROPS : s.props })),
}));
