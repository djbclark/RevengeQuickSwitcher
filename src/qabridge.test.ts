import { describe, expect, it } from "vitest";
import { formatQaBridgeLine, parseQaBridgeLine, QA_BRIDGE_PREFIX } from "./qabridge";

describe("formatQaBridgeLine / parseQaBridgeLine", () => {
  it("round-trips a message with args", () => {
    const line = formatQaBridgeLine("4.6.0", "navigateToGuild openUrl ok", [{ id: "123" }]);
    expect(line.startsWith(QA_BRIDGE_PREFIX)).toBe(true);
    expect(parseQaBridgeLine(line)).toEqual({
      v: "4.6.0",
      msg: "navigateToGuild openUrl ok",
      args: [{ id: "123" }],
    });
  });

  it("omits args when empty", () => {
    const parsed = parseQaBridgeLine(formatQaBridgeLine("4.6.0", "onLoad", []));
    expect(parsed).toEqual({ v: "4.6.0", msg: "onLoad" });
  });

  it("parses the prefix mid-line, as logcat prepends tags", () => {
    const line = "07-19 22:00:00.000 I ReactNativeJS: " + formatQaBridgeLine("4.6.0", "command invoke", []);
    expect(parseQaBridgeLine(line)?.msg).toBe("command invoke");
  });

  it("degrades cyclic args to strings instead of throwing", () => {
    const cyclic: Record<string, unknown> = {};
    cyclic.self = cyclic;
    const parsed = parseQaBridgeLine(formatQaBridgeLine("4.6.0", "weird", [cyclic]));
    expect(parsed?.msg).toBe("weird");
    expect(typeof parsed?.args?.[0]).toBe("string");
  });

  it("returns null for non-bridge and malformed lines", () => {
    expect(parseQaBridgeLine("ReactNativeJS: hello")).toBeNull();
    expect(parseQaBridgeLine(QA_BRIDGE_PREFIX + "{not json")).toBeNull();
    expect(parseQaBridgeLine(QA_BRIDGE_PREFIX + '{"v":"4.6.0"}')).toBeNull();
  });
});
