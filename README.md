# RevengeQuickSwitcher

A high-performance server navigation utility built natively for the **Revenge** Discord mobile client (display name: **Quick Server Switcher**).

---

## Documentation

| Document | Purpose |
|----------|---------|
| [HANDOFF.md](HANDOFF.md) | Maintainer / AI cold-start — current state, nav invariants, gotchas |
| [HACKING.md](HACKING.md) | Developer setup, Hermes/IIFE constraints, debug loop |
| [OPTIONS.md](OPTIONS.md) | Open work menu (reference IDs like `A1`, `C4`) |
| [TESTING.md](TESTING.md) | Local `make verify` + Revenge device checklist |
| [CHANGELOG.md](CHANGELOG.md) | Release notes and semver policy |

---

## Features

- **Switcher sheet**: `/servers` opens a top-docked searchable panel (keyboard-safe); tap to jump. Bot-message list remains a fallback when sheet APIs are missing.
- **Fuzzy-search navigation**: Jump via subsequence matching (e.g. typing `wsh` finds `Wayland High School`; subsequence needs 3+ characters).
- **Recent servers**: `/servers recent` and `/servers r1` jump slots; history recorded only when this plugin navigates.
- **Excluded servers**: Skip noisy or similarly named guilds in search (optional hide from list).
- **Ambiguous-match pick list**: When several servers share the best score, lists them instead of guessing.
- **Custom aliases**: Map shortcodes to full server names in settings (e.g. `chess=Maynard-area Chess Club`), with clipboard export/import.
- **Flat sidebar mode**: Overrides Discord's native UI to present an alphabetically sorted, folder-free guild list (skipped gracefully if SortedGuildStore is missing).
- **Smart pagination**: Pages by item count (up to 40) and character budget so fallback replies stay under Discord's 2000-character limit, with numeric page aliases (`/servers 2`).
- **Debug logging**: Optional Metro/patch/command diagnostics plus **Copy debug logs** (version-stamped, clipboard-safe single line).

Jump path uses Discord deep links (`openUrl`), matching known-good Revenge plugins (JumpTo / Stealmoji). See [HANDOFF.md](HANDOFF.md) before changing navigation.

---

## Installation (Revenge Client)

Revenge fetches `{url}/manifest.json`, so you must paste a **raw** base URL (not the GitHub repo page):

```
https://raw.githubusercontent.com/djbclark/RevengeQuickSwitcher/main/
```

1. Copy the URL above (trailing slash is fine).
2. Open Discord on your device and go to **User Settings → Revenge → Plugins**.
3. Tap **Install a plugin** / **+**, paste the URL, and confirm (allow unproxied install if prompted).
4. Reload the client.
5. Toggle the plugin **on**. An **X** on the toggle means start failed (see logging below).

If install fails with “Failed to fetch manifest”, you almost certainly pasted `https://github.com/...` instead of the `raw.githubusercontent.com` URL.

### Smoke test plugin (load isolation)

If the main plugin installs but will not enable, install this tiny plugin first:

```
https://raw.githubusercontent.com/djbclark/RevengeQuickSwitcher/main/smoke/
```

- If **smoke enables** (toggle stays on, wrench opens): Revenge loading works; the main plugin still has a start bug.
- If **smoke also shows an X**: the problem is broader (client/safe mode/network), not Quick Server Switcher logic.

### Where to look for Revenge plugin logs

1. **Safe Mode** — Revenge Settings → disable Safe Mode if enabled (plugins do not start in safe mode).
2. **Developer settings** — Revenge Settings → Developer (may require tapping the version repeatedly). Useful: debugger URL, React DevTools, Eval command.
3. **`/debug`** — built-in Revenge command; prints client/Revenge/React versions to chat.
4. **In-plugin debug buffer (easiest to share)** — open Quick Server Switcher settings → **Copy debug logs**, then paste into chat/GitHub. The paste is a single line (` | `-separated) because Discord mobile clipboard often drops newlines. Logs persist across restarts and are stamped with the plugin version.
5. **Logcat (Android)** — with USB debugging: `adb logcat | grep -iE 'revenge|vendetta|Quick|plugin|hermes'`. Plugin start errors are logged as `Plugin <id> errored whilst loading`. Switcher lines are tagged `[QuickSwitcher]`.
6. **Plugin info sheet** — the `i` icon → Refetch after a main-branch update; Delete + reinstall if the hash is stuck.

