import { describe, expect, it } from "vitest";
import { countExcludeRules, isGuildExcluded, parseExcludeRules } from "./excludes";

describe("parseExcludeRules", () => {
  it("parses ids, exact names, contains patterns, and ignores comments", () => {
    const rules = parseExcludeRules("123456789012345678\nWayland Parents\n~parents\n# note\n\n");
    expect(rules).toEqual([
      { type: "id", value: "123456789012345678" },
      { type: "name", value: "wayland parents", mode: "exact" },
      { type: "name", value: "parents", mode: "contains" },
    ]);
  });

  it("rejects tiny contains patterns", () => {
    expect(parseExcludeRules("~a")).toEqual([]);
  });
});

describe("isGuildExcluded", () => {
  const rules = parseExcludeRules("123456789012345678\nAlpha Guild\n~parent");

  it("matches by id", () => {
    expect(isGuildExcluded("123456789012345678", "other", rules)).toBe(true);
  });

  it("matches exact normalized names", () => {
    expect(isGuildExcluded("1", "alpha guild", rules)).toBe(true);
    expect(isGuildExcluded("1", "alpha", rules)).toBe(false);
  });

  it("matches contains patterns", () => {
    expect(isGuildExcluded("1", "wayland parents chat", rules)).toBe(true);
  });
});

describe("countExcludeRules", () => {
  it("counts parsed rules", () => {
    expect(countExcludeRules("Alpha Guild\n~spam")).toBe(2);
    expect(countExcludeRules("")).toBe(0);
  });
});

describe("parseExcludeRules edges", () => {
  it("skips comments, short ~patterns, and classifies snowflakes as id rules", () => {
    const rules = parseExcludeRules("# note\n123456789012345678\n~a\n~ok\n  \nReal Name");
    expect(rules).toEqual([
      { type: "id", value: "123456789012345678" },
      { type: "name", value: "ok", mode: "contains" },
      { type: "name", value: "real name", mode: "exact" },
    ]);
  });

  it("id rules never match names and empty names never match name rules", () => {
    const rules = parseExcludeRules("123456789012345678\n~spam");
    expect(isGuildExcluded("123456789012345678", "whatever", rules)).toBe(true);
    expect(isGuildExcluded("999", "", rules)).toBe(false);
    expect(isGuildExcluded("", "big spam server", rules)).toBe(true);
  });
});
