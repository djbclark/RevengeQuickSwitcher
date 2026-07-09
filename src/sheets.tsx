import React from "react";
import { findByProps } from "@revenge-mod/metro";
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  TextInput,
  Text,
  View,
} from "react-native";

export type SwitcherItem = {
  id: string;
  name: string;
};

export type SwitcherSheetProps = {
  title: string;
  subtitle?: string;
  items: SwitcherItem[];
  recentItems?: SwitcherItem[];
  initialQuery?: string;
  onPick: (item: SwitcherItem) => void;
  onClose?: () => void;
};

type ActionSheetHost = {
  openLazy?: (importer: Promise<{ default: React.ComponentType<any> }>, key: string, props: object) => void;
  hideActionSheet?: (key?: string) => void;
  close?: () => void;
};

type AlertHost = {
  openAlert?: (key: string, element: React.ReactElement) => void;
  dismissAlert?: (key?: string) => void;
};

type LegacyAlertsHost = {
  openLazy?: (opts: unknown) => void;
  close?: () => void;
  show?: (opts: unknown) => void;
};

type SimpleActionSheetApi = {
  showSimpleActionSheet?: (opts: {
    key: string;
    header: { title: string };
    options: Array<{ label: string; onPress?: () => void }>;
  }) => void;
};

const SHEET_KEY = "quick-switcher-sheet";
const ALERT_KEY = "quick-switcher-top";
const SIMPLE_KEY = "quick-switcher-simple";
const MAX_SIMPLE_OPTIONS = 12;

/** Rows per page in the top-docked switcher (keeps the panel above the keyboard). */
export const SHEET_PAGE_SIZE = 8;

export const sheetPageCount = (itemCount: number, pageSize = SHEET_PAGE_SIZE) =>
  Math.max(1, Math.ceil(Math.max(0, itemCount) / pageSize));

export const getSheetPageItems = <T,>(
  items: T[],
  page: number,
  pageSize = SHEET_PAGE_SIZE
): { pageItems: T[]; page: number; totalPages: number } => {
  const totalPages = sheetPageCount(items.length, pageSize);
  const safePage = Math.min(Math.max(1, page), totalPages);
  const start = (safePage - 1) * pageSize;
  return {
    pageItems: items.slice(start, start + pageSize),
    page: safePage,
    totalPages,
  };
};

export const filterSwitcherItems = (items: SwitcherItem[], query: string) => {
  const q = query.trim().toLowerCase();
  if (!q) return items;
  return items.filter((item) => item.name.toLowerCase().includes(q));
};

let _sheetHost: ActionSheetHost | undefined;
let _alertHost: AlertHost | undefined;
let _legacyAlerts: LegacyAlertsHost | undefined;
let _simpleSheet: SimpleActionSheetApi | undefined;
let _activeClose: (() => void) | undefined;

const getSheetHost = () => {
  if (_sheetHost) return _sheetHost;
  try {
    _sheetHost = findByProps("openLazy", "hideActionSheet") as ActionSheetHost | undefined;
  } catch {
    _sheetHost = undefined;
  }
  return _sheetHost;
};

const getAlertHost = () => {
  if (_alertHost) return _alertHost;
  try {
    _alertHost = findByProps("openAlert", "dismissAlert") as AlertHost | undefined;
  } catch {
    _alertHost = undefined;
  }
  return _alertHost;
};

const getLegacyAlerts = () => {
  if (_legacyAlerts) return _legacyAlerts;
  try {
    _legacyAlerts = findByProps("openLazy", "close") as LegacyAlertsHost | undefined;
  } catch {
    _legacyAlerts = undefined;
  }
  return _legacyAlerts;
};

const getSimpleActionSheet = () => {
  if (_simpleSheet) return _simpleSheet;
  try {
    _simpleSheet =
      (findByProps("hideActionSheet", "showSimpleActionSheet") as SimpleActionSheetApi | undefined) ||
      (findByProps("showSimpleActionSheet") as SimpleActionSheetApi | undefined);
  } catch {
    _simpleSheet = undefined;
  }
  return _simpleSheet;
};

