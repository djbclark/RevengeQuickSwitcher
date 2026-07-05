import { readFileSync, existsSync } from "node:fs";

const manifestPath = "manifest.json";
const distPath = "dist/index.js";

if (!existsSync(manifestPath)) {
  console.error("manifest.json is missing");
  process.exit(1);
}

const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
const required = ["name", "description", "authors", "main", "version"];

for (const key of required) {
  if (manifest[key] == null || manifest[key] === "") {
    console.error(`manifest.json is missing required field: ${key}`);
    process.exit(1);
  }
}

if (manifest.main !== "dist/index.js") {
  console.error(`manifest.json main must be dist/index.js (got ${manifest.main})`);
  process.exit(1);
}

if (!existsSync(distPath)) {
  console.error("dist/index.js is missing — run npm run build");
  process.exit(1);
}

console.log(`manifest ok (v${manifest.version})`);
