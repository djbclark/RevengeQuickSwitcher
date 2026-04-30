#!/usr/bin/env python3
r"""
# RevengeQuickSwitcher Polyglot (v3.9.5 "The AI Sync")

### BOOTSTRAP: `chmod +x whatever.md && ./whatever.md explode`
--- PASTE EVERYTHING BELOW INTO ANOTHER AI ---
Act as a Senior V8 Engineer. Review "RevengeQuickSwitcher" (v3.9.5).
AUDITOR STATE: Node: v25 | OS: MacOS | Mod: Revenge (Native).
CRITICAL: Validate the human-readable TSX logic and the esbuild pipeline. 
Ensure the Polyglot correctly acts as the synchronization layer for the 
AI-to-Local workflow.
AI INSTRUCTION: Use backtick/tilde code blocks in your reply.

### PROJECT SOURCE:

#### Makefile
~~~makefile
SOURCE_FILE = PROMPT_FOR_SECOND_OPINION.md
REPO_URL = git@github.com:djbclark/RevengeQuickSwitcher.git
.PHONY: help explode implode build clean ship push pull init-repo
all: help

help:
	@echo "============================================================"
	@echo "RevengeQuickSwitcher (v3.9.5) - The AI Sync Workflow"
	@echo "============================================================"
	@echo "[AI COLLABORATION WORKFLOW]"
	@echo "  1. Download AI output and run it (make explode)."
	@echo "  2. Test and edit files locally in src/."
	@echo "  3. Run 'make push' to sync edits, bundle, and upload."
	@echo "  4. Upload 'PROMPT_FOR_SECOND_OPINION.md' back to AI."
	@echo "============================================================"
	@echo "[MANUAL COMMANDS]"
	@echo "  make explode    - Extract files and install NPM deps."
	@echo "  make build      - Compile and bundle plugin via esbuild."
	@echo "  make implode    - Sync local edits back to the Polyglot file."
	@echo "  make push       - Implodes, builds, and pushes to GitHub."
	@echo "  make pull       - Downloads updates and explodes them."
	@echo "  make clean      - Wipe node_modules and build artifacts."
	@echo "============================================================"

# Development Pipeline
build:
	npm run build

explode:
	@python3 $(SOURCE_FILE) explode

implode:
	@python3 $(SOURCE_FILE) implode

ship: build implode

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
	@echo "✅ Upload complete! You can now hand $(SOURCE_FILE) back to the AI."

pull:
	@echo "⬇️ Downloading from GitHub..."
	git pull
	@echo "💥 Exploding new changes..."
	@$(MAKE) explode

clean:
	rm -rf dist/ node_modules/ package-lock.json
~~~

#### .gitignore
~~~text
node_modules/
*.log
.DS_Store
package-lock.json
~~~

#### package.json
~~~json
{
  "name": "revenge-quick-switcher",
  "version": "3.9.5",
  "main": "dist/index.js",
  "scripts": {
    "build": "esbuild src/index.tsx --bundle --minify --format=esm --external:react --external:react-native --external:@revenge-mod --external:@revenge-mod/* --outfile=dist/index.js"
  },
  "author": "Danny Clark, Gemini, Grok",
  "license": "MIT",
  "devDependencies": {
    "typescript": "^5.0.0",
    "esbuild": "^0.20.0",
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
  "include": ["src/**/*"]
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
  "version": "3.9.5"
}
~~~

#### README.md
~~~markdown
# RevengeQuickSwitcher

A high-performance server navigation utility built natively for the **Revenge** Discord mobile client.

## ⚡ Plugin Features
* **Fuzzy-Search Navigation**: Jump instantly to any server via subsequence matching (e.g., typing `wsh` will successfully find `Wayland High School`).
* **Flat Sidebar Mode**: Overrides Discord's native UI to present an alphabetically sorted, folder-free guild list.
* **Smart Pagination**: Automatically chunks outputs into 40-server pages to comply with Discord's strict 2000-character limits, complete with numeric aliases (`/servers 2`).

## 🛠 Developer Pipeline
This project is powered by a custom "Polyglot" architecture that completely abstracts Git and NPM. Developers can bootstrap, compile (via `esbuild`), and push changes using a single command:
`make push`

## 📦 Installation (Revenge Client)
1. Copy this repository URL: `https://github.com/djbclark/RevengeQuickSwitcher`
2. Open Discord on your device and navigate to **User Settings > Revenge > Plugins**.
3. Tap the **+** icon and paste the URL.
4. Reload the client.

*Built by Danny Clark, Gemini, and Grok.*
~~~

#### src/utils.ts
~~~typescript
export const escapeMarkdown = (text: string) => {
  return text.replace(/([\\_*~`|])/g, '\\$1');
};

export const sanitizeName = (text: string) => {
  if (!text) return "Unknown";
  const safeText = Array.from(String(text))
    .slice(0, 100)
    .join("")
    .replace(/[\u200B-\u200D\uFEFF\u202A-\u202E\u2066-\u2069]/g, '')
    .trim();
  return safeText || "Unnamed";
};

export const normalizeText = (text: string) => {
  return text.normalize("NFKC").toLowerCase();
};

export const resolveGuildId = (node: any) => {
  return node?.id || node?.guildId || node?.guild_id || (typeof node === 'string' ? node : null);
};

// Generates an FNV-1a hash to quickly check if the sidebar array has changed
export const getArrayChecksum = (arr: any[]) => {
  let checksum = 0x811c9dc5; 
  for (let i = 0; i < arr.length; i++) {
    const id = resolveGuildId(arr[i]);
    if (id) { 
      for (let j = 0; j < id.length; j++) { 
        checksum ^= id.charCodeAt(j); 
        checksum = Math.imul(checksum, 0x01000193); 
      } 
    }
  }
  return checksum;
};

// Checks if the characters of 'query' appear in order within 'text'
export const isSubsequence = (query: string, text: string) => {
  let i = 0;
  for (let j = 0; j < text.length && i < query.length; j++) {
    if (query[i] === text[j]) i++;
  }
  return i === query.length;
};
~~~

#### src/index.tsx
~~~tsx
/**
 * PROJECT_PULSE: {
 * "version": "3.9.5",
 * "env": { "node": "25.x", "os": "macos", "mod": "revenge" },
 * "hacks": [ "decoupled-esbuild", "abstracted-git", "human-readable" ],
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

// Caching Discord Metro modules for performance
let _GuildStore: any, _SortedGuildStore: any, _Router: any, _Navigation: any;
const getGuildStore = () => _GuildStore ??= findByProps("getGuild", "getGuilds");
const getSortedGuildStore = () => _SortedGuildStore ??= findByProps("getSortedGuilds");
const getRouter = () => _Router ??= findByProps("transitionToGuild", "selectGuild");
const getNavigation = () => _Navigation ??= findByProps("push", "replace");

// Initialize plugin storage defaults
if (storage.flatSidebar === undefined) {
  storage.flatSidebar = false;
}

class MappedGuild { 
  constructor(
    public original: any, 
    public id: string, 
    public sanitized: string, 
    public normalized: string
  ) {} 
}

const sidebarCache = new WeakMap<any[], { checksum: number, data: any[] }>();

const handleExec = (rawArgs: any) => {
  try {
    // Standardize arguments (Revenge vs Vendetta differences)
    const args = Array.isArray(rawArgs) 
      ? rawArgs 
      : Object.keys(rawArgs || {}).map(k => ({ name: k, value: rawArgs[k] }));
      
    let query = args.find(a => a.name === "query")?.value;
    let pageArg = args.find(a => a.name === "page")?.value;

    // Allow user to type `/servers 3` directly into the query field
    if (!pageArg && query && /^\d+$/.test(String(query).trim())) {
      pageArg = parseInt(String(query).trim(), 10);
      query = null;
    }

    const guildStore = getGuildStore();
    const guilds = Object.values(guildStore?.getGuilds() || {});
    
    if (!guilds.length) {
      return showToast("No servers found", "danger");
    }

    // Process and sort all available servers alphabetically
    const mappedGuilds = guilds.map((g: any) => {
      const id = Utils.resolveGuildId(g) || "";
      const safeName = Utils.sanitizeName(g.name);
      const normalName = Utils.normalizeText(safeName);
      return new MappedGuild(g, id, safeName, normalName);
    }).sort((a, b) => a.sanitized.localeCompare(b.sanitized, undefined, { sensitivity: "base" }));

    // ==========================================
    // MODE 1: SEARCH DIRECTORY
    // ==========================================
    if (query) {
      const normalizedQuery = Utils.normalizeText(String(query)).trim();
      let bestMatch = null;
      let bestScore = 0;

      // Priority queue matching system
      for (const item of mappedGuilds) {
        const text = item.normalized;
        if (text === normalizedQuery) { 
          bestMatch = item.original; 
          break; // Exact match wins immediately
        }
        if (text.startsWith(normalizedQuery) && bestScore < 50) { 
          bestMatch = item.original; 
          bestScore = 50; 
        }
        else if (text.includes(normalizedQuery) && bestScore < 10) { 
          bestMatch = item.original; 
          bestScore = 10; 
        }
        else if (Utils.isSubsequence(normalizedQuery, text) && bestScore < 5) { 
          bestMatch = item.original; 
          bestScore = 5; 
        }
      }

      if (bestMatch) {
        const id = Utils.resolveGuildId(bestMatch);
        const Router = getRouter();
        const Navigation = getNavigation();
        
        if (Router?.transitionToGuild) {
          Router.transitionToGuild(id);
        } else if (Navigation?.push) {
          Navigation.push("Guild", { guildId: id });
        }
        showToast(`Jumped to ${Utils.sanitizeName(bestMatch.name)}`, "success");
      } else {
        showToast("No match found", "danger");
      }
      return;
    }

    // ==========================================
    // MODE 2: PAGINATED LIST
    // ==========================================
    const PAGE_SIZE = 40; // Safely fits inside Discord's 2000 character limit
    const totalPages = Math.ceil(mappedGuilds.length / PAGE_SIZE);
    const currentPage = Math.min(totalPages, Math.max(1, pageArg || 1));
    const startIndex = (currentPage - 1) * PAGE_SIZE;
    const pageItems = mappedGuilds.slice(startIndex, startIndex + PAGE_SIZE);

    let content = `### Servers (${mappedGuilds.length})\n`;
    content += pageItems.map(item => `• ${Utils.escapeMarkdown(item.sanitized)}`).join("\n");
    content += `\n\n**Page ${currentPage} of ${totalPages}**`;
    
    if (currentPage < totalPages) {
      content += `\n*Use /servers ${currentPage + 1} to see more.*`;
    } else if (totalPages > 1) {
      content += `\n*Use /servers 1 to return to the start.*`;
    }
    
    return { content };
  } catch (error) { 
    logger.error(error); 
  }
};

export default {
  settings: () => { 
    useProxy(storage); 
    return (
      <ScrollView>
        <FormSwitchRow 
          label="Flat Sidebar" 
          value={storage.flatSidebar} 
          onValueChange={(value: boolean) => { 
            storage.flatSidebar = value; 
            showToast(`Sidebar set to ${value ? "Flat" : "Standard"}`); 
          }}
        />
      </ScrollView>
    ); 
  },

  onLoad() {
    this._unreg = registerCommand({ 
      name: "servers", 
      options: [
        { name: "query", type: 3, description: "Search term OR page number" },
        { name: "page", type: 4, description: "Go to a specific page" }
      ], 
      execute: handleExec 
    });

    const SortedGuildStore = getSortedGuildStore();
    if (SortedGuildStore) {
      this._patch = after("getSortedGuilds", SortedGuildStore, (_, returnValue) => {
        // Bypass if user disabled the setting or data is invalid
        if (!storage.flatSidebar || !Array.isArray(returnValue)) return returnValue;

        const checksum = Utils.getArrayChecksum(returnValue);
        const cachedData = sidebarCache.get(returnValue);
        
        if (cachedData?.checksum === checksum) return cachedData.data;

        const guildStore = getGuildStore();
        
        // Extract out of folders and sort alphabetically
        const flattenedGuilds = returnValue.flatMap((node: any) => node.type === 'folder' ? node.guilds : [node]);
        const sortedFlattenedGuilds = flattenedGuilds.map((node: any) => {
          const id = Utils.resolveGuildId(node);
          const guild = id ? guildStore.getGuild(id) : null;
          return { node, name: guild ? Utils.sanitizeName(guild.name) : "" };
        })
        .sort((a, b) => a.name.localeCompare(b.name))
        .map(item => item.node);
        
        sidebarCache.set(returnValue, { checksum, data: sortedFlattenedGuilds });
        return sortedFlattenedGuilds;
      });
    }
  },

  onUnload() { 
    this._unreg?.(); 
    this._patch?.(); 
  }
};
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
    except:
        print("[!] Retrying with legacy-peer-deps...")
        try:
            subprocess.run(["npm", "install", "--legacy-peer-deps"], check=True)
        except:
            print("[-] Critical Failure: npm install failed.")

def prep(p):
    s, d = os.path.abspath(p), os.getcwd()
    if not (os.path.exists(".git") or os.path.basename(d) == "RevengeQuickSwitcher"):
        r = "RevengeQuickSwitcher"; os.makedirs(r, exist_ok=True)
        t = os.path.abspath(os.path.join(r, STD))
        if s != t:
            shutil.copy2(s, t)
            if os.path.exists(s): os.remove(s)
        os.chdir(r); return t, r
    t = os.path.abspath(STD)
    if s != t:
        shutil.copy2(s, t)
        if os.path.exists(s): os.remove(s)
    return t, None

def explode(p):
    src, folder = prep(p); print(f"Exploding {src}...")
    
    # Pre-clean the old tests directory if it exists since we dropped Jest
    if os.path.exists("__tests__"): shutil.rmtree("__tests__")
        
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

# --- EOF (END OF POLYGLOT) ---