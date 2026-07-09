import * as Excludes from "./excludes";
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
  excludes?: string;
  hideExcludedFromList?: boolean;
};

type CommandArg = { name?: string; value?: unknown; type?: number; [key: string]: unknown };

/** Discord/Revenge option values are usually primitives, but clients sometimes nest them. */
export const unwrapArgValue = (value: unknown): unknown => {
  if (value == null) return null;
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return value;
  }
  if (typeof value === "object") {
    const record = value as Record<string, unknown>;
    if ("value" in record) return unwrapArgValue(record.value);
    if (typeof record.text === "string") return record.text;
    if (typeof record.label === "string") return record.label;
  }
  return value;
};

const normalizeArgList = (rawArgs: unknown): CommandArg[] => {
  if (rawArgs == null) return [];
  if (Array.isArray(rawArgs)) return rawArgs as CommandArg[];
  if (typeof rawArgs === "object") {
    return Object.keys(rawArgs as Record<string, unknown>).map((name) => ({
      name,
      value: (rawArgs as Record<string, unknown>)[name],
    }));
  }
  return [];
};

export const parseCommandArgs = (rawArgs: unknown) => {
  const args = normalizeArgList(rawArgs);

  const namedQuery = args.find((arg) => arg?.name === "query");
  const namedPage = args.find((arg) => arg?.name === "page");

  let query = unwrapArgValue(namedQuery?.value);
  let page = unwrapArgValue(namedPage?.value);

  // Some clients omit `name` and only pass filled options in order (query, page).
  if (query == null && page == null && args.length > 0) {
    const first = unwrapArgValue(args[0]?.value ?? args[0]);
    const second = args.length > 1 ? unwrapArgValue(args[1]?.value ?? args[1]) : null;
    if (typeof first === "number" || (typeof first === "string" && /^\d+$/.test(first.trim()))) {
      page = first;
    } else if (first != null && first !== "") {
      query = first;
      if (second != null && second !== "") page = second;
    }
  }

  if (page == null && query != null && /^\d+$/.test(String(query).trim())) {
    page = parseInt(String(query).trim(), 10);
    query = null;
  }

  const pageNumber = page != null ? Number(page) : null;

  return {
    query: query != null && String(query).length > 0 ? String(query) : null,
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
    return { kind: "error" as const, content: "Could not resolve server id" };
  }
  deps.navigateToGuild(id);
  deps.recordRecent?.(id);
  const name = Utils.sanitizeName(guild.name);
  const message = successMessage ?? `Jumped to ${name}`;
  deps.showToast(message, "success");
  // Always return content so the host can post a visible in-channel confirmation
  // (toasts alone are easy to miss / sometimes no-op on mobile).
  return { kind: "jump" as const, content: `→ **${Utils.escapeMarkdown(name)}**`, id, name };
};

export const executeServersCommand = (rawArgs: unknown, deps: ServersCommandDeps) => {
  const { query, page } = parseCommandArgs(rawArgs);
  const guilds = deps.getGuilds();
  const excludeRules = Excludes.parseExcludeRules(deps.excludes || "");
  deps.debugLog?.("executeServersCommand", {
    query,
    page,
    guildCount: guilds.length,
    excludeRules: excludeRules.length,
  });

  if (!guilds.length) {
    deps.showToast("No servers found", "danger");
    return;
  }

  const mappedGuilds = guilds
    .map((guild) => {
      const id = Utils.resolveGuildId(guild) || "";
      const sanitized = Utils.sanitizeName(guild.name);
      const normalized = Utils.normalizeText(sanitized);
      return {
        original: guild,
        id,
        sanitized,
        normalized,
        excluded: Excludes.isGuildExcluded(id, normalized, excludeRules),
      };
    })
    .sort((a, b) => a.sanitized.localeCompare(b.sanitized, undefined, { sensitivity: "base" }));

  const searchableGuilds = mappedGuilds.filter((item) => !item.excluded);
  const listGuilds = deps.hideExcludedFromList ? searchableGuilds : mappedGuilds;

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
      return jumpToGuild(deps, guild);
    }

    if (!searchableGuilds.length) {
      deps.showToast("All servers are excluded", "danger");
      return { kind: "error" as const, content: "All servers are excluded" };
    }

    const aliasMap = Utils.parseAliases(deps.aliases);
    const normalizedQuery = Utils.resolveSearchQuery(trimmed, aliasMap);
    const { matches, score } = Utils.findBestMatches(normalizedQuery, searchableGuilds);
    deps.debugLog?.("search", { normalizedQuery, score, matchCount: matches.length });

    if (matches.length === 0) {
      deps.showToast("No match found", "danger");
      return { kind: "error" as const, content: `No match for \`${Utils.escapeMarkdown(trimmed)}\`` };
    }

    if (matches.length > 1) {
      deps.showToast(`${matches.length} matches — refine your query`, "danger");
      return Utils.formatMatchPickList(
        trimmed,
        matches.map((match) => match.sanitized)
      );
    }

    return jumpToGuild(deps, matches[0].original);
  }

  if (!listGuilds.length) {
    deps.showToast("All servers are excluded", "danger");
    return;
  }

  const sanitizedNames = listGuilds.map((item) => item.sanitized);
  return Utils.formatServerListPage(sanitizedNames, page);
};
