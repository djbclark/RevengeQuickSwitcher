import { findByProps } from "@revenge-mod/metro";

type ColorModule = {
  meta?: {
    resolveSemanticColor?: (theme: string, key: string) => string | number | undefined;
  };
  internal?: {
    resolveSemanticColor?: (theme: string, key: string) => string | number | undefined;
  };
  colors?: Record<string, unknown>;
};

type ThemeStore = {
  theme?: string;
  getState?: () => { theme?: string };
};

const FALLBACKS = {
  textMuted: "#A3A6AA",
  textNormal: "#DBDEE1",
  textFaint: "#80848E",
  backgroundSecondary: "#2B2D31",
} as const;

let _colorModule: ColorModule | undefined;
let _themeStore: ThemeStore | undefined;

const getColorModule = () =>
  (_colorModule ??= findByProps("colors", "unsafe_rawColors") as ColorModule | undefined);

const getThemeStore = () =>
  (_themeStore ??= findByProps("theme", "darkTheme") as ThemeStore | undefined);

const currentThemeName = () => {
  const store = getThemeStore();
  return store?.theme ?? store?.getState?.()?.theme ?? "dark";
};

const toCssColor = (value: string | number | undefined, fallback: string): string => {
  if (typeof value === "string" && value.length > 0) return value;
  if (typeof value === "number") {
    const hex = (value >>> 0).toString(16).padStart(8, "0");
    // Discord often packs AARRGGBB; drop alpha for RN style strings.
    return `#${hex.slice(2)}`;
  }
  return fallback;
};

const resolveSemantic = (keys: string[], fallback: string): string => {
  const mod = getColorModule();
  const resolver = mod?.meta?.resolveSemanticColor ?? mod?.internal?.resolveSemanticColor;
  if (!resolver) return fallback;

  const theme = currentThemeName();
  for (const key of keys) {
    try {
      const resolved = resolver(theme, key);
      if (resolved != null && resolved !== "") return toCssColor(resolved, fallback);
    } catch {
      // Discord color tables change often; keep trying alternates.
    }
  }
  return fallback;
};

export type SettingsThemeColors = {
  textMuted: string;
  textNormal: string;
  textFaint: string;
  backgroundSecondary: string;
};

/** Resolve settings colors from Discord semantic tokens, with dark-mode fallbacks. */
export const getSettingsThemeColors = (): SettingsThemeColors => ({
  textMuted: resolveSemantic(["HEADER_SECONDARY", "TEXT_MUTED", "INTERACTIVE_MUTED"], FALLBACKS.textMuted),
  textNormal: resolveSemantic(["TEXT_NORMAL", "HEADER_PRIMARY"], FALLBACKS.textNormal),
  textFaint: resolveSemantic(["TEXT_MUTED", "INTERACTIVE_MUTED"], FALLBACKS.textFaint),
  backgroundSecondary: resolveSemantic(
    ["BACKGROUND_SECONDARY", "BG_BASE_SECONDARY", "BACKGROUND_SECONDARY_ALT"],
    FALLBACKS.backgroundSecondary
  ),
});