/** Dismiss every known host for the switcher overlay. */
export const hideSwitcherSheet = () => {
  try {
    _activeClose?.();
  } catch {
    /* ignore */
  }
  _activeClose = undefined;

  try {
    getAlertHost()?.dismissAlert?.(ALERT_KEY);
  } catch {
    /* ignore */
  }
  try {
    getAlertHost()?.dismissAlert?.();
  } catch {
    /* ignore */
  }
  try {
    getSheetHost()?.hideActionSheet?.(SHEET_KEY);
  } catch {
    /* ignore */
  }
  try {
    getSheetHost()?.hideActionSheet?.();
  } catch {
    /* ignore */
  }
  try {
    getLegacyAlerts()?.close?.();
  } catch {
    /* ignore */
  }
};

/** Tappable rows for ambiguous matches (C5). Returns false if the API is unavailable. */
export const openSimplePickSheet = (
  title: string,
  items: SwitcherItem[],
  onPick: (item: SwitcherItem) => void
): boolean => {
  try {
    const api = getSimpleActionSheet();
    const show = api?.showSimpleActionSheet;
    if (typeof show !== "function" || items.length === 0) return false;

    const limited = items.slice(0, MAX_SIMPLE_OPTIONS);
    show({
      key: SIMPLE_KEY,
      header: { title },
      options: limited.map((item) => ({
        label: item.name,
        onPress: () => onPick(item),
      })),
    });
    return true;
  } catch {
    return false;
  }
};

type PanelColors = {
  text: string;
  muted: string;
  faint: string;
  bg: string;
  panel: string;
  border: string;
  accent: string;
};

const COLORS: PanelColors = {
  text: "#DBDEE1",
  muted: "#A3A6AA",
  faint: "#80848E",
  bg: "rgba(0,0,0,0.55)",
  panel: "#2B2D31",
  border: "#1E1F22",
  accent: "#5865F2",
};

/**
 * Top-docked searchable switcher panel.
 * Intentionally NOT wrapped in RN Modal — Discord's openAlert/openLazy already hosts
 * the tree. Nesting Modal made Close/dismiss leave a stuck overlay.
 */
export const SwitcherTopPanel: React.ComponentType<
  SwitcherSheetProps & { onRequestClose: () => void }
