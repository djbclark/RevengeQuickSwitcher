import { findByProps } from "@revenge-mod/metro";
import React from "react";
import { Platform, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { getSheetColors } from "./theme";
import { normalizeText } from "./utils";

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

type LazyActionSheetHost = {
  openLazy?: (importer: Promise<{ default: React.ComponentType<any> }>, key: string, props?: object) => void;
  hideActionSheet?: (key?: string) => void;
};

type AlertHost = {
  openAlert?: (key: string, element: React.ReactElement) => void;
  dismissAlert?: (key?: string) => void;
};

type SimpleActionSheetApi = {
  showSimpleActionSheet?: (opts: {
    key: string;
    header: { title: string; subtitle?: string; onClose?: () => void };
    options: Array<{ label: string; onPress?: () => void }>;
  }) => void;
};

const SHEET_KEY = "quick-switcher-sheet";
const ALERT_KEY = "quick-switcher-top";
const SIMPLE_KEY = "quick-switcher-simple";
const MAX_SIMPLE_OPTIONS = 12;

/** Rows per page — keeps the top panel short enough to sit above the keyboard. */
export const SHEET_PAGE_SIZE = 8;

export const sheetPageCount = (itemCount: number, pageSize = SHEET_PAGE_SIZE) =>
  Math.max(1, Math.ceil(Math.max(0, itemCount) / pageSize));

export const getSheetPageItems = <T,>(
  items: T[],
  page: number,
  pageSize = SHEET_PAGE_SIZE,
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
  const q = normalizeText(query.trim());
  if (!q) return items;
  return items.filter((item) => normalizeText(item.name).includes(q));
};

let _lazySheet: LazyActionSheetHost | undefined;
let _alertHost: AlertHost | undefined;
let _simpleSheet: SimpleActionSheetApi | undefined;
let _activeClose: (() => void) | undefined;

const getLazyActionSheet = () => {
  if (_lazySheet) return _lazySheet;
  try {
    _lazySheet =
      (findByProps("openLazy", "hideActionSheet") as LazyActionSheetHost | undefined) ||
      (findByProps("hideActionSheet") as LazyActionSheetHost | undefined);
  } catch {
    _lazySheet = undefined;
  }
  return _lazySheet;
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

/**
 * Dismiss every known host. Stealmoji/JumpTo always hideActionSheet before follow-ups;
 * top-docked UI also needs dismissAlert (v4.5.6–4.5.7 dead-tap QA).
 */
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
    getLazyActionSheet()?.hideActionSheet?.(SHEET_KEY);
  } catch {
    /* ignore */
  }
  try {
    getLazyActionSheet()?.hideActionSheet?.(SIMPLE_KEY);
  } catch {
    /* ignore */
  }
  try {
    getLazyActionSheet()?.hideActionSheet?.();
  } catch {
    /* ignore */
  }
};

/**
 * Stealmoji / JumpTo pattern: dismiss host first, then run the action.
 * Never call openUrl while an overlay is still mounted.
 */
export const dismissThenRun = (action: () => void, delayMs = 200) => {
  try {
    hideSwitcherSheet();
  } catch {
    /* ignore */
  }
  setTimeout(() => {
    try {
      action();
    } catch {
      /* ignore */
    }
  }, delayMs);
};

/** @deprecated use dismissThenRun */
export const runAfterSwitcherDismissed = dismissThenRun;

/**
 * Top-docked searchable panel (v4.5.1 keyboard fix).
 *
 * Hosted by openAlert so it sits at the top of the screen — bottom ActionSheets
 * are covered by the Android keyboard (v4.5.8 screenshot).
 *
 * Critical vs broken v4.5.6 overlay:
 * - No full-screen Pressable scrim
 * - Outer container pointerEvents="box-none" (no leftover touch sink)
 * - Pick path: hide/dismiss first, then onPick → openUrl (Stealmoji)
 * - TextInput never autoFocus (keyboard only when user taps Filter)
 */
