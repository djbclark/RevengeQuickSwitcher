import { escapeMarkdown, sanitizeName } from "./utils";

export const DEFAULT_RECENT_HISTORY_SIZE = 10;
export const MIN_RECENT_HISTORY_SIZE = 1;
export const MAX_RECENT_HISTORY_SIZE = 15;

export const clampRecentHistorySize = (value: unknown): number => {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return DEFAULT_RECENT_HISTORY_SIZE;
  return Math.min(MAX_RECENT_HISTORY_SIZE, Math.max(MIN_RECENT_HISTORY_SIZE, Math.trunc(n)));
};

export const parseRecentIds = (raw: unknown): string[] => {
  if (Array.isArray(raw)) {
    return raw.map(String).filter(Boolean);
  }
  if (typeof raw !== "string" || !raw.trim()) return [];
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) return parsed.map(String).filter(Boolean);
  } catch {
    // Fall through to newline-separated format.
  }
  return raw
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
};

export const serializeRecentIds = (ids: string[]): string => JSON.stringify(ids);

/** Move id to the front, dedupe, and cap length. */
export const pushRecentId = (ids: string[], id: string, maxSize: number): string[] => {
  if (!id) return ids.slice(0, clampRecentHistorySize(maxSize));
  const size = clampRecentHistorySize(maxSize);
  return [id, ...ids.filter((existing) => existing !== id)].slice(0, size);
};

export const isRecentListQuery = (query: string): boolean => {
  return /^recent$/i.test(query.trim());
};

/** `r1` → 1-based slot index, or null if not a recent-slot query. */
export const parseRecentSlot = (query: string): number | null => {
  const match = /^r(\d+)$/i.exec(query.trim());
  if (!match) return null;
  const slot = parseInt(match[1], 10);
  return slot >= 1 ? slot : null;
};

export type RecentEntry = {
  id: string;
  name: string;
};

export const resolveRecentEntries = (recentIds: string[], guildsById: Map<string, { name: string }>): RecentEntry[] => {
  const entries: RecentEntry[] = [];
  for (const id of recentIds) {
    const guild = guildsById.get(id);
    if (!guild) continue;
    entries.push({ id, name: sanitizeName(guild.name) });
  }
  return entries;
};

export const formatRecentList = (entries: RecentEntry[]) => {
  if (entries.length === 0) {
    return {
      kind: "recent-list" as const,
      content:
        "### Recent servers\n*No recent jumps yet. Use `/servers query:…` to jump; history is recorded only when this plugin navigates.*",
      count: 0,
    };
  }

  const lines = entries.map(
    (entry, index) => `${index + 1}. ${escapeMarkdown(entry.name)} — \`/servers r${index + 1}\``,
  );
  const content =
    `### Recent servers (${entries.length})\n` +
    lines.join("\n") +
    `\n\n*History updates only when Quick Server Switcher jumps you.*`;

  return { kind: "recent-list" as const, content, count: entries.length };
};
