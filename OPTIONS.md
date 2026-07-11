# OPTIONS — open work

> **For agents:** When the operator asks for **options** or **next steps**, read this
> file, present the open items **with descriptions and risk**, do any requested work,
> then **replace** this list (drop completed items; keep IDs stable). **Commit and
> push** in the same turn.
>
> Session context: [HANDOFF.md](HANDOFF.md). Dev setup: [HACKING.md](HACKING.md).
> Device checklist: [TESTING.md](TESTING.md). Release notes: [CHANGELOG.md](CHANGELOG.md).
> Strategic directions: [HANDOFF.md appendix](HANDOFF.md#appendix--strategic-directions).

**Plugin snapshot (2026-07-11):** Released on `main` as **v4.5.9** — top-docked
switcher, dismiss-then-`openUrl` jump, Copy debug logs. Unit gate: `make verify`
(96 tests). Cloud agents cannot reach the phone; **A1** is the human/device gate.

**Risk scale:** **Low** = mostly our code / storage / docs · **Medium** = Metro/UI
discovery with graceful fallbacks · **High** = deep Discord internals; easy to
break on client updates · **Latent** = only act if a symptom returns.

**Suggested agent order:** close or drive **A1** (device QA) before new features;
prefer **C4** (pins) over **C2**/**C3** (high Metro surface). **D1** (pytest +
Handsets harness) can run in parallel with **A1** but should assert the same
checklist. Do not reintroduce Flux/`selectChannel` jump paths or full-screen
scrims (see HANDOFF).

**How to reference:** say **A1**, **C4**, **D1**, etc. Keep IDs stable forever;
when an item ships, move it to **Closed** (do not renumber).

---

## Pick a track

| Track | Focus | Open IDs | Typical risk |
|-------|-------|----------|--------------|
| **A — Device QA** | Revenge client checklist | A1 | Low (process); blocks confidence in sheet/nav |
| **B — Switcher polish** | Pins and list UX on stable sheet | C4 | Low–Medium |
| **C — High-risk Metro** | Channels / folder-aware sidebar | C2, C3 | Medium–High |
| **D — Engineering** | Device QA harness (pytest + Handsets) + Metro smoke | D1 (blocked on leave_voice_channel) | Low–Medium |
| **E — Latent follow-ups** | Only if a symptom returns | C1b | Latent / Medium–High |

---

### Track A — Device QA

#### A1 — Device QA (human + agent assist) · Risk: **Low** (process)

Requires a Revenge Discord client and the checklist in [TESTING.md](TESTING.md).

**Retest on v4.5.9:**

1. Top-docked switcher stays **above** the Android keyboard while filtering.
2. After a server tap, jump lands and Discord taps still work (no dead UI).
3. Copy debug logs show `v4.5.9` and `openUrl` (not mixed older versions).
4. Close dismisses the panel; bot-message fallback still OK if sheet APIs missing.

Close **A1** when the operator signs off (or **D1** pytest+Handsets harness
covers the same assertions). Agents: prepare checklists / interpret log pastes;
do not claim pass from CI alone.

---

### Track B — Switcher polish

#### C4 — Favorites / pinned servers (agent) · Risk: **Low** (list-only) / **Medium** (flat sidebar)

User-chosen servers that always float to the top of `/servers` (and optionally
the flat sidebar), independent of A–Z order or recents.

**User-facing shape:**

- Settings: ordered pins by name/id, reorder, clear
- Switcher / list: pinned block first, then the rest A–Z
- Optional later: `/servers query:p1`-style shortcodes; export with aliases

**How:** store ordered guild IDs in plugin storage; partition pinned vs
unpinned when building the list; resolve names via GuildStore; drop/flag stale
IDs after leaving a server.

**Why:** aliases speed *search*; pins change *priority*. Complements recents
(**C1** / B8) without Metro guild-select hooks.

**Depends on:** sheet path stable (**A1** preferred first). Pairs with excludes
and alias export.

---

### Track C — High-risk Metro (explicit ask only)

#### C2 — Channel search / jump (agent) · Risk: **High**

Search and jump to channels, not only servers. Large Metro surface
(permissions, channel stores, navigation); breaks often across Discord
versions. May deserve a **separate plugin**. Do not start unless the operator
explicitly picks this.

#### C3 — Folder-aware (non-flat) sort (agent) · Risk: **Medium**

Keep Discord folders, but sort inside them and/or sort folder nodes — modes
beyond today's all-or-nothing flat list. Folder node shapes vary; wrong
assumptions scramble the sidebar. Needs defensive parsing + device tests
(**A1**-style). Natural Flat Sidebar extension; still explicit-ask preferred.

---

### Track D — Engineering

#### D1 — Unattended device QA harness (stayturgid + Handsets) · Risk: **Low–Medium**

Replace "human taps → pastes Copy debug logs → agent guesses" with a Mac-side
script that arms a stayturgid UI session, drives Discord through the failing
flow, captures screenshots + hierarchy + plugin debug ring, and emits a
machine-readable report (`report.json` + PNGs) the agent can act on.

Vitest (`make test`, 96 tests) stays the default local gate. **D1** adds an
optional Mac→Android tier. Borrow patterns from
[stayturgid](https://github.com/djbclark/stayturgid) — **not** the full
fleet/Ansible stack. Do **not** Appium-first; never run u2 + Handsets together.

**Core rule (from stayturgid research):** hold **one** `ScreenControlSession`
for the whole flow; screenshot every step; prefer text/id selectors over
coordinates; assert durable state (not just toasts).

**Stayturgid pieces to reuse:**

| Piece | Role for QSS |
|-------|----------------|
| `control/lib/ui_driver.py` | Handsets primary — `tap_text` / `tap_id` |
| Raw dump + tap | Fallback when Handsets missing |
| `ScreenControlSession` | Inversion = "agent owns glass"; gate input |
| `STAYTURGID_PRESENCE_QUIET=1` | No torch/vibrate/dialogs for unattended runs |
| `mac/gui_audit.py` | Template: open app → navigate → screenshot → assert → soft-fail `issues[]` |
| Wireless ADB + stayturgid reconnect | Keep `ip:5555` alive for Mac agents |

Reference docs in stayturgid: `docs/research/mac-android-ui-automation.md`,
`docs/research/ui-automation.md`.

---

**Phase 0 — Access (one-time; pick per environment)**

| Option | How | Best for |
|--------|-----|----------|
| **A. Cursor Desktop on Mac** (recommended) | Both `stayturgid` + QSS workspaces; wireless ADB; Handsets at `~/.handsets/` | Live UI loops |
| **B. Clone stayturgid beside QSS** | Submodule or sparse checkout of `control/lib` + `docs/research` | Doc-aware cloud planning |
| **C. Paste doc into QSS** | Copy `mac-android-ui-automation.md` under `docs/` | Lightweight cloud context |
| **D. Expose ADB to cloud** | Tunnel egress to phone | Rare; usually avoid |

Cloud Cursor **cannot** see Mac disk or phone without a bridge. Agents need
**ADB reachability + UI stack** — not Discord credentials (device already
logged in). Preferred device: **s24** (see HANDOFF fleet order).

---

**Phase 1 — Harness (ship first)**

**Current state (2026-07-11):** `scripts/device_qa_qss.py` with 3-tier vision
(OCR → Cloud VLM → Local UI-TARS), screen lease force-steal, screenshot
validation, and improved navigation. Most components tested individually.

**BLOCKER: `leave_voice_channel` hangs on voice overlay.** When the device
is left in a voice channel (Stream Room), `leave_voice_channel()` calls
`hs.tap_text("Show Chat")` / `hs.tap_desc("Disconnect")` which time out
because Handsets can't find those targets in the full-screen voice overlay UI.
The function never returns, the harness hangs until the 600s timeout.

**To unblock:**

| Approach | Detail |
|----------|--------|
| **A. Debug Handsets voice UI** | Check what `hs.ui()` returns during voice overlay — maybe the dump doesn't include voice panel elements. Use raw dump + `adb exec-out` as fallback. |
| **B. Raw ADB tap fallback** | Add a branch in `leave_voice_channel` that tries `session.shell("input", "tap", x, y)` with known coordinates for "Disconnect" button when Handsets taps fail. |
| **C. Kill voice channel via ADB** | Use `am broadcast` or `input keyevent` to navigate back / disconnect from voice without Handsets. e.g. `session.shell("input", "keyevent", "KEYCODE_BACK")` multiple times. |
| **D. Skip voice channel** | Add a config to rejoin a text channel before starting QA, or `am start` with an intent that opens a specific text channel instead of reconnecting to voice. |

**D1 lessons from manual S24 navigation (2026-07-11):**

| Lesson | Detail |
|--------|--------|
| **Use `hs swipe` for scrolling** | `adb shell input swipe` often overscrolls or has zero effect. `hs swipe down` does a single reliable page-down. |
| **Check element bounds before tapping** | Handsets may report elements with y > screen height (2340 on S24). Tapping off-screen coordinates silently misses. Always verify `y < screen_h` before using the coordinate. |
| **Tap "Revenge" row first** | The main settings page has `Plugins` as a sibling of `Revenge, (3cfc115-main)` at the same level. Tapping `Plugins` directly navigates to the plugin list — but only if it's fully on-screen (y < 2340). If off-screen, `hs.tap_text("Plugins")` returns success but nothing happens. |
| **Scroll half-screen, not full-screen** | Revenge/Plugins rows sit just below "Chat" (~3361). A full `hs swipe down` overshoots to y=-339. A short bottom-to-middle swipe (540,2000 → 540,1700, 200ms) lands them at y~1797, safely within bounds. |
| **Settings "Back" is at top-left** | After entering a sub-page, the back button is at (84,176) via content-desc "Back". |
| **Voice auto-reconnect on relaunch** | `force-stop` + `am start` reconnects to the last voice channel. Must `hs tap "Disconnect"` or tap the red hang-up at (944,2196) first, then swipe back once if Soundboard opened accidentally. Two KEYCODE_BACK presses may exit the app entirely. |
| **Screenshot corruption** | `adb exec-out screencap -p` can return corrupt/empty data during screen transitions. Fixed with PNG header validation + 3 retries in `shot()`. |
| **OCR is free, VLM is slow** | Tesseract OCR gate (`scripts/ocr_gate.py`) runs in <0.5s and catches ~60-70% of checks. Cloud VLM takes 2-8s per call. Always prefer OCR path. |

**OCR gate check patterns (scripts/ocr_gate.py):**

| Check | Matches |
|-------|---------|
| `discord_home` | Danny, Online, Browse Channels, message #, Quick Server Switcher, Filter servers |
| `discord_not_launcher` | Rejects when phone dialer, camera, calculator, or launcher shows |
| `safe_test_channel` | #dc-general, #dc-games, #ogden, #college, member list |
| `switcher_open` | Filter servers, Quick Server Switcher, Close, Guild List |
| `switcher_closed` | Rejects when switcher still present |

Add `scripts/device_qa_qss.py` (or `stayturgid/control/bin/gui_audit.py`) mirroring
`gui_audit.py`:

```text
STAYTURGID_PRESENCE_QUIET=1
resolve_adb(s24) → connect → ScreenControlSession
try_handsets(serial)
  am start Discord
  wait for chat / slash
  invoke /servers (slash picker or settings → Open switcher)
  screenshot 01_sheet.png + dump hierarchy
  assert: switcher visible; panel near TOP (y bounds)
  tap known server name
  wait 1–2s
  screenshot 02_after_jump.png
  assert: taps still work (composer / channel list / sidebar)
  plugin settings → Copy debug logs → read clipboard via adb
  write report.json: { version, openUrl, afterGuild, issues[] }
HOME / restore foreground
```

Optional pytest wrapper: `tests/device/` + `conftest.py` (skip when no device /
no `hs`). Entry: `make qa` or `pytest tests/device`.

**Automated checks that would have caught v4.5.x bugs:**

| Bug | Check |
|-----|-------|
| Freeze / dead taps | After jump, `hs.tap_text` on known control fails → `issues=dead_taps` |
| Keyboard covers sheet | Switcher bounds bottom > keyboard top → `issues=keyboard_cover` |
| Wrong nav API | Clipboard/logcat: no `selectChannel` / `CHANNEL_SELECT`; must see `openUrl` |
| Stuck overlay | After Close/jump, switcher title still in hierarchy → `issues=overlay_stuck` |
| Version confusion | Debug dump contains `vX.Y.Z` matching `manifest.json` |

Also cover **A1** checklist: top-dock, Filter above keyboard, Close dismisses.

---

**Phase 2 — Agent workflow (minimal human)**

1. Agent bumps plugin → `make verify` → push (as now)
2. Install/update on device via raw GitHub URL refetch **or** opt-in `adb` sideload
3. Run `device_qa_qss.py`; on failure, read `report.json` + PNGs
4. Agent patches and re-runs until green or hits human gate (login, captcha, OEM perm)

---

**Phase 3 — Hardening**

- Content-desc / text ("Close", "Filter servers", server names) over coords
- Discord package/activity discovery in one helper (`pm path` / `dumpsys`)
- Artifacts under `~/.local/share/RevengeQuickSwitcher/artifacts/qss-qa/<date>/`
- Optional launchd after plugin tag; default agent-triggered only
- Layer 1 (independent): Metro prop docs + optional runtime self-check when debug on

**D1 non-goals:** full Discord E2E; emulator-only QA; cloud driving phone
without Mac ADB; Ansible/Termux deploy; CI green without reachable device.

**Safety (s24):** Only automate when a **safe channel** is active:
`#dc-general`, `#dc-games` (preferred), `#ogden`, `#college`.
Sidebar icons DCs / LL/DC are hints; channel list is ground truth. No slash
in-channel. Default device: **s24**. `make qa QSS_GUILD=dcs`

**Vision gates (3-tier):**

1. **OCR gate** (Tesseract) — free, <0.5s, runs before every VLM call. `pytesseract` + PIL.
2. **Cloud VLM** (Anthropic Haiku 4.5 → Gemini 3.5 Flash) — paid, 2-8s. API keys in `~/.config/RevengeQuickSwitcher/secrets.env`. Set `QSS_VLM_CLOUD=anthropic,google`.
3. **Local UI-TARS** — fallback when cloud unconfigured. `make vlm-install` once, `make vlm-server`.

**Uncommitted changes (2026-07-11):**

| File | Change |
|------|--------|
| `scripts/device_qa_qss.py` | OCR gate, cloud VLM primary, screenshot validation, voice markers, scroll/nav/lease fixes |
| `scripts/ocr_gate.py` | New — Tesseract OCR with 12 keyword check patterns |
| `scripts/vlm_cloud.py` | Model updated to `gemini-3.5-flash` |
| `OPTIONS.md` | This update |

---

### Track E — Latent follow-ups (symptom-driven)

#### C1b — Auto-track recents via guild-select hooks (agent) · Risk: **Latent / Medium–High**

Shipped recents (**C1** / B8) only record when *this* plugin navigates. A
follow-up could hook Discord "current guild" / select modules for automatic
history. **Do not start** without a clear product ask — high churn, easy to
freeze (see v4.5.x saga in HANDOFF). Trigger: operator wants sidebar-driven
recents and accepts Metro risk.

---

**Non-goals / do-not-touch:**

- Faux DM or fake Discord server as the switcher UI (rejected in C8)
- Jump via loose `selectChannel`, Flux `CHANNEL_SELECT` / `GUILD_SELECT`, or
  `selectGuild` as primary path (use dismiss-then-`openUrl`)
- Full-screen touch scrims / nested RN `Modal` hosts that outlive the sheet
- Bottom `ActionSheet` as the **primary** searchable switcher on Android
  (keyboard covers it; top-dock is intentional)
- Renumbering shipped IDs; editing git history to "clean" Done items

---

**Closed (2026-07-10):** Docs HANDOFF / HACKING / README index (PR docs branch).

**Closed (v4.5.9 / B17–B18, C5, C8):** Top-docked switcher + dismiss-then-`openUrl`;
freeze/dead-tap saga; tappable disambiguation; dedicated sheet UI (not faux DM).

**Closed (v4.5.2–4.5.8):** Overlay dismiss iterations; Copy debug logs;
version-stamped ring; JumpTo `openUrl`; ActionSheet host experiment.

**Closed (v4.4.x / B9–B16, C7):** Excludes; install URL / IIFE / Hermes enable;
slash menu `shouldHide`; `sendBotMessage`; query jump replies.

**Closed (v4.1–4.3 / B1–B8, C1, C6, D2–D3):** Author id; pick-list; theme
settings; debug toggle; releases/changelog/semver; alias export-import;
low-risk recents.
