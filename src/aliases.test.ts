import { describe, expect, it } from "vitest";
import { countAliasEntries, mergeAliasText, normalizeAliasText } from "./aliases";

describe("normalizeAliasText", () => {
  it("drops blanks and sorts normalized alias=target lines", () => {
    expect(normalizeAliasText("wow=World of Warcraft\n\nchess=Maynard Chess\n")).toBe(
      "chess=maynard chess\nwow=world of warcraft",
    );
  });

  it("returns empty string for blank input", () => {
    expect(normalizeAliasText("")).toBe("");
    expect(normalizeAliasText("\n\n")).toBe("");
  });
});

describe("mergeAliasText", () => {
  it("merges import lines and lets import win on duplicate aliases", () => {
    const result = mergeAliasText("chess=Old Club\nwow=World of Warcraft", "chess=New Club\nfoo=Bar");
    expect(result.imported).toBe(2);
    expect(result.skipped).toBe(0);
    expect(result.total).toBe(3);
    expect(result.text).toContain("chess=new club");
    expect(result.text).toContain("foo=bar");
    expect(result.text).toContain("wow=world of warcraft");
  });

  it("counts malformed lines as skipped", () => {
    const result = mergeAliasText("a=b", "noequals\n=only\nok=yes\n");
    expect(result.imported).toBe(1);
    expect(result.skipped).toBe(2);
    expect(result.total).toBe(2);
  });
});

describe("countAliasEntries", () => {
  it("counts parsed aliases", () => {
    expect(countAliasEntries("a=b\nc=d")).toBe(2);
    expect(countAliasEntries("")).toBe(0);
  });
});