> = (sheetProps) => {
  const [visible, setVisible] = React.useState(true);
  const [query, setQuery] = React.useState(sheetProps.initialQuery || "");
  const [page, setPage] = React.useState(1);
  const closedRef = React.useRef(false);
  const colors = COLORS;

  const recent = sheetProps.recentItems || [];
  const filtered = filterSwitcherItems(sheetProps.items, query);
  const { pageItems, page: safePage, totalPages } = getSheetPageItems(filtered, page);

  React.useEffect(() => {
    setPage(1);
  }, [query]);

  const finishClose = React.useCallback(
    (after?: () => void) => {
      if (closedRef.current) return;
      closedRef.current = true;
      setVisible(false);
      try {
        sheetProps.onRequestClose();
      } catch {
        /* ignore */
      }
      try {
        hideSwitcherSheet();
      } catch {
        /* ignore */
      }
      try {
        sheetProps.onClose?.();
      } catch {
        /* ignore */
      }
      // Navigate after the overlay has a chance to unmount.
      if (after) {
        setTimeout(() => {
          try {
            after();
          } catch {
            /* ignore */
          }
        }, 75);
      }
    },
    // Intentionally depend on the callback props only.
    [sheetProps.onRequestClose, sheetProps.onClose]
  );

  const pick = (item: SwitcherItem) => {
    finishClose(() => sheetProps.onPick(item));
  };

  if (!visible) return null;

  const row = (item: SwitcherItem, keyPrefix: string) => (
    <Pressable
      key={`${keyPrefix}:${item.id}`}
      onPress={() => pick(item)}
      style={{
        paddingVertical: 12,
        paddingHorizontal: 4,
        borderBottomWidth: 1,
        borderBottomColor: colors.border,
      }}
      accessibilityRole="button"
      accessibilityLabel={`Jump to ${item.name}`}
    >
      <Text style={{ color: colors.text, fontSize: 16 }}>{item.name}</Text>
    </Pressable>
  );

  const pager =
    totalPages > 1 ? (
      <View
        style={{
          flexDirection: "row",
          alignItems: "center",
          justifyContent: "space-between",
          marginTop: 10,
        }}
      >
        <Pressable
          onPress={() => setPage((p) => Math.max(1, p - 1))}
          disabled={safePage <= 1}
          style={{
            flex: 1,
            marginRight: 6,
            paddingVertical: 10,
            borderRadius: 8,
            backgroundColor: safePage <= 1 ? "#3A3C41" : colors.accent,
            alignItems: "center",
            opacity: safePage <= 1 ? 0.5 : 1,
          }}
          accessibilityRole="button"
          accessibilityLabel="Previous page"
        >
          <Text style={{ color: colors.text, fontWeight: "600" }}>Previous</Text>
        </Pressable>
        <Text style={{ color: colors.muted, fontSize: 13, minWidth: 72, textAlign: "center" }}>
          {safePage} / {totalPages}
        </Text>
        <Pressable
          onPress={() => setPage((p) => Math.min(totalPages, p + 1))}
          disabled={safePage >= totalPages}
          style={{
            flex: 1,
            marginLeft: 6,
            paddingVertical: 10,
            borderRadius: 8,
            backgroundColor: safePage >= totalPages ? "#3A3C41" : colors.accent,
            alignItems: "center",
            opacity: safePage >= totalPages ? 0.5 : 1,
          }}
          accessibilityRole="button"
          accessibilityLabel="Next page"
        >
          <Text style={{ color: colors.text, fontWeight: "600" }}>Next</Text>
        </Pressable>
      </View>
    ) : null;

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, justifyContent: "flex-start" }}>
      <Pressable
        style={{ position: "absolute", top: 0, right: 0, bottom: 0, left: 0 }}
        onPress={() => finishClose()}
        accessibilityRole="button"
        accessibilityLabel="Dismiss switcher"
      />
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        style={{ width: "100%" }}
      >
        <View
          style={{
            marginTop: Platform.OS === "ios" ? 48 : 28,
            marginHorizontal: 12,
            backgroundColor: colors.panel,
            borderRadius: 12,
            paddingHorizontal: 14,
            paddingTop: 12,
            paddingBottom: 14,
            maxHeight: 420,
            borderWidth: 1,
            borderColor: colors.border,
          }}
        >
          <View style={{ flexDirection: "row", alignItems: "center", marginBottom: 4 }}>
            <Text style={{ color: colors.text, fontSize: 18, fontWeight: "700", flex: 1 }}>
              {sheetProps.title}
            </Text>
            <Pressable
              onPress={() => finishClose()}
              accessibilityRole="button"
              accessibilityLabel="Close switcher"
              hitSlop={12}
              style={{
                paddingHorizontal: 12,
                paddingVertical: 8,
                borderRadius: 8,
                backgroundColor: "#3A3C41",
              }}
            >
              <Text style={{ color: colors.text, fontSize: 15, fontWeight: "600" }}>Close</Text>
            </Pressable>
          </View>
          {sheetProps.subtitle ? (
            <Text style={{ color: colors.muted, fontSize: 13, marginBottom: 10 }}>{sheetProps.subtitle}</Text>
          ) : null}
          <TextInput
            value={query}
            onChangeText={setQuery}
            placeholder="Filter servers"
            placeholderTextColor={colors.faint}
            autoFocus={false}
            style={{
              backgroundColor: "#1E1F22",
              color: colors.text,
              borderRadius: 8,
              paddingHorizontal: 12,
              paddingVertical: 10,
              marginBottom: 10,
            }}
          />
          <ScrollView
            keyboardShouldPersistTaps="handled"
            style={{ flexGrow: 0 }}
            nestedScrollEnabled={true}
          >
            {!query.trim() && recent.length > 0 && safePage === 1 ? (
              <View style={{ marginBottom: 10 }}>
                <Text
                  style={{
                    color: colors.muted,
                    fontSize: 11,
                    fontWeight: "700",
                    textTransform: "uppercase",
                    marginBottom: 4,
                  }}
                >
                  Recent
                </Text>
                {recent.slice(0, 5).map((item) => row(item, "recent"))}
              </View>
            ) : null}
            <Text
              style={{
                color: colors.muted,
                fontSize: 11,
                fontWeight: "700",
                textTransform: "uppercase",
                marginBottom: 4,
              }}
            >
              {query.trim()
                ? `Matches (${filtered.length})`
                : `Servers (${filtered.length}) · page ${safePage}/${totalPages}`}
            </Text>
            {pageItems.length === 0 ? (
              <Text style={{ color: colors.faint, paddingVertical: 16 }}>No servers match.</Text>
            ) : (
              pageItems.map((item) => row(item, "all"))
            )}
          </ScrollView>
          {pager}
        </View>
      </KeyboardAvoidingView>
    </View>
  );
};

