/**
 * PROJECT_PULSE: {
 * "version": "3.9.1",
 * "env": { "node": "25.x", "os": "macos", "mod": "revenge" },
 * "hacks": [ "decoupled-esbuild", "abstracted-git-makefile", "forceful-init" ],
 * "limit": "2000-char-discord-pagination"
 * }
 */
import React from "react";
import { findByProps } from "@revenge-mod/metro";
import { after } from "@revenge-mod/patcher";
import { showToast } from "@revenge-mod/ui/toast";
import { logger } from "@revenge-mod";
import { registerCommand } from "@revenge-mod/commands";
import { storage } from "@revenge-mod/plugin";
import { useProxy } from "@revenge-mod/storage";
import { Forms } from "@revenge-mod/ui/components";
import { ScrollView } from "react-native";
import * as Utils from "./utils";

const { FormSwitchRow } = Forms;
let _G: any, _S: any, _R: any, _N: any;
const getGS = () => _G ??= findByProps("getGuild", "getGuilds");
const getSGS = () => _S ??= findByProps("getSortedGuilds");
const getR = () => _R ??= findByProps("transitionToGuild", "selectGuild");
const getN = () => _N ??= findByProps("push", "replace");

if (storage.flatSidebar === undefined) storage.flatSidebar = false;
class MappedGuild { constructor(public original: any, public id: string, public sanitized: string, public normalized: string) {} }
const sidebarCache = new WeakMap<any[], { checksum: number, data: any[] }>();

const handleExec = (rawArgs: any) => {
  try {
    const args = Array.isArray(rawArgs) ? rawArgs : Object.keys(rawArgs || {}).map(k => ({ name: k, value: rawArgs[k] }));
    let query = args.find(a => a.name === "query")?.value;
    let pageArg = args.find(a => a.name === "page")?.value;

    if (!pageArg && query && /^\d+$/.test(String(query).trim())) {
      pageArg = parseInt(String(query).trim());
      query = null;
    }

    const guilds = Object.values(getGS()?.getGuilds() || {});
    if (!guilds.length) return showToast("No servers found", "danger");
    const mapped = guilds.map((g: any) => new MappedGuild(g, Utils.resolveGuildId(g) || "", Utils.sanitizeName(g.name), Utils.normalizeText(Utils.sanitizeName(g.name))))
      .sort((a, b) => a.sanitized.localeCompare(b.sanitized, undefined, { sensitivity: "base" }));

    if (query) {
      const q = Utils.normalizeText(String(query)).trim();
      let match = null, score = 0;
      for (const item of mapped) {
        const t = item.normalized;
        if (t === q) { match = item.original; break; }
        if (t.startsWith(q) && score < 50) { match = item.original; score = 50; }
        else if (t.includes(q) && score < 10) { match = item.original; score = 10; }
        else if (Utils.isSubsequence(q, t) && score < 5) { match = item.original; score = 5; }
      }
      if (match) {
        const id = Utils.resolveGuildId(match), R = getR(), N = getN();
        if (R?.transitionToGuild) R.transitionToGuild(id);
        else if (N?.push) N.push("Guild", { guildId: id });
        showToast(`Jumped to ${Utils.sanitizeName(match.name)}`, "success");
      } else showToast("No match", "danger");
      return;
    }

    const PAGE_SIZE = 40; 
    const totalPages = Math.ceil(mapped.length / PAGE_SIZE);
    const currentPage = Math.min(totalPages, Math.max(1, pageArg || 1));
    const start = (currentPage - 1) * PAGE_SIZE;
    const pageItems = mapped.slice(start, start + PAGE_SIZE);

    let content = `### Servers (${mapped.length})\n`;
    content += pageItems.map(i => `• ${Utils.escapeMarkdown(i.sanitized)}`).join("\n");
    content += `\n\n**Page ${currentPage} of ${totalPages}**`;
    if (currentPage < totalPages) content += `\n*Use /servers ${currentPage + 1} to see more.*`;
    else if (totalPages > 1) content += `\n*Use /servers 1 to return to the start.*`;
    return { content };
  } catch (e) { logger.error(e); }
};

export default {
  settings: () => { useProxy(storage); return (<ScrollView><FormSwitchRow label="Flat Sidebar" value={storage.flatSidebar} onValueChange={v => { storage.flatSidebar = v; showToast(`Sidebar ${v ? "Flat" : "Standard"}`); }}/></ScrollView>); },
  onLoad() {
    this._unreg = registerCommand({ 
      name: "servers", 
      options: [
        { name: "query", type: 3, description: "Search OR page number" },
        { name: "page", type: 4, description: "Go to page" }
      ], 
      execute: handleExec 
    });
    const SGS = getSGS();
    if (SGS) this._patch = after("getSortedGuilds", SGS, (_, ret) => {
      if (!storage.flatSidebar || !Array.isArray(ret)) return ret;
      const ck = Utils.getArrayChecksum(ret);
      const cached = sidebarCache.get(ret);
      if (cached?.checksum === ck) return cached.data;
      const flat = ret.flatMap((n: any) => n.type === 'folder' ? n.guilds : [n]);
      const GS = getGS();
      const res = flat.map(n => { const id = Utils.resolveGuildId(n), g = id ? GS.getGuild(id) : null; return { n, name: g ? Utils.sanitizeName(g.name) : "" }; }).sort((a, b) => a.name.localeCompare(b.name)).map(i => i.n);
      sidebarCache.set(ret, { checksum: ck, data: res });
      return res;
    });
  },
  onUnload() { this._unreg?.(); this._patch?.(); }
};
