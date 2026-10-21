import { describe, expect, it } from "vitest";
import { SCENARIO_IDS } from "../controlroom/logic";
import { START_HERE } from "../copy/scenarios";
import { HOME, NAV_ITEMS, PAGE_INFO, backTarget, clicksFromHome, demoChain, navPageFor, nextStep, parseRoute, routeHash, type PageId, type Route } from "./route";

const ALL_PAGES: PageId[] = ["home", "shipments", "shipment", "decisions", "proof", "about", "story"];
const sample = (page: PageId): Route => (page === "shipment" ? { page, id: START_HERE } : { page });

describe("routes", () => {
  it("round-trips every page and every shipment through the hash", () => {
    for (const page of ALL_PAGES) {
      const r = sample(page);
      expect(parseRoute(routeHash(r))).toEqual(r);
    }
    for (const id of SCENARIO_IDS) expect(parseRoute(`#/shipments/${id}`)).toEqual({ page: "shipment", id });
  });

  it("falls back to Home for an empty or unknown hash, and to the list for an unknown shipment", () => {
    expect(parseRoute("")).toEqual(HOME);
    expect(parseRoute("#/")).toEqual(HOME);
    expect(parseRoute("#/nowhere")).toEqual(HOME);
    expect(parseRoute("#/shipments/not_a_shipment")).toEqual({ page: "shipments" });
  });

  it("sends the old Control Room address to the list of shipments", () => {
    expect(parseRoute("#/control-room")).toEqual({ page: "shipments" });
  });
});

describe("navigation (easy-navigation rules)", () => {
  it("lists every page in the top navigation, in a fixed order, and every label is plain", () => {
    expect(NAV_ITEMS.map((n) => n.page)).toEqual(["home", "shipments", "decisions", "proof", "about", "story"]);
    expect(new Set(NAV_ITEMS.map((n) => n.label)).size).toBe(NAV_ITEMS.length);
  });

  it("makes every page reachable: the top-level pages in one click, a shipment in two", () => {
    for (const page of ALL_PAGES) {
      const r = sample(page);
      const nav = navPageFor(r);
      expect(NAV_ITEMS.some((n) => n.page === nav), page).toBe(true);
      expect(clicksFromHome(r), page).toBeLessThanOrEqual(2);
    }
    expect(clicksFromHome({ page: "shipments" })).toBe(1);
    expect(clicksFromHome(sample("shipment"))).toBe(2);
  });

  it("gives every page except Home a Back target, and Home none", () => {
    expect(backTarget(HOME)).toBeNull();
    for (const page of ALL_PAGES.filter((p) => p !== "home")) {
      const back = backTarget(sample(page));
      expect(back, page).not.toBeNull();
      expect(ALL_PAGES).toContain(back!.page);
    }
    expect(backTarget(sample("shipment"))).toEqual({ page: "shipments" });
  });

  it("gives every page a title and a one-line lead", () => {
    for (const page of ALL_PAGES) {
      expect(PAGE_INFO[page].title.length).toBeGreaterThan(2);
      expect(PAGE_INFO[page].lead.length).toBeGreaterThan(20);
      expect(PAGE_INFO[page].lead).not.toContain("\n");
    }
  });

  it("walks the Next-step chain through every demo page once, with no loop", () => {
    const chain = demoChain();
    const pages = chain.map((r) => r.page);
    expect(pages).toEqual(["home", "shipments", "shipment", "decisions", "proof", "about"]);
    expect(new Set(pages).size).toBe(pages.length);
    expect(nextStep(chain[chain.length - 1])).toBeNull();
  });

  it("never leaves a dead end: each demo page has a Next step or is the last, and the last has a Back", () => {
    for (const r of demoChain()) {
      const next = nextStep(r);
      if (next) expect(next.label.length).toBeGreaterThan(3);
      else expect(backTarget(r)).not.toBeNull();
    }
    expect(nextStep({ page: "home" })?.route).toEqual({ page: "shipments" });
  });

  it("the Story is reachable and has a way out", () => {
    expect(NAV_ITEMS.map((n) => n.page)).toContain("story");
    expect(backTarget({ page: "story" })).toEqual(HOME);
  });
});
