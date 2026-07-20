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
