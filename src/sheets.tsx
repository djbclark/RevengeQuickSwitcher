import React from "react";
import { findByProps } from "@revenge-mod/metro";
import {
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

type LazyActionSheetHost = {
  openLazy?: (importer: Promise<{ default: React.ComponentType<any> }>, key: string, props?: object) => void;
  hideActionSheet?: (key?: string) => void;
};

type SimpleActionSheetApi = {
  showSimpleActionSheet?: (opts: {
    key: string;
    header: { title: string; subtitle?: string; onClose?: () => void };
    options: Array<{ label: string; onPress?: () => void }>;
  }) => void;
};

type ActionSheetModule = {
  ActionSheet?: React.ComponentType<{ children?: React.ReactNode; scrollable?: boolean }>;
};

type TitleHeaderModule = {
  ActionSheetTitleHeader?: React.ComponentType<{
    title: string;
    subtitle?: string;
    trailing?: React.ReactNode;
  }>;
  BottomSheetTitleHeader?: React.ComponentType<{
    title: string;
    trailing?: React.ReactNode;
  }>;
};

type CloseButtonModule = {
  ActionSheetCloseButton?: React.ComponentType<{ onPress?: () => void }>;
};

const SHEET_KEY = "quick-switcher-sheet";
const SIMPLE_KEY = "quick-switcher-simple";
/** Keep simple sheets short — Discord’s native simple sheet auto-dismisses on press. */
const MAX_SIMPLE_OPTIONS = 12;

/** Rows per page in the native ActionSheet body. */
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

let _lazySheet: LazyActionSheetHost | undefined;
let _simpleSheet: SimpleActionSheetApi | undefined;
let _ActionSheet: React.ComponentType<{ children?: React.ReactNode; scrollable?: boolean }> | undefined;
let _TitleHeader: React.ComponentType<{ title: string; subtitle?: string; trailing?: React.ReactNode }> | undefined;
let _CloseButton: React.ComponentType<{ onPress?: () => void }> | undefined;
let _lookedUpNative = false;

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
 * Resolve Discord’s native ActionSheet pieces the way Stealmoji / Bunny plugins do.
 * Custom Views opened via openLazy WITHOUT this wrapper leave a touch-blocking shell
 * after hideActionSheet + openUrl (device QA v4.5.6–4.5.7).
 */
const ensureNativeSheetParts = () => {
  if (_lookedUpNative) return;
  _lookedUpNative = true;
  try {
    const sheetMod = findByProps("ActionSheet") as ActionSheetModule | undefined;
    _ActionSheet = sheetMod?.ActionSheet;
  } catch {
    /* ignore */
  }
  try {
    const titleMod = findByProps("ActionSheetTitleHeader") as TitleHeaderModule | undefined;
    _TitleHeader = titleMod?.ActionSheetTitleHeader;
  } catch {
    /* ignore */
  }
  if (!_TitleHeader) {
    try {
      const bottom = findByProps("BottomSheetTitleHeader") as TitleHeaderModule | undefined;
      _TitleHeader = bottom?.BottomSheetTitleHeader;
    } catch {
      /* ignore */
    }
  }
  try {
    const closeMod = findByProps("ActionSheetCloseButton") as CloseButtonModule | undefined;
    _CloseButton = closeMod?.ActionSheetCloseButton;
  } catch {
    /* ignore */
  }
};

/** Hide Discord’s LazyActionSheet host (JumpTo / Stealmoji / Bunny). */
export const hideSwitcherSheet = () => {
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
 * Stealmoji / JumpTo pattern: hideActionSheet first, then run the action.
 * Never navigate while a custom overlay is still mounted.
 */
export const dismissThenRun = (action: () => void, delayMs = 160) => {
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

/** @deprecated use dismissThenRun — kept for callers that imported the old name */
export const runAfterSwitcherDismissed = dismissThenRun;

const COLORS = {
  text: "#DBDEE1",
  muted: "#A3A6AA",
  faint: "#80848E",
  panel: "#2B2D31",
  border: "#1E1F22",
  accent: "#5865F2",
};

/**
 * Body rendered INSIDE Discord’s native ActionSheet (Stealmoji AddToServer pattern).
 * Do not use a full-screen flex:1 overlay or openAlert — those leave dead taps after jump.
 */
const SwitcherSheetBody: React.ComponentType<SwitcherSheetProps> = (sheetProps) => {
  const [query, setQuery] = React.useState(sheetProps.initialQuery || "");
  const [page, setPage] = React.useState(1);
  const colors = COLORS;

  const recent = sheetProps.recentItems || [];
  const filtered = filterSwitcherItems(sheetProps.items, query);
  const { pageItems, page: safePage, totalPages } = getSheetPageItems(filtered, page);

  React.useEffect(() => {
    setPage(1);
  }, [query]);

  const pick = (item: SwitcherItem) => {
    // Match Stealmoji: hideActionSheet before the follow-up action.
    dismissThenRun(() => {
      try {
        sheetProps.onClose?.();
      } catch {
        /* ignore */
      }
      sheetProps.onPick(item);
    });
  };

  const closeOnly = () => {
    hideSwitcherSheet();
    try {
      sheetProps.onClose?.();
    } catch {
      /* ignore */
    }
  };

  ensureNativeSheetParts();
  const ActionSheet = _ActionSheet;
  const TitleHeader = _TitleHeader;
  const CloseButton = _CloseButton;

  const header =
    TitleHeader && CloseButton ? (
      <TitleHeader
        title={sheetProps.title}
        subtitle={sheetProps.subtitle}
        trailing={<CloseButton onPress={closeOnly} />}
      />
    ) : (
      <View style={{ flexDirection: "row", alignItems: "center", paddingHorizontal: 16, paddingVertical: 12 }}>
        <Text style={{ color: colors.text, fontSize: 18, fontWeight: "700", flex: 1 }}>{sheetProps.title}</Text>
        <Pressable onPress={closeOnly} hitSlop={12} accessibilityRole="button" accessibilityLabel="Close">
          <Text style={{ color: colors.accent, fontWeight: "600" }}>Close</Text>
        </Pressable>
      </View>
    );

  const row = (item: SwitcherItem, keyPrefix: string) => (
    <Pressable
      key={`${keyPrefix}:${item.id}`}
      onPress={() => pick(item)}
      style={{
        paddingVertical: 14,
        paddingHorizontal: 16,
        borderBottomWidth: 1,
        borderBottomColor: colors.border,
      }}
      accessibilityRole="button"
      accessibilityLabel={`Jump to ${item.name}`}
    >
      <Text style={{ color: colors.text, fontSize: 16 }}>{item.name}</Text>
    </Pressable>
  );

  const body = (
    <>
      {header}
      {sheetProps.subtitle && !TitleHeader ? (
        <Text style={{ color: colors.muted, fontSize: 13, paddingHorizontal: 16, marginBottom: 8 }}>
          {sheetProps.subtitle}
        </Text>
      ) : null}
      <TextInput
        value={query}
        onChangeText={setQuery}
        placeholder="Filter servers"
        placeholderTextColor={colors.faint}
        autoFocus={false}
        style={{
          marginHorizontal: 16,
          marginBottom: 8,
          backgroundColor: "#1E1F22",
          color: colors.text,
          borderRadius: 8,
          paddingHorizontal: 12,
          paddingVertical: 10,
        }}
      />
      <ScrollView style={{ maxHeight: 360 }} keyboardShouldPersistTaps="handled" nestedScrollEnabled={true}>
        {!query.trim() && recent.length > 0 && safePage === 1 ? (
          <View style={{ marginBottom: 8 }}>
            <Text
              style={{
                color: colors.muted,
                fontSize: 11,
                fontWeight: "700",
                textTransform: "uppercase",
                paddingHorizontal: 16,
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
            paddingHorizontal: 16,
            marginBottom: 4,
          }}
        >
          {query.trim()
            ? `Matches (${filtered.length})`
            : `Servers (${filtered.length}) · page ${safePage}/${totalPages}`}
        </Text>
        {pageItems.length === 0 ? (
          <Text style={{ color: colors.faint, padding: 16 }}>No servers match.</Text>
        ) : (
          pageItems.map((item) => row(item, "all"))
        )}
      </ScrollView>
      {totalPages > 1 ? (
        <View
          style={{
            flexDirection: "row",
            alignItems: "center",
            justifyContent: "space-between",
            paddingHorizontal: 16,
            paddingVertical: 12,
            paddingBottom: 20,
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
      ) : (
        <View style={{ height: 16 }} />
      )}
    </>
  );

  if (ActionSheet) {
    return <ActionSheet scrollable>{body}</ActionSheet>;
  }
  // Last resort: still open via LazyActionSheet but without ActionSheet chrome.
  return <View style={{ backgroundColor: colors.panel }}>{body}</View>;
};

/** Native Discord simple sheet — auto-dismisses on option press (JumpTo-adjacent). */
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
      header: {
        title,
        onClose: () => hideSwitcherSheet(),
      },
      options: limited.map((item) => ({
        label: item.name,
        onPress: () => {
          // Native simple sheet usually dismisses itself; still hide + delay like Stealmoji.
          dismissThenRun(() => onPick(item), 120);
        },
      })),
    });
    return true;
  } catch {
    return false;
  }
};

/** Full searchable switcher inside Discord’s LazyActionSheet + ActionSheet. */
export const openSwitcherSheet = (props: SwitcherSheetProps): boolean => {
  try {
    ensureNativeSheetParts();
    const host = getLazyActionSheet();
    if (typeof host?.openLazy !== "function") return false;

    host.openLazy!(Promise.resolve({ default: SwitcherSheetBody }), SHEET_KEY, props);
    return true;
  } catch {
    return false;
  }
};

/**
 * Prefer native ActionSheet host; use simple sheet for short lists.
 * Never use openAlert — device QA showed leftover touch-blocking shells.
 */
export const openSwitcherUi = (
  props: SwitcherSheetProps & { preferSimple?: boolean }
): "sheet" | "simple" | null => {
  const preferSimple =
    !!props.preferSimple && props.items.length > 0 && props.items.length <= MAX_SIMPLE_OPTIONS;

  if (preferSimple) {
    if (openSimplePickSheet(props.title, props.items, props.onPick)) return "simple";
  }

  if (openSwitcherSheet(props)) return "sheet";

  if (!preferSimple && props.items.length > 0 && props.items.length <= MAX_SIMPLE_OPTIONS) {
    if (openSimplePickSheet(props.title, props.items, props.onPick)) return "simple";
  }

  return null;
};
