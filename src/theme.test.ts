import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@revenge-mod/metro", () => ({
  findByProps: vi.fn(() => undefined),
}));

import { getSettingsThemeColors } from "./theme";

describe("getSettingsThemeColors", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns dark fallbacks when Metro color modules are missing", () => {
    expect(getSettingsThemeColors()).toEqual({
      textMuted: "#A3A6AA",
      textNormal: "#DBDEE1",
      textFaint: "#80848E",
      backgroundSecondary: "#2B2D31",
    });
  });
});

describe("semantic color resolution", () => {
  it("converts packed AARRGGBB numbers to #RRGGBB and resolves all sheet tokens", async () => {
    const { findByProps } = await import("@revenge-mod/metro");
    (findByProps as ReturnType<typeof vi.fn>).mockReturnValue({
      colors: {},
      theme: "light",
      meta: {
        resolveSemanticColor: (_theme: string, key: string) => (key === "TEXT_NORMAL" ? 0xff112233 : "#ABCDEF"),
      },
    });
    const { getSheetColors } = await import("./theme");
    const colors = getSheetColors();
    expect(colors.text).toBe("#112233"); // alpha byte dropped
    for (const key of ["muted", "faint", "panel", "border", "accent", "chip", "inputBg"] as const) {
      expect(colors[key]).toBe("#ABCDEF");
    }
  });
});
