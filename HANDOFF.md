# RevengeQuickSwitcher — AI Handoff Document

> **Purpose:** This file is a prompt for an AI agent taking over development. Read it fully before doing anything else. It describes what the project does, the current state, the environment, the tooling rules, and what's next.
>
> **Human index:** [README.md](README.md). Full clean-install setup + Hermes/Revenge gotchas: [HACKING.md](HACKING.md). **Open work menu:** [OPTIONS.md](OPTIONS.md). Device checklist: [TESTING.md](TESTING.md). Release notes: [CHANGELOG.md](CHANGELOG.md). **Cursor agent rules:** [.cursor/rules/](.cursor/rules/) (persistent instructions for AI handoffs). Git history has the detailed narrative of every change; this file is the condensed durable record.

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

**As of 2026-07-10 (evening).** Released on `main`: **v4.5.9**. **Active QA device:** **s24** (Galaxy S24, USB `RFCX219CHKA`). **QSS plugin:** operator installed on s24 from raw URL (2026-07-10). p7a artifacts archived under `artifacts/qss-qa/p7a-final-archive/` — do not use p7a unless operator asks.

| Field | Value |
|-------|-------|
| Package / manifest version | `4.5.9` |
| Display name | Quick Server Switcher |
| Bundle | Vendetta IIFE, ES2015 target, `__QSS_VERSION__` injected |
| Unit tests | **96** Vitest tests (`make verify`) |
| Open human gate | **A1** — device QA on Revenge Android (s24) |
| D1 harness | `scripts/device_qa_qss.py` + `make qa` — **implemented, uncommitted** on `main` |
| Latest s24 QA | Partial — nav to `#dc-general` OK; switcher/jump **not yet green** (see below) |

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

**Next work:** [OPTIONS.md](OPTIONS.md) — **open work only**. Primary gate: **A1** full pass on s24 with QSS installed. Harness: **D1** (`device_qa_qss.py` + stayturgid/Handsets). **Do not** run ad-hoc `python -c` probes that type into composers — use `make qa` only (see Safety below).

---

## Device QA handoff (s24, 2026-07-10)

### What passed

| Step | Status |
|------|--------|
| `make verify` / CI | Green (96 tests) |
| Revenge package `app.revenge` on s24 | OK |
| Local UI-TARS (`http://127.0.0.1:8081`) | OK |
| Nav to test guild **dcs** → `#dc-general` | Usually OK (VLM `safe_test_channel` passes) |
| **QSS plugin installed** | Operator confirmed + installed from raw URL |

### What failed / flaky (last runs)

| Issue | Cause | Harness note |
|-------|-------|--------------|
| `switcher_open_failed` | Could not reach profile → Settings → Plugins before plugin install | Should improve now that QSS is installed |
| `quest_bar_blocks_profile` | Discord Quest Bar + Wordle pill over profile chip | Dismiss on device or improve `dismiss_quest_overlay()` |
| `safe_guild_nav_failed` (intermittent) | Sidebar guild tap: **coord tap** on icon column does not select guild; **`tap_text("Danny Clark's server")` works** | `tap_sidebar_guild()` already prefers `tap_text` — verify on next run |
| Emoji keyboard obstruction | Prior coord taps hit emoji toggle | `dismiss_emoji_keyboard()` added before profile |
| Accidental chat/DM text | `handsets type/fill` with `QSS_VLM=0` on DM threads; slash `fill "/"` + `tap_text "/ servers"` → `//servers` | **Fixed** — see Safety |

Artifacts: `~/.local/share/RevengeQuickSwitcher/artifacts/qss-qa/2026-07-10/s24/`

### Safety policy (mandatory for agents)

**Priority #1:** never send chat/DM text to real users or non-test channels. Speed does not matter.

| Control | Env / code |
|---------|------------|
| Safe mode (default on) | `QSS_SAFE_MODE=1` — all typing requires VLM `before_type` + surface check |
| Post-type verify | Screenshot + VLM `after_type` after every `fill`/`type` |
| DM block | `ui_dm_thread()` — abort if composer shows `Message @user` |
| Allowlisted typing only | Switcher **Filter servers**, plugin install URL, safe `#channel` slash (only if `QSS_ALLOW_SLASH=1`) |
| Default switcher path | Settings → Plugins → **Open switcher** (slash disabled by default) |
| No debug probes | Do **not** run one-off scripts that `type`/`fill`/tap composers on live account |

Full runbook: [VLM.md](VLM.md) (Safety-first automation section).

### Incidents (learn from these)

1. **Stray `,` DM to kuriboh** — device on DM thread; coord/wordle probes typed into composer with VLM off.
2. **`//servers` in channel** — slash path typed `/` then `tap_text("/ servers")` doubled the slash; old path could tap Send.

### Device cleanup (end of session)

After QA, restore s24 without UI automation:

