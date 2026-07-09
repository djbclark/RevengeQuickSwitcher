import { readFileSync, existsSync } from "node:fs";
import { execFileSync } from "node:child_process";

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

// In CI, the committed bundle must match a fresh build (verify runs build first).
if (process.env.CI) {
  try {
    execFileSync("git", ["diff", "--exit-code", "--", distPath], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
    });
  } catch (error) {
    if (error && typeof error === "object" && "status" in error && error.status === 1) {
      console.error("dist/index.js is out of date — run npm run build and commit the result");
      process.exit(1);
    }
  }
}

console.log(`manifest ok (v${manifest.version})`);
