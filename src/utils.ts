export type GuildLike = {
  id?: string;
  guildId?: string;
  guild_id?: string;
  type?: string;
  guilds?: GuildLike[];
  name?: string;
};

export const escapeMarkdown = (text: string) => {
  return text.replace(/[\\_*~`|[\]()]/g, "\\$&");
};

export const sanitizeName = (text: string) => {
  if (!text) return "Unknown";
  const safeText = Array.from(String(text))
    .slice(0, 100)
    .join("")
    .replace(/[\u200B-\u200D\uFEFF\u202A-\u202E\u2066-\u2069]/g, "")
    .trim();
  return safeText || "Unnamed";
};

export const normalizeText = (text: string) => {
  return text.normalize("NFKC").toLowerCase();
};

export const resolveGuildId = (node: GuildLike | string | null | undefined): string | null => {
  if (typeof node === "string") return node;
  if (!node) return null;
  return node.id || node.guildId || node.guild_id || null;
};

const hashString = (checksum: number, value: string): number => {
  for (let i = 0; i < value.length; i++) {
    checksum ^= value.charCodeAt(i);
    checksum = Math.imul(checksum, 0x01000193);
  }
  // Field separator so "ab"+"c" differs from "a"+"bc"
  checksum ^= 0xff;
  checksum = Math.imul(checksum, 0x01000193);
  return checksum;
};

const visitSidebarFingerprint = (
  nodes: GuildLike[],
  getGuildName: ((id: string) => string | null) | undefined,
  visit: (token: string) => void
) => {
  for (const node of nodes) {
    if (node?.type === "folder") {
      const folderId = resolveGuildId(node);
      visit(`folder:${folderId ?? "?"}`);
      if (Array.isArray(node.guilds)) {
        visitSidebarFingerprint(node.guilds, getGuildName, visit);
      }
      continue;
    }

    const id = resolveGuildId(node);
    if (!id) continue;
    const name = getGuildName?.(id) ?? node.name ?? "";
    visit(id);
    if (name) visit(name);
  }
};

/** FNV-1a over flattened guild ids/names so folder membership and renames invalidate caches. */
export const getArrayChecksum = (
  arr: GuildLike[],
  getGuildName?: (id: string) => string | null
) => {
  let checksum = 0x811c9dc5;
  visitSidebarFingerprint(arr, getGuildName, (token) => {
    checksum = hashString(checksum, token);
  });
  return checksum;
};

// Checks if the characters of 'query' appear in order within 'text'
export const isSubsequence = (query: string, text: string) => {
  let i = 0;
  for (let j = 0; j < text.length && i < query.length; j++) {
    if (query[i] === text[j]) i++;
  }
  return i === query.length;
};

/** Subsequence matching is too aggressive for 1–2 character queries. */
export const MIN_SUBSEQUENCE_LENGTH = 3;

// Parses newline-separated alias strings into a Map
export const parseAliases = (raw: string) => {
  const map = new Map<string, string>();
  if (!raw) return map;

  raw.split("\n").forEach((line) => {
    const separator = line.indexOf("=");
    if (separator <= 0) return;
    const alias = normalizeText(line.slice(0, separator).trim());
    const target = normalizeText(line.slice(separator + 1).trim());
    if (alias && target) map.set(alias, target);
  });
  return map;
};

export const resolveSearchQuery = (query: string, aliasMap: Map<string, string>) => {
  let normalizedQuery = normalizeText(query).trim();
  if (aliasMap.has(normalizedQuery)) {
    normalizedQuery = aliasMap.get(normalizedQuery)!;
  }
  return normalizedQuery;
};

export const scoreGuildMatch = (normalizedQuery: string, normalizedName: string) => {
  if (normalizedName === normalizedQuery) return 100;
  if (normalizedName.startsWith(normalizedQuery)) return 50;
  if (normalizedName.includes(normalizedQuery)) return 10;
  if (
    normalizedQuery.length >= MIN_SUBSEQUENCE_LENGTH &&
    isSubsequence(normalizedQuery, normalizedName)
  ) {
    return 5;
  }
  return 0;
};

export type MatchResult<T> = {
  score: number;
  indexes: number[];
  matches: T[];
};

/** All candidates that share the highest positive score (list should be sorted). */
export const findBestMatches = <T extends { normalized: string }>(
  normalizedQuery: string,
  candidates: T[]
): MatchResult<T> => {
  let bestScore = 0;
  const indexes: number[] = [];

  for (let i = 0; i < candidates.length; i++) {
    const score = scoreGuildMatch(normalizedQuery, candidates[i].normalized);
    if (score <= 0) continue;
    if (score > bestScore) {
      bestScore = score;
      indexes.length = 0;
      indexes.push(i);
      continue;
    }
    if (score === bestScore) indexes.push(i);
  }

  return {
    score: bestScore,
    indexes,
    matches: indexes.map((index) => candidates[index]),
  };
};

/** Highest tier wins; within a tier the first candidate wins (list should be sorted). */
export const findBestMatchIndex = <T extends { normalized: string }>(
  normalizedQuery: string,
  candidates: T[]
): number => {
  const { indexes } = findBestMatches(normalizedQuery, candidates);
  return indexes[0] ?? -1;
};

/** Soft cap on items per page for typical short names. */
export const PAGE_SIZE = 40;

/** Hard cap so Discord command responses stay under the 2000-character limit. */
export const MAX_CONTENT_LENGTH = 1900;

export const formatMatchPickList = (
  query: string,
  sanitizedNames: string[]
) => {
  const header = `### Multiple matches for \`${escapeMarkdown(query)}\`\n`;
  const lines = sanitizedNames.map((name) => `• ${escapeMarkdown(name)}`);
  const hint = "\n\n*Refine your query or use a custom alias.*";
  let content = header + lines.join("\n") + hint;

  // Keep under Discord's limit if somehow huge.
  if (content.length > MAX_CONTENT_LENGTH) {
    const budget = MAX_CONTENT_LENGTH - header.length - hint.length - 20;
    const kept: string[] = [];
    let used = 0;
    for (const line of lines) {
      const extra = kept.length > 0 ? 1 + line.length : line.length;
      if (used + extra > budget) break;
      kept.push(line);
      used += extra;
    }
    const omitted = lines.length - kept.length;
    content =
      header +
      kept.join("\n") +
      (omitted > 0 ? `\n• …and ${omitted} more` : "") +
      hint;
  }

  return { kind: "pick-list" as const, content, count: sanitizedNames.length };
};

const FOOTER_RESERVE = 90;

const buildPages = (sanitizedNames: string[]): string[][] => {
  const headerLen = `### Servers (${sanitizedNames.length})\n`.length;
  const budget = Math.max(32, MAX_CONTENT_LENGTH - headerLen - FOOTER_RESERVE);
  const pages: string[][] = [];
  let current: string[] = [];
  let currentLen = 0;

  for (const name of sanitizedNames) {
    const line = `• ${escapeMarkdown(name)}`;
    const lineLen = line.length;
    const needsSeparator = current.length > 0;
    const contribution = lineLen + (needsSeparator ? 1 : 0);

    if ((needsSeparator && currentLen + contribution > budget) || current.length >= PAGE_SIZE) {
      pages.push(current);
      current = [];
      currentLen = 0;
    }

    current.push(name);
    currentLen += current.length === 1 ? lineLen : 1 + lineLen;
  }

  if (current.length > 0 || pages.length === 0) {
    pages.push(current);
  }

  return pages;
};

export const formatServerListPage = (
  sanitizedNames: string[],
  pageArg?: number | null
) => {
  const pages = buildPages(sanitizedNames);
  const totalPages = pages.length;
  const requested = pageArg != null && Number.isFinite(pageArg) ? pageArg : 1;
  const currentPage = Math.min(totalPages, Math.max(1, requested));
  const pageItems = pages[currentPage - 1] ?? [];

  let content = `### Servers (${sanitizedNames.length})\n`;
  content += pageItems.map((name) => `• ${escapeMarkdown(name)}`).join("\n");
  content += `\n\n**Page ${currentPage} of ${totalPages}**`;

  if (currentPage < totalPages) {
    content += `\n*Use /servers ${currentPage + 1} to see more.*`;
  } else if (totalPages > 1) {
    content += `\n*Use /servers 1 to return to the start.*`;
  }

  return { kind: "page" as const, content, currentPage, totalPages };
};
