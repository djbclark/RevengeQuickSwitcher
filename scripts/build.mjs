import * as esbuild from "esbuild";
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";

const vendettaShimPlugin = {
  name: "vendetta-shim",
  setup(build) {
    const loaders = {
      "@revenge-mod/metro": "module.exports = vendetta.metro;",
      "@revenge-mod/patcher": "module.exports = vendetta.patcher;",
      "@revenge-mod/ui/toast": `
        module.exports = {
          showToast(message, _type) {
            return vendetta.ui.toasts.showToast(String(message));
          }
        };
      `,
      "@revenge-mod": "module.exports = vendetta;",
      "@revenge-mod/commands": "module.exports = vendetta.commands;",
      "@revenge-mod/plugin": "module.exports = vendetta.plugin;",
      "@revenge-mod/storage": "module.exports = vendetta.storage;",
      "@revenge-mod/ui/components": "module.exports = vendetta.ui.components;",
      react: "module.exports = vendetta.metro.common.React;",
      "react-native": "module.exports = vendetta.metro.common.ReactNative;",
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
// Vendetta evals: vendetta => { return <plugin.js> }
const wrapped =
  "(()=>{const module={exports:{}};const exports=module.exports;" +
  bundled +
  ";return module.exports.default??module.exports;})()";

writeFileSync("dist/index.js", wrapped);

const hash = createHash("sha256").update(wrapped).digest("hex");
const manifest = JSON.parse(readFileSync("manifest.json", "utf8"));
manifest.hash = hash;
manifest.main = "dist/index.js";
writeFileSync("manifest.json", `${JSON.stringify(manifest, null, 2)}\n`);

console.log(`built dist/index.js (${wrapped.length} bytes, hash ${hash.slice(0, 12)}…)`);
