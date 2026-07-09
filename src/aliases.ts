import { parseAliases } from "./utils";

/** Normalize alias text: trim lines, drop blanks, keep first-= semantics via parseAliases round-trip. */
export const normalizeAliasText = (raw: string): string => {
  if (!raw) return "";
  const map = parseAliases(raw);
  return Array.from(map.entries())
    .map(([alias, target]) => `${alias}=${target}`)
    .sort((a, b) => a.localeCompare(b))
    .join("\n");
};

export type MergeAliasesResult = {
  text: string;
  imported: number;
  skipped: number;
  total: number;
};

/**
 * Merge clipboard/import text into existing aliases.
 * Later duplicate alias keys overwrite earlier ones (import wins over existing).
 */
export const mergeAliasText = (existing: string, incoming: string): MergeAliasesResult => {
  const before = parseAliases(existing);
  const incomingMap = parseAliases(incoming);
  let imported = 0;
  let skipped = 0;

  for (const line of incoming.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    const separator = trimmed.indexOf("=");
    if (separator <= 0) {
      skipped += 1;
      continue;
    }
    const alias = trimmed.slice(0, separator).trim();
    const target = trimmed.slice(separator + 1).trim();
    if (!alias || !target) {
      skipped += 1;
      continue;
    }
    imported += 1;
  }

  const merged = new Map([...before, ...incomingMap]);
  const text = Array.from(merged.entries())
    .map(([alias, target]) => `${alias}=${target}`)
    .sort((a, b) => a.localeCompare(b))
    .join("\n");

  return {
    text,
    imported,
    skipped,
    total: merged.size,
  };
};

export const countAliasEntries = (raw: string): number => parseAliases(raw).size;
