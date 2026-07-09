import * as esbuild from "esbuild";
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";

/**
 * Build a classic Vendetta/Revenge plugin bundle.
 * Working plugins look like:
 *   (function(exports, ...){ ...; return exports.default=plugin, exports })({}, vendetta.metro, ...)
 * Revenge evals: vendetta => { return <plugin.js> }
 */
const vendettaShimPlugin = {
  name: "vendetta-shim",
  setup(build) {
    const loaders = {
      "@revenge-mod/metro": "module.exports = __vd.metro;",
      "@revenge-mod/patcher": "module.exports = __vd.patcher;",
      "@revenge-mod/ui/toast": `
        module.exports = {
          showToast(message, _type) {
            return __vd.ui.toasts.showToast(String(message));
          }
        };
      `,
      "@revenge-mod": "module.exports = __vd;",
      "@revenge-mod/commands": "module.exports = __vd.commands;",
      "@revenge-mod/plugin": "module.exports = __vd.plugin;",
      "@revenge-mod/storage": "module.exports = __vd.storage;",
      "@revenge-mod/ui/components": "module.exports = __vd.ui.components;",
      react: "module.exports = __vd.metro.common.React;",
      "react-native": "module.exports = __vd.metro.common.ReactNative;",
    };

    build.onResolve({ filter: /.*/ }, (args) => {
      if (loaders[args.path]) {
        return { path: args.path, namespace: "vendetta-shim" };
      }
    });

    build.onLoad({ filter: /.*/, namespace: "vendetta-shim" }, (args) => {
      const contents = loaders[args.path];
      if (!contents) {
        return { errors: [{ text: `No Vendetta mapping for ${args.path}` }] };
      }
      return { contents, loader: "js" };
    });
  },
};

const result = await esbuild.build({
  entryPoints: ["src/index.tsx"],
  bundle: true,
  minify: true,
  write: false,
  format: "cjs",
  platform: "neutral",
  plugins: [vendettaShimPlugin],
});

const bundled = result.outputFiles[0].text;

// Match the shape of known-working Revenge plugins (IIFE closing over `vendetta`).
const wrapped =
  "(function(exports){" +
  "var __vd=vendetta;" +
  "var module={exports:exports};" +
  bundled +
  ";if(module.exports&&module.exports.__esModule&&module.exports.default!=null)" +
  "{exports.default=module.exports.default;}" +
  "else if(module.exports&&module.exports.default!=null)" +
  "{exports.default=module.exports.default;}" +
  "else{exports.default=module.exports;}" +
  "Object.defineProperty(exports,'__esModule',{value:!0});" +
  "return exports;" +
  "})({})";

writeFileSync("dist/index.js", wrapped);

const hash = createHash("sha256").update(wrapped).digest("hex");
const manifest = JSON.parse(readFileSync("manifest.json", "utf8"));
manifest.hash = hash;
manifest.main = "dist/index.js";
writeFileSync("manifest.json", `${JSON.stringify(manifest, null, 2)}\n`);

console.log(`built dist/index.js (${wrapped.length} bytes, hash ${hash.slice(0, 12)}…)`);
