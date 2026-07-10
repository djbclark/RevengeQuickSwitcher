# RevengeQuickSwitcher — AI Handoff Document

> **Purpose:** This file is a prompt for an AI agent taking over development. Read it fully before doing anything else. It describes what the project does, the current state, the environment, the tooling rules, and what's next.
>
> **Human index:** [README.md](README.md). Full clean-install setup + Hermes/Revenge gotchas: [HACKING.md](HACKING.md). **Open work menu:** [OPTIONS.md](OPTIONS.md). Device checklist: [TESTING.md](TESTING.md). Release notes: [CHANGELOG.md](CHANGELOG.md). Git history has the detailed narrative of every change; this file is the condensed durable record.

---

## What this project does

**RevengeQuickSwitcher** (display name: **Quick Server Switcher**) is a Revenge Discord mobile plugin for fast server navigation:

- `/servers` opens a **top-docked searchable switcher** (keyboard-safe); tap a row to jump
- Fuzzy search, aliases, excludes, recent-jump slots (`/servers recent`, `/servers rN`)
- Optional **flat sidebar** (alphabetical, folder-free)
- Bot-message list remains a **fallback** when sheet/alert APIs are missing
- Jump path: dismiss overlay → `openUrl("https://discord.com/channels/{guild}/{channel}")` (JumpTo / Stealmoji pattern)

Install URL (raw base — not the GitHub HTML page):

```
https://raw.githubusercontent.com/djbclark/RevengeQuickSwitcher/main/
```

Smoke plugin (load isolation):

```
https://raw.githubusercontent.com/djbclark/RevengeQuickSwitcher/main/smoke/
```

---

## 🚦 Cold-start — current state (read this first)

**As of 2026-07-10.** Released on `main`: **v4.5.9**.

| Field | Value |
|-------|-------|
| Package / manifest version | `4.5.9` |
| Display name | Quick Server Switcher |
| Bundle | Vendetta IIFE, ES2015 target, `__QSS_VERSION__` injected |
| Unit tests | **96** Vitest tests (`make verify`) |
| Open human gate | **A1** — device QA on Revenge Android |

**Working navigation (device-proven):**

1. Open switcher via `/servers` or settings **Open switcher**
2. Host is **top-docked** `openAlert` panel (not bottom ActionSheet — keyboard covers bottom sheets)
3. On pick / Close: `dismissThenRun` / `hideSwitcherSheet` fully tears down the host
4. Then `openUrl` deep link to last/default channel in that guild
5. Do **not** call loose `selectChannel`, Flux `CHANNEL_SELECT` / `GUILD_SELECT`, or `selectGuild` for the jump — those froze or failed to stick on device

**Recent landings (v4.5.x freeze / overlay saga):**

| Ver | What landed | Device outcome |
|-----|-------------|----------------|
| 4.5.4 | Drop loose `selectChannel`; Flux CHANNEL/GUILD_SELECT | Still froze |
| 4.5.5 | Prefer `selectGuild`; version-stamp debug lines | CHANNEL_SELECT verified then freeze; selectGuild didn't stick |
| 4.5.6 | JumpTo-style `openUrl` only | Jump worked; taps dead after |
| 4.5.7 | Harder dismiss before `openUrl` | Still dead taps (leftover overlay) |
| 4.5.8 | Native `ActionSheet` + `hideActionSheet` then `openUrl` | Jump + taps OK; keyboard covered bottom sheet |
| 4.5.9 | Restore **top-docked** panel; keep dismiss-then-`openUrl`; no full-screen scrim; Filter not auto-focused | Keyboard-safe; taps OK |

**Known device facts:**

- `SortedGuildStore not found` → flat sidebar patch is skipped (lower priority; not a start failure)
- Debug ring persists across restarts; every line stamped `[vX.Y.Z …]`; ring clears on version upgrade
- Settings → **Copy debug logs** pastes a single `|`-separated line (Discord mobile clipboard drops newlines)
- Cloud agents **cannot** reach the phone over ADB; device QA is operator-side (**A1**)

**Next work:** [OPTIONS.md](OPTIONS.md) — open items only. Primary gate: **A1** retest of v4.5.9 (top-dock above keyboard; taps after jump; logs show `v4.5.9` + `openUrl`). Feature backlog highlights: **C4** pins, **C2** channel jump (high risk), **C3** folder-aware sort, **D1** Metro smoke harness.

