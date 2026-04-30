#!/usr/bin/env python3
r"""
# RevengeQuickSwitcher Polyglot (v3.9.1 "The Forceful Init")

### BOOTSTRAP: `chmod +x whatever.md && ./whatever.md explode`
--- PASTE EVERYTHING BELOW INTO ANOTHER AI ---
Act as a Senior V8 Engineer. Review "RevengeQuickSwitcher" (v3.9.1).
AUDITOR STATE: Node: v25 | OS: MacOS | Mod: Revenge (Native).
CRITICAL: Verify 'make init-repo' uses 'git push -u origin main -f' to 
bypass initial GitHub repo conflicts. 
AI INSTRUCTION: Use backtick/tilde code blocks in your reply.

### PROJECT SOURCE:

#### Makefile
~~~makefile
SOURCE_FILE = PROMPT_FOR_SECOND_OPINION.md
REPO_URL = git@github.com:djbclark/RevengeQuickSwitcher.git
.PHONY: help explode implode build test clean ship push pull init-repo
all: help

help:
	@echo "============================================================"
	@echo "RevengeQuickSwitcher (v3.9.1) - The Forceful Init"
	@echo "============================================================"
	@echo "[DEVELOPMENT]"
	@echo "  make explode    - Bootstrap (Extract files, install deps)."
	@echo "  make build      - Run tests, then bundle via esbuild."
	@echo ""
	@echo "[VERSION CONTROL (No Git Knowledge Required)]"
	@echo "  make init-repo  - (ONE-TIME) Link local folder to GitHub & force-upload."
	@echo "  make push       - (SAFE) Implodes, tests, builds, and uploads changes."
	@echo "  make pull       - Downloads updates from GitHub and explodes them."
	@echo ""
	@echo "[MAINTENANCE]"
	@echo "  make implode    - Sync local edits back to the Polyglot file."
	@echo "  make clean      - Wipe node_modules and build artifacts."
	@echo "============================================================"

# Development Pipeline
test:
	npm run test

build: test
	npm run build

explode:
	@python3 $(SOURCE_FILE) explode

implode:
	@python3 $(SOURCE_FILE) implode

ship: test build implode

# Abstracted Git Workflow
init-repo:
	@echo "🌱 Initializing GitHub upload..."
	git init
	git branch -M main
	git add .
	git commit -m "Initial commit" || true
	git remote add origin $(REPO_URL) || echo "Remote already exists."
	@echo "🚀 Force-pushing to establish local as source of truth..."
	git push -u origin main -f
	@echo "✅ Project initialized and uploaded."

push: ship
	@echo "🚀 Committing and uploading to GitHub..."
	git add .
	git commit -m "Auto-sync: $$(date +'%Y-%m-%d %H:%M:%S')" || echo "No new edits to commit."
	git push
	@echo "✅ Upload complete."

pull:
	@echo "⬇️ Downloading from GitHub..."
	git pull
	@echo "💥 Exploding new changes..."
	@$(MAKE) explode

clean:
	rm -rf dist/ node_modules/ coverage/ package-lock.json
~~~

#### .gitignore
~~~text
node_modules/
coverage/
*.log
.DS_Store
package-lock.json
~~~

#### package.json
~~~json
{
  "name": "revenge-quick-switcher",
  "version": "3.9.1",
  "main": "dist/index.js",
  "scripts": {
    "build": "esbuild src/index.tsx --bundle --minify --format=esm --external:react --external:react-native --external:@revenge-mod --external:@revenge-mod/* --outfile=dist/index.js",
    "test": "jest"
  },
  "author": "Danny Clark, Gemini, Grok",
  "license": "MIT",
  "devDependencies": {
    "typescript": "^5.0.0",
    "esbuild": "^0.20.0",
    "jest": "^29.0.0",
    "ts-jest": "^29.0.0",
    "@types/jest": "^29.0.0",
    "@revenge-mod/types": "npm:vendetta-types@latest"
  }
}
~~~

#### tsconfig.json
~~~json
{
  "compilerOptions": {
    "target": "es2022",
    "module": "commonjs",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "jsx": "react",
    "baseUrl": ".",
    "paths": { "@revenge-mod/*": ["./node_modules/@revenge-mod/types/dist/*"] }
  },
  "include": ["src/**/*", "__tests__/**/*"]
}
~~~

#### manifest.json
~~~json
{
  "name": "Quick Server Switcher",
  "description": "Alphabetical server list + fuzzy search + flat sidebar for Revenge.",
  "authors": [
    { "name": "Danny Clark", "id": "0" },
    { "name": "Gemini", "id": "1" },
    { "name": "Grok", "id": "2" }
  ],
  "main": "dist/index.js",
  "version": "3.9.1"
}
~~~

#### src/utils.ts
~~~typescript
export const escapeMarkdown = (t: string) => t.replace(/([\\_*~`|])/g, '\\$1');
export const sanitizeName = (t: string) => t ? Array.from(String(t)).slice(0, 100).join("").replace(/[\u200B-\u200D\uFEFF\u202A-\u202E\u2066-\u2069]/g, '').trim() || "Unnamed" : "Unknown";
export const normalizeText = (t: string) => t.normalize("NFKC").toLowerCase();
export const resolveGuildId = (n: any) => n?.id || n?.guildId || n?.guild_id || (typeof n === 'string' ? n : null);
export const getArrayChecksum = (arr: any[]) => {
  let ck = 0x811c9dc5; 
  for (let i = 0; i < arr.length; i++) {
    const id = resolveGuildId(arr[i]);
    if (id) { for (let j = 0; j < id.length; j++) { ck ^= id.charCodeAt(j); ck = Math.imul(ck, 0x01000193); } }
  }
  return ck;
};
export const isSubsequence = (q: string, t: string) => {
  let i = 0;
  for (let j = 0; j < t.length && i < q.length; j++) if (q[i] === t[j]) i++;
  return i === q.length;
};
~~~

#### src/index.tsx
~~~tsx
/**
 * PROJECT_PULSE: {
 * "version": "3.9.1",
 * "env": { "node": "25.x", "os": "macos", "mod": "revenge" },
 * "hacks": [ "decoupled-esbuild", "abstracted-git-makefile", "forceful-init" ],
 * "limit": "2000-char-discord-pagination"
 * }
 */
import React from "react";
import { findByProps } from "@revenge-mod/metro";
import { after } from "@revenge-mod/patcher";
import { showToast } from "@revenge-mod/ui/toast";
import { logger } from "@revenge-mod";
import { registerCommand } from "@revenge-mod/commands";
import { storage } from "@revenge-mod/plugin";
import { useProxy } from "@revenge-mod/storage";
import { Forms } from "@revenge-mod/ui/components";
import { ScrollView } from "react-native";
import * as Utils from "./utils";

const { FormSwitchRow } = Forms;
let _G: any, _S: any, _R: any, _N: any;
const getGS = () => _G ??= findByProps("getGuild", "getGuilds");
const getSGS = () => _S ??= findByProps("getSortedGuilds");
const getR = () => _R ??= findByProps("transitionToGuild", "selectGuild");
const getN = () => _N ??= findByProps("push", "replace");

if (storage.flatSidebar === undefined) storage.flatSidebar = false;
class MappedGuild { constructor(public original: any, public id: string, public sanitized: string, public normalized: string) {} }
const sidebarCache = new WeakMap<any[], { checksum: number, data: any[] }>();

const handleExec = (rawArgs: any) => {
  try {
    const args = Array.isArray(rawArgs) ? rawArgs : Object.keys(rawArgs || {}).map(k => ({ name: k, value: rawArgs[k] }));
    let query = args.find(a => a.name === "query")?.value;
    let pageArg = args.find(a => a.name === "page")?.value;

    if (!pageArg && query && /^\d+$/.test(String(query).trim())) {
      pageArg = parseInt(String(query).trim());
      query = null;
    }

    const guilds = Object.values(getGS()?.getGuilds() || {});
    if (!guilds.length) return showToast("No servers found", "danger");
    const mapped = guilds.map((g: any) => new MappedGuild(g, Utils.resolveGuildId(g) || "", Utils.sanitizeName(g.name), Utils.normalizeText(Utils.sanitizeName(g.name))))
      .sort((a, b) => a.sanitized.localeCompare(b.sanitized, undefined, { sensitivity: "base" }));

    if (query) {
      const q = Utils.normalizeText(String(query)).trim();
      let match = null, score = 0;
      for (const item of mapped) {
        const t = item.normalized;
        if (t === q) { match = item.original; break; }
        if (t.startsWith(q) && score < 50) { match = item.original; score = 50; }
        else if (t.includes(q) && score < 10) { match = item.original; score = 10; }
        else if (Utils.isSubsequence(q, t) && score < 5) { match = item.original; score = 5; }
      }
      if (match) {
        const id = Utils.resolveGuildId(match), R = getR(), N = getN();
        if (R?.transitionToGuild) R.transitionToGuild(id);
        else if (N?.push) N.push("Guild", { guildId: id });
        showToast(`Jumped to ${Utils.sanitizeName(match.name)}`, "success");
      } else showToast("No match", "danger");
      return;
    }

    const PAGE_SIZE = 40; 
    const totalPages = Math.ceil(mapped.length / PAGE_SIZE);
    const currentPage = Math.min(totalPages, Math.max(1, pageArg || 1));
    const start = (currentPage - 1) * PAGE_SIZE;
    const pageItems = mapped.slice(start, start + PAGE_SIZE);

    let content = `### Servers (${mapped.length})\n`;
    content += pageItems.map(i => `• ${Utils.escapeMarkdown(i.sanitized)}`).join("\n");
    content += `\n\n**Page ${currentPage} of ${totalPages}**`;
    if (currentPage < totalPages) content += `\n*Use /servers ${currentPage + 1} to see more.*`;
    else if (totalPages > 1) content += `\n*Use /servers 1 to return to the start.*`;
    return { content };
  } catch (e) { logger.error(e); }
};

export default {
  settings: () => { useProxy(storage); return (<ScrollView><FormSwitchRow label="Flat Sidebar" value={storage.flatSidebar} onValueChange={v => { storage.flatSidebar = v; showToast(`Sidebar ${v ? "Flat" : "Standard"}`); }}/></ScrollView>); },
  onLoad() {
    this._unreg = registerCommand({ 
      name: "servers", 
      options: [
        { name: "query", type: 3, description: "Search OR page number" },
        { name: "page", type: 4, description: "Go to page" }
      ], 
      execute: handleExec 
    });
    const SGS = getSGS();
    if (SGS) this._patch = after("getSortedGuilds", SGS, (_, ret) => {
      if (!storage.flatSidebar || !Array.isArray(ret)) return ret;
      const ck = Utils.getArrayChecksum(ret);
      const cached = sidebarCache.get(ret);
      if (cached?.checksum === ck) return cached.data;
      const flat = ret.flatMap((n: any) => n.type === 'folder' ? n.guilds : [n]);
      const GS = getGS();
      const res = flat.map(n => { const id = Utils.resolveGuildId(n), g = id ? GS.getGuild(id) : null; return { n, name: g ? Utils.sanitizeName(g.name) : "" }; }).sort((a, b) => a.name.localeCompare(b.name)).map(i => i.n);
      sidebarCache.set(ret, { checksum: ck, data: res });
      return res;
    });
  },
  onUnload() { this._unreg?.(); this._patch?.(); }
};
~~~

#### __tests__/utils.test.ts
~~~typescript
import * as Utils from '../src/utils';
describe('Git Abstraction Utils', () => {
  test('isSubsequence matches discontinuous fuzzy queries', () => {
    expect(Utils.isSubsequence('cafe', 'cat fanciers')).toBe(true);
  });
});
~~~
"""
import sys, os, re, shutil, subprocess
STD = "PROMPT_FOR_SECOND_OPINION.md"

