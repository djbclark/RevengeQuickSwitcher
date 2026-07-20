# HACKING — RevengeQuickSwitcher Development Environment

This document gets a developer from a clean machine to a working build, install, and debug loop for Quick Server Switcher on Revenge Discord mobile. Follow the sections in order.

Agent cold-start / current product state: [HANDOFF.md](HANDOFF.md). User install: [README.md](README.md). Device checklist: [TESTING.md](TESTING.md).

---

## What you're setting up

| Layer                | Role                                           |
| -------------------- | ---------------------------------------------- |
| Node.js + npm        | Build, typecheck, Vitest                       |
| `dist/index.js`      | Bundled plugin Revenge evals (committed)       |
| `manifest.json`      | Plugin metadata + content `hash`               |
| Discord + Revenge    | Runtime on Android/iOS device or emulator      |
| Optional: adb logcat | Native logs when Copy debug logs is not enough |

---

## Tested versions

| Tool                 | Version               | Notes                                        |
| -------------------- | --------------------- | -------------------------------------------- |
| Node.js              | 18+ (20+ recommended) | CI uses current Node LTS                     |
| npm                  | bundled with Node     | Lockfile committed                           |
| TypeScript           | ^5                    | `tsc --noEmit` via `tsconfig.typecheck.json` |
| esbuild              | ^0.28                 | `scripts/build.mjs`                          |
| Vitest               | ^3                    | 96 unit tests                                |
| `@revenge-mod/types` | vendetta-types 2.4.21 | Dev types only                               |
| Plugin               | **4.5.9**             | See `package.json` / `manifest.json`         |

Revenge and Discord client versions churn; always record `/debug` output when filing device bugs.

---

## Part 1 — Local setup

### 1.1 Clone and install

```bash
git clone https://github.com/djbclark/RevengeQuickSwitcher.git
cd RevengeQuickSwitcher
just install   # or: npm install
```

### 1.2 Verify

```bash
just verify
```

Runs, in order:

1. **Typecheck** — all `src/` modules including `index.tsx`
2. **Unit tests** — Vitest (`*.test.ts`)
3. **Build** — esbuild → `dist/index.js`, updates `manifest.json` `hash`
4. **Manifest check** — `scripts/check-manifest.mjs`

Expected: all steps exit 0; tests **96 passed**; `manifest ok (v…)`.

Individual targets:

| Command          | Purpose                          |
| ---------------- | -------------------------------- |
| `just build`     | Rebuild bundle only              |
| `just test`      | Vitest only                      |
| `just typecheck` | `tsc` only                       |
| `just clean`     | Remove `node_modules/`           |
| `just clean-all` | Remove `dist/` + `node_modules/` |

npm equivalents: `npm run build`, `npm test`, `npm run typecheck`, `npm run verify`.

### 1.3 After editing source

1. Change files under `src/`.
2. `just verify`.
3. Commit **`src/`**, **`dist/index.js`**, and **`manifest.json`** together when shipping (Revenge loads the committed bundle from GitHub raw).
4. If releasing: bump `version` in `package.json` **and** `manifest.json`, update `CHANGELOG.md` and OPTIONS statuses.

---

## Part 2 — Bundle constraints (CRITICAL)

Revenge loads plugins like Vendetta: the client wraps/evals the file and expects a plugin export object. This repo matches the known-good shape.

### 2.1 IIFE + CJS

`scripts/build.mjs` bundles `src/index.tsx` as CJS, then wraps:

```js
(function(exports){ ...; return exports })({})
```

Do not switch to ESM-only output without re-validating enable on device.

### 2.2 Hermes / ES2015

Discord's Hermes historically rejects newer syntax (`??=`, some optional-chain forms) at eval time. Build **`target: ["es2015"]`**.

Symptoms of a bad bundle: plugin installs but toggle shows **X**; smoke plugin still enables → main bundle/start bug.

### 2.3 Version injection

`__QSS_VERSION__` is defined from `package.json` at build time. Debug log lines are stamped `[vX.Y.Z …]`. Keep `package.json` and `manifest.json` versions in sync.

### 2.4 No eval-time storage / `this`

Plugin enable failed historically when touching `storage` or relying on `this` at module eval time (see CHANGELOG 4.4.3–4.4.4). Keep side effects inside `onLoad` / settings render paths.

### 2.5 Externals

React, React Native, and `@revenge-mod/*` stay external — provided by the client at runtime. Types live in `src/revenge-mod.d.ts`.

---

## Part 3 — Install on Revenge

### 3.1 Raw URL (not github.com HTML)

```
https://raw.githubusercontent.com/djbclark/RevengeQuickSwitcher/main/
```

Revenge fetches `{url}/manifest.json`. Trailing slash is fine. If you paste the repo page URL, install fails with “Failed to fetch manifest”.

### 3.2 Steps

1. User Settings → Revenge → Plugins → Install / **+**
2. Paste raw URL; allow unproxied install if prompted
3. Reload Discord (force-quit recommended after updates)
4. Toggle plugin **on**; open wrench/settings

### 3.3 Smoke plugin

If main will not enable:

```
https://raw.githubusercontent.com/djbclark/RevengeQuickSwitcher/main/smoke/
```