**Verify / ship:**

```bash
make install   # once
make verify    # typecheck + 96 tests + build + manifest hash
```

After source edits: commit updated `dist/index.js` + `manifest.json` `hash` (verify rewrites hash). Bump `package.json` + `manifest.json` `version` together; update `CHANGELOG.md`.

---

## Agent conventions

### Device preference (when operator has stayturgid fleet)

Same order as stayturgid when a phone must be used and the choice does not matter:

1. **s24** (Galaxy S24) — preferred
2. **hd8** (Kindle Fire HD 8) — second
3. **p7a** (Pixel 7a) — third (daily driver; avoid unless needed)

Announce before live UI work when someone may be on the device:

`🚨📱🚨 USING — s24 — Revenge QA — ~N min`

When done: `✅📱✅ FREE — s24 ✅📱✅`

Mac→Android UI automation research lives in the **stayturgid** repo (`docs/research/mac-android-ui-automation.md`). This plugin repo does **not** ship Handsets/Appium harnesses yet (**D1**). Prefer Vitest here; any future device harness should stay thin (e.g. Vitest + Handsets CLI), not Appium-first.

### Cloud / Desktop resume

This project's cloud-agent runs are under the same Cursor account as stayturgid work. Example resume URL for the docs/nav saga context:

```
https://cursor.com/agents/bc-0b0c3481-2bce-460e-a05e-55297c36db57
```

Repo: `https://github.com/djbclark/RevengeQuickSwitcher` (GitHub may also show `revengequickswitcher` casing). Default base branch: **`main`**. Feature branches for cloud agents: `cursor/<descriptive-name>-db57`.

### Do / don't

| Do | Don't |
|----|-------|
| Keep bot-message fallback when sheet APIs missing | Call loose Metro `selectChannel` / Flux select for jumps |
| Dismiss switcher host **before** `openUrl` | Leave full-screen scrims / nested RN `Modal` hosts |
| Target ES2015 IIFE; avoid `??=` / optional-chain in output | Eval-time `storage` / top-level `this` (breaks enable) |
| Stamp debug lines with plugin version | Mix multi-version debug pastes without clearing ring |
| Update OPTIONS status + CHANGELOG in the same PR as behavior | Renumber shipped option IDs |

---

## How updates work

GitHub `main` is the source of truth. Revenge loads `manifest.json` + `main` (`dist/index.js`) from the raw URL.

1. Edit `src/`, bump version in `package.json` + `manifest.json` when shipping behavior.
2. `make verify` (rebuilds `dist/`, refreshes `hash`).
3. Update `CHANGELOG.md` + OPTIONS statuses.
4. Commit, push, open PR → merge to `main`.
5. On device: plugin info → **Refetch**, or delete + reinstall raw URL; force-quit Discord.

Semver policy: top of [CHANGELOG.md](CHANGELOG.md).

---

## Key files

```
src/
  index.tsx          # Plugin entry: settings, flat sidebar patch, /servers, navigateToGuild
  sheets.tsx         # Top-docked switcher + dismissThenRun + openSwitcherUi
  command.ts         # /servers logic (testable without Revenge mocks)
  aliases.ts         # Alias normalize / merge (clipboard export-import)
  excludes.ts        # Exclude-rule parse/match
  recents.ts         # Recent-history helpers (plugin-only recording)
  sidebar.ts         # Flat sidebar flatten/sort + cache
  theme.ts           # Settings colors
  utils.ts           # Fuzzy match, sanitization
  revenge-mod.d.ts   # @revenge-mod/* stubs + __QSS_VERSION__
  *.test.ts          # Vitest unit tests
scripts/
  build.mjs          # esbuild → Vendetta IIFE, ES2015, version define
  check-manifest.mjs # manifest + dist hash gate
smoke/               # Tiny plugin to isolate Revenge load failures
dist/index.js        # Committed bundle Revenge evals
manifest.json        # name, version, hash, authors
OPTIONS.md           # Living backlog (A1, B*, C*, D*)
TESTING.md           # Local verify + device checklist
HACKING.md           # Dev setup
HANDOFF.md           # This file
```

---

## Architecture notes (durable)

### Navigation

`navigateToGuild` in `src/index.tsx`:

