import { getArrayChecksum, resolveGuildId, sanitizeName, type GuildLike } from "./utils";

export type SidebarNode = GuildLike;

export const flattenSidebarNodes = (nodes: SidebarNode[]) => {
  return nodes.flatMap((node) => (node.type === "folder" ? node.guilds ?? [] : [node]));
};

export const sortSidebarNodesByGuildName = (
  nodes: SidebarNode[],
  getGuildName: (id: string) => string | null
) => {
  return flattenSidebarNodes(nodes)
    .map((node) => {
      const id = resolveGuildId(node);
      const name = id ? getGuildName(id) : null;
      return { node, name: name ? sanitizeName(name) : "" };
    })
    .sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: "base" }))
    .map((item) => item.node);
};

export type SidebarCache<T extends GuildLike> = {
  clear: () => void;
  getOrCompute: (
    source: T[],
    compute: () => SidebarNode[],
    getGuildName?: (id: string) => string | null
  ) => SidebarNode[];
};

export const createSidebarCache = <T extends GuildLike>(): SidebarCache<T> => {
  let cache = new WeakMap<T[], { checksum: number; data: SidebarNode[] }>();

  return {
    clear() {
      cache = new WeakMap();
    },
    getOrCompute(source, compute, getGuildName) {
      const checksum = getArrayChecksum(source, getGuildName);
      const cached = cache.get(source);
      if (cached?.checksum === checksum) return cached.data;

      const data = compute();
      cache.set(source, { checksum, data });
      return data;
    },
  };
};

export const transformFlatSidebar = (
  returnValue: unknown,
  enabled: boolean,
  getGuildName: (id: string) => string | null,
  cache: SidebarCache<SidebarNode>
) => {
  if (!enabled || !Array.isArray(returnValue)) return returnValue;

  return cache.getOrCompute(
    returnValue,
    () => sortSidebarNodesByGuildName(returnValue, getGuildName),
    getGuildName
  );
};
