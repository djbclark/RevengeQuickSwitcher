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
import { countExcludeRules, formatExcludeHelp } from "./excludes";
import {
  clampRecentHistorySize,
  DEFAULT_RECENT_HISTORY_SIZE,
  parseRecentIds,
  pushRecentId,
  serializeRecentIds,
} from "./recents";
import { createSidebarCache, transformFlatSidebar, type SidebarNode } from "./sidebar";
import { getSettingsThemeColors } from "./theme";

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

type MessageUtilModule = {
  sendBotMessage?: (channelId: string, content: string) => void;
  sendMessage?: (
    channelId: string,
    message: { content: string },
    ...rest: unknown[]
  ) => void;
};

type CommandContext = {
  channel?: { id?: string };
};

type SwitchRowProps = {
  label: string;
  value: boolean;
  onValueChange: (value: boolean) => void;
};

// Caching Discord Metro modules for performance
let _GuildStore: GuildStore | undefined;
let _SortedGuildStore: SortedGuildStore | undefined;
let _Router: RouterModule | undefined;
let _Navigation: NavigationModule | undefined;
let _Clipboard: ClipboardModule | undefined;
let _MessageUtil: MessageUtilModule | undefined;

const getGuildStore = () => (_GuildStore ??= findByProps("getGuild", "getGuilds") as GuildStore | undefined);
const getSortedGuildStore = () =>
  (_SortedGuildStore ??= findByProps("getSortedGuilds") as SortedGuildStore | undefined);
const getRouter = () =>
  (_Router ??= findByProps("transitionToGuild", "selectGuild") as RouterModule | undefined);
const getNavigation = () =>
  (_Navigation ??= findByProps("push", "replace") as NavigationModule | undefined);
const getClipboard = () =>
  (_Clipboard ??= findByProps("setString", "getString") as ClipboardModule | undefined);
const getMessageUtil = () =>
  (_MessageUtil ??= findByProps("sendBotMessage") as MessageUtilModule | undefined);

/** Post command output locally (same path as Revenge /debug ephemeral). */
const postCommandReply = (channelId: string | undefined, content: string) => {
  if (!channelId || !content) return;
  const messageUtil = getMessageUtil();
  if (messageUtil?.sendBotMessage) {
    messageUtil.sendBotMessage(channelId, content);
    return;
  }
  if (messageUtil?.sendMessage) {
    messageUtil.sendMessage(channelId, { content }, void 0, { nonce: Date.now().toString() });
    return;
  }
  showToast("Could not post /servers reply in this channel", "danger");
};

const ensureStorageDefaults = () => {
  try {
    if (storage.flatSidebar === undefined) storage.flatSidebar = false;
    if (storage.aliases === undefined) storage.aliases = "";
    if (storage.debugLogging === undefined) storage.debugLogging = false;
    if (storage.recentIds === undefined) storage.recentIds = "[]";
    if (storage.recentHistorySize === undefined) storage.recentHistorySize = DEFAULT_RECENT_HISTORY_SIZE;
    if (storage.excludes === undefined) storage.excludes = "";
    if (storage.hideExcludedFromList === undefined) storage.hideExcludedFromList = false;
  } catch (error) {
    logger.error?.("Failed to initialize plugin storage", error);
  }
};

// Do not touch storage at module eval time — Vendetta evals the whole file
// before onLoad, and a throw here disables the plugin (X on the toggle).

let sidebarCache = createSidebarCache<SidebarNode>();
let warnedMissingSortedGuildStore = false;
let unregisterCommand: (() => void) | undefined;
let unpatchSidebar: (() => void) | undefined;

const clearSidebarCache = () => {
  sidebarCache.clear();
  sidebarCache = createSidebarCache<SidebarNode>();
};

const debugLog = (message: string, ...args: unknown[]) => {
  try {
    if (!storage.debugLogging) return;
    if (typeof logger.info === "function") {
      logger.info(`[QuickSwitcher] ${message}`, ...args);
    } else {
      logger.error(`[QuickSwitcher:debug] ${message}`, ...args);
    }
  } catch {
    /* ignore — never let logging break enable */
  }
};

const getStoredRecentIds = () => parseRecentIds(storage.recentIds);

