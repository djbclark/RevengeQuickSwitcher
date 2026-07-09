import { describe, expect, it } from "vitest";
import {
  createSidebarCache,
  flattenSidebarNodes,
  sortSidebarNodesByGuildName,
  transformFlatSidebar,
} from "./sidebar";

const guildNames: Record<string, string> = {
  "1": "Zeta Server",
  "2": "Alpha Server",
  "3": "Beta Server",
};

const getGuildName = (id: string) => guildNames[id] ?? null;

describe("flattenSidebarNodes", () => {
  it("expands folders and keeps standalone guild nodes", () => {
    const nodes = [
      { id: "1" },
      { type: "folder", guilds: [{ id: "2" }, { id: "3" }] },
    ];

    expect(flattenSidebarNodes(nodes)).toEqual([{ id: "1" }, { id: "2" }, { id: "3" }]);
  });

  it("handles empty folder guild lists", () => {
    expect(flattenSidebarNodes([{ type: "folder", guilds: [] }])).toEqual([]);
  });
});

describe("sortSidebarNodesByGuildName", () => {
  it("sorts guilds alphabetically by resolved names", () => {
    const nodes = [{ id: "1" }, { id: "3" }, { id: "2" }];
    expect(sortSidebarNodesByGuildName(nodes, getGuildName)).toEqual([
      { id: "2" },
      { id: "3" },
      { id: "1" },
    ]);
  });

  it("places unknown guild names first in sort order", () => {
    const nodes = [{ id: "1" }, { id: "missing" }];
    const sorted = sortSidebarNodesByGuildName(nodes, getGuildName);
    expect(sorted[0]).toEqual({ id: "missing" });
    expect(sorted[1]).toEqual({ id: "1" });
  });
});

describe("createSidebarCache", () => {
  it("reuses cached output when checksum is unchanged", () => {
    const cache = createSidebarCache<{ id: string }>();
    const source = [{ id: "2" }, { id: "1" }];
    let computeCount = 0;

    const compute = () => {
      computeCount += 1;
      return sortSidebarNodesByGuildName(source, getGuildName);
    };

    const first = cache.getOrCompute(source, compute, getGuildName);
    const second = cache.getOrCompute(source, compute, getGuildName);

    expect(first).toBe(second);
    expect(computeCount).toBe(1);
  });

  it("recomputes when the source array identity changes", () => {
    const cache = createSidebarCache<{ id: string }>();
    let computeCount = 0;

    const compute = (source: { id: string }[]) => {
      computeCount += 1;
      return sortSidebarNodesByGuildName(source, getGuildName);
    };

    cache.getOrCompute([{ id: "2" }], () => compute([{ id: "2" }]), getGuildName);
    cache.getOrCompute([{ id: "1" }], () => compute([{ id: "1" }]), getGuildName);

    expect(computeCount).toBe(2);
  });

  it("recomputes when nested folder membership changes on the same array", () => {
    const cache = createSidebarCache<{ id?: string; type?: string; guilds?: { id: string }[] }>();
    const source = [{ type: "folder", id: "folder1", guilds: [{ id: "1" }, { id: "2" }] }];
    let computeCount = 0;

    const first = cache.getOrCompute(
      source,
      () => {
        computeCount += 1;
        return sortSidebarNodesByGuildName(source, getGuildName);
      },
      getGuildName
    );

    source[0].guilds = [{ id: "1" }, { id: "3" }];

    const second = cache.getOrCompute(
      source,
      () => {
        computeCount += 1;
        return sortSidebarNodesByGuildName(source, getGuildName);
      },
      getGuildName
    );

    expect(computeCount).toBe(2);
    expect(first).not.toBe(second);
    expect(second.map((node) => node.id)).toEqual(["3", "1"]);
  });

  it("clears cached entries", () => {
    const cache = createSidebarCache<{ id: string }>();
    const source = [{ id: "2" }, { id: "1" }];
    let computeCount = 0;
    const compute = () => {
      computeCount += 1;
      return sortSidebarNodesByGuildName(source, getGuildName);
    };

    cache.getOrCompute(source, compute, getGuildName);
    cache.clear();
    cache.getOrCompute(source, compute, getGuildName);

    expect(computeCount).toBe(2);
  });
});

describe("transformFlatSidebar", () => {
  it("returns input unchanged when flat sidebar is disabled", () => {
    const cache = createSidebarCache();
    const input = [{ id: "2" }, { id: "1" }];
    expect(transformFlatSidebar(input, false, getGuildName, cache)).toBe(input);
  });

  it("returns input unchanged for non-array values", () => {
    const cache = createSidebarCache();
    expect(transformFlatSidebar(null, true, getGuildName, cache)).toBeNull();
  });

  it("flattens folders and sorts when enabled", () => {
    const cache = createSidebarCache();
    const input = [
      { type: "folder", guilds: [{ id: "1" }, { id: "3" }] },
      { id: "2" },
    ];

    expect(transformFlatSidebar(input, true, getGuildName, cache)).toEqual([
      { id: "2" },
      { id: "3" },
      { id: "1" },
    ]);
  });
});
