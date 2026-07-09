import { describe, expect, it, vi } from "vitest";

vi.mock("react", () => ({
  default: {
    useState: (v: unknown) => [v, () => undefined],
    createElement: () => null,
  },
}));

vi.mock("react-native", () => ({
  Pressable: "Pressable",
  ScrollView: "ScrollView",
  TextInput: "TextInput",
  Text: "Text",
  View: "View",
}));

vi.mock("@revenge-mod/metro", () => ({
  findByProps: () => undefined,
}));

import { openSimplePickSheet, openSwitcherUi } from "./sheets";

describe("sheets fallbacks", () => {
  it("returns false from openSimplePickSheet when Metro APIs are missing", () => {
    expect(openSimplePickSheet("Pick", [{ id: "1", name: "Alpha" }], () => undefined)).toBe(false);
  });

  it("returns null from openSwitcherUi when no sheet APIs are available", () => {
    expect(
      openSwitcherUi({
        title: "Servers",
        items: [{ id: "1", name: "Alpha" }],
        onPick: () => undefined,
      })
    ).toBeNull();
  });
});
