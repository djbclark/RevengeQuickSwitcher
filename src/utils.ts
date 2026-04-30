export const escapeMarkdown = (t: string) => t.replace(/([\\_*~`|])/g, '\\$1');
export const sanitizeName = (t: string) => t ? Array.from(String(t)).slice(0, 100).join("").replace(/[\u200B-\u200D\uFEFF\u202A-\u202E\u2066-\u2069]/g, '').trim() || "Unnamed" : "Unknown";
export const normalizeText = (t: string) => t.normalize("NFKC").toLowerCase();
export const resolveGuildId = (n: any) => n?.id || n?.guildId || n?.guild_id || (typeof n === 'string' ? n : null);
export const getArrayChecksum = (arr: any[]) => {
  let ck = 0x811c9dc5; 
  for (let i = 0; i < arr.length; i++) {
    const id = resolveGuildId(arr[i]);
    if (id) { for (let j = 0; j < id.length; j++) { ck ^= id.charCodeAt(j); ck = Math.imul(ck, 0x01000193); } }
  }
  return ck;
};
export const isSubsequence = (q: string, t: string) => {
  let i = 0;
  for (let j = 0; j < t.length && i < q.length; j++) if (q[i] === t[j]) i++;
  return i === q.length;
};