When reporting a stuck switcher / failed jump, please include: Discord build (from `/debug`), whether Close dismisses the panel, whether the jump toast appeared, and the **Copy debug logs** paste.

---

## Development

Full setup, Hermes constraints, and device debug loop: **[HACKING.md](HACKING.md)**. Agent / maintainer cold-start: **[HANDOFF.md](HANDOFF.md)**.

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
| `make test` | Run unit tests (96) |
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
  index.tsx          # Plugin entry: settings UI, flat sidebar patch, command wiring, openUrl jump
  sheets.tsx         # Top-docked switcher UI + dismiss-then-run
  excludes.ts        # Exclude-rule parse/match helpers
  aliases.ts         # Alias normalize / merge helpers for clipboard export-import
  recents.ts         # Recent-history helpers (low-risk plugin-only recording)
  command.ts         # /servers command logic (testable without Revenge mocks)
  sidebar.ts         # Flat sidebar flatten/sort + cache helpers
  theme.ts           # Settings color resolution (semantic tokens + fallbacks)
  utils.ts           # Pure helpers (fuzzy match, aliases, sanitization)
  revenge-mod.d.ts   # Type stubs for @revenge-mod/* imports
  *.test.ts          # Vitest unit tests
scripts/
  build.mjs          # Vendetta IIFE, ES2015, __QSS_VERSION__ inject
  check-manifest.mjs # Validates manifest.json and dist/index.js (run via verify)
smoke/               # Minimal plugin for load isolation
dist/
  index.js           # Built output consumed by Revenge (commit after build)
manifest.json        # Revenge plugin metadata (display name: Quick Server Switcher)
HANDOFF.md           # AI / maintainer handoff
HACKING.md           # Developer environment
OPTIONS.md           # Open work menu (tracks + risk; closed summary)
TESTING.md           # Local + device test plan
CHANGELOG.md         # Release notes
```

After changing source files, run `make build` (or `make verify`) and commit the updated `dist/index.js` so the plugin loads correctly from GitHub.

---

## Usage

- `/servers` — open switcher (or bot-message list fallback)
- `/servers query:<name>` — fuzzy-search and jump (or open filtered sheet / pick list)
- `/servers 2` — jump to page 2 of the server list (fallback pagination)
- `/servers recent` — list recent jumps from this plugin
- `/servers r1` — jump to recent slot 1 (also `r2`, …)

Configure **Flat Sidebar**, **Debug Logging**, **Excluded servers**, **Recent servers**, and **Custom Aliases** (with **Copy** / **Import**) under the plugin settings. Use **Open switcher** or **Copy debug logs** from settings as needed.

See **[OPTIONS.md](OPTIONS.md)** for open work (and closed IDs) and **[CHANGELOG.md](CHANGELOG.md)** for release notes and the semver policy.

---

## Testing

See **[TESTING.md](TESTING.md)** for local verification (`make verify`) and the full Revenge device test plan.

Quick pre-release check:

```bash
make verify
```

Then walk the checklist at the bottom of `TESTING.md` on your device (**OPTIONS A1**).

---

## Contributing

1. Fork the repo and create a branch.
2. Make changes in `src/`, run `make verify`.
3. Update docs (`CHANGELOG.md` / `OPTIONS.md` / handoff notes) when behavior changes.
4. Open a pull request with a clear description of the change.

Bug reports and feature requests are welcome via [GitHub Issues](https://github.com/djbclark/RevengeQuickSwitcher/issues).

### CI

GitHub Actions runs `npm run verify` on every push and pull request to `main` (typecheck, tests, build, manifest check). See `.github/workflows/ci.yml`.