def run_install():
    if os.path.exists("package-lock.json"): os.remove("package-lock.json")
    print("[!] Running npm install (standardized stack)...")
    try:
        subprocess.run(["npm", "install"], check=True)
        print("[+] Installation successful via NPM registry.")
        print("\n[!] NOTE: Any 'vulnerabilities' reported by npm are typical for development")
        print("    and testing tools (like Jest). They do not affect the security of the")
        print("    final plugin bundle produced by esbuild.\n")
    except:
        print("[!] Retrying with legacy-peer-deps...")
        try:
            subprocess.run(["npm", "install", "--legacy-peer-deps"], check=True)
            print("\n[!] NOTE: Any 'vulnerabilities' reported by npm are typical for development")
            print("    and testing tools (like Jest). They do not affect the security of the")
            print("    final plugin bundle produced by esbuild.\n")
        except:
            print("[-] Critical Failure: npm install failed.")

def prep(p):
    s, d = os.path.abspath(p), os.getcwd()
    if not (os.path.exists(".git") or os.path.basename(d) == "RevengeQuickSwitcher"):
        r = "RevengeQuickSwitcher"; os.makedirs(r, exist_ok=True)
        t = os.path.abspath(os.path.join(r, STD)); shutil.copy2(s, t)
        if s != t: os.remove(s)
        os.chdir(r); return t, r
    t = os.path.abspath(STD); shutil.copy2(s, t)
    if s != t: os.remove(s)
    return t, None

