import { describe, expect, it } from "vitest";
import {
  clampRecentHistorySize,
  formatRecentList,
  isRecentListQuery,
  parseRecentIds,
  parseRecentSlot,
  pushRecentId,
  resolveRecentEntries,
  serializeRecentIds,
} from "./recents";

describe("clampRecentHistorySize", () => {
  it("clamps to the allowed range", () => {
    expect(clampRecentHistorySize(0)).toBe(1);
    expect(clampRecentHistorySize(99)).toBe(15);
    expect(clampRecentHistorySize(7)).toBe(7);
    expect(clampRecentHistorySize("nope")).toBe(10);
  });
});

describe("parseRecentIds / serializeRecentIds", () => {
  it("round-trips JSON arrays", () => {
    const ids = ["1", "2", "3"];
    expect(parseRecentIds(serializeRecentIds(ids))).toEqual(ids);
  });

  it("accepts newline-separated fallback", () => {
    expect(parseRecentIds("a\nb\n")).toEqual(["a", "b"]);
  });
});

describe("pushRecentId", () => {
  it("moves an existing id to the front and caps length", () => {
    expect(pushRecentId(["1", "2", "3"], "2", 3)).toEqual(["2", "1", "3"]);
    expect(pushRecentId(["1", "2", "3"], "9", 3)).toEqual(["9", "1", "2"]);
  });
});

describe("recent query helpers", () => {
  it("detects list and slot queries", () => {
    expect(isRecentListQuery("recent")).toBe(true);
    expect(isRecentListQuery(" Recent ")).toBe(true);
    expect(isRecentListQuery("r1")).toBe(false);
    expect(parseRecentSlot("r1")).toBe(1);
    expect(parseRecentSlot("R12")).toBe(12);
    expect(parseRecentSlot("recent")).toBeNull();
    expect(parseRecentSlot("r0")).toBeNull();
  });
});

describe("resolveRecentEntries / formatRecentList", () => {
  it("skips unknown guild ids and formats a numbered list", () => {
    const entries = resolveRecentEntries(
      ["3", "missing", "1"],
      new Map([
        ["1", { name: "Alpha" }],
        ["3", { name: "Wayland" }],
      ]),
    );
    expect(entries).toEqual([
      { id: "3", name: "Wayland" },
      { id: "1", name: "Alpha" },
    ]);
    const { content, count } = formatRecentList(entries);
    expect(count).toBe(2);
    expect(content).toContain("1. Wayland — `/servers r1`");
    expect(content).toContain("2. Alpha — `/servers r2`");
  });

  it("explains empty history", () => {
    expect(formatRecentList([]).content).toContain("No recent jumps yet");
  });
});
