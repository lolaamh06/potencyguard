// The top navigation: on every page, always in the same place and order, with the current page
// highlighted (colour, underline and aria-current). Holds the logo, the page links, Help, the theme
// choice and the Simple/Technical switch. On a phone it collapses to a Menu button with the same order.
import { NAV_ITEMS, goTo, navPageFor, routeHash, type Route } from "./route";
import { useUi } from "./ui";
import { useAppStore } from "./appStore";
import type { ThemeChoice } from "../theme/prefs";

const THEMES: { id: ThemeChoice; label: string }[] = [
  { id: "system", label: "System" },
  { id: "light", label: "Light" },
  { id: "dark", label: "Dark" },
];

export function Nav({ route }: { route: Route }) {
  const mode = useUi((s) => s.mode);
  const setMode = useUi((s) => s.setMode);
  const theme = useUi((s) => s.themeChoice);
  const setTheme = useUi((s) => s.setTheme);
  const menuOpen = useUi((s) => s.menuOpen);
  const setMenu = useUi((s) => s.setMenu);
  const setHelp = useAppStore((s) => s.setHelpOpen);
  const current = navPageFor(route);

  return (
    <header className="topnav">
      <a className="logo" href="#/" aria-label="PotencyGuard, go to Home">PotencyGuard</a>
      <button type="button" className="btn menu-btn" aria-expanded={menuOpen} aria-controls="main-nav" onClick={() => setMenu(!menuOpen)}>
        {menuOpen ? "Close menu" : "Menu"}
      </button>
      <nav id="main-nav" aria-label="Main" className={menuOpen ? "open" : ""}>
        <ul>
          {NAV_ITEMS.map((item) => (
            <li key={item.page}>
              <a href={routeHash({ page: item.page })} aria-current={item.page === current ? "page" : undefined} onClick={() => setMenu(false)}>
                {item.label}
              </a>
            </li>
          ))}
        </ul>
        <div className="nav-tools">
          <button type="button" className="btn" onClick={() => setHelp(true)}>Help</button>
          <div className="seg" role="group" aria-label="Theme">
            {THEMES.map((t) => (
              <button key={t.id} type="button" className="btn seg-btn" aria-pressed={theme === t.id} onClick={() => setTheme(t.id)}>
                {t.label}
              </button>
            ))}
          </div>
          <div className="seg" role="group" aria-label="How much detail">
            {(["simple", "technical"] as const).map((m) => (
              <button key={m} type="button" className="btn seg-btn" aria-pressed={mode === m} onClick={() => setMode(m)}>
                {m === "simple" ? "Simple" : "Technical"}
              </button>
            ))}
          </div>
        </div>
      </nav>
    </header>
  );
}

export { goTo };
