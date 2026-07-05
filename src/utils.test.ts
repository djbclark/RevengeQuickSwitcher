import { describe, expect, it } from "vitest";
import {
  escapeMarkdown,
  getArrayChecksum,
  isSubsequence,
  normalizeText,
  parseAliases,
  resolveGuildId,
  sanitizeName,
} from "./utils";

describe("escapeMarkdown", () => {
  it("escapes Discord markdown special characters", () => {
    expect(escapeMarkdown("hello_world *bold*")).toBe("hello\\_world \\*bold\\*");
    expect(escapeMarkdown("pipe|tilde~")).toBe("pipe\\|tilde\\~");
  });

  it("leaves plain text unchanged", () => {
    expect(escapeMarkdown("Wayland High School")).toBe("Wayland High School");
  });
});

describe("sanitizeName", () => {
  it("returns Unknown for empty input", () => {
    expect(sanitizeName("")).toBe("Unknown");
    expect(sanitizeName(null as unknown as string)).toBe("Unknown");
  });

  it("strips invisible unicode and trims whitespace", () => {
    expect(sanitizeName("  \u200BHello\uFEFF  ")).toBe("Hello");
  });

  it("truncates long names to 100 characters", () => {
    const long = "a".repeat(150);
    expect(sanitizeName(long).length).toBe(100);
  });

  it("returns Unnamed when only invisible characters remain", () => {
    expect(sanitizeName("\u200B\uFEFF")).toBe("Unnamed");
  });
});

describe("normalizeText", () => {
  it("lowercases and applies NFKC normalization", () => {
    expect(normalizeText("Wayland High School")).toBe("wayland high school");
    expect(normalizeText("ＡＢＣ")).toBe("abc");
  });
});

describe("resolveGuildId", () => {
  it("reads id from common guild object shapes", () => {
    expect(resolveGuildId({ id: "123" })).toBe("123");
    expect(resolveGuildId({ guildId: "456" })).toBe("456");
    expect(resolveGuildId({ guild_id: "789" })).toBe("789");
  });

  it("returns string nodes directly", () => {
    expect(resolveGuildId("abc")).toBe("abc");
  });

  it("returns null when no id is present", () => {
    expect(resolveGuildId({ name: "no id" })).toBeNull();
    expect(resolveGuildId(null)).toBeNull();
  });
});

describe("getArrayChecksum", () => {
  it("is stable for the same guild ordering", () => {
    const guilds = [{ id: "a" }, { id: "b" }, { id: "c" }];
    expect(getArrayChecksum(guilds)).toBe(getArrayChecksum(guilds));
  });

  it("changes when guild ids change", () => {
    const a = [{ id: "a" }, { id: "b" }];
    const b = [{ id: "a" }, { id: "c" }];
    expect(getArrayChecksum(a)).not.toBe(getArrayChecksum(b));
  });
});

describe("isSubsequence", () => {
  it("matches characters in order but not necessarily adjacent", () => {
    expect(isSubsequence("wsh", "wayland high school")).toBe(true);
    expect(isSubsequence("abc", "a x b y c")).toBe(true);
  });

  it("rejects queries that skip required order", () => {
    expect(isSubsequence("hsy", "wayland high school")).toBe(false);
    expect(isSubsequence("cba", "abc")).toBe(false);
  });

  it("handles empty query as a match", () => {
    expect(isSubsequence("", "anything")).toBe(true);
  });
});

describe("parseAliases", () => {
  it("parses alias=target lines into a normalized map", () => {
    const map = parseAliases("chess=Maynard Chess\nwow=World of Warcraft");
    expect(map.get("chess")).toBe("maynard chess");
    expect(map.get("wow")).toBe("world of warcraft");
  });

  it("ignores malformed lines", () => {
    const map = parseAliases("valid=target\nnoequals\n=a\nb=\n");
    expect(map.size).toBe(1);
    expect(map.get("valid")).toBe("target");
  });

  it("returns an empty map for blank input", () => {
    expect(parseAliases("").size).toBe(0);
    expect(parseAliases("\n\n").size).toBe(0);
  });
});
