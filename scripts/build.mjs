import * as esbuild from "esbuild";
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";

/**
 * Build a Vendetta/Revenge plugin expression matching the official template shape:
 *   (function(exports){ ...; return exports })({})
 *
 * Revenge evals: vendetta => { return <plugin.js> }
 * then uses: ret?.default ?? ret
 *
 * Important: target ES2015 so Hermes can parse the bundle. Discord's Hermes
 * historically chokes on ??= / some newer syntax that esbuild would otherwise keep.
 */
const pkg = JSON.parse(readFileSync("package.json", "utf8"));
const pluginVersion = typeof pkg.version === "string" ? pkg.version : "0.0.0";

const result = await esbuild.build({
  entryPoints: ["src/index.tsx"],
  bundle: true,
  minify: true,
  write: false,
  format: "cjs",
  platform: "neutral",
  // Drop optional chaining / nullish / ??= that older Hermes rejects at eval time.
  // Keep ES2015 (let/const/class/arrow) — smoke uses those and enables successfully.
  target: ["es2015"],
  define: {
    __QSS_VERSION__: JSON.stringify(pluginVersion),
  },
  external: [
    "react",
    "react-native",
    "@revenge-mod",
    "@revenge-mod/metro",
    "@revenge-mod/patcher",
    "@revenge-mod/ui/toast",
    "@revenge-mod/commands",
    "@revenge-mod/plugin",
    "@revenge-mod/storage",
    "@revenge-mod/ui/components",
  ],
});

let bundled = result.outputFiles[0].text;

// Official Vendetta template maps @vendetta/* → vendetta.* globals and react → window.React.
// We close over the `vendetta` param from Revenge's eval wrapper the same way.
const requireMap = {
  react: "(vendetta.metro.common.React||window.React)",
  "react-native": "(vendetta.metro.common.ReactNative||window.ReactNative)",
  "@revenge-mod": "vendetta",
  "@revenge-mod/metro": "vendetta.metro",
  "@revenge-mod/patcher": "vendetta.patcher",
  "@revenge-mod/ui/toast":
    "{showToast:function(message,_type){return vendetta.ui.toasts.showToast(String(message));}}",
  "@revenge-mod/commands": "vendetta.commands",
  "@revenge-mod/plugin": "vendetta.plugin",
  "@revenge-mod/storage": "vendetta.storage",
  "@revenge-mod/ui/components": "vendetta.ui.components",
};

bundled = bundled.replace(/require\("([^"]+)"\)/g, (match, id) => {
  const mapped = requireMap[id];
  if (!mapped) {
    throw new Error(`Unmapped require in bundle: ${id}`);
  }
  return mapped;
});

const wrapped = `(function(exports){var module={exports:exports};${bundled}
var _exp=module.exports;
var _plugin=(_exp&&_exp.__esModule&&_exp.default!=null)?_exp.default:(_exp&&_exp.default!=null?_exp.default:_exp);
exports.default=_plugin;
Object.defineProperty(exports,"__esModule",{value:!0});
return exports;
})({})`;

writeFileSync("dist/index.js", wrapped);

const hash = createHash("sha256").update(wrapped).digest("hex");
const manifest = JSON.parse(readFileSync("manifest.json", "utf8"));
manifest.hash = hash;
manifest.main = "dist/index.js";
writeFileSync("manifest.json", `${JSON.stringify(manifest, null, 2)}\n`);

console.log(`built dist/index.js (${wrapped.length} bytes, hash ${hash.slice(0, 12)}…)`);
