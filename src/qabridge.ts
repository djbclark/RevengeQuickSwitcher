/**
 * QA bridge (QA-REENGINEERING.md Phase 1): mirror debug-ring lines to
 * console.log with a grep-able prefix. RN console output lands in logcat
 * under ReactNativeJS, so a harness can assert on structured events with
 * `adb logcat -s ReactNativeJS` instead of screenshots.
 *
 * Off by default (storage.qaBridge); no behavior change when off.
 */

export const QA_BRIDGE_PREFIX = "QSSQA|";

export type QaBridgeEvent = {
  v: string;
  msg: string;
  args?: unknown[];
};

const safeArg = (arg: unknown): unknown => {
  try {
    // Cyclic or otherwise unserializable args degrade to their string form.
    JSON.stringify(arg);
    return arg;
  } catch {
    return String(arg);
  }
};

export const formatQaBridgeLine = (version: string, message: string, args: unknown[]): string => {
  const event: QaBridgeEvent = { v: version, msg: message };
  if (args.length > 0) event.args = args.map(safeArg);
  let payload: string;
  try {
    payload = JSON.stringify(event);
  } catch {
    payload = JSON.stringify({ v: version, msg: message });
  }
  return QA_BRIDGE_PREFIX + payload;
};

/**
 * Contract for consumers (the Python harness mirrors this): find the prefix
 * anywhere in the logcat line, JSON-parse the remainder, require `msg`.
 */
export const parseQaBridgeLine = (line: string): QaBridgeEvent | null => {
  const idx = line.indexOf(QA_BRIDGE_PREFIX);
  if (idx < 0) return null;
  try {
    const parsed = JSON.parse(line.slice(idx + QA_BRIDGE_PREFIX.length));
    if (parsed && typeof parsed === "object" && typeof (parsed as QaBridgeEvent).msg === "string") {
      return parsed as QaBridgeEvent;
    }
  } catch {
    /* malformed payload */
  }
  return null;
};
