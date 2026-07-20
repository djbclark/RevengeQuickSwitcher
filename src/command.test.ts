import { describe, expect, it, vi } from "vitest";
import { executeServersCommand, parseCommandArgs } from "./command";

const sampleGuilds = [
  { id: "1", name: "Alpha Guild" },
  { id: "2", name: "Beta Guild" },
  { id: "3", name: "Wayland High School" },
];

const createDeps = (overrides: Partial<Parameters<typeof executeServersCommand>[1]> = {}) => ({
  getGuilds: () => sampleGuilds,
  aliases: "",
  navigateToGuild: vi.fn(),
  showToast: vi.fn(),
  ...overrides,
});

describe("parseCommandArgs", () => {
  it("reads query and page from object-style args", () => {
    expect(parseCommandArgs({ query: "alpha", page: 2 })).toEqual({
      query: "alpha",
      page: 2,
    });
  });

  it("reads query and page from array-style args", () => {
    expect(
      parseCommandArgs([
        { name: "query", value: "beta" },
        { name: "page", value: 3 },
      ]),
    ).toEqual({
      query: "beta",
      page: 3,
    });
  });

  it("reads nested option values", () => {
    expect(
      parseCommandArgs([
        { name: "query", value: { value: "alpha" } },
        { name: "page", value: { value: 2 } },
      ]),
    ).toEqual({
      query: "alpha",
      page: 2,
    });
  });

  it("falls back to positional filled options when names are missing", () => {
    expect(parseCommandArgs([{ value: "wayland" }])).toEqual({
      query: "wayland",
      page: null,
    });
  });

  it("treats numeric query as a page number", () => {
    expect(parseCommandArgs({ query: "2" })).toEqual({
      query: null,
      page: 2,
    });
  });

  it("preserves non-numeric query strings", () => {
    expect(parseCommandArgs({ query: "  alpha  " })).toEqual({
      query: "  alpha  ",
      page: null,
    });
  });

  it("ignores non-finite page values", () => {
    expect(parseCommandArgs({ page: "abc" })).toEqual({
      query: null,
      page: null,
    });
  });
});

describe("unwrapArgValue cycle guard", () => {
  it("terminates on self-referencing option objects", () => {
    const cyclic: Record<string, unknown> = {};
    cyclic.value = cyclic;
    expect(() => parseCommandArgs([{ name: "query", value: cyclic }])).not.toThrow();
  });
});

