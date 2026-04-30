export const escapeMarkdown = (text: string) => {
  return text.replace(/([\\_*~`|])/g, '\\$1');
};

export const sanitizeName = (text: string) => {
  if (!text) return "Unknown";
  const safeText = Array.from(String(text))
    .slice(0, 100)
    .join("")
    .replace(/[\u200B-\u200D\uFEFF\u202A-\u202E\u2066-\u2069]/g, '')
    .trim();
  return safeText || "Unnamed";
};

export const normalizeText = (text: string) => {
  return text.normalize("NFKC").toLowerCase();
};

export const resolveGuildId = (node: any) => {
  return node?.id || node?.guildId || node?.guild_id || (typeof node === 'string' ? node : null);
};

// Generates an FNV-1a hash to quickly check if the sidebar array has changed
export const getArrayChecksum = (arr: any[]) => {
  let checksum = 0x811c9dc5; 
  for (let i = 0; i < arr.length; i++) {
    const id = resolveGuildId(arr[i]);
    if (id) { 
      for (let j = 0; j < id.length; j++) { 
        checksum ^= id.charCodeAt(j); 
        checksum = Math.imul(checksum, 0x01000193); 
      } 
    }
  }
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

// Parses newline-separated alias strings into a Map
export const parseAliases = (raw: string) => {
  const map = new Map<string, string>();
  if (!raw) return map;
  
  raw.split('\n').forEach(line => {
    const parts = line.split('=');
    if (parts.length === 2) {
      const alias = normalizeText(parts[0].trim());
      const target = normalizeText(parts[1].trim());
      if (alias && target) map.set(alias, target);
    }
  });
  return map;
};