export const SwitcherTopPanel: React.ComponentType<SwitcherSheetProps & { onRequestClose: () => void }> = (
  sheetProps,
) => {
  const [visible, setVisible] = React.useState(true);
  const [query, setQuery] = React.useState(sheetProps.initialQuery || "");
  const [page, setPage] = React.useState(1);
  const closedRef = React.useRef(false);
  const colors = getSheetColors();

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
      if (after) {
        dismissThenRun(after, 200);
      }
    },
    [sheetProps.onRequestClose, sheetProps.onClose],
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
          onPress={() => setPage(Math.max(1, safePage - 1))}
          disabled={safePage <= 1}
          style={{
            flex: 1,
            marginRight: 6,
            paddingVertical: 10,
            borderRadius: 8,
            backgroundColor: safePage <= 1 ? colors.chip : colors.accent,
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
          onPress={() => setPage(Math.min(totalPages, safePage + 1))}
          disabled={safePage >= totalPages}
          style={{
            flex: 1,
            marginLeft: 6,
            paddingVertical: 10,
            borderRadius: 8,
            backgroundColor: safePage >= totalPages ? colors.chip : colors.accent,
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

  // Top-aligned panel only — no full-bleed flex:1 touch sink under the keyboard.
  return (
    <View pointerEvents="box-none" style={{ flex: 1, justifyContent: "flex-start" }}>
      <View
        style={{
          marginTop: Platform.OS === "ios" ? 48 : 28,
          marginHorizontal: 12,
          backgroundColor: colors.panel,
          borderRadius: 12,
          paddingHorizontal: 14,
          paddingTop: 12,
          paddingBottom: 14,
          maxHeight: 380,
          borderWidth: 1,
          borderColor: colors.border,
        }}
      >
        <View style={{ flexDirection: "row", alignItems: "center", marginBottom: 4 }}>
          <Text style={{ color: colors.text, fontSize: 18, fontWeight: "700", flex: 1 }}>{sheetProps.title}</Text>
          <Pressable
            onPress={() => finishClose()}
            accessibilityRole="button"
            accessibilityLabel="Close switcher"
            hitSlop={12}
            style={{
              paddingHorizontal: 12,
              paddingVertical: 8,
              borderRadius: 8,
              backgroundColor: colors.chip,
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
          // Never auto-focus — keyboard must not cover the list until the user taps Filter.
          autoFocus={false}
          style={{
            backgroundColor: colors.inputBg,
            color: colors.text,
            borderRadius: 8,
            paddingHorizontal: 12,
            paddingVertical: 10,
            marginBottom: 10,
          }}
        />
        <ScrollView keyboardShouldPersistTaps="handled" style={{ flexGrow: 0 }} nestedScrollEnabled={true}>
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
    </View>
  );
};

/** Top-docked via openAlert — stays above the Android keyboard. */
const openViaAlert = (props: SwitcherSheetProps): boolean => {
  try {
    const host = getAlertHost();
    if (typeof host?.openAlert !== "function") return false;

    try {
      _activeClose?.();
    } catch {
      /* ignore */
    }

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
        getLazyActionSheet()?.hideActionSheet?.();
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
      }),
    );
    return true;
  } catch {
    return false;
  }
};

/** Fallback: LazyActionSheet with the same top panel body (no ActionSheet chrome). */
const openViaLazy = (props: SwitcherSheetProps): boolean => {
  try {
    const host = getLazyActionSheet();
    if (typeof host?.openLazy !== "function") return false;

    try {
      _activeClose?.();
    } catch {
      /* ignore */
    }

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
        getAlertHost()?.dismissAlert?.(ALERT_KEY);
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

export const openSimplePickSheet = (
  title: string,
  items: SwitcherItem[],
  onPick: (item: SwitcherItem) => void,
): boolean => {
  try {
    const api = getSimpleActionSheet();
    const show = api?.showSimpleActionSheet;
    if (typeof show !== "function" || items.length === 0) return false;

    const limited = items.slice(0, MAX_SIMPLE_OPTIONS);
    show({
      key: SIMPLE_KEY,
      header: {
        title,
        onClose: () => hideSwitcherSheet(),
      },
      options: limited.map((item) => ({
        label: item.name,
        onPress: () => {
          dismissThenRun(() => onPick(item), 120);
        },
      })),
    });
    return true;
  } catch {
    return false;
  }
};

/** Prefer top-docked alert (keyboard-safe); fall back to LazyActionSheet. */
export const openSwitcherSheet = (props: SwitcherSheetProps): boolean => {
  if (openViaAlert(props)) return true;
  if (openViaLazy(props)) return true;
  return false;
};

export const openSwitcherUi = (props: SwitcherSheetProps & { preferSimple?: boolean }): "sheet" | "simple" | null => {
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
