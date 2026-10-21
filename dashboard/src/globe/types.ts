// The props a later phase drives: the route's state colour, an optional planned alternative,
// where the shipment is, and the illustrative points. Everything here is an illustrative journey.
import type { LatLon } from "./geo";

export type RouteState = "safe" | "warning" | "danger";

export interface GlobeProps {
  routeState: RouteState;
  /** Draw the planned alternative as a dashed violet arc. */
  showAlternative: boolean;
  /** 0..1 along the route, or null for no shipment marker. */
  shipmentProgress: number | null;
  origin: LatLon;
  destination: LatLon;
  /** The alternative route passes through this point. */
  alternativeVia: LatLon;
}

/** Generic illustrative points, the same as in the replay files. Not a real shipment. */
export const DEFAULT_GLOBE_PROPS: GlobeProps = {
  routeState: "safe",
  showAlternative: false,
  shipmentProgress: null,
  origin: { lat: 50.11, lon: 8.68 },
  destination: { lat: 1.35, lon: 103.82 },
  alternativeVia: { lat: 25.2, lon: 55.3 },
};
