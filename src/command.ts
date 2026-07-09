import * as Recents from "./recents";
import * as Utils from "./utils";

export type GuildRecord = {
  id?: string;
  guildId?: string;
  guild_id?: string;
  name: string;
};

export type ServersCommandDeps = {
  getGuilds: () => GuildRecord[];
  aliases: string;
  navigateToGuild: (id: string) => void;
  showToast: (message: string, type?: string) => void;
  debugLog?: (message: string, ...args: unknown[]) => void;
  getRecentIds?: () => string[];
  recordRecent?: (id: string) => void;
};

type CommandArg = { name: string; value: unknown };

export const parseCommandArgs = (rawArgs: unknown) => {
  const args: CommandArg[] = Array.isArray(rawArgs)
    ? rawArgs
    : Object.keys((rawArgs as Record<string, unknown>) || {}).map((name) => ({
        name,
        value: (rawArgs as Record<string, unknown>)[name],
      }));

  let query = args.find((arg) => arg.name === "query")?.value;
  let page = args.find((arg) => arg.name === "page")?.value;

  if (page == null && query != null && /^\d+$/.test(String(query).trim())) {
    page = parseInt(String(query).trim(), 10);
    query = null;
  }

  const pageNumber = page != null ? Number(page) : null;

  return {
    query: query != null ? String(query) : null,
    page: pageNumber != null && Number.isFinite(pageNumber) ? pageNumber : null,
  };
};

const jumpToGuild = (
  deps: ServersCommandDeps,
  guild: GuildRecord,
  successMessage?: string
) => {
  const id = Utils.resolveGuildId(guild);
  if (!id) {
    deps.showToast("Could not resolve server id", "danger");
    return;
  }
  deps.navigateToGuild(id);
  deps.recordRecent?.(id);
  deps.showToast(successMessage ?? `Jumped to ${Utils.sanitizeName(guild.name)}`, "success");
};

export const executeServersCommand = (rawArgs: unknown, deps: ServersCommandDeps) => {
  const { query, page } = parseCommandArgs(rawArgs);
  const guilds = deps.getGuilds();
  deps.debugLog?.("executeServersCommand", { query, page, guildCount: guilds.length });

  if (!guilds.length) {
    deps.showToast("No servers found", "danger");
    return;
  }

  const mappedGuilds = guilds
    .map((guild) => {
      const id = Utils.resolveGuildId(guild) || "";
      const sanitized = Utils.sanitizeName(guild.name);
      return {
        original: guild,
        id,
        sanitized,
        normalized: Utils.normalizeText(sanitized),
      };
    })
    .sort((a, b) => a.sanitized.localeCompare(b.sanitized, undefined, { sensitivity: "base" }));

  const guildsById = new Map(
    mappedGuilds.filter((item) => item.id).map((item) => [item.id, item.original])
  );

  if (query?.trim()) {
    const trimmed = query.trim();

    if (Recents.isRecentListQuery(trimmed)) {
      const recentIds = deps.getRecentIds?.() ?? [];
      const entries = Recents.resolveRecentEntries(recentIds, guildsById);
      deps.debugLog?.("recent list", { stored: recentIds.length, resolved: entries.length });
      return Recents.formatRecentList(entries);
    }

    const recentSlot = Recents.parseRecentSlot(trimmed);
    if (recentSlot != null) {
      const recentIds = deps.getRecentIds?.() ?? [];
      const entries = Recents.resolveRecentEntries(recentIds, guildsById);
      const entry = entries[recentSlot - 1];
      if (!entry) {
        deps.showToast(`No recent server in slot r${recentSlot}`, "danger");
        return;
      }
      const guild = guildsById.get(entry.id);
      if (!guild) {
        deps.showToast("Could not resolve server id", "danger");
        return;
      }
      jumpToGuild(deps, guild);
      return;
    }

    const aliasMap = Utils.parseAliases(deps.aliases);
    const normalizedQuery = Utils.resolveSearchQuery(trimmed, aliasMap);
    const { matches, score } = Utils.findBestMatches(normalizedQuery, mappedGuilds);
    deps.debugLog?.("search", { normalizedQuery, score, matchCount: matches.length });

    if (matches.length === 0) {
      deps.showToast("No match found", "danger");
      return;
    }

    if (matches.length > 1) {
      deps.showToast(`${matches.length} matches — refine your query`, "danger");
      return Utils.formatMatchPickList(
        trimmed,
        matches.map((match) => match.sanitized)
      );
    }

    jumpToGuild(deps, matches[0].original);
    return;
  }

  const sanitizedNames = mappedGuilds.map((item) => item.sanitized);
  return Utils.formatServerListPage(sanitizedNames, page);
};
