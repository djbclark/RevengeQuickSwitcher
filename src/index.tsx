import React from "react";
import { findByProps } from "@revenge-mod/metro";
import { after } from "@revenge-mod/patcher";
import { showToast } from "@revenge-mod/ui/toast";
import { logger } from "@revenge-mod";
import { registerCommand } from "@revenge-mod/commands";
import { storage } from "@revenge-mod/plugin";
import { useProxy } from "@revenge-mod/storage";
import { Forms } from "@revenge-mod/ui/components";
import { Pressable, ScrollView, TextInput, Text, View } from "react-native";
import { countAliasEntries, mergeAliasText, normalizeAliasText } from "./aliases";
import { executeServersCommand } from "./command";
import { SidebarCache, transformFlatSidebar, type SidebarNode } from "./sidebar";
import { getSettingsThemeColors } from "./theme";

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

type ClipboardModule = {
  setString?: (text: string) => void;
  getString?: () => Promise<string>;
};

// Caching Discord Metro modules for performance
let _GuildStore: GuildStore | undefined;
let _SortedGuildStore: SortedGuildStore | undefined;
let _Router: RouterModule | undefined;
let _Navigation: NavigationModule | undefined;
let _Clipboard: ClipboardModule | undefined;

const getGuildStore = () => (_GuildStore ??= findByProps("getGuild", "getGuilds") as GuildStore | undefined);
const getSortedGuildStore = () =>
  (_SortedGuildStore ??= findByProps("getSortedGuilds") as SortedGuildStore | undefined);
const getRouter = () =>
  (_Router ??= findByProps("transitionToGuild", "selectGuild") as RouterModule | undefined);
const getNavigation = () =>
  (_Navigation ??= findByProps("push", "replace") as NavigationModule | undefined);
const getClipboard = () =>
  (_Clipboard ??= findByProps("setString", "getString") as ClipboardModule | undefined);

// Initialize plugin storage defaults
if (storage.flatSidebar === undefined) storage.flatSidebar = false;
if (storage.aliases === undefined) storage.aliases = "";
if (storage.debugLogging === undefined) storage.debugLogging = false;

let sidebarCache = new SidebarCache<SidebarNode>();
let warnedMissingSortedGuildStore = false;

const clearSidebarCache = () => {
  sidebarCache.clear();
  sidebarCache = new SidebarCache<SidebarNode>();
};

const debugLog = (message: string, ...args: unknown[]) => {
  if (!storage.debugLogging) return;
  if (typeof logger.info === "function") {
    logger.info(`[QuickSwitcher] ${message}`, ...args);
  } else {
    logger.error(`[QuickSwitcher:debug] ${message}`, ...args);
  }
};

const copyAliasesToClipboard = () => {
  const clipboard = getClipboard();
  if (!clipboard?.setString) {
    showToast("Clipboard unavailable on this client", "danger");
    return;
  }
  const text = normalizeAliasText(storage.aliases || "");
  if (!text) {
    showToast("No aliases to copy", "danger");
    return;
  }
  clipboard.setString(text);
  debugLog("exported aliases", { count: countAliasEntries(text) });
  showToast(`Copied ${countAliasEntries(text)} alias(es)`, "success");
};

const importAliasesFromClipboard = async () => {
  const clipboard = getClipboard();
  if (!clipboard?.getString) {
    showToast("Clipboard unavailable on this client", "danger");
    return;
  }
  try {
    const incoming = await clipboard.getString();
    if (!incoming?.trim()) {
      showToast("Clipboard is empty", "danger");
      return;
    }
    const result = mergeAliasText(storage.aliases || "", incoming);
    if (result.imported === 0) {
      showToast(
        result.skipped > 0 ? "No valid alias lines on clipboard" : "Clipboard is empty",
        "danger"
      );
      return;
    }
    storage.aliases = result.text;
    debugLog("imported aliases", result);
    const skipNote = result.skipped > 0 ? ` (${result.skipped} skipped)` : "";
    showToast(`Imported ${result.imported}; ${result.total} total${skipNote}`, "success");
  } catch (error) {
    logger.error(error);
    showToast("Could not read clipboard", "danger");
  }
};

