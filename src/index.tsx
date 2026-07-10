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
import { openSwitcherUi, type SwitcherItem } from "./sheets";
import { getSettingsThemeColors } from "./theme";

type GuildStore = {
  getGuild: (id: string) => { name?: string } | undefined;
  getGuilds: () => Record<string, { id?: string; name?: string; guildId?: string; guild_id?: string }>;
};

type SortedGuildStore = {
  getSortedGuilds: () => SidebarNode[];
};

type ChannelIdStore = {
  getLastSelectedChannelId?: (guildId: string) => string | undefined | null;
  getChannelId?: (guildId?: string) => string | undefined | null;
};

type GuildChannelStore = {
  getChannels?: (guildId: string) =>
    | { SELECTABLE?: Array<{ channel?: { id?: string }; id?: string }> }
    | Array<{ id?: string }>
    | undefined;
  getDefaultChannel?: (guildId: string) => { id?: string } | string | undefined | null;
};

type SelectedGuildStore = {
  getGuildId?: () => string | undefined | null;
};

/** Discord deep-link opener — same module aliernfrog/JumpTo uses on Revenge Android. */
type OpenUrlModule = {
  openUrl?: (href: string) => void;
  openURL?: (href: string) => void;
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
let _Clipboard: ClipboardModule | undefined;
let _MessageUtil: MessageUtilModule | undefined;
let _ChannelIdStore: ChannelIdStore | undefined;
let _GuildChannelStore: GuildChannelStore | undefined;
let _SelectedGuildStore: SelectedGuildStore | undefined;
let _OpenUrl: OpenUrlModule | undefined;

const getGuildStore = () => (_GuildStore ??= findByProps("getGuild", "getGuilds") as GuildStore | undefined);
const getSortedGuildStore = () =>
  (_SortedGuildStore ??= findByProps("getSortedGuilds") as SortedGuildStore | undefined);
const getClipboard = () =>
  (_Clipboard ??= findByProps("setString", "getString") as ClipboardModule | undefined);
const getMessageUtil = () =>
  (_MessageUtil ??= findByProps("sendBotMessage") as MessageUtilModule | undefined);
const getChannelIdStore = () =>
  (_ChannelIdStore ??=
    (findByProps("getLastSelectedChannelId") as ChannelIdStore | undefined) ||
    (findByProps("getChannelId", "getVoiceChannelId") as ChannelIdStore | undefined));
const getGuildChannelStore = () =>
  (_GuildChannelStore ??=
    (findByProps("getChannels", "getDefaultChannel") as GuildChannelStore | undefined) ||
    (findByProps("getDefaultChannel") as GuildChannelStore | undefined));
const getSelectedGuildStore = () =>
  (_SelectedGuildStore ??= findByProps("getGuildId", "getLastSelectedGuildId") as SelectedGuildStore | undefined);
/** Match JumpTo: `findByProps("openUrl")`, with common mobile casing fallbacks. */
const getOpenUrl = () =>
  (_OpenUrl ??=
    (findByProps("openUrl") as OpenUrlModule | undefined) ||
    (findByProps("openURL", "openDeeplink") as OpenUrlModule | undefined) ||
    (findByProps("openURL") as OpenUrlModule | undefined));

const readSelectedGuildId = () => {
  try {
    return getSelectedGuildStore()?.getGuildId?.() ?? null;
  } catch {
    return null;
  }
};

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

/** Injected at build time from package.json; keep fallback in sync when bumping. */
const PLUGIN_VERSION =
  typeof __QSS_VERSION__ !== "undefined" && __QSS_VERSION__ ? __QSS_VERSION__ : "4.5.8";

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

const DEBUG_RING_MAX = 80;
const debugRing: string[] = [];
let debugRingHydrated = false;

const clearDebugRing = () => {
  debugRing.length = 0;
  try {
    storage.debugLogText = "";
    storage.debugLogPluginVersion = PLUGIN_VERSION;
  } catch {
    /* ignore */
  }
};

const hydrateDebugRing = () => {
  if (debugRingHydrated) return;
  debugRingHydrated = true;
  try {
    // Drop lines from older builds so Copy debug logs is not a mix of versions.
    if (storage.debugLogPluginVersion !== PLUGIN_VERSION) {
      clearDebugRing();
      return;
    }
    const raw = storage.debugLogText;
    if (typeof raw !== "string" || !raw.trim()) return;
    const parts = raw.includes("\n") ? raw.split("\n") : raw.split("\u001e");
    for (const part of parts) {
      const line = part.trim();
      if (!line || line.startsWith("Quick Server Switcher") || line.startsWith("lines=")) continue;
      debugRing.push(line);
    }
    while (debugRing.length > DEBUG_RING_MAX) debugRing.shift();
  } catch {
    /* ignore */
  }
};

const persistDebugRing = () => {
  try {
    storage.debugLogText = debugRing.join("\n");
    storage.debugLogPluginVersion = PLUGIN_VERSION;
  } catch {
    /* ignore */
  }
};

const pushDebugRing = (message: string, ...args: unknown[]) => {
  try {
    hydrateDebugRing();
    const stamp = new Date().toISOString().slice(11, 23);
    const extra =
      args.length === 0
        ? ""
        : " " +
          args
            .map((arg) => {
              try {
                if (typeof arg === "string") return arg;
                return JSON.stringify(arg);
              } catch {
                return String(arg);
              }
            })
            .join(" ");
    // Version on every line so mixed pastes / old rings are unambiguous.
    debugRing.push(`[v${PLUGIN_VERSION} ${stamp}] ${message}${extra}`);
    if (debugRing.length > DEBUG_RING_MAX) debugRing.shift();
    persistDebugRing();
  } catch {
    /* ignore */
  }
};

const formatDebugRing = () => {
  hydrateDebugRing();
  return [
    `Quick Server Switcher debug log v${PLUGIN_VERSION}`,
    `lines=${debugRing.length}`,
    ...debugRing,
  ].join("\n");
};

/** Some Discord clipboard paths collapse or drop newlines — also provide a one-line form. */
const formatDebugRingClipboard = () => {
  hydrateDebugRing();
  const header = `Quick Server Switcher debug log v${PLUGIN_VERSION} | lines=${debugRing.length}`;
  if (debugRing.length === 0) return `${header} | (empty — open /servers or tap a server first)`;
  // Use " | " so a single-line paste still carries every event.
  return `${header} | ${debugRing.join(" | ")}`;
};

const copyDebugLogs = () => {
  hydrateDebugRing();
  const clipboard = getClipboard();
  const multiline = formatDebugRing();
  const singleLine = formatDebugRingClipboard();

  let copied = false;
  if (clipboard?.setString) {
    try {
      // Prefer single-line form — Discord mobile clipboard often drops newlines.
      clipboard.setString(singleLine);
      copied = true;
    } catch (error) {
      debugLog("copyDebugLogs setString failed", String(error));
    }
  }

  // Always try to surface the dump somewhere visible.
  try {
    logger.info?.("[QuickSwitcher] debug dump\n" + multiline);
  } catch {
    /* ignore */
  }

  if (copied) {
    const preview = debugRing.length > 0 ? debugRing[debugRing.length - 1] : "(empty)";
    showToast(`Copied ${debugRing.length} line(s): ${preview.slice(0, 48)}`, "success");
    return;
  }

  showToast("Clipboard unavailable — enable Debug Logging and check Revenge logs", "danger");
};

const debugLog = (message: string, ...args: unknown[]) => {
  try {
    pushDebugRing(message, ...args);
    try {
      if (typeof logger.info === "function") {
        logger.info(`[QuickSwitcher] ${message}`, ...args);
      } else if (storage.debugLogging) {
        logger.error(`[QuickSwitcher:debug] ${message}`, ...args);
      }
    } catch {
      /* ignore */
    }
  } catch {
    /* ignore — never let logging break enable */
  }
};

/** Resolve a channel id in the target guild (needed for discord.com/channels/{guild}/{channel}). */
const resolveChannelIdForGuild = (guildId: string): string | null => {
  const ChannelIdStore = getChannelIdStore();
  const fromSelected =
    ChannelIdStore?.getLastSelectedChannelId?.(guildId) || ChannelIdStore?.getChannelId?.(guildId) || null;
  if (fromSelected) return String(fromSelected);

  try {
    const GuildChannels = getGuildChannelStore();
    const def = GuildChannels?.getDefaultChannel?.(guildId);
    if (typeof def === "string" && def) return def;
    if (def && typeof def === "object" && def.id) return String(def.id);

    const channels = GuildChannels?.getChannels?.(guildId);
    if (Array.isArray(channels)) {
      const first = channels.find((c) => c?.id);
      if (first?.id) return String(first.id);
    } else if (channels && typeof channels === "object") {
      const selectable = (channels as { SELECTABLE?: Array<{ channel?: { id?: string }; id?: string }> })
        .SELECTABLE;
      if (Array.isArray(selectable)) {
        for (const entry of selectable) {
          const cid = entry?.channel?.id || entry?.id;
          if (cid) return String(cid);
        }
      }
    }
  } catch (error) {
    debugLog("resolveChannelIdForGuild failed", String(error));
  }
  return null;
};

/**
 * Switch guild via Discord's own channel deep link.
 *
 * Research (Revenge Android–tested plugins):
 * - aliernfrog/JumpTo (stable on latest Revenge): `findByProps("openUrl").openUrl("https://discord.com/channels/...")`
 * - Vencord KeepCurrentChannel (desktop): `NavigationRouter.transitionTo("/channels/...")` — same route shape
 *
 * Device history for THIS plugin (do not reuse):
 * - v4.5.3: loose `selectChannel(guildId, channelId)` freezes
 * - v4.5.4: Flux `CHANNEL_SELECT` verifies store then freezes UI
 * - v4.5.5: `selectGuild` / `GUILD_SELECT` do not stick; failure toast then freeze
 *
 * Never call selectChannel / CHANNEL_SELECT / selectGuild / GUILD_SELECT.
 */
const navigateToGuild = (id: string): boolean => {
  if (!id) {
    debugLog("navigateToGuild missing id");
    return false;
  }

  const before = readSelectedGuildId();
  if (before === id) {
    debugLog("navigateToGuild already selected", { id });
    return true;
  }

  const channelId = resolveChannelIdForGuild(id);
  const OpenUrl = getOpenUrl();
  const openFn =
    (typeof OpenUrl?.openUrl === "function" && OpenUrl.openUrl) ||
    (typeof OpenUrl?.openURL === "function" && OpenUrl.openURL) ||
    null;

  debugLog("navigateToGuild", {
    id,
    before,
    channelId,
    hasOpenUrl: !!openFn,
  });

  if (!channelId) {
    debugLog("navigateToGuild no channel for guild", { id });
    return false;
  }
  if (!openFn) {
    debugLog("navigateToGuild openUrl module missing");
    return false;
  }

  const href = `https://discord.com/channels/${id}/${channelId}`;
  try {
    openFn(href);
    const after = readSelectedGuildId();
    debugLog("navigateToGuild openUrl ok", { href, after });
    // JumpTo treats openUrl as fire-and-forget; Discord often updates selection async.
    // Accept the call if it did not throw — do not chain any other nav APIs after.
    if (after === id) {
      debugLog("navigateToGuild verified", { label: "openUrl", after });
    } else {
      debugLog("navigateToGuild openUrl accepted (async)", { after, expected: id });
    }
    return true;
  } catch (error) {
    debugLog("navigateToGuild openUrl failed", String(error));
    return false;
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
    try {
      logger.info?.(
        "[QuickSwitcher] command invoke",
        Array.isArray(rawArgs)
          ? rawArgs.map((arg) =>
              arg && typeof arg === "object"
                ? {
                    name: (arg as { name?: string }).name,
                    value: (arg as { value?: unknown }).value,
                    keys: Object.keys(arg as object),
                  }
                : arg
            )
          : rawArgs
      );
    } catch {
      /* ignore */
    }
    debugLog("command invoke", rawArgs);

    const navigated: { ok: boolean } = { ok: false };
    const jumpToItem = (item: SwitcherItem) => {
      debugLog("jumpToItem", { id: item.id, name: item.name });
      // sheets.tsx already called hideActionSheet + delay (Stealmoji/JumpTo pattern).
      navigated.ok = navigateToGuild(item.id);
      if (navigated.ok) {
        recordRecentJump(item.id);
        showToast(`Jumped to ${item.name}`, "success");
      } else {
        showToast("Could not navigate to server", "danger");
      }
    };

    const result = executeServersCommand(rawArgs, {
      getGuilds: () =>
        Object.values(getGuildStore()?.getGuilds() || {}).map((guild) => ({
          ...guild,
          name: guild.name ?? "",
        })),
      aliases: storage.aliases || "",
      navigateToGuild: (id) => {
        navigated.ok = navigateToGuild(id);
        if (!navigated.ok) {
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

    if (!result || typeof result !== "object") {
      showToast("No /servers output — use the query or page options from the slash menu", "danger");
      return;
    }

    // C8: bare /servers → searchable sheet (fallback: bot list).
    if (result.kind === "switcher" && Array.isArray(result.items) && result.items.length > 0) {
      const opened = openSwitcherUi({
        title: "Quick Server Switcher",
        subtitle: `${result.items.length} servers · tap to jump`,
        items: result.items,
        recentItems: Array.isArray(result.recentItems) ? result.recentItems : [],
        onPick: jumpToItem,
      });
      if (opened) {
        debugLog("opened switcher UI", opened);
        return;
      }
      if (typeof result.content === "string") {
        postCommandReply(ctx?.channel?.id, result.content);
      }
      return;
    }

    // C5: ambiguous search → tappable pick sheet (fallback: markdown pick list).
    if (result.kind === "pick-list" && Array.isArray(result.items) && result.items.length > 0) {
      const queryLabel =
        "query" in result && typeof result.query === "string" ? result.query : "your query";
      const opened = openSwitcherUi({
        title: `Matches for “${queryLabel}”`,
        subtitle: "Tap a server to jump",
        items: result.items,
        preferSimple: true,
        onPick: jumpToItem,
      });
      if (opened) {
        debugLog("opened pick UI", opened);
        return;
      }
      if (typeof result.content === "string") {
        postCommandReply(ctx?.channel?.id, result.content);
      }
      return;
    }

    // Recent list: prefer sheet of recent entries when available.
    if (result.kind === "recent-list" && Array.isArray(result.items) && result.items.length > 0) {
      const opened = openSwitcherUi({
        title: "Recent servers",
        subtitle: "Tap to jump · history from this plugin only",
        items: result.items,
        preferSimple: result.items.length <= 12,
        onPick: jumpToItem,
      });
      if (opened) {
        debugLog("opened recent UI", opened);
        return;
      }
    }

    if ("content" in result && typeof result.content === "string") {
      let content = result.content;
      if ("kind" in result && result.kind === "jump" && !navigated.ok) {
        content = `${content}\n_(navigation API unavailable — enable Debug Logging and check logs)_`;
      }
      postCommandReply(ctx?.channel?.id, content);
      return;
    }

    showToast("No /servers output — use the query or page options from the slash menu", "danger");
  } catch (error) {
    logger.error(error);
    showToast("Something went wrong running /servers", "danger");
    try {
      postCommandReply(ctx?.channel?.id, `Quick Switcher error: ${String(error)}`);
    } catch {
      /* ignore */
    }
  }
};

const openSwitcherFromSettings = () => {
  try {
    const result = executeServersCommand(
      {},
      {
        getGuilds: () =>
          Object.values(getGuildStore()?.getGuilds() || {}).map((guild) => ({
            ...guild,
            name: guild.name ?? "",
          })),
        aliases: storage.aliases || "",
        navigateToGuild: (id) => {
          if (!navigateToGuild(id)) showToast("Could not navigate to server", "danger");
        },
        showToast,
        debugLog,
        getRecentIds: getStoredRecentIds,
        recordRecent: recordRecentJump,
        excludes: storage.excludes || "",
        hideExcludedFromList: !!storage.hideExcludedFromList,
      }
    );

    if (result && result.kind === "switcher" && Array.isArray(result.items)) {
      const opened = openSwitcherUi({
        title: "Quick Server Switcher",
        subtitle: `${result.items.length} servers · tap to jump`,
        items: result.items,
        recentItems: Array.isArray(result.recentItems) ? result.recentItems : [],
        onPick: (item) => {
          // Sheet body already dismissed via hideActionSheet before this runs.
          if (navigateToGuild(item.id)) {
            recordRecentJump(item.id);
            showToast(`Jumped to ${item.name}`, "success");
          } else {
            showToast("Could not navigate to server", "danger");
          }
        },
      });
      if (opened) return;
    }
    showToast("Switcher sheet unavailable on this client", "danger");
  } catch (error) {
    logger.error?.(error);
    showToast("Could not open switcher", "danger");
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
        <View style={{ flexDirection: "row", marginHorizontal: 12, marginTop: 8, marginBottom: 8 }}>
          <Pressable
            style={actionStyle}
            onPress={openSwitcherFromSettings}
            accessibilityRole="button"
            accessibilityLabel="Open server switcher"
          >
            <Text style={{ color: colors.textNormal, fontWeight: "600" }}>Open switcher</Text>
          </Pressable>
          <Pressable
            style={actionStyle}
            onPress={copyDebugLogs}
            accessibilityRole="button"
            accessibilityLabel="Copy debug logs"
          >
            <Text style={{ color: colors.textNormal, fontWeight: "600" }}>Copy debug logs</Text>
          </Pressable>
        </View>
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
      hydrateDebugRing();
      debugLog("onLoad", { version: PLUGIN_VERSION });
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
            required: false,
          },
          {
            name: "page",
            type: 4,
            description: "Go to a specific page",
            displayName: "page",
            displayDescription: "Go to a specific page",
            required: false,
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
