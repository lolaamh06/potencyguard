// The theme the 3D globe and the 2D fallback use: the Story is a dark cinematic experience in both
// themes; every other page follows the chosen theme.
import { useUi } from "../app/ui";
import { PALETTES, type Palette, type ThemeName } from "../theme/palette";

export function useGlobeTheme(): { theme: ThemeName; colors: Palette } {
  const resolved = useUi((s) => s.resolved);
  const cinematic = useUi((s) => s.cinematic);
  const theme: ThemeName = cinematic ? "dark" : resolved;
  return { theme, colors: PALETTES[theme] };
}
