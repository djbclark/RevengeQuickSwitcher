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
import { executeServersCommand } from "./command";

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

const sidebarCache = new WeakMap<any[], { checksum: number, data: any[] }>();

const handleExec = (rawArgs: any) => {
  try {
    return executeServersCommand(rawArgs, {
      getGuilds: () => Object.values(getGuildStore()?.getGuilds() || {}),
      aliases: storage.aliases || "",
      navigateToGuild: (id) => {
        const Router = getRouter();
        const Navigation = getNavigation();
        if (Router?.transitionToGuild) {
          Router.transitionToGuild(id);
        } else if (Navigation?.push) {
          Navigation.push("Guild", { guildId: id });
        }
      },
      showToast,
    });
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
