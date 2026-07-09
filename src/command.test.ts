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
    expect(parseCommandArgs([
      { name: "query", value: "beta" },
      { name: "page", value: 3 },
    ])).toEqual({
      query: "beta",
      page: 3,
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

describe("executeServersCommand", () => {
  it("shows a toast when no guilds are available", () => {
    const deps = createDeps({ getGuilds: () => [] });
    executeServersCommand({}, deps);
    expect(deps.showToast).toHaveBeenCalledWith("No servers found", "danger");
  });

  it("returns a paginated server list by default", () => {
    const deps = createDeps();
    const result = executeServersCommand({}, deps);
    expect(result?.content).toContain("### Servers (3)");
    expect(result?.content).toContain("• Alpha Guild");
    expect(result?.currentPage).toBe(1);
  });

  it("navigates to a fuzzy-matched guild", () => {
    const deps = createDeps();
    executeServersCommand({ query: "wsh" }, deps);
    expect(deps.navigateToGuild).toHaveBeenCalledWith("3");
    expect(deps.showToast).toHaveBeenCalledWith("Jumped to Wayland High School", "success");
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
    expect(result?.currentPage).toBe(1);
    expect(result?.totalPages).toBe(1);
  });

  it("does not navigate when a match lacks a guild id", () => {
    const deps = createDeps({
      getGuilds: () => [{ name: "Ghost Guild" }],
    });
    executeServersCommand({ query: "ghost" }, deps);
    expect(deps.navigateToGuild).not.toHaveBeenCalled();
    expect(deps.showToast).toHaveBeenCalledWith("Could not resolve server id", "danger");
  });
});
