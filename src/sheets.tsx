import React from "react";
import { findByProps } from "@revenge-mod/metro";
import { Pressable, ScrollView, TextInput, Text, View } from "react-native";

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
};

type SimpleActionSheetApi = {
  showSimpleActionSheet?: (opts: {
    key: string;
    header: { title: string };
    options: Array<{ label: string; onPress?: () => void }>;
  }) => void;
};

const SHEET_KEY = "quick-switcher-sheet";
const SIMPLE_KEY = "quick-switcher-simple";
const MAX_SIMPLE_OPTIONS = 12;

let _sheetHost: ActionSheetHost | undefined;
let _simpleSheet: SimpleActionSheetApi | undefined;
let _ActionSheet: React.ComponentType<{ children?: React.ReactNode }> | undefined;

const getSheetHost = () => {
  if (_sheetHost) return _sheetHost;
  try {
    _sheetHost = findByProps("openLazy", "hideActionSheet") as ActionSheetHost | undefined;
  } catch {
    _sheetHost = undefined;
  }
  return _sheetHost;
};

const getSimpleActionSheet = () => {
  if (_simpleSheet) return _simpleSheet;
  try {
    // Prefer modules that own both hide + show (avoids Discord getter traps on some builds).
    _simpleSheet =
      (findByProps("hideActionSheet", "showSimpleActionSheet") as SimpleActionSheetApi | undefined) ||
      (findByProps("showSimpleActionSheet") as SimpleActionSheetApi | undefined);
  } catch {
    _simpleSheet = undefined;
  }
  return _simpleSheet;
};

const getActionSheetComponent = () => {
  if (_ActionSheet) return _ActionSheet;
  try {
    const mod = findByProps("ActionSheet") as { ActionSheet?: React.ComponentType<{ children?: React.ReactNode }> } | undefined;
    if (mod?.ActionSheet) {
      _ActionSheet = mod.ActionSheet;
      return _ActionSheet;
    }
  } catch {
    /* ignore */
  }
  _ActionSheet = ({ children }) => <View style={{ paddingBottom: 24 }}>{children}</View>;
  return _ActionSheet;
};

export const hideSwitcherSheet = () => {
  try {
    getSheetHost()?.hideActionSheet?.(SHEET_KEY);
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

const filterItems = (items: SwitcherItem[], query: string) => {
  const q = query.trim().toLowerCase();
  if (!q) return items;
  return items.filter((item) => item.name.toLowerCase().includes(q));
};

/** Full searchable switcher sheet (C8). Returns false if openLazy is unavailable. */
export const openSwitcherSheet = (props: SwitcherSheetProps): boolean => {
  try {
    const host = getSheetHost();
    if (typeof host?.openLazy !== "function") return false;

    const Sheet: React.ComponentType<SwitcherSheetProps> = (sheetProps) => {
      const ActionSheet = getActionSheetComponent();
      const [query, setQuery] = React.useState(sheetProps.initialQuery || "");
      const colors = {
        text: "#DBDEE1",
        muted: "#A3A6AA",
        faint: "#80848E",
        bg: "#2B2D31",
        accent: "#5865F2",
      };

      const recent = sheetProps.recentItems || [];
      const filtered = filterItems(sheetProps.items, query);

      const pick = (item: SwitcherItem) => {
        try {
          hideSwitcherSheet();
        } catch {
          /* ignore */
        }
        sheetProps.onPick(item);
        sheetProps.onClose?.();
      };

      const row = (item: SwitcherItem, keyPrefix: string) => (
        <Pressable
          key={`${keyPrefix}:${item.id}`}
          onPress={() => pick(item)}
          style={{
            paddingVertical: 12,
            paddingHorizontal: 4,
            borderBottomWidth: 1,
            borderBottomColor: "#1E1F22",
          }}
          accessibilityRole="button"
          accessibilityLabel={`Jump to ${item.name}`}
        >
          <Text style={{ color: colors.text, fontSize: 16 }}>{item.name}</Text>
        </Pressable>
      );

      return (
        <ActionSheet>
          <View style={{ paddingHorizontal: 16, paddingTop: 8, paddingBottom: 20, maxHeight: 520 }}>
            <Text style={{ color: colors.text, fontSize: 18, fontWeight: "700", marginBottom: 4 }}>
              {sheetProps.title}
            </Text>
            {sheetProps.subtitle ? (
              <Text style={{ color: colors.muted, fontSize: 13, marginBottom: 10 }}>{sheetProps.subtitle}</Text>
            ) : null}
            <TextInput
              value={query}
              onChangeText={setQuery}
              placeholder="Filter servers"
              placeholderTextColor={colors.faint}
              autoFocus={!!sheetProps.initialQuery}
              style={{
                backgroundColor: colors.bg,
                color: colors.text,
                borderRadius: 8,
                paddingHorizontal: 12,
                paddingVertical: 10,
                marginBottom: 12,
              }}
            />
            <ScrollView keyboardShouldPersistTaps="handled">
              {!query.trim() && recent.length > 0 ? (
                <View style={{ marginBottom: 12 }}>
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
                  {recent.map((item) => row(item, "recent"))}
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
                {query.trim() ? `Matches (${filtered.length})` : `Servers (${filtered.length})`}
              </Text>
              {filtered.length === 0 ? (
                <Text style={{ color: colors.faint, paddingVertical: 16 }}>No servers match.</Text>
              ) : (
                filtered.map((item) => row(item, "all"))
              )}
            </ScrollView>
          </View>
        </ActionSheet>
      );
    };

    host.openLazy!(Promise.resolve({ default: Sheet }), SHEET_KEY, props);
    return true;
  } catch {
    return false;
  }
};

/**
 * Prefer full searchable sheet; fall back to simple action sheet for short lists.
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
