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
  const totalLines = incoming.split("\n").filter((l) => l.trim()).length;
  const imported = incomingMap.size;
  const skipped = totalLines - imported;

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
