import { describe, expect, it, vi } from "vitest";

vi.mock("react", () => ({
  default: {
    useState: (v: unknown) => [v, () => undefined],
    useEffect: () => undefined,
    createElement: () => null,
  },
}));

vi.mock("react-native", () => ({
  Pressable: "Pressable",
  ScrollView: "ScrollView",
  TextInput: "TextInput",
  Text: "Text",
  View: "View",
  Modal: "Modal",
  KeyboardAvoidingView: "KeyboardAvoidingView",
  Platform: { OS: "android" },
}));

vi.mock("@revenge-mod/metro", () => ({
  findByProps: () => undefined,
}));

import {
  filterSwitcherItems,
  getSheetPageItems,
  openSimplePickSheet,
  openSwitcherUi,
  sheetPageCount,
  SHEET_PAGE_SIZE,
} from "./sheets";

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

describe("sheet paging helpers", () => {
  it("computes page counts from item totals", () => {
    expect(sheetPageCount(0)).toBe(1);
    expect(sheetPageCount(SHEET_PAGE_SIZE)).toBe(1);
    expect(sheetPageCount(SHEET_PAGE_SIZE + 1)).toBe(2);
    expect(sheetPageCount(25, 8)).toBe(4);
  });

  it("slices items for the requested page and clamps out-of-range pages", () => {
    const items = Array.from({ length: 20 }, (_, i) => ({ id: String(i + 1), name: `S${i + 1}` }));
    expect(getSheetPageItems(items, 1, 8).pageItems.map((x) => x.id)).toEqual([
      "1",
      "2",
      "3",
      "4",
      "5",
      "6",
      "7",
      "8",
    ]);
    expect(getSheetPageItems(items, 3, 8).pageItems.map((x) => x.id)).toEqual(["17", "18", "19", "20"]);
    expect(getSheetPageItems(items, 99, 8).page).toBe(3);
    expect(getSheetPageItems(items, 0, 8).page).toBe(1);
  });

  it("filters switcher items case-insensitively", () => {
    const items = [
      { id: "1", name: "Alpha" },
      { id: "2", name: "Beta Guild" },
    ];
    expect(filterSwitcherItems(items, "alp")).toEqual([{ id: "1", name: "Alpha" }]);
    expect(filterSwitcherItems(items, "  ")).toEqual(items);
  });
});