const handleExec = (rawArgs: unknown) => {
  try {
    debugLog("command invoke", rawArgs);
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
        debugLog("navigateToGuild", { id, hasRouter: !!Router?.transitionToGuild, hasNav: !!Navigation?.push });
        if (Router?.transitionToGuild) {
          Router.transitionToGuild(id);
        } else if (Navigation?.push) {
          Navigation.push("Guild", { guildId: id });
        } else {
          showToast("Could not navigate to server", "danger");
        }
      },
      showToast,
      debugLog,
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
    const colors = getSettingsThemeColors();
    const actionStyle = {
      flex: 1,
      marginHorizontal: 4,
      paddingVertical: 10,
      borderRadius: 8,
      backgroundColor: colors.backgroundSecondary,
      alignItems: "center" as const,
    };
    return (
      <ScrollView>
        <FormSwitchRow
          label="Flat Sidebar"
          value={storage.flatSidebar ?? false}
          onValueChange={(value: boolean) => {
            storage.flatSidebar = value;
            clearSidebarCache();
            debugLog("flatSidebar toggled", value);
            showToast(`Sidebar set to ${value ? "Flat" : "Standard"}`);
          }}
        />
        <FormSwitchRow
          label="Debug Logging"
          value={storage.debugLogging ?? false}
          onValueChange={(value: boolean) => {
            storage.debugLogging = value;
            showToast(`Debug logging ${value ? "on" : "off"}`);
            if (value) debugLog("debug logging enabled");
          }}
        />
        <Text
          style={{
            marginHorizontal: 16,
            marginTop: 16,
            color: colors.textMuted,
            fontWeight: "bold",
            textTransform: "uppercase",
            fontSize: 12,
          }}
        >
          Custom Aliases (alias=server)
        </Text>
        <Text style={{ marginHorizontal: 16, marginTop: 4, color: colors.textFaint, fontSize: 12 }}>
          One per line. Only the first = separates alias from target.
        </Text>
        <TextInput
          style={{
            margin: 16,
            marginBottom: 8,
            padding: 12,
            backgroundColor: colors.backgroundSecondary,
            color: colors.textNormal,
            borderRadius: 8,
            textAlignVertical: "top",
          }}
          multiline={true}
          numberOfLines={4}
          placeholder={"chess=Maynard\nwow=World of Warcraft"}
          placeholderTextColor={colors.textFaint}
          value={storage.aliases || ""}
          onChangeText={(value: string) => {
            storage.aliases = value;
          }}
        />
        <View style={{ flexDirection: "row", marginHorizontal: 12, marginBottom: 16 }}>
          <Pressable
            style={actionStyle}
            onPress={copyAliasesToClipboard}
            accessibilityRole="button"
            accessibilityLabel="Copy aliases to clipboard"
          >
            <Text style={{ color: colors.textNormal, fontWeight: "600" }}>Copy</Text>
          </Pressable>
          <Pressable
            style={actionStyle}
            onPress={() => {
              void importAliasesFromClipboard();
            }}
            accessibilityRole="button"
            accessibilityLabel="Import aliases from clipboard"
          >
            <Text style={{ color: colors.textNormal, fontWeight: "600" }}>Import</Text>
          </Pressable>
        </View>
        <Text style={{ marginHorizontal: 16, marginBottom: 24, color: colors.textFaint, fontSize: 12 }}>
          Copy exports normalized aliases. Import merges from the clipboard (imported names win on
          duplicates).
        </Text>
      </ScrollView>
    );
  },

  onLoad() {
    debugLog("onLoad");
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
      debugLog("patching getSortedGuilds");
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
    } else {
      debugLog("SortedGuildStore not found; flat sidebar patch skipped");
    }
  },

  onUnload() {
    debugLog("onUnload");
    this._unreg?.();
    this._patch?.();
    clearSidebarCache();
  },
};

export default plugin;
