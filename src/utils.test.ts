import { describe, expect, it } from "vitest";
import {
  escapeMarkdown,
  findBestMatches,
  findBestMatchIndex,
  formatMatchPickList,
  formatServerListPage,
  getArrayChecksum,
  isSubsequence,
  MAX_CONTENT_LENGTH,
  MIN_SUBSEQUENCE_LENGTH,
  normalizeText,
  parseAliases,
  resolveGuildId,
  resolveSearchQuery,
  sanitizeName,
  scoreGuildMatch,
  truncateForDisplay,
} from "./utils";

describe("escapeMarkdown", () => {
  it("escapes Discord markdown special characters", () => {
    expect(escapeMarkdown("hello_world *bold*")).toBe("hello\\_world \\*bold\\*");
    expect(escapeMarkdown("pipe|tilde~")).toBe("pipe\\|tilde\\~");
    expect(escapeMarkdown("link[text](url)")).toBe("link\\[text\\]\\(url\\)");
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

  it("changes when nested folder membership changes", () => {
    const a = [{ type: "folder", id: "folder1", guilds: [{ id: "1" }, { id: "2" }] }];
    const b = [{ type: "folder", id: "folder1", guilds: [{ id: "1" }, { id: "99" }] }];
    expect(getArrayChecksum(a)).not.toBe(getArrayChecksum(b));
  });

  it("changes when a guild is renamed via getGuildName", () => {
    const nodes = [{ id: "1" }, { id: "2" }];
    const before = getArrayChecksum(nodes, (id) => (id === "1" ? "Alpha" : "Beta"));
    const after = getArrayChecksum(nodes, (id) => (id === "1" ? "Zeta" : "Beta"));
    expect(before).not.toBe(after);
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

  it("keeps everything after the first = as the target", () => {
    const map = parseAliases("eq=Bar=Baz Club");
    expect(map.get("eq")).toBe("bar=baz club");
  });

  it("returns an empty map for blank input", () => {
    expect(parseAliases("").size).toBe(0);
    expect(parseAliases("\n\n").size).toBe(0);
  });
});

describe("resolveSearchQuery", () => {
  it("applies alias substitution before matching", () => {
    const aliases = parseAliases("chess=Maynard Chess");
    expect(resolveSearchQuery("chess", aliases)).toBe("maynard chess");
    expect(resolveSearchQuery("other", aliases)).toBe("other");
  });
});

describe("scoreGuildMatch", () => {
  it("ranks exact matches above prefix, contains, and subsequence", () => {
    expect(scoreGuildMatch("abc", "abc")).toBe(100);
    expect(scoreGuildMatch("ab", "abc guild")).toBe(50);
    expect(scoreGuildMatch("bc", "abc guild")).toBe(10);
    expect(scoreGuildMatch("ac", "abc guild")).toBe(0);
    expect(scoreGuildMatch("acx", "abc x guild")).toBe(5);
    expect(scoreGuildMatch("xyz", "abc guild")).toBe(0);
  });

  it(`does not use subsequence for queries shorter than ${MIN_SUBSEQUENCE_LENGTH}`, () => {
    expect(scoreGuildMatch("ws", "wayland high school")).toBe(0);
    expect(scoreGuildMatch("wsh", "wayland high school")).toBe(5);
  });
});

describe("findBestMatchIndex", () => {
  const candidates = [
    { normalized: "alpha beta", name: "Alpha Beta" },
    { normalized: "alphabet soup", name: "Alphabet Soup" },
    { normalized: "wayland high school", name: "Wayland High School" },
  ];

  it("prefers exact match", () => {
    expect(findBestMatchIndex("alpha beta", candidates)).toBe(0);
  });

  it("prefers prefix over contains and subsequence", () => {
    expect(findBestMatchIndex("alpha", candidates)).toBe(0);
  });

  it("uses subsequence matching when no stronger match exists", () => {
    expect(findBestMatchIndex("wsh", candidates)).toBe(2);
  });

  it("returns -1 for short subsequence-only queries", () => {
    expect(findBestMatchIndex("ws", candidates)).toBe(-1);
  });

  it("returns -1 when nothing matches", () => {
    expect(findBestMatchIndex("zzz", candidates)).toBe(-1);
  });
});

describe("findBestMatches", () => {
  it("returns every candidate that shares the top score", () => {
    const candidates = [
      { normalized: "alpha one", sanitized: "Alpha One" },
      { normalized: "alpha two", sanitized: "Alpha Two" },
      { normalized: "beta", sanitized: "Beta" },
    ];
    const result = findBestMatches("alpha", candidates);
    expect(result.score).toBe(50);
    expect(result.matches.map((m) => m.sanitized)).toEqual(["Alpha One", "Alpha Two"]);
  });

  it("returns a single exact match without siblings", () => {
    const candidates = [
      { normalized: "alpha", sanitized: "Alpha" },
      { normalized: "alphabet", sanitized: "Alphabet" },
    ];
    const result = findBestMatches("alpha", candidates);
    expect(result.score).toBe(100);
    expect(result.matches).toHaveLength(1);
  });
});

describe("truncateForDisplay", () => {
  it("passes short text through and truncates long text with an ellipsis", () => {
    expect(truncateForDisplay("alpha")).toBe("alpha");
    const long = "x".repeat(200);
    expect(truncateForDisplay(long).length).toBe(81);
    expect(truncateForDisplay(long).endsWith("\u2026")).toBe(true);
  });
});

describe("formatMatchPickList", () => {
  it("clamps huge queries so the header cannot blow the content budget", () => {
    const { content } = formatMatchPickList("q".repeat(5000), ["Alpha"]);
    expect(content.length).toBeLessThanOrEqual(MAX_CONTENT_LENGTH);
  });

  it("lists tied matches and a refine hint", () => {
    const { content, count } = formatMatchPickList("alpha", ["Alpha One", "Alpha Two"]);
    expect(count).toBe(2);
    expect(content).toContain("### Multiple matches for `alpha`");
    expect(content).toContain("• Alpha One");
    expect(content).toContain("• Alpha Two");
    expect(content).toContain("Refine your query");
  });
});

describe("formatServerListPage", () => {
  it("formats the first page of server names", () => {
    const { content, currentPage, totalPages } = formatServerListPage(["Alpha", "Beta"], 1);
    expect(currentPage).toBe(1);
    expect(totalPages).toBe(1);
    expect(content).toContain("### Servers (2)");
    expect(content).toContain("• Alpha");
    expect(content).toContain("• Beta");
  });

  it("paginates and includes next-page hint", () => {
    const names = Array.from({ length: 41 }, (_, i) => `Server ${i + 1}`);
    const { content, currentPage, totalPages } = formatServerListPage(names, 1);
    expect(currentPage).toBe(1);
    expect(totalPages).toBe(2);
    expect(content).toContain("*Use /servers 2 to see more.*");
  });

  it("escapes markdown in server names", () => {
    const { content } = formatServerListPage(["Test_Server"], 1);
    expect(content).toContain("• Test\\_Server");
  });

  it("keeps each page under the Discord character budget", () => {
    const names = Array.from({ length: 40 }, () => "a".repeat(100));
    const { totalPages } = formatServerListPage(names, 1);
    expect(totalPages).toBeGreaterThan(1);

    for (let page = 1; page <= totalPages; page++) {
      const { content } = formatServerListPage(names, page);
      expect(content.length).toBeLessThanOrEqual(MAX_CONTENT_LENGTH);
    }
  });

  it("treats non-finite page args as page 1", () => {
    const { currentPage } = formatServerListPage(["Alpha"], Number.NaN);
    expect(currentPage).toBe(1);
  });
});