```bash
# Release lease
DEVICE_SCREEN_CONTROL_PROJECT=RevengeQuickSwitcher \
  python3 ~/stayturgid/control/bin/screen_lease.py release s24

# Inversion off + auto-rotate back (adb only — no Handsets)
serial=RFCX219CHKA
adb -s $serial shell settings put secure accessibility_display_inversion_enabled 0
adb -s $serial shell settings put system accelerometer_rotation 1
adb -s $serial shell settings put global window_animation_scale 1
adb -s $serial shell settings put global transition_animation_scale 1
adb -s $serial shell settings put global animator_duration_scale 1
```

Use `restore_screen=False` during QA so session exit does not land on Termux/other prior app.

### Commands for next agent (full A1 pass)

```bash
curl -sf http://127.0.0.1:8081/health   # UI-TARS up
DEVICE_SCREEN_CONTROL_PROJECT=RevengeQuickSwitcher \
  python3 ~/stayturgid/control/bin/screen_lease.py release s24

QSS_VLM=1 QSS_SAFE_MODE=1 QSS_VLM_CLOUD=google,anthropic \
  make qa QSS_DEVICE=s24 QSS_GUILD=dcs
```

If quest bar still blocks profile: operator dismisses Quest Bar / Wordle pill once on device, then re-run.

**Uncommitted harness work** (2026-07-10): `scripts/device_qa_qss.py`, `VLM.md`, `Makefile`, `HANDOFF.md`, `scripts/ui_tars_local.py`, `scripts/vlm_cloud.py`, `.cursor/rules/vlm-docs.mdc` — not committed; operator has not requested commit.

---

**Verify / ship:**

```bash
make install   # once
make verify    # typecheck + 96 tests + build + manifest hash
```

After source edits: commit updated `dist/index.js` + `manifest.json` `hash` (verify rewrites hash). Bump `package.json` + `manifest.json` `version` together; update `CHANGELOG.md`.

---

## Agent conventions

### Cursor rules (`.cursor/rules/`)

This repo ships **Cursor project rules** under [`.cursor/rules/`](.cursor/rules/) — `.mdc` files with YAML frontmatter that Cursor injects into agent sessions (some `alwaysApply: true`, others scoped by glob).

**On handoff, read these before improvising:**

| Rule file | Scope | Purpose |
|-----------|-------|---------|
| [`vlm-docs.mdc`](.cursor/rules/vlm-docs.mdc) | always | After QA/VLM discoveries, update [`VLM.md`](VLM.md) in the same session |

Add new rules here when standing conventions emerge (device QA, commit style, doc maintenance). Rules complement this file and [`VLM.md`](VLM.md); they are not a substitute for reading HANDOFF cold-start state.

### Device preference (when operator has stayturgid fleet)

Same order as stayturgid when a phone must be used and the choice does not matter:

1. **s24** (Galaxy S24) — preferred
2. **hd8** (Kindle Fire HD 8) — second
3. **p7a** (Pixel 7a) — third (daily driver; avoid unless needed)

Announce before live UI work when someone may be on the device:

`🚨📱🚨 USING — s24 — Revenge QA — ~N min`

When done: `✅📱✅ FREE — s24 ✅📱✅`

Mac→Android UI automation lives in **stayturgid** (`control/lib/ui_driver.py`, `control/bin/gui_audit.py`). This plugin ships **`scripts/device_qa_qss.py`** + `make qa` (**D1** Phase 1). Prefer Vitest here; device QA uses Handsets + ScreenControlSession, not Appium-first.

**Cloud vs Desktop:** cloud agents cannot reach the phone over ADB. Run **D1** from **Cursor Desktop on the Mac** with stayturgid + Handsets + ADB.

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
  device_qa_qss.py   # D1 device QA harness (Handsets + VLM gates)
  ui_tars_local.py   # Local UI-TARS vision gates
  vlm_cloud.py       # Optional cloud VLM fallback
smoke/               # Tiny plugin to isolate Revenge load failures
dist/index.js        # Committed bundle Revenge evals
manifest.json        # name, version, hash, authors
OPTIONS.md           # Open work menu (A1, C2–C4, D1, …; closed at bottom)
TESTING.md           # Local verify + device checklist
HACKING.md           # Dev setup
HANDOFF.md           # This file
.cursor/rules/       # Cursor agent rules (.mdc) — read on AI handoff
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

- **2026-07-10** — D1 harness on s24; QSS plugin installed; safety gates (`QSS_SAFE_MODE`, `after_type`); quest bar still blocks profile on some runs; uncommitted harness docs/code.
- **2026-07-10** — Docs: HANDOFF / HACKING / README index; VLM.md runbook.
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
| **D — Harness** | Unattended `device_qa_qss.py` + Handsets (**D1** Phases 0–3) | Repeatable device regression; Desktop Mac + ADB |
| **E — Docs only** | Keep HANDOFF/OPTIONS/TESTING current | After every behavior PR |

**Rejected / avoid:** faux DM or fake server as switcher UI (**C8**); Flux/`selectChannel` jump paths; full-screen touch-blocking scrims; Appium-first automation for this small plugin.