| Smoke   | Main  | Meaning                                 |
| ------- | ----- | --------------------------------------- |
| Enables | Fails | Main start/bundle bug                   |
| Also X  | —     | Broader Revenge/safe-mode/network issue |

### 3.4 Update loop

After pushing to `main`: plugin info → **Refetch**, or delete + reinstall. Confirm debug lines show the new `vX.Y.Z` (ring clears on upgrade).

---

## Part 4 — Debugging on device

### 4.1 In-plugin buffer (preferred for sharing)

1. Enable **Debug Logging** in plugin settings (optional but useful).
2. Reproduce the issue (open switcher, tap server, etc.).
3. Settings → **Copy debug logs**.
4. Paste into chat/GitHub (single line, `|`-separated).

Every line includes the plugin version. On upgrade, the ring resets so pastes are not mixed builds.

When reporting stuck switcher / failed jump, include:

- Discord / Revenge versions from `/debug`
- Whether Close dismisses the panel
- Whether a jump toast appeared
- The Copy debug logs paste

### 4.2 Revenge / system logs

1. **Safe Mode** off (plugins do not start in safe mode).
2. Revenge Developer settings (tap version repeatedly if needed).
3. Built-in `/debug` command.
4. Android logcat:

```bash
adb logcat | grep -iE 'revenge|vendetta|Quick|plugin|hermes'
```

Start failures often look like `Plugin <id> errored whilst loading`. Switcher lines are tagged `[QuickSwitcher]`.

### 4.3 Navigation invariants (do not regress)

Working path (v4.5.6+):

1. Dismiss switcher host completely.
2. `openUrl("https://discord.com/channels/{guild}/{channel}")`.

Do **not** reintroduce for jumps:

- Loose `findByProps("selectChannel")`
- Flux `CHANNEL_SELECT` / `GUILD_SELECT` as primary success path
- Full-screen touch scrims / nested RN `Modal` that outlive the sheet

UI host: prefer **top-docked** alert panel so the Android keyboard does not cover the list. Bottom `ActionSheet` is fine for short menus, not the primary searchable switcher.

---

## Part 5 — Development workflow

### 5.1 Feature work

1. Branch from `main` (cloud agents: `cursor/<name>-db57`).
2. Implement in `src/`; add/adjust Vitest coverage for pure helpers.
3. `just verify`.
4. Replace completed IDs in OPTIONS.md (keep IDs stable) and update CHANGELOG when behavior ships.
5. PR → merge → device **A1** checklist in TESTING.md.

### 5.2 What belongs in unit tests

Pure logic: fuzzy match, aliases, excludes, recents, command branching, sidebar transform/cache, sheet paging/filter helpers.

Not mocked end-to-end: real Metro stores, real `openUrl`, real keyboard. Those are device QA (**A1**) or future harness (**D1**).

### 5.3 Slash command on mobile

Type `/`, pick **servers**, fill **query** / **page** fields. Sending plain text `/servers foo` is not a slash invocation.

### 5.4 Optional: stayturgid / Handsets

For Mac-driven Android UI automation, see the stayturgid repo (`docs/research/mac-android-ui-automation.md`). This plugin does not vendor Handsets. If adding automation later, prefer a thin driver over Appium/Maestro as the primary stack, and keep Vitest as the default `just test`.

---

## Part 6 — Verification checklist

### Local

```bash
just verify
# Tests  96 passed (96)
# manifest ok (v4.5.9)   # or current version
```

### Device (short)

1. Install/refetch raw `main/` URL; force-quit Discord.
2. Enable plugin; open settings; **Open switcher**.
3. Filter field visible **above** keyboard when typing.
4. Tap a server → lands in that guild; Discord buttons still work.
5. Copy debug logs → lines show current version + `openUrl`.
6. Smoke through TESTING.md sections you touched (search, recents, excludes, flat sidebar).

Full plan: [TESTING.md](TESTING.md).

---

## Repo structure

```
RevengeQuickSwitcher/
  README.md          — user-facing overview + install
  HACKING.md         — this file
  HANDOFF.md         — AI / maintainer cold-start
  OPTIONS.md         — open work menu (stable IDs)
  TESTING.md         — verify + device QA
  CHANGELOG.md       — semver + release notes
  justfile           — install / build / test / verify
  package.json       — version + scripts
  manifest.json      — Revenge metadata + hash
  src/               — TypeScript / TSX sources + tests
  scripts/           — build.mjs, check-manifest.mjs
  smoke/             — minimal load-isolation plugin
  dist/index.js      — committed bundle
  .github/workflows/ — CI verify
```

---

## Gotchas (quick list)

| Symptom                  | Likely cause                                     |
| ------------------------ | ------------------------------------------------ |
| Failed to fetch manifest | Non-raw GitHub URL                               |
| Toggle X; smoke OK       | Bundle syntax / onLoad throw                     |
| Toggle X; smoke X        | Safe mode, Revenge, or network                   |
| Jump OK, taps dead       | Overlay not dismissed                            |
| Keyboard covers list     | Bottom sheet host                                |
| Freeze on tap            | Non-`openUrl` navigation path                    |
| Mixed version in logs    | Old ring; upgrade should clear — confirm refetch |
| `/servers` missing       | Old build with `shouldHide`; update plugin       |
| Flat sidebar no-op       | SortedGuildStore missing — expected skip         |
