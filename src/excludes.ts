import { normalizeText } from "./utils";

export type ExcludeRule = { type: "id"; value: string } | { type: "name"; value: string; mode: "exact" | "contains" };

const looksLikeSnowflake = (value: string) => /^\d{5,}$/.test(value);

/** Parse newline-separated exclude rules (ids or names). */
export const parseExcludeRules = (raw: string): ExcludeRule[] => {
  if (!raw) return [];
  const rules: ExcludeRule[] = [];

  for (const line of raw.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;

    if (looksLikeSnowflake(trimmed)) {
      rules.push({ type: "id", value: trimmed });
      continue;
    }

    // `~pattern` → substring match; otherwise exact normalized name.
    if (trimmed.startsWith("~")) {
      const value = normalizeText(trimmed.slice(1).trim());
      if (value.length >= 2) rules.push({ type: "name", value, mode: "contains" });
      continue;
    }

    const value = normalizeText(trimmed);
    if (value) rules.push({ type: "name", value, mode: "exact" });
  }

  return rules;
};

export const isGuildExcluded = (id: string, normalizedName: string, rules: ExcludeRule[]): boolean => {
  if (!rules.length) return false;

  for (const rule of rules) {
    if (rule.type === "id") {
      if (id && id === rule.value) return true;
      continue;
    }
    if (!normalizedName) continue;
    if (rule.mode === "exact" && normalizedName === rule.value) return true;
    if (rule.mode === "contains" && normalizedName.includes(rule.value)) return true;
  }

  return false;
};

export const countExcludeRules = (raw: string): number => parseExcludeRules(raw).length;

export const formatExcludeHelp = () =>
  "One per line: server name, Discord id, or ~partial name. Lines starting with # are comments.";