const openViaAlert = (props: SwitcherSheetProps): boolean => {
  try {
    const host = getAlertHost();
    if (typeof host?.openAlert !== "function") return false;

    const close = () => {
      try {
        host.dismissAlert?.(ALERT_KEY);
      } catch {
        /* ignore */
      }
      try {
        host.dismissAlert?.();
      } catch {
        /* ignore */
      }
      try {
        getLegacyAlerts()?.close?.();
      } catch {
        /* ignore */
      }
    };
    _activeClose = close;

    host.openAlert!(
      ALERT_KEY,
      React.createElement(SwitcherTopPanel, {
        ...props,
        onRequestClose: close,
      })
    );
    return true;
  } catch {
    return false;
  }
};

const openViaLazyModal = (props: SwitcherSheetProps): boolean => {
  try {
    const host = getSheetHost();
    if (typeof host?.openLazy !== "function") return false;

    const close = () => {
      try {
        host.hideActionSheet?.(SHEET_KEY);
      } catch {
        /* ignore */
      }
      try {
        host.hideActionSheet?.();
      } catch {
        /* ignore */
      }
      try {
        getLegacyAlerts()?.close?.();
      } catch {
        /* ignore */
      }
    };
    _activeClose = close;

    const Sheet: React.ComponentType<SwitcherSheetProps> = (sheetProps) => (
      <SwitcherTopPanel {...sheetProps} onRequestClose={close} />
    );

    host.openLazy!(Promise.resolve({ default: Sheet }), SHEET_KEY, props);
    return true;
  } catch {
    return false;
  }
};

/** Full searchable switcher UI docked to the top. Returns false if no host API works. */
export const openSwitcherSheet = (props: SwitcherSheetProps): boolean => {
  if (openViaAlert(props)) return true;
  if (openViaLazyModal(props)) return true;
  return false;
};

/**
 * Prefer full searchable top panel; fall back to simple action sheet for short lists.
 * Returns which surface opened, or null if neither worked.
 */
export const openSwitcherUi = (
  props: SwitcherSheetProps & { preferSimple?: boolean }
): "sheet" | "simple" | null => {
  const preferSimple = !!props.preferSimple && props.items.length > 0 && props.items.length <= MAX_SIMPLE_OPTIONS;

  if (preferSimple) {
    if (openSimplePickSheet(props.title, props.items, props.onPick)) return "simple";
  }

  if (openSwitcherSheet(props)) return "sheet";

  if (!preferSimple && props.items.length > 0 && props.items.length <= MAX_SIMPLE_OPTIONS) {
    if (openSimplePickSheet(props.title, props.items, props.onPick)) return "simple";
  }

  return null;
};
