// Hash routing without a router library, and the map of the whole app: the pages, the top
// navigation, the Back target and the guided "Next step" chain. Pure, so a test can walk it.
import { useEffect, useState } from "react";
import { isScenarioId, type ScenarioId } from "../controlroom/logic";
import { START_HERE } from "../copy/scenarios";

export type PageId = "home" | "shipments" | "shipment" | "decisions" | "proof" | "about" | "story";

export interface Route {
  page: PageId;
  id?: ScenarioId;
}

export const HOME: Route = { page: "home" };

export function parseRoute(hash: string): Route {
  const parts = hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  const [first, second] = parts;
  switch (first) {
    case undefined:
    case "home":
      return HOME;
    case "shipments":
      if (second && isScenarioId(second)) return { page: "shipment", id: second };
      return { page: "shipments" };
    case "control-room": // the old single page: its replacement is the list of shipments
      return { page: "shipments" };
    case "decisions":
    case "proof":
    case "about":
    case "story":
      return { page: first };
    default:
      return HOME;
  }
}

export function routeHash(route: Route): string {
  if (route.page === "home") return "#/";
  if (route.page === "shipment") return `#/shipments/${route.id ?? START_HERE}`;
  return `#/${route.page}`;
}

export function goTo(route: Route): void {
  window.location.hash = routeHash(route);
}

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.hash));
  useEffect(() => {
    const onChange = () => setRoute(parseRoute(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}

// ---------------------------------------------------------------- the map

export interface NavItem {
  page: Exclude<PageId, "shipment">;
  label: string;
}

/** The top navigation: always in this order, on every page. */
export const NAV_ITEMS: readonly NavItem[] = [
  { page: "home", label: "Home" },
  { page: "shipments", label: "Shipments" },
  { page: "decisions", label: "Decisions" },
  { page: "proof", label: "Proof" },
  { page: "about", label: "About this data" },
  { page: "story", label: "Story" },
];

export const PAGE_INFO: Record<PageId, { title: string; lead: string }> = {
  home: { title: "PotencyGuard", lead: "Watch a medicine shipment, see when something goes wrong, and decide what to do." },
  shipments: { title: "Shipments", lead: "Each card is a sample journey from a simulation. Open one to watch it and see what we recommend." },
  shipment: { title: "Shipment", lead: "Press Play to watch the journey. Read the recommendation, then decide." },
  decisions: { title: "Decisions", lead: "These shipments are waiting for a person. Approve, choose another action, or reject." },
  proof: { title: "Proof", lead: "Check that the records have not been changed, and see what happens when one is." },
  about: { title: "About this data", lead: "What is real, what is simulated, and where the numbers come from." },
  story: { title: "The story", lead: "Scroll to follow the idea from the first worry to the finished product." },
};

/** The page whose navigation entry is highlighted for a route. */
export function navPageFor(route: Route): NavItem["page"] {
  return route.page === "shipment" ? "shipments" : route.page;
}

/** Where the Back link goes (null on Home). */
export function backTarget(route: Route, startHere: ScenarioId = START_HERE): Route | null {
  switch (route.page) {
    case "home":
      return null;
    case "shipments":
    case "story":
      return HOME;
    case "shipment":
      return { page: "shipments" };
    case "decisions":
      return { page: "shipment", id: startHere };
    case "proof":
      return { page: "decisions" };
    case "about":
      return { page: "proof" };
  }
}

export interface NextStep {
  label: string;
  route: Route;
}

/** The big "Next step" button of the guided demo flow (null at the end of it, and on the Story). */
export function nextStep(route: Route, startHere: ScenarioId = START_HERE): NextStep | null {
  switch (route.page) {
    case "home":
      return { label: "Try the demo", route: { page: "shipments" } };
    case "shipments":
      return { label: "Open the “Start here” shipment", route: { page: "shipment", id: startHere } };
    case "shipment":
      return { label: "Next step: Decisions", route: { page: "decisions" } };
    case "decisions":
      return { label: "Next step: Proof", route: { page: "proof" } };
    case "proof":
      return { label: "Next step: About this data", route: { page: "about" } };
    case "about":
    case "story":
      return null;
  }
}

/** The guided flow, from Home to the end: each page once. */
export function demoChain(startHere: ScenarioId = START_HERE): Route[] {
  const chain: Route[] = [HOME];
  for (let i = 0; i < 20; i++) {
    const next = nextStep(chain[chain.length - 1], startHere);
    if (!next) break;
    chain.push(next.route);
  }
  return chain;
}

/** Clicks from Home to reach a page using the top navigation and the page buttons. */
export function clicksFromHome(route: Route): number {
  if (route.page === "home") return 0;
  return route.page === "shipment" ? 2 : 1;
}