describe("executeServersCommand", () => {
  it("shows a toast when no guilds are available", () => {
    const deps = createDeps({ getGuilds: () => [] });
    executeServersCommand({}, deps);
    expect(deps.showToast).toHaveBeenCalledWith("No servers found", "danger");
  });

  it("returns a switcher payload by default (sheet-first, markdown fallback)", () => {
    const deps = createDeps();
    const result = executeServersCommand({}, deps);
    expect(result?.kind).toBe("switcher");
    expect(result?.content).toContain("### Servers (3)");
    expect(result?.content).toContain("• Alpha Guild");
    if (result && "items" in result) {
      expect(result.items).toEqual([
        { id: "1", name: "Alpha Guild" },
        { id: "2", name: "Beta Guild" },
        { id: "3", name: "Wayland High School" },
      ]);
    }
  });

  it("returns a paginated page payload when page is set", () => {
    const deps = createDeps();
    const result = executeServersCommand({ page: 1 }, deps);
    expect(result?.kind).toBe("page");
    expect(result?.content).toContain("### Servers (3)");
  });

  it("navigates to a fuzzy-matched guild", () => {
    const recordRecent = vi.fn();
    const deps = createDeps({ recordRecent });
    const result = executeServersCommand({ query: "wsh" }, deps);
    expect(deps.navigateToGuild).toHaveBeenCalledWith("3");
    expect(recordRecent).toHaveBeenCalledWith("3");
    expect(deps.showToast).toHaveBeenCalledWith("Jumped to Wayland High School", "success");
    expect(result?.kind).toBe("jump");
    expect(result?.content).toContain("Wayland High School");
  });

  it("does not record recents or claim success when navigation fails", () => {
    const recordRecent = vi.fn();
    const deps = createDeps({ navigateToGuild: vi.fn(() => false), recordRecent });
    const result = executeServersCommand({ query: "wsh" }, deps);
    expect(recordRecent).not.toHaveBeenCalled();
    expect(deps.showToast).toHaveBeenCalledWith("Could not navigate to server", "danger");
    expect(deps.showToast).not.toHaveBeenCalledWith("Jumped to Wayland High School", "success");
    expect(result?.kind).toBe("error");
  });

  it("returns an error payload when no guilds are available", () => {
    const deps = createDeps({ getGuilds: () => [] });
    const result = executeServersCommand({}, deps);
    expect(result?.kind).toBe("error");
    expect(result?.content).toContain("No servers found");
  });

  it("truncates very long queries in the no-match reply", () => {
    const deps = createDeps();
    const result = executeServersCommand({ query: "z".repeat(500) }, deps);
    expect(result?.kind).toBe("error");
    expect(result!.content!.length).toBeLessThan(200);
  });

  it("returns visible content when no match is found", () => {
    const deps = createDeps();
    const result = executeServersCommand({ query: "zzzznotaserver" }, deps);
    expect(deps.showToast).toHaveBeenCalledWith("No match found", "danger");
    expect(result?.kind).toBe("error");
    expect(result?.content).toContain("No match");
  });

  it("reads revenge-style array args for query jumps", () => {
    const deps = createDeps();
    const result = executeServersCommand([{ name: "query", value: "wsh", type: 3 }], deps);
    expect(deps.navigateToGuild).toHaveBeenCalledWith("3");
    expect(result?.kind).toBe("jump");
  });

  it("lists recent servers from stored ids", () => {
    const deps = createDeps({
      getRecentIds: () => ["3", "1"],
    });
    const result = executeServersCommand({ query: "recent" }, deps);
    expect(result?.kind).toBe("recent-list");
    expect(result?.content).toContain("Wayland High School");
    expect(result?.content).toContain("`/servers r1`");
    expect(deps.navigateToGuild).not.toHaveBeenCalled();
  });

  it("jumps to a recent slot and records it again", () => {
    const recordRecent = vi.fn();
    const deps = createDeps({
      getRecentIds: () => ["2", "3"],
      recordRecent,
    });
    executeServersCommand({ query: "r2" }, deps);
    expect(deps.navigateToGuild).toHaveBeenCalledWith("3");
    expect(recordRecent).toHaveBeenCalledWith("3");
  });

  it("reports when a recent slot is empty", () => {
    const deps = createDeps({ getRecentIds: () => ["1"] });
    executeServersCommand({ query: "r3" }, deps);
    expect(deps.showToast).toHaveBeenCalledWith("No recent server in slot r3", "danger");
    expect(deps.navigateToGuild).not.toHaveBeenCalled();
  });

  it("returns a pick list when multiple servers share the best score", () => {
    const deps = createDeps({
      getGuilds: () => [
        { id: "1", name: "Alpha One" },
        { id: "2", name: "Alpha Two" },
        { id: "3", name: "Beta" },
      ],
    });
    const result = executeServersCommand({ query: "alpha" }, deps);
    expect(deps.navigateToGuild).not.toHaveBeenCalled();
    expect(deps.showToast).toHaveBeenCalledWith("2 matches — refine your query", "danger");
    expect(result?.kind).toBe("pick-list");
    expect(result?.content).toContain("Multiple matches");
    expect(result?.content).toContain("• Alpha One");
    expect(result?.content).toContain("• Alpha Two");
    if (result && "items" in result) {
      expect(result.items).toEqual([
        { id: "1", name: "Alpha One" },
        { id: "2", name: "Alpha Two" },
      ]);
    }
  });

  it("resolves aliases before searching", () => {
    const deps = createDeps({ aliases: "school=Wayland High School" });
    executeServersCommand({ query: "school" }, deps);
    expect(deps.navigateToGuild).toHaveBeenCalledWith("3");
  });

  it("reports when search finds no match", () => {
    const deps = createDeps();
    executeServersCommand({ query: "missing-server" }, deps);
    expect(deps.showToast).toHaveBeenCalledWith("No match found", "danger");
    expect(deps.navigateToGuild).not.toHaveBeenCalled();
  });

  it("lists servers when query is only whitespace", () => {
    const deps = createDeps();
    const result = executeServersCommand({ query: "   " }, deps);
    expect(result?.content).toContain("### Servers (3)");
    expect(deps.navigateToGuild).not.toHaveBeenCalled();
  });

  it("clamps page numbers beyond the last page", () => {
    const deps = createDeps();
    const result = executeServersCommand({ page: 99 }, deps);
    expect(result?.kind).toBe("page");
    if (result?.kind === "page") {
      expect(result.currentPage).toBe(1);
      expect(result.totalPages).toBe(1);
    }
  });

  it("does not navigate when a match lacks a guild id", () => {
    const deps = createDeps({
      getGuilds: () => [{ name: "Ghost Guild" }],
    });
    executeServersCommand({ query: "ghost" }, deps);
    expect(deps.navigateToGuild).not.toHaveBeenCalled();
    expect(deps.showToast).toHaveBeenCalledWith("Could not resolve server id", "danger");
  });

  it("ignores excluded servers during search", () => {
    const deps = createDeps({
      excludes: "Beta Guild\n~wayland",
    });
    executeServersCommand({ query: "beta" }, deps);
    expect(deps.navigateToGuild).not.toHaveBeenCalled();
    expect(deps.showToast).toHaveBeenCalledWith("No match found", "danger");

    executeServersCommand({ query: "wsh" }, deps);
    expect(deps.navigateToGuild).not.toHaveBeenCalled();
  });

  it("still lists excluded servers unless hideExcludedFromList is on", () => {
    const deps = createDeps({ excludes: "Beta Guild" });
    const listed = executeServersCommand({}, deps);
    expect(listed?.content).toContain("• Beta Guild");

    const hidden = executeServersCommand(
      {},
      createDeps({
        excludes: "Beta Guild",
        hideExcludedFromList: true,
      }),
    );
    expect(hidden?.content).not.toContain("• Beta Guild");
    expect(hidden?.content).toContain("### Servers (2)");
  });
});
