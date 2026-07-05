import React from "react";
import { findByProps } from "@revenge-mod/metro";
import { after } from "@revenge-mod/patcher";
import { showToast } from "@revenge-mod/ui/toast";
import { logger } from "@revenge-mod";
import { registerCommand } from "@revenge-mod/commands";
import { storage } from "@revenge-mod/plugin";
import { useProxy } from "@revenge-mod/storage";
import { Forms } from "@revenge-mod/ui/components";
import { ScrollView, TextInput, Text } from "react-native";
import * as Utils from "./utils";

const { FormSwitchRow } = Forms;

// Caching Discord Metro modules for performance
let _GuildStore: any, _SortedGuildStore: any, _Router: any, _Navigation: any;
const getGuildStore = () => _GuildStore ??= findByProps("getGuild", "getGuilds");
const getSortedGuildStore = () => _SortedGuildStore ??= findByProps("getSortedGuilds");
const getRouter = () => _Router ??= findByProps("transitionToGuild", "selectGuild");
const getNavigation = () => _Navigation ??= findByProps("push", "replace");

// Initialize plugin storage defaults
if (storage.flatSidebar === undefined) storage.flatSidebar = false;
if (storage.aliases === undefined) storage.aliases = "";

class MappedGuild { 
  constructor(
    public original: any, 
    public id: string, 
    public sanitized: string, 
    public normalized: string
  ) {} 
}

const sidebarCache = new WeakMap<any[], { checksum: number, data: any[] }>();

const handleExec = (rawArgs: any) => {
  try {
    // Standardize arguments (Revenge vs Vendetta differences)
    const args = Array.isArray(rawArgs) 
      ? rawArgs 
      : Object.keys(rawArgs || {}).map(k => ({ name: k, value: rawArgs[k] }));
      
    let query = args.find(a => a.name === "query")?.value;
    let pageArg = args.find(a => a.name === "page")?.value;

    // Allow user to type `/servers 3` directly into the query field
    if (!pageArg && query && /^\d+$/.test(String(query).trim())) {
      pageArg = parseInt(String(query).trim(), 10);
      query = null;
    }

    const guildStore = getGuildStore();
    const guilds = Object.values(guildStore?.getGuilds() || {});
    
    if (!guilds.length) {
      return showToast("No servers found", "danger");
    }

    // Process and sort all available servers alphabetically
    const mappedGuilds = guilds.map((g: any) => {
      const id = Utils.resolveGuildId(g) || "";
      const safeName = Utils.sanitizeName(g.name);
      const normalName = Utils.normalizeText(safeName);
      return new MappedGuild(g, id, safeName, normalName);
    }).sort((a, b) => a.sanitized.localeCompare(b.sanitized, undefined, { sensitivity: "base" }));

    // ==========================================
    // MODE 1: SEARCH DIRECTORY
    // ==========================================
    if (query) {
      let normalizedQuery = Utils.normalizeText(String(query)).trim();
      
      // Inject Alias Resolution
      const aliasMap = Utils.parseAliases(storage.aliases || "");
      if (aliasMap.has(normalizedQuery)) {
        normalizedQuery = aliasMap.get(normalizedQuery)!;
      }

      let bestMatch = null;
      let bestScore = 0;

      // Priority queue matching system
      for (const item of mappedGuilds) {
        const text = item.normalized;
        if (text === normalizedQuery) { 
          bestMatch = item.original; 
          break; // Exact match wins immediately
        }
        if (text.startsWith(normalizedQuery) && bestScore < 50) { 
          bestMatch = item.original; 
          bestScore = 50; 
        }
        else if (text.includes(normalizedQuery) && bestScore < 10) { 
          bestMatch = item.original; 
          bestScore = 10; 
        }
        else if (Utils.isSubsequence(normalizedQuery, text) && bestScore < 5) { 
          bestMatch = item.original; 
          bestScore = 5; 
        }
      }

      if (bestMatch) {
        const id = Utils.resolveGuildId(bestMatch);
        const Router = getRouter();
        const Navigation = getNavigation();
        
        if (Router?.transitionToGuild) {
          Router.transitionToGuild(id);
        } else if (Navigation?.push) {
          Navigation.push("Guild", { guildId: id });
        }
        showToast(`Jumped to ${Utils.sanitizeName(bestMatch.name)}`, "success");
      } else {
        showToast("No match found", "danger");
      }
      return;
    }

    // ==========================================
    // MODE 2: PAGINATED LIST
    // ==========================================
    const PAGE_SIZE = 40; // Safely fits inside Discord's 2000 character limit
    const totalPages = Math.ceil(mappedGuilds.length / PAGE_SIZE);
    const currentPage = Math.min(totalPages, Math.max(1, pageArg || 1));
    const startIndex = (currentPage - 1) * PAGE_SIZE;
    const pageItems = mappedGuilds.slice(startIndex, startIndex + PAGE_SIZE);

    let content = `### Servers (${mappedGuilds.length})\n`;
    content += pageItems.map(item => `• ${Utils.escapeMarkdown(item.sanitized)}`).join("\n");
    content += `\n\n**Page ${currentPage} of ${totalPages}**`;
    
    if (currentPage < totalPages) {
      content += `\n*Use /servers ${currentPage + 1} to see more.*`;
    } else if (totalPages > 1) {
      content += `\n*Use /servers 1 to return to the start.*`;
    }
    
    return { content };
  } catch (error) { 
    logger.error(error); 
  }
};

