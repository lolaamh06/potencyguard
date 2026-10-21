// Hash routing without a router library: #/story (default) and #/control-room.
import { useEffect, useState } from "react";

export type Route = "story" | "control-room";

export function parseRoute(hash: string): Route {
  return hash.replace(/^#\/?/, "") === "control-room" ? "control-room" : "story";
}

export function routeHash(route: Route): string {
  return route === "control-room" ? "#/control-room" : "#/story";
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