def explode(p):
    src, folder = prep(p); print(f"Exploding {src}...")
    with open(src, 'r') as f: content = f.read()
    pattern = re.compile(r'#{3,} ([^\n]+)\n(?:~~~|[\x60]{3})[a-z]*\n(.*?)\n(?:~~~|[\x60]{3})', re.DOTALL)
    m = pattern.findall(content)
    for f, c in m:
        f = f.strip(); d = os.path.dirname(f)
        if d: os.makedirs(d, exist_ok=True)
        with open(f, 'w') as fh: fh.write(c.strip() + '\n')
        print(f" [+] {f}")
    if os.path.exists("package.json"):
        print("\n[!] CONTEXT - WHY THE BELOW IS NEEDED:")
        print("    - Installs 'esbuild' (guaranteed registry-backed bundler).")
        print("    - Fetches Revenge types for full IntelliSense support.")
        print("    - Sets up Jest for fail-fast logic checks.")
        ans = input("\n[?] Run 'npm install' now? [Y/n]: ").lower().strip()
        if ans == '' or ans == 'y': run_install()
    if folder: print(f"\n[!] Type 'cd {folder}' then 'make' to see the pipeline.")

def implode(p):
    src, _ = prep(p); print(f"Imploding {src}...")
    with open(src, 'r') as f: content = f.read()
    pattern = re.compile(r'(#{3,} ([^\n]+)\n(?:~~~|[\x60]{3})[a-z]*\n)(.*?)(~~~|[\x60]{3})', re.DOTALL)
    def rep(m):
        f = m.group(2).strip()
        if os.path.exists(f):
            with open(f, 'r') as fh: return f"{m.group(1)}{fh.read().strip()}\n{m.group(4)}"
        return m.group(0)
    with open(src, 'w') as f: f.write(pattern.sub(rep, content))

if __name__ == "__main__":
    s = sys.argv[0]; c = sys.argv[1].lower() if len(sys.argv) > 1 else "explode"
    if c == "implode": implode(s)
    else: explode(s)
# --- END ---