export default {
  settings: () => { 
    useProxy(storage); 
    return (
      <ScrollView>
        <FormSwitchRow 
          label="Flat Sidebar" 
          value={storage.flatSidebar} 
          onValueChange={(value: boolean) => { 
            storage.flatSidebar = value; 
            showToast(`Sidebar set to ${value ? "Flat" : "Standard"}`); 
          }}
        />
        <Text style={{ marginHorizontal: 16, marginTop: 16, color: "#A3A6AA", fontWeight: "bold", textTransform: "uppercase", fontSize: 12 }}>
          Custom Aliases (alias=server)
        </Text>
        <TextInput
          style={{ margin: 16, padding: 12, backgroundColor: "#2B2D31", color: "#DBDEE1", borderRadius: 8, textAlignVertical: "top" }}
          multiline={true}
          numberOfLines={4}
          placeholder={"chess=Maynard\nwow=World of Warcraft"}
          placeholderTextColor="#80848E"
          value={storage.aliases || ""}
          onChangeText={(value: string) => storage.aliases = value}
        />
      </ScrollView>
    ); 
  },

  onLoad() {
    this._unreg = registerCommand({ 
      name: "servers", 
      options: [
        { name: "query", type: 3, description: "Search term OR page number" },
        { name: "page", type: 4, description: "Go to a specific page" }
      ], 
      execute: handleExec 
    });

    const SortedGuildStore = getSortedGuildStore();
    if (SortedGuildStore) {
      this._patch = after("getSortedGuilds", SortedGuildStore, (_, returnValue) => {
        // Bypass if user disabled the setting or data is invalid
        if (!storage.flatSidebar || !Array.isArray(returnValue)) return returnValue;

        const checksum = Utils.getArrayChecksum(returnValue);
        const cachedData = sidebarCache.get(returnValue);
        
        if (cachedData?.checksum === checksum) return cachedData.data;

        const guildStore = getGuildStore();
        
        // Extract out of folders and sort alphabetically
        const flattenedGuilds = returnValue.flatMap((node: any) => node.type === 'folder' ? node.guilds : [node]);
        const sortedFlattenedGuilds = flattenedGuilds.map((node: any) => {
          const id = Utils.resolveGuildId(node);
          const guild = id ? guildStore.getGuild(id) : null;
          return { node, name: guild ? Utils.sanitizeName(guild.name) : "" };
        })
        .sort((a, b) => a.name.localeCompare(b.name))
        .map(item => item.node);
        
        sidebarCache.set(returnValue, { checksum, data: sortedFlattenedGuilds });
        return sortedFlattenedGuilds;
      });
    }
  },

  onUnload() { 
    this._unreg?.(); 
    this._patch?.(); 
  }
};
