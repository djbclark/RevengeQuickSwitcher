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

  if (query?.trim()) {
    const aliasMap = Utils.parseAliases(deps.aliases);
    const normalizedQuery = Utils.resolveSearchQuery(query.trim(), aliasMap);
    const { matches, score } = Utils.findBestMatches(normalizedQuery, mappedGuilds);
    deps.debugLog?.("search", { normalizedQuery, score, matchCount: matches.length });

    if (matches.length === 0) {
      deps.showToast("No match found", "danger");
      return;
    }

    if (matches.length > 1) {
      deps.showToast(`${matches.length} matches — refine your query`, "danger");
      return Utils.formatMatchPickList(
        query.trim(),
        matches.map((match) => match.sanitized)
      );
    }

    const bestMatch = matches[0].original;
    const id = Utils.resolveGuildId(bestMatch);
    if (id) {
      deps.navigateToGuild(id);
      deps.showToast(`Jumped to ${Utils.sanitizeName(bestMatch.name)}`, "success");
    } else {
      deps.showToast("Could not resolve server id", "danger");
    }
    return;
  }

  const sanitizedNames = mappedGuilds.map((item) => item.sanitized);
  return Utils.formatServerListPage(sanitizedNames, page);
};
