# RevengeQuickSwitcher

A high-performance server navigation utility built natively for the **Revenge** Discord mobile client.

## Features

- **Fuzzy-search navigation**: Jump to any server via subsequence matching (e.g. typing `wsh` finds `Wayland High School`; subsequence needs 3+ characters).
- **Ambiguous-match pick list**: When several servers share the best score, lists them instead of guessing.
- **Custom aliases**: Map shortcodes to full server names in settings (e.g. `chess=Maynard-area Chess Club`).
- **Flat sidebar mode**: Overrides Discord's native UI to present an alphabetically sorted, folder-free guild list.
- **Smart pagination**: Pages by item count (up to 40) and character budget so responses stay under Discord's 2000-character limit, with numeric page aliases (`/servers 2`).
- **Debug logging**: Optional setting that logs Metro/patch/command diagnostics through Revenge's logger.

## Installation (Revenge Client)

1. Copy this repository URL: `https://github.com/djbclark/RevengeQuickSwitcher`
2. Open Discord on your device and go to **User Settings → Revenge → Plugins**.
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
| `make typecheck` | Type-check all `src/` modules (including `index.tsx`) |
| `make verify` | Run typecheck, tests, build, and manifest validation |
| `make clean` | Remove `node_modules/` (keeps committed `dist/`) |
| `make clean-all` | Remove `dist/` and `node_modules/` |

Or use npm directly:

```bash
npm run build
npm test
npm run typecheck
npm run verify
```

### Project layout

```
src/
  index.tsx          # Plugin entry: settings UI, flat sidebar patch, command wiring
  command.ts         # /servers command logic (testable without Revenge mocks)
  sidebar.ts         # Flat sidebar flatten/sort + cache helpers
  theme.ts           # Settings color resolution (semantic tokens + fallbacks)
  utils.ts           # Pure helpers (fuzzy match, aliases, sanitization)
  revenge-mod.d.ts   # Type stubs for @revenge-mod/* imports
  *.test.ts          # Vitest unit tests
scripts/
  check-manifest.mjs # Validates manifest.json and dist/index.js (run via verify)
dist/
  index.js           # Built output consumed by Revenge (commit after build)
manifest.json        # Revenge plugin metadata (display name: Quick Server Switcher)
OPTIONS.md           # Living backlog of product/engineering options
CHANGELOG.md         # Release notes
```

After changing source files, run `make build` and commit the updated `dist/index.js` so the plugin loads correctly from GitHub.

## Usage

- `/servers` — list servers (paginated)
- `/servers query:<name>` — fuzzy-search and jump to a server
- `/servers 2` — jump to page 2 of the server list

Configure **Flat Sidebar**, **Debug Logging**, and **Custom Aliases** under the plugin settings in Revenge.

See **[OPTIONS.md](OPTIONS.md)** for the product backlog and **[CHANGELOG.md](CHANGELOG.md)** for release notes.

## Testing

See **[TESTING.md](TESTING.md)** for local verification (`make verify`) and the full Revenge device test plan.

Quick pre-release check:

```bash
make verify
```

Then walk the checklist at the bottom of `TESTING.md` on your device.

## Contributing

1. Fork the repo and create a branch.
2. Make changes in `src/`, run `make verify`.
3. Open a pull request with a clear description of the change.

Bug reports and feature requests are welcome via [GitHub Issues](https://github.com/djbclark/RevengeQuickSwitcher/issues).

### CI

GitHub Actions runs `npm run verify` on every push and pull request to `main` (typecheck, tests, build, manifest check). See `.github/workflows/ci.yml`.
