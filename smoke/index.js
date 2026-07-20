({
  onLoad() {
    try {
      vendetta.logger.log("QuickSwitcherSmoke: onLoad");
      vendetta.ui.toasts.showToast("Smoke plugin loaded");
    } catch (e) {
      // Last-resort: avoid throwing out of onLoad
      try {
        console.log("QuickSwitcherSmoke onLoad error", e);
      } catch (_) {}
    }
  },
  onUnload() {
    try {
      vendetta.logger.log("QuickSwitcherSmoke: onUnload");
    } catch (_) {}
  },
  settings: () => {
    const React = vendetta.metro.common.React;
    const { Text, View } = vendetta.metro.common.ReactNative;
    return React.createElement(
      View,
      { style: { padding: 16 } },
      React.createElement(
        Text,
        { style: { color: "#DBDEE1" } },
        "Smoke plugin is running. If you can see this, Vendetta plugin loading works.",
      ),
    );
  },
});
