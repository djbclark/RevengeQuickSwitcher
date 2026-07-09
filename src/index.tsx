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
import { executeServersCommand } from "./command";
import { SidebarCache, transformFlatSidebar, type SidebarNode } from "./sidebar";

const { FormSwitchRow } = Forms;

type GuildStore = {
  getGuild: (id: string) => { name?: string } | undefined;
  getGuilds: () => Record<string, { id?: string; name?: string; guildId?: string; guild_id?: string }>;
};

type SortedGuildStore = {
  getSortedGuilds: () => SidebarNode[];
};

type RouterModule = {
  transitionToGuild?: (id: string) => void;
  selectGuild?: (id: string) => void;
};

type NavigationModule = {
  push?: (route: string, params: { guildId: string }) => void;
  replace?: (route: string, params: { guildId: string }) => void;
};

// Caching Discord Metro modules for performance
let _GuildStore: GuildStore | undefined;
let _SortedGuildStore: SortedGuildStore | undefined;
let _Router: RouterModule | undefined;
let _Navigation: NavigationModule | undefined;

const getGuildStore = () => (_GuildStore ??= findByProps("getGuild", "getGuilds") as GuildStore | undefined);
const getSortedGuildStore = () =>
  (_SortedGuildStore ??= findByProps("getSortedGuilds") as SortedGuildStore | undefined);
const getRouter = () =>
  (_Router ??= findByProps("transitionToGuild", "selectGuild") as RouterModule | undefined);
const getNavigation = () =>
  (_Navigation ??= findByProps("push", "replace") as NavigationModule | undefined);

// Initialize plugin storage defaults
if (storage.flatSidebar === undefined) storage.flatSidebar = false;
if (storage.aliases === undefined) storage.aliases = "";

let sidebarCache = new SidebarCache<SidebarNode>();
let warnedMissingSortedGuildStore = false;

const clearSidebarCache = () => {
  sidebarCache.clear();
  sidebarCache = new SidebarCache<SidebarNode>();
};

const handleExec = (rawArgs: unknown) => {
  try {
    return executeServersCommand(rawArgs, {
      getGuilds: () =>
        Object.values(getGuildStore()?.getGuilds() || {}).map((guild) => ({
          ...guild,
          name: guild.name ?? "",
        })),
      aliases: storage.aliases || "",
      navigateToGuild: (id) => {
        const Router = getRouter();
        const Navigation = getNavigation();
        if (Router?.transitionToGuild) {
          Router.transitionToGuild(id);
        } else if (Navigation?.push) {
          Navigation.push("Guild", { guildId: id });
        } else {
          showToast("Could not navigate to server", "danger");
        }
      },
      showToast,
    });
  } catch (error) {
    logger.error(error);
    showToast("Something went wrong running /servers", "danger");
  }
};

type PluginInstance = {
  _unreg?: () => void;
  _patch?: () => void;
  settings: () => React.ReactElement;
  onLoad(this: PluginInstance): void;
  onUnload(this: PluginInstance): void;
};

const plugin: PluginInstance = {
  settings: () => {
    useProxy(storage);
    return (
      <ScrollView>
        <FormSwitchRow
          label="Flat Sidebar"
          value={storage.flatSidebar ?? false}
          onValueChange={(value: boolean) => {
            storage.flatSidebar = value;
            clearSidebarCache();
            showToast(`Sidebar set to ${value ? "Flat" : "Standard"}`);
          }}
        />
        <Text
          style={{
            marginHorizontal: 16,
            marginTop: 16,
            color: "#A3A6AA",
            fontWeight: "bold",
            textTransform: "uppercase",
            fontSize: 12,
          }}
        >
          Custom Aliases (alias=server)
        </Text>
        <Text style={{ marginHorizontal: 16, marginTop: 4, color: "#80848E", fontSize: 12 }}>
          One per line. Only the first = separates alias from target.
        </Text>
        <TextInput
          style={{
            margin: 16,
            padding: 12,
            backgroundColor: "#2B2D31",
            color: "#DBDEE1",
            borderRadius: 8,
            textAlignVertical: "top",
          }}
          multiline={true}
          numberOfLines={4}
          placeholder={"chess=Maynard\nwow=World of Warcraft"}
          placeholderTextColor="#80848E"
          value={storage.aliases || ""}
          onChangeText={(value: string) => {
            storage.aliases = value;
          }}
        />
      </ScrollView>
    );
  },

  onLoad() {
    this._unreg = registerCommand({
      name: "servers",
      options: [
        { name: "query", type: 3, description: "Search term OR page number" },
        { name: "page", type: 4, description: "Go to a specific page" },
      ],
      execute: handleExec,
    });

    const SortedGuildStore = getSortedGuildStore();
    if (SortedGuildStore) {
      this._patch = after("getSortedGuilds", SortedGuildStore, (_args: unknown, returnValue: unknown) => {
        const guildStore = getGuildStore();
        return transformFlatSidebar(
          returnValue,
          !!storage.flatSidebar,
          (id) => {
            const guild = guildStore?.getGuild(id);
            return guild?.name ?? null;
          },
          sidebarCache
        );
      });
    } else if (storage.flatSidebar && !warnedMissingSortedGuildStore) {
      warnedMissingSortedGuildStore = true;
      logger.error("Flat sidebar enabled but SortedGuildStore was not found");
      showToast("Flat sidebar unavailable on this client", "danger");
    }
  },

  onUnload() {
    this._unreg?.();
    this._patch?.();
    clearSidebarCache();
  },
};

export default plugin;
