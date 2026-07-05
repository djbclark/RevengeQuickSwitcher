# RevengeQuickSwitcher

A high-performance server navigation utility built natively for the **Revenge** Discord mobile client.

## Features

- **Fuzzy-search navigation**: Jump to any server via subsequence matching (e.g. typing `wsh` finds `Wayland High School`).
- **Custom aliases**: Map shortcodes to full server names in settings (e.g. `chess=Maynard-area Chess Club`).
- **Flat sidebar mode**: Overrides Discord's native UI to present an alphabetically sorted, folder-free guild list.
- **Smart pagination**: Chunks server lists into 40-server pages to stay within Discord's 2000-character limit, with numeric page aliases (`/servers 2`).

## Installation (Revenge Client)

1. Copy this repository URL: `https://github.com/djbclark/RevengeQuickSwitcher`
2. Open Discord on your device and go to **User Settings > Revenge > Plugins**.
3. Tap the **+** icon and paste the URL.
4. Reload the client.

## Development

### Prerequisites

- Node.js 18+ (Node 20+ recommended)
- npm

### Setup

```bash
git clone https://github.com/djbclark/RevengeQuickSwitcher.git
cd RevengeQuickSwitcher
make install   # or: npm install
```

### Commands

| Command | Description |
|---------|-------------|
| `make build` | Bundle `src/` to `dist/index.js` via esbuild |
| `make test` | Run unit tests |
| `make typecheck` | Type-check testable modules (`command`, `sidebar`, `utils`) |
| `make verify` | Run typecheck, tests, and build |
| `make clean` | Remove `dist/` and `node_modules/` |

Or use npm directly:

```bash
npm run build
npm test
npm run verify
```

### Project layout

```
src/
  index.tsx     # Plugin entry: settings UI, flat sidebar patch, command wiring
  command.ts    # /servers command logic (testable without Revenge mocks)
  sidebar.ts    # Flat sidebar flatten/sort + cache helpers
  utils.ts      # Pure helpers (fuzzy match, aliases, sanitization)
dist/
  index.js    # Built output consumed by Revenge (commit after build)
manifest.json # Revenge plugin metadata
```

After changing source files, run `make build` and commit the updated `dist/index.js` so the plugin loads correctly from GitHub.

## Usage

- `/servers` — list servers (paginated)
- `/servers query:<name>` — fuzzy-search and jump to a server
- `/servers 2` — jump to page 2 of the server list

Configure **Flat Sidebar** and **Custom Aliases** under the plugin settings in Revenge.

## Device testing checklist

After building locally, verify on a Revenge client:

1. **Install/reload** — add or reload the plugin from the repo URL, then restart Discord.
2. **`/servers`** — first page lists servers alphabetically with a page footer.
3. **`/servers 2`** (or higher if you have 40+ servers) — pagination advances and the footer updates.
4. **`/servers query:<partial name>`** — fuzzy match jumps to the correct server and shows a success toast.
5. **Custom alias** — add `short=Full Server Name` in settings, then `/servers query:short` jumps correctly.
6. **Flat sidebar** — enable in settings; server list in the sidebar loses folders and sorts A–Z. Disable restores default behavior.
7. **Edge cases** — empty search (`/servers query:` with blank value) lists servers; unknown query shows "No match found".

Run `make verify` before testing on device to catch regressions in pure logic.

## Contributing

1. Fork the repo and create a branch.
2. Make changes in `src/`, run `make test` and `make build`.
3. Open a pull request with a clear description of the change.

Bug reports and feature requests are welcome via [GitHub Issues](https://github.com/djbclark/RevengeQuickSwitcher/issues).

### CI setup

The repo includes `.github/workflows/ci.yml` (test + build on push/PR). GitHub requires the `workflow` OAuth scope to push workflow files. If push is rejected for that reason:

```bash
gh auth refresh -h github.com -s workflow
git add .github/workflows/ci.yml
git commit -m "Add GitHub Actions CI"
git push origin main
```