const recordRecentJump = (id: string) => {
  const next = pushRecentId(getStoredRecentIds(), id, storage.recentHistorySize ?? DEFAULT_RECENT_HISTORY_SIZE);
  storage.recentIds = serializeRecentIds(next);
  debugLog("recordRecent", { id, size: next.length });
};

const clearRecentHistory = () => {
  storage.recentIds = "[]";
  showToast("Recent history cleared", "success");
  debugLog("clearRecentHistory");
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

const handleExec = (rawArgs: unknown, ctx?: CommandContext) => {
  try {
    debugLog("command invoke", rawArgs);
    const result = executeServersCommand(rawArgs, {
      getGuilds: () =>
        Object.values(getGuildStore()?.getGuilds() || {}).map((guild) => ({
          ...guild,
          name: guild.name ?? "",
        })),
      aliases: storage.aliases || "",
      navigateToGuild: (id) => {
        const Router = getRouter();
        const Navigation = getNavigation();
        debugLog("navigateToGuild", {
          id,
          hasRouter: !!Router?.transitionToGuild,
          hasNav: !!Navigation?.push,
        });
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
      getRecentIds: getStoredRecentIds,
      recordRecent: recordRecentJump,
      excludes: storage.excludes || "",
      hideExcludedFromList: !!storage.hideExcludedFromList,
    });
    // Do not rely on Revenge's return→sendMessage wrapper (often fails without a nonce).
    // Post locally like /debug ephemeral so the list is visible in-channel.
    if (result && typeof result === "object" && "content" in result && typeof result.content === "string") {
      postCommandReply(ctx?.channel?.id, result.content);
    }
  } catch (error) {
    logger.error(error);
    showToast("Something went wrong running /servers", "danger");
  }
};

const resolveSwitchRow = (): React.ComponentType<SwitchRowProps> => {
  try {
    const Candidate = (Forms as { FormSwitchRow?: React.ComponentType<SwitchRowProps> } | undefined)
      ?.FormSwitchRow;
    if (Candidate) return Candidate;
  } catch (error) {
    logger.error?.("FormSwitchRow unavailable", error);
  }

  // Minimal fallback so settings still render if Discord renamed FormSwitchRow.
  return ({ label, value, onValueChange }) => (
    <Pressable
      onPress={() => onValueChange(!value)}
      style={{ marginHorizontal: 16, marginVertical: 8, paddingVertical: 10 }}
      accessibilityRole="button"
      accessibilityLabel={label}
    >
      <Text style={{ color: "#DBDEE1", fontWeight: "600" }}>
        {label}: {value ? "On" : "Off"} (tap to toggle)
      </Text>
    </Pressable>
  );
};

type PluginInstance = {
  settings: () => React.ReactElement;
  onLoad(): void;
  onUnload(): void;
};

const plugin: PluginInstance = {
  settings: () => {
    ensureStorageDefaults();
    useProxy(storage);
    const colors = getSettingsThemeColors();
    const FormSwitchRow = resolveSwitchRow();
    const historySize = clampRecentHistorySize(storage.recentHistorySize);
    const recentCount = getStoredRecentIds().length;
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
        <FormSwitchRow
          label="Hide excluded from /servers list"
          value={storage.hideExcludedFromList ?? false}
          onValueChange={(value: boolean) => {
            storage.hideExcludedFromList = value;
            showToast(value ? "Excluded servers hidden from list" : "Excluded servers shown in list");
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
          Excluded servers
        </Text>
        <Text style={{ marginHorizontal: 16, marginTop: 4, color: colors.textFaint, fontSize: 12 }}>
          {formatExcludeHelp()}
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
          numberOfLines={3}
          placeholder={"Wayland Parents\n~spam\n123456789012345678"}
          placeholderTextColor={colors.textFaint}
          value={storage.excludes || ""}
          onChangeText={(value: string) => {
            storage.excludes = value;
          }}
        />
        <Text style={{ marginHorizontal: 16, marginBottom: 8, color: colors.textFaint, fontSize: 12 }}>
          {countExcludeRules(storage.excludes || "")} active rule(s) · always skipped by search
        </Text>
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
          Recent servers
        </Text>
        <Text style={{ marginHorizontal: 16, marginTop: 4, color: colors.textFaint, fontSize: 12 }}>
          Recorded only when this plugin jumps you. Use /servers recent or /servers r1.
        </Text>
        <Text style={{ marginHorizontal: 16, marginTop: 12, color: colors.textFaint, fontSize: 12 }}>
          History size (1–15)
        </Text>
        <TextInput
          style={{
            marginHorizontal: 16,
            marginTop: 4,
            marginBottom: 8,
            padding: 12,
            backgroundColor: colors.backgroundSecondary,
            color: colors.textNormal,
            borderRadius: 8,
          }}
          keyboardType="number-pad"
          value={String(historySize)}
          onChangeText={(value: string) => {
            const digits = value.replace(/[^\d]/g, "");
            if (!digits) {
              storage.recentHistorySize = DEFAULT_RECENT_HISTORY_SIZE;
              return;
            }
            const nextSize = clampRecentHistorySize(parseInt(digits, 10));
            storage.recentHistorySize = nextSize;
            storage.recentIds = serializeRecentIds(getStoredRecentIds().slice(0, nextSize));
          }}
        />
        <Text style={{ marginHorizontal: 16, marginBottom: 8, color: colors.textFaint, fontSize: 12 }}>
          {recentCount} stored · shrinking the size trims oldest entries
        </Text>
        <View style={{ flexDirection: "row", marginHorizontal: 12, marginBottom: 8 }}>
          <Pressable
            style={actionStyle}
            onPress={clearRecentHistory}
            accessibilityRole="button"
            accessibilityLabel="Clear recent server history"
          >
            <Text style={{ color: colors.textNormal, fontWeight: "600" }}>Clear recent</Text>
          </Pressable>
        </View>
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
    // Vendetta calls onLoad() without a receiver — never use `this` here.
    // Also never throw out of onLoad: any throw disables the plugin (X toggle).
    try {
      ensureStorageDefaults();
      debugLog("onLoad");
    } catch (error) {
      try {
        logger.error?.("Quick Switcher onLoad init failed", error);
      } catch {
        /* ignore */
      }
    }

    try {
      // Drop any prior registration from a hot reload / failed unload so /servers
      // does not appear twice in the slash picker.
      try {
        unregisterCommand?.();
      } catch {
        /* ignore */
      }
      unregisterCommand = undefined;

      // Revenge filters with `shouldHide?.() !== false` (inverted name): returning
      // false hides the command. Omit shouldHide so /servers always appears, matching
      // core commands like /debug. If you must set it, use () => true to show.
      unregisterCommand = registerCommand({
        name: "servers",
        description: "List or jump to servers (fuzzy search, recent, pages)",
        applicationId: "-1",
        type: 1,
        inputType: 0,
        displayName: "servers",
        displayDescription: "List or jump to servers (fuzzy search, recent, pages)",
        options: [
          {
            name: "query",
            type: 3,
            description: "Search, page number, recent, or r1",
            displayName: "query",
            displayDescription: "Search, page number, recent, or r1",
          },
          {
            name: "page",
            type: 4,
            description: "Go to a specific page",
            displayName: "page",
            displayDescription: "Go to a specific page",
          },
        ],
        execute: handleExec,
      } as Parameters<typeof registerCommand>[0]);
    } catch (error) {
      try {
        logger.error("Failed to register /servers command", error);
        showToast("Quick Switcher loaded, but /servers failed to register", "danger");
      } catch {
        /* ignore */
      }
    }

    try {
      const SortedGuildStore = getSortedGuildStore();
      if (SortedGuildStore) {
        debugLog("patching getSortedGuilds");
        unpatchSidebar = after("getSortedGuilds", SortedGuildStore, (_args: unknown, returnValue: unknown) => {
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
    } catch (error) {
      try {
        logger.error("Failed to patch flat sidebar", error);
      } catch {
        /* ignore */
      }
    }

    try {
      showToast("Quick Server Switcher loaded");
    } catch {
      /* ignore */
    }
  },

  onUnload() {
    try {
      debugLog("onUnload");
    } catch {
      /* ignore */
    }
    try {
      unregisterCommand?.();
    } catch (error) {
      try {
        logger.error("Failed to unregister /servers", error);
      } catch {
        /* ignore */
      }
    }
    unregisterCommand = undefined;
    try {
      unpatchSidebar?.();
    } catch (error) {
      try {
        logger.error("Failed to unpatch sidebar", error);
      } catch {
        /* ignore */
      }
    }
    unpatchSidebar = undefined;
    try {
      clearSidebarCache();
    } catch {
      /* ignore */
    }
  },
};

export default plugin;