- Resolve a channel id (last selected / default / first selectable)
- Require `findByProps("openUrl")` (or `openURL` casing)
- `openUrl("https://discord.com/channels/{guildId}/{channelId}")`
- Treat as fire-and-forget; SelectedGuildStore may update async

Prior art: **aliernfrog/JumpTo**, **Stealmoji** (`hideActionSheet` before side effects).

### Switcher UI

`src/sheets.tsx`:

- Prefer top-docked `openAlert` host (`SwitcherTopPanel`) so Android keyboard does not cover the list
- Bottom native `ActionSheet` worked for taps (4.5.8) but failed keyboard UX → reverted for primary path in 4.5.9
- `dismissThenRun`: hide/dismiss first, then run `onPick` → `openUrl`
- Simple action sheet + bot messages as degraded paths

### Slash command

Revenge inverted `shouldHide` historically hid `/servers` — omit that flag and fill command metadata (see CHANGELOG 4.4.5). Replies use `sendBotMessage` when falling back to in-channel lists. Unregister-before-register avoids duplicates.

### Bundle shape

Revenge evals roughly: `vendetta => { return <plugin.js> }` then `ret?.default ?? ret`. Build wraps CJS in `(function(exports){ ...; return exports })({})`. Hermes rejects some modern syntax → **ES2015** target.

---

## Known issues / gotchas

- **Paste GitHub HTML URL** → “Failed to fetch manifest”. Must use `raw.githubusercontent.com/.../main/`.
- **Safe Mode** → plugins do not start.
- **X on toggle** → start failed; try smoke plugin; check Copy debug logs / logcat.
- **Dead taps after jump** → almost always leftover overlay host, not failed `openUrl`. Dismiss harder; avoid full-screen custom scrims.
- **Keyboard covers list** → do not use bottom ActionSheet as the primary switcher host on Android.
- **Flat sidebar silent skip** → SortedGuildStore missing on some builds; log and continue.
- **Clipboard newlines** → Copy debug logs is one line on purpose.
- **Cloud VM has no phone** — never claim device QA passed from CI alone.

---

## Repository & environment

| Field | Value |
|-------|-------|
| GitHub | `github.com/djbclark/RevengeQuickSwitcher` |
| Default branch | `main` |
| Runtime | Discord mobile + Revenge (Hermes) |
| Dev machine | Node 18+ (20+ recommended), npm |
| CI | `.github/workflows/ci.yml` → `npm run verify` |
| Author Discord ID | `689173209785958424` |

Related lab / automation context (separate repo): [stayturgid](https://github.com/djbclark/stayturgid) — fleet ADB/SSH, Handsets, ScreenControlSession. Do not conflate deploy tooling; QSS ships only the plugin + docs.

---

## Changelog (condensed — see CHANGELOG.md)

- **2026-07-10** — Docs: HANDOFF / HACKING / README index (this work).
- **4.5.9** — Top-docked switcher above keyboard; keep dismiss-then-`openUrl`.
- **4.5.8** — Native ActionSheet host (Stealmoji); fixed dead taps.
- **4.5.6–4.5.7** — `openUrl` jump; dismiss-before-navigate.
- **4.5.2–4.5.5** — Overlay/freeze iterations; Copy debug logs; version-stamped ring.
- **4.4.x** — Install URL / IIFE / Hermes enable / slash menu / bot replies.
- **4.1–4.3** — Theme settings, aliases export, recents, excludes, debug toggle.

---

## Appendix — Strategic directions

| Track | Summary | Best when… |
|-------|---------|------------|
| **A — Device QA** | Close **A1** on v4.5.9; capture Copy debug logs | Operator has Revenge phone |
| **B — Switcher polish** | Pins (**C4**), paging UX, settings entry points | A1 green; sheet path stable |
| **C — High-risk Metro** | Channel jump (**C2**), folder-aware sort (**C3**) | Explicit ask; expect client churn |
| **D — Harness** | Metro smoke / optional Handsets-driven QA (**D1**) | Repeatable device regression needed |
| **E — Docs only** | Keep HANDOFF/OPTIONS/TESTING current | After every behavior PR |

**Rejected / avoid:** faux DM or fake server as switcher UI (**C8**); Flux/`selectChannel` jump paths; full-screen touch-blocking scrims; Appium-first automation for this small plugin.
