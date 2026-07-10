# UI-TARS-1.5-7B — local vision gates for Android screenshots

This project uses **UI-TARS-1.5-7B** (ByteDance’s GUI-focused vision-language model) as a **local screenshot verifier** during device QA. It does not drive the phone autonomously. Instead it answers yes/no questions about PNGs captured from ADB (`adb exec-out screencap`) *before* the harness types or taps — for example: “Are we in Discord, not Niagara Launcher?” and “Are we on `#dc-general`?”

**Optional cloud vision** (OpenAI / Anthropic / Google) supplements local UI-TARS when the server is down, a gate is ambiguous, or you need a second opinion on a stuck navigation step. See [Hybrid local + cloud](#hybrid-local--cloud-best-practices-july-2026).

Related: [PATHS.md](PATHS.md) (directories, launchctl commands, AI ops) · [TESTING.md](TESTING.md) · [OPTIONS.md](OPTIONS.md) (**D1** harness) · `scripts/ui_tars_local.py` · `scripts/vlm_cloud.py` · `scripts/device_qa_qss.py`

> **Living doc:** After any interesting QA/VLM discovery (new blocker, model quirk, provider pick, harness pitfall), **update this file in the same session** before moving on. Agents working on device QA or vision gates should treat `VLM.md` as the canonical runbook.

---

## When to use it

| Good fit | Poor fit |
|----------|----------|
| Gate checks before typing in a filter/composer | Full autonomous “agent” that plans every tap |
| Confirm safe test channel / switcher open / not launcher | Pixel-perfect coordinate grounding every frame |
| One screenshot → one JSON verdict (~10–90s on Apple Silicon) | Sub-second real-time video |

**Design principle:** use UI-TARS for **high-stakes verification**, not for every navigation step. Handsets + a11y text selectors remain primary; VLM is the safety net.

### Safety-first automation (July 2026)

**Priority #1:** never send chat/DM text to real users or non-test channels. Speed is irrelevant.

| Layer | Rule |
|-------|------|
| **Allowlisted surfaces** | Typing only on: switcher **Filter servers** (switcher open), plugin **Install URL** dialog, or safe `#channel` slash (if `QSS_ALLOW_SLASH=1`). |
| **`QSS_SAFE_MODE=1` (default)** | All `handsets type/fill` blocked unless VLM `before_type` passes **and** a11y proves the target surface. Blocks ad-hoc `QSS_VLM=0` debug runs that typed into DM composers. |
| **DM detection** | `ui_dm_thread()` — composer shows `Message @user` not `Message #channel`. Harness aborts typing immediately. |
| **No blind bottom taps** | Coord taps in the bottom 5% (Wordle pill, quest bar) only after confirming not on a DM thread. |
| **Settings-only switcher** | Default path: profile → User Settings → Plugins → **Open switcher**. Slash posts to chat on misfire. |
| **Probe scripts** | Never run one-off `python -c` probes that `type`, `fill`, or tap the composer region on a live account. |

**Incident (s24):** device on **kuriboh DM**; coord probes + `handsets type` with `QSS_VLM=0` typed into the DM composer → stray `,` sent. Fix: `typing_safety_gate()` + navigate to `#dc-general` before typing.

**Post-type verify:** every `handsets fill/type` saves `after_type_*.png` and runs VLM `after_type` gate. Slash path types `/servers` once (never `fill "/"` + `tap_text "/ servers"` which produced `//servers`). Slash never taps Send.

**Timing:** UI navigation uses short `wait_until` polls (`UI_POLL` ≈ 0.25s, caps 6–18s). **Local VLM gates are not capped** — budget `QSS_VLM_TIMEOUT` (default 900s) per image; expect 10–90s on Apple Silicon.

---

## Requirements

| Resource | Notes |
|----------|-------|
| **macOS** (recommended) | Apple Silicon uses Metal via `llama-server -ngl 99` |
| **RAM** | ~6 GB for Q4_K_M weights + mmproj; **16 GB** machine minimum; close heavy apps |
| **Disk** | ~6 GB under `~/.local/share/ui-tars/models/1.5-7b/` ([PATHS.md](PATHS.md)) |
| **Homebrew** | `llama.cpp` (required), `ollama` (installed for convenience; server uses llama.cpp) |
| **ADB** | Phone reachable; screenshots via `adb exec-out screencap -p` |

Pure CPU (`QSS_VLM_NGL=0`) works but is **very slow** (minutes per image) and may OOM on 16 GB hosts. Prefer Metal on Mac.

---

## Quick start

### 1. One-time install

```bash
scripts/vlm_install.sh
```

- `brew install llama.cpp` (and `ollama` if missing)
- Downloads GGUF + mmproj to `~/.local/share/ui-tars/models/1.5-7b/` (~5.9 GB)

### 2. Start the server (macOS — launchd)

**Persistent (login + auto-restart):** see [PATHS.md](PATHS.md) for standard `launchctl` commands.

```bash
scripts/vlm_service.sh install    # once: migrate old paths, write plist, bootstrap
curl -sf http://127.0.0.1:8081/health
launchctl print "gui/$(id -u)/homebrew.mxcl.ui-tars"
```

| Item | Path / value |
|------|----------------|
| Service label | `homebrew.mxcl.ui-tars` |
| Plist | `~/Library/LaunchAgents/homebrew.mxcl.ui-tars.plist` |
| Log | `~/Library/Logs/ui-tars/server.log` |
| Models | `~/.local/share/ui-tars/models/1.5-7b/` |

**Start / stop / restart (do not use `make` in automation):**

```bash
launchctl kickstart -k "gui/$(id -u)/homebrew.mxcl.ui-tars"   # restart
launchctl bootout "gui/$(id -u)" ~/Library/LaunchAgents/homebrew.mxcl.ui-tars.plist  # stop
```

Model load takes **20–60 s** after bootstrap.

**One-shot (no launchd):** `scripts/ui_tars_server.sh`

Verify: `python3 scripts/vlm_check.py`

### 3. Run device QA with vision gates

```bash
curl -sf http://127.0.0.1:8081/health
make qa    # QSS_VLM=1 by default
```

Artifacts: `~/.local/share/RevengeQuickSwitcher/artifacts/qss-qa/<YYYY-MM-DD>/<host>/vlm/`

---

## Operations guide (for humans and other AIs)

**Canonical reference:** [PATHS.md](PATHS.md) — directory layout, `launchctl` start/stop, recovery checklist.

```bash
curl -sf http://127.0.0.1:8081/health && echo OK
launchctl print "gui/$(id -u)/homebrew.mxcl.ui-tars"
```

---

## How Android screenshots reach the model

```
p7a (Revenge)                    Mac
─────────────                    ───
ScreenControlSession  ──►  adb exec-out screencap -p  ──►  PNG on disk
Handsets UI dump      ──►  (parallel, not sent to VLM)
                              │
                              ▼
                         sips -Z 720  (downscale, macOS)
                              │
                              ▼
                    POST /v1/chat/completions
                    (OpenAI-compatible, llama-server)
                              │
                              ▼
                         JSON { ok, confidence, notes }
```

Capture helper in the harness:

```python
# scripts/device_qa_qss.py
adb -s <serial> exec-out screencap -p > screenshot.png
```

Downscale before inference (`scripts/ui_tars_local.py`):

```bash
sips -Z 720 screenshot.png --out screenshot.vlm.png
```

Full-resolution phone PNGs (1080×2400+) are slow and memory-heavy for a 7B VLM on CPU/Metal. Default max width **720** is a good balance.

---

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `QSS_VLM` | `1` in `make qa` | Enable vision gates (`0` to disable) |
| `QSS_VLM_STRICT` | `1` | Block QA actions when server down or check fails |
| `QSS_VLM_PORT` | `8081` | `llama-server` listen port |
| `QSS_VLM_TIMEOUT` | `900` | Seconds per inference (CPU hosts: raise this) |
| `QSS_VLM_MAX_WIDTH` | `720` | Downscale width before base64 encode |
| `QSS_VLM_NGL` | `99` on Darwin, `0` elsewhere | Metal GPU layers |
| `QSS_VLM_CTX` | `2048` | Context size (lower = less RAM) |
| `QSS_VLM_THREADS` | `4` | CPU threads for llama-server |
| `QSS_VLM_IMAGE_MIN` | `256` | Min image tokens per screenshot |
| `QSS_VLM_IMAGE_MAX` | `512` | Max image tokens per screenshot |
| `UI_TARS_MODEL_DIR` | `~/.local/share/ui-tars/models/1.5-7b` | Weight path |
| `UI_TARS_PORT` | `8081` | `llama-server` listen port (`QSS_VLM_PORT` alias) |
| `QSS_DATA_HOME` | `~/.local/share/RevengeQuickSwitcher` | QA artifacts + logs |
| `QSS_DEBUG_DIR` | (off) | Save before/after profile UI dumps + PNGs when debugging settings path |
| `STAYTURGID_PRESENCE_QUIET` | `1` in `make qa` | Skip torch/consent; keep inversion + lease |
| `DEVICE_SCREEN_CONTROL_PROJECT` | `RevengeQuickSwitcher` | DSCL v1 project slug (set by `make qa`) |

Server log: `~/Library/Logs/ui-tars/server.log` ([PATHS.md](PATHS.md))

---

## Built-in check types

Defined in `scripts/ui_tars_local.py` → `CHECK_PROMPTS`. Each check expects **JSON only** in the model reply.

| Check | Use on Android screenshot |
|-------|---------------------------|
| `discord_not_launcher` | After launch / foreground guard — not Niagara, not home screen |
| `safe_test_channel` | Channel header or `Message #…` shows `#dc-general`, `#dc-games`, `#ogden`, or `#college` |
| `server_sidebar_visible` | Left column of round server icons visible |
| `switcher_open` | Top-docked switcher: “Filter servers”, “Close”, jump list |
| `settings_plugins_path` | User Settings with Revenge → plain “Plugins” row (not About, not Log Out) |
| `profile_chip` | Profile chip / settings drawer reachable; obstruction id (`quest`, `voice`, `emoji`, …) |
| `before_type` | About to type in filter/composer — Discord focused, not public chat on wrong server |

Harness call sites (`device_qa_qss.py`):

1. After Discord home screenshot → `discord_not_launcher`
2. After safe guild navigation → `safe_test_channel`
3. After switcher opens → `switcher_open`
4. **Before every `handsets_fill` / type into filter** → `before_type`
5. After server jump → `safe_test_channel` again (`post_jump_channel`)
6. On `switcher_open_failed` → `profile_chip` (obstruction diagnosis on `01_profile_fail_vlm.png`)

Failed checks add issues like `vlm_safe_test_channel_failed` and, with strict mode, **stop typing**.

---

## Best practices for Android screenshots

### Capture timing

- Wait for UI to settle after taps (**0.8–1.5 s** minimum; switcher filter ~0.9 s after typing).
- Capture **after** animations settle, not mid-transition.
- For “before type” gates, screenshot **immediately before** `handsets fill` / `type`, not after.

### Image quality

- Use **PNG** from `screencap -p` (lossless).
- **Downscale** to 720px width unless you have a reason not to (accuracy vs speed).
- Avoid cropping unless testing a specific region (e.g. sidebar-only); full screen gives channel header context.

### Prompt design

- Ask for **structured JSON** with `ok`, `confidence`, and `notes`.
- Name **safe allowlists** explicitly (channel names, UI strings).
- Name **forbidden** patterns (launcher, `#general`, Bee, etc.).
- Keep prompts **single-purpose** — one screenshot, one question.
- Set `temperature: 0.1` and `max_tokens: 256` (already in `ask_image`).

### Safety workflow (this repo)

1. **Channel name is ground truth** — not server title, not sidebar icon label.
2. Never slash-command in channels during QA (`QSS_ALLOW_SLASH` off by default).
3. VLM confirms safe channel **before** typing in switcher filter.
4. VLM confirms safe channel **after** server jump; harness aborts on `#life`, plugin settings, etc.
5. Jump rows must match `Jump to <allowlisted server>` — forbidden guild markers rejected in code.

### Performance

| Platform | Typical latency per gate |
|----------|-------------------------|
| Apple Silicon + Metal (`-ngl 99`) | ~10–20 s |
| CPU only (`-ngl 0`) | Minutes; often impractical on 16 GB |

A full `make qa` run with VLM may add **~1–3 minutes** of vision time on top of navigation.

### Strict vs permissive mode

```bash
# Block when VLM unavailable (recommended for unattended QA)
QSS_VLM_STRICT=1 make qa

# Skip gates if server down (Handsets-only fallback)
QSS_VLM=0 make qa
```

---

## Programmatic usage

### Smoke test

```bash
python3 scripts/vlm_check.py
```

### Python API

```python
from pathlib import Path
import sys
sys.path.insert(0, "scripts")
import ui_tars_local as vlm

gate = vlm.VlmGate(autostart=True)  # starts server if needed
ok, detail = gate.verify(Path("/path/to/screenshot.png"), "before_type")
print(detail["parsed"], detail["elapsed_s"])
```

### Raw HTTP (OpenAI-compatible)

```bash
# Model id from GET http://127.0.0.1:8081/v1/models
curl -s http://127.0.0.1:8081/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "<model-id-from-/v1/models>",
    "messages": [{
      "role": "user",
      "content": [
        {"type": "text", "text": "Describe this Android screen. Reply JSON: {\"ok\":true,\"notes\":\"...\"}"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
      ]
    }],
    "max_tokens": 256,
    "temperature": 0.1
  }'
```

Encode a local PNG:

```python
import base64
from pathlib import Path
b64 = base64.b64encode(Path("shot.png").read_bytes()).decode()
url = "data:image/png;base64," + b64
```

### Manual screenshot from device

```bash
adb -s <serial> exec-out screencap -p > /tmp/p7a.png
sips -Z 720 /tmp/p7a.png --out /tmp/p7a.vlm.png
QSS_VLM_TIMEOUT=120 python3 -c "
from pathlib import Path
import sys; sys.path.insert(0,'scripts')
import ui_tars_local as vlm
g = vlm.VlmGate(autostart=False)
print(g.verify(Path('/tmp/p7a.vlm.png'), 'discord_not_launcher'))
"
```

---

## Hybrid local + cloud (best practices, July 2026)

Use **both** tiers deliberately — not as interchangeable drop-ins.

### Decision tree (read this first)

```
Screenshot gate needed?
├─ Routine pass/fail (home, channel, switcher, before-type)
│  └─ Local UI-TARS first (free). Cloud retry only if QSS_VLM_CLOUD set and local fails.
├─ Local server down?
│  └─ QSS_VLM_CLOUD=openai (or anthropic/google) — CloudVlmGate becomes primary in init_vlm().
├─ Local says ok:false AND cloud says ok:false on same PNG?
│  └─ Device state or harness nav is wrong — fix navigation/a11y, do NOT keep burning cloud credits.
├─ switcher_open_failed but screenshot shows User Settings (Log Out at bottom)?
│  └─ Harness scroll bug (Plugins offscreen) — not a VLM problem. See “A11y vs vision” below.
└─ profile/settings unreachable (quest, voice, emoji)?
   └─ Cloud profile_chip step (Google → Anthropic) to name obstruction; fix harness dismiss_* first.
```

### Tiered workflow

| Tier | When | Latency | Cost |
|------|------|---------|------|
| **Local UI-TARS** | Every routine gate (`discord_not_launcher`, `safe_test_channel`, `switcher_open`, `before_type`) | ~10–90 s/image (Metal) | Free |
| **Cloud vision** | Local server down; one stuck nav step; local/cloud disagree | ~2–8 s/image | ~$0.01–0.05/image |
| **Handsets + a11y** | All navigation taps | Sub-second | Free |

**Default run:** local only (`make qa`). Add cloud only when you need it:

```bash
# Stuck on profile → settings → plugins (quest bar, voice UI, dense chrome)
QSS_VLM=1 QSS_VLM_CLOUD=google,anthropic QSS_VLM_CLOUD_STEP=profile_chip \
  python3 scripts/device_qa_qss.py p7a --guild dcs

# Local down — cloud replaces primary gate
QSS_VLM=1 QSS_VLM_CLOUD=openai python3 scripts/device_qa_qss.py p7a --guild dcs
```

### Verified model IDs (do not use retired names)

Older Haiku / Gemini Flash IDs **404 on current API accounts**. Defaults in `scripts/vlm_cloud.py`:

| Provider | Default model | Notes |
|----------|---------------|-------|
| OpenAI | `gpt-4o-mini` | Cheap JSON gates |
| Anthropic | `claude-haiku-4-5-20251001` | Replaces `claude-3-5-haiku-*` |
| Google | `gemini-flash-latest` | Alias → current Flash (e.g. `gemini-3.5-flash`); **not** `gemini-2.0-flash` |
| Escalation | `claude-sonnet-4-6` | Second opinion only (`ambiguous` step) |

Pinned Google models (`gemini-2.0-flash`, `gemini-2.5-flash`) may return *"no longer available to new users"* — prefer `-latest` aliases.

### API keys (not in git)

Store in `~/.config/RevengeQuickSwitcher/secrets.env` (`chmod 600`):

```bash
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...          # or GEMINI_API_KEY=
OPENAI_API_KEY=sk-...       # optional
```

`scripts/load_qss_secrets.py` loads this automatically in `device_qa_qss.py` and `vlm_cloud.py`.

### Local-first with cloud retry

When `QSS_VLM_CLOUD` is set **and** keys are configured, `vlm_require()` in the harness:

1. Runs the **local** UI-TARS gate first.
2. On failure, **retries once** via `CloudVlmGate` (same check, same screenshot).
3. Records both in `artifacts/.../vlm/` (`switcher_open.json`, `switcher_open_cloud.json`).

Cloud retry does **not** fix navigation — it confirms whether the screenshot really shows the expected UI. If **both local and cloud** fail the same check on the same artifact, the blocker is almost always **device state or harness logic**, not model choice.

### A11y vs vision (do not conflate)

Handsets UI dumps list nodes **above and below** the viewport. A label can appear in the dump while **offscreen** (negative `y`).

**July 2026 p7a example — `switcher_open_failed`:**

| Signal | What it showed | Correct read |
|--------|----------------|--------------|
| UI dump | `"Plugins"` present, `y=-520`; `Log Out` at `y=2333` | Settings opened **scrolled to bottom** — Plugins not tappable |
| Local VLM `switcher_open` | `ok:false` — no filter field / Close button | **Correct** — switcher never opened |
| Harness `wait_until` | Passed because `"Plugins" in ui` | **Bug** — string presence ≠ on-screen row |

**Best practice:** for navigation, trust **positive-y coordinates** (`find_plugins_row`, `settings_scrolled_past_revenge`) over substring checks. Use VLM `settings_plugins_path` or cloud Gemini when you need a **human-readable scroll-position** verdict on a screenshot.

### Portrait lock (screen control)

`ScreenControlSession` (stayturgid) now **locks portrait** for the whole session:

- On enter: save rotation prefs → `accelerometer_rotation=0`, `user_rotation=0` (+ best-effort `wm` lock)
- Keepalive: re-assert every ~45 s
- On exit: restore saved prefs

Landscape screenshots confuse overlay/switcher gates. Always acquire the screen lease before QA (`make qa` sets `DEVICE_SCREEN_CONTROL_PROJECT=RevengeQuickSwitcher`). Release stale leases after killed runs:

```bash
make lease-status
DEVICE_SCREEN_CONTROL_PROJECT=RevengeQuickSwitcher \
  python3 ~/stayturgid/control/bin/screen_lease.py release p7a
```

### When to escalate cloud (by step)

| Stuck step | Provider | Why |
|------------|----------|-----|
| `profile_chip` | Google → Anthropic | Quest bar, voice chrome, bottom-bar obstructions |
| `switcher_open` | Anthropic → Google | Software overlay / filter field |
| `settings_plugins_path` | Google | Dense settings lists, scroll position |
| `safe_test_channel` | OpenAI → Anthropic | Voice vs text channel mis-read |
| `ambiguous` | Anthropic Sonnet | Local + mini disagree |

Failed runs write `cloud_vlm_request.json` + `cloud_vlm_suggested.txt` in the artifact dir with a rerun command.

**Artifact triage order** when a run fails:

1. `report.json` → `issues` list
2. `01_switcher_ui.txt` (or latest `*_ui.txt`) — scroll position, negative-y rows
3. `vlm/*.json` — local gate raw/parsed notes
4. `vlm/*_cloud.json` — cloud retry on same PNG (if `QSS_VLM_CLOUD` set)
5. `cloud_vlm_request.json` — suggested provider + `QSS_VLM_CLOUD_STEP`
6. `01_profile_fail.png` / `QSS_DEBUG_DIR` captures — profile → settings path

### Device state before blaming VLM

July 2026 p7a findings — navigation failed while local VLM correctly said switcher was closed:

| Blocker | Symptom in UI dump / screenshot | Harness fix |
|---------|--------------------------------|-------------|
| **Settings scrolled to bottom** | `Log Out` / `Developer` on-screen; `Plugins` at negative `y` | `scroll_settings_toward_top()` + `tap_plugins_settings()` with on-screen coords |
| **Active voice call** | `Disconnect`, `Unmute`, `Stream Room`, `Voice call active` | `leave_voice_channel()` — must run even when `Message #dc-general` composer is visible |
| **Quest / promo bar** | `Quest Bar`, `Watch 3m`, `Unlock 1.2x` over profile chip | `dismiss_quest_overlay()` before profile tap |
| **Emoji panel** | `Toggle emoji keyboard`, sticker chrome | `dismiss_emoji_panels()` |
| **Google feedback overlay** | `Send feedback to Google`, `Discard your feedback?` | `dismiss_system_dialogs()` — avoid blind bottom-right coord taps |
| **Screen-control clearance** | Digital Wellbeing / launcher after lease | `restore_screen=False` + relaunch Discord after session start |
| **Handsets timeout** | `audit_exception` / ping timeout | Retry; check Handsets on :9010 |
| **Stale DSCL lease** | `screen_lease_foreign_hold` | `screen_lease.py release <host>` |
| **Quest bar blocks profile (S24)** | `Quest Bar` + `Watch 3m` over `Danny, Online`; profile tap never opens sheet | Close sponsored video (**top-left X** ~75,210) if present; dismiss **How's Wordle go?** pill via **X** to the right of text (~961,2265 on 1080×2340 — often absent from a11y); then quest **More** (~752,2226); issue `quest_bar_blocks_profile` |
| **Plugin not installed** | Plugins page: `Oops! Nothing to see here… yet!`, `Install a plugin` | Install QSS on device before QA; issue `qss_plugin_not_installed` (skip `profile_chip` / `switcher_open` VLM — expected false negatives) |
| **S24 taller viewport** | `find_plugins_row` missed Plugins at y>2280; tap did not wait for Plugins sub-page | Dynamic `max_y` from screen height; `ui_on_plugins_list()` + `tap_text("Plugins")` (Jul 2026) |
| **DM home on cold start** | `Direct Messages` + DM rows; sidebar visible but no `#dc-general` | Tap named guild (`Danny Clark's server`) before blind sidebar slot probes (s24) |

Clear these **before** spending cloud credits on obstruction analysis.

### Debug captures

```bash
QSS_DEBUG_DIR=/tmp/qss-profile-debug QSS_VLM=1 QSS_VLM_CLOUD=google,anthropic \
  python3 scripts/device_qa_qss.py p7a --guild dcs
```

Writes `profile_attempt_N_before.{txt,png}` and `_after.*` under `QSS_DEBUG_DIR` during the profile → settings path.

### Timing budget

| Phase | Cap | Notes |
|-------|-----|-------|
| UI `wait_until` | 6–18 s | `UI_POLL=0.25s` — navigation only |
| Local VLM gate | `QSS_VLM_TIMEOUT` (900 s default) | Not subject to UI caps |
| Cloud VLM gate | ~120 s HTTP timeout | Typically 2–8 s |

A full `make qa` with local VLM: **~3–8 min** vision time. Adding cloud on 1–2 stuck steps: **+10–20 s**.

### Screen-control lease (DSCL v1)

QSS shares phones with stayturgid on the same Mac. Before UI work:

```bash
make lease-status
# or: python3 ~/stayturgid/control/bin/screen_lease.py check p7a
```

QSS registers as `DEVICE_SCREEN_CONTROL_PROJECT=RevengeQuickSwitcher`. `ScreenControlSession` acquires/releases the Mac lease automatically. Foreign holds → `screen_lease_foreign_hold` in `report.json`.

Spec: `~/stayturgid/docs/modules/screen-control-lease.md`

---

## Optional cloud fallback (agent-requested)

> **Canonical hybrid guide:** [Hybrid local + cloud](#hybrid-local--cloud-best-practices-july-2026) above. This section is a quick operator cheat sheet.

Local UI-TARS is preferred (free, offline). The QA agent may ask you for **low-limit API keys** for one or more cloud providers when:

- Local llama-server is down
- A screenshot gate is ambiguous (local vs cloud disagree)
- A **specific navigation step keeps failing** (profile chip, switcher open, settings scroll)

Failed runs write `cloud_vlm_request.json` in the artifact folder with a provider recommendation and rerun command.

### Which provider when

| Situation | Ask for | Model | Why |
|-----------|---------|-------|-----|
| Routine yes/no gates (Discord home, safe channel) | **OpenAI** | `gpt-4o-mini` | Cheapest cloud JSON gates |
| Local server down | **OpenAI** | `gpt-4o-mini` | Standard cloud fallback |
| Switcher overlay / jump list visible? | **Anthropic** | `claude-haiku-4-5-20251001` | Strong on mobile software UI |
| Settings → Plugins scroll position | **Google** | `gemini-flash-latest` | Dense UIs, many controls |
| Profile chip blocked (quest bar, voice UI) | **Google** or **Anthropic** | `gemini-flash-latest` / Haiku 4.5 | Obstruction ID + bottom bar |
| Local + cloud disagree (second opinion) | **Anthropic** | `claude-sonnet-4-6` | Higher reasoning; use sparingly |

**Strategy:** local UI-TARS for bulk gates; **one cloud call per stuck step** with screenshot attached. Multi-provider chain: `QSS_VLM_CLOUD=openai,anthropic,google`.

### Rerun examples

```bash
# Cheap bulk fallback
QSS_VLM=1 QSS_VLM_CLOUD=openai OPENAI_API_KEY=sk-... \
  python3 scripts/device_qa_qss.py p7a --guild dcs

# Stuck on switcher / profile path — Claude for software UI
QSS_VLM=1 QSS_VLM_CLOUD=anthropic QSS_VLM_CLOUD_STEP=switcher_open \
  python3 scripts/device_qa_qss.py p7a --guild dcs

# Dense settings list — Gemini (keys auto-load from secrets.env)
QSS_VLM=1 QSS_VLM_CLOUD=google QSS_VLM_CLOUD_STEP=settings_plugins_path \
  python3 scripts/device_qa_qss.py p7a --guild dcs

# Profile chip / quest bar — Gemini first
QSS_VLM=1 QSS_VLM_CLOUD=google,anthropic QSS_VLM_CLOUD_STEP=profile_chip \
  python3 scripts/device_qa_qss.py p7a --guild dcs
```

| Env | Default | Notes |
|-----|---------|-------|
| `QSS_VLM_CLOUD` | (off) | `openai`, `anthropic`, `google`, or comma-separated chain |
| `QSS_VLM_CLOUD_STEP` | — | Stuck step id → auto-pick provider (`switcher_open`, `profile_chip`, …) |
| `OPENAI_API_KEY` | — | [platform.openai.com](https://platform.openai.com/api-keys) |
| `ANTHROPIC_API_KEY` | — | [console.anthropic.com](https://console.anthropic.com/settings/keys) |
| `GOOGLE_API_KEY` | — | [aistudio.google.com](https://aistudio.google.com/apikey) |
| `QSS_VLM_OPENAI_MODEL` | `gpt-4o-mini` | Override OpenAI model |
| `QSS_VLM_ANTHROPIC_MODEL` | `claude-haiku-4-5-20251001` | Override Anthropic model |
| `QSS_VLM_GOOGLE_MODEL` | `gemini-flash-latest` | Override Gemini model |
| `QSS_SECRETS` | `~/.config/RevengeQuickSwitcher/secrets.env` | Override secrets file path |
| `DEVICE_SCREEN_CONTROL_PROJECT` | `RevengeQuickSwitcher` | DSCL v1 project slug (set by `make qa`) |

Implementation: `scripts/vlm_cloud.py` (`STEP_RECOMMENDATIONS`, `write_cloud_vlm_request`, `CloudVlmGate`).

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `VLM UI-TARS unavailable` | Server not running | [PATHS.md](PATHS.md): `launchctl kickstart -k gui/$(id -u)/homebrew.mxcl.ui-tars` |
| Server starts then dies | OOM or sandbox killed child | Use Metal on Mac; lower `UI_TARS_CTX`; close other apps; check log |
| `curl: connection refused` on :8081 | Stale pid / crash / service stopped | `launchctl kickstart -k …/homebrew.mxcl.ui-tars`; see log |
| Inference timeout | CPU-only or huge image | `QSS_VLM_NGL=99`, lower `QSS_VLM_MAX_WIDTH`, raise `QSS_VLM_TIMEOUT` |
| `unparseable_response` | Model replied with prose | Tighten prompt: “Reply JSON only”; check raw in `report.json` → `vlm.checks` |
| Low confidence false negative | Dark theme / unusual layout | Read `notes` in VLM JSON; adjust prompt or retake after UI settle |
| `switcher_open_failed` + settings visible | Plugins offscreen (scroll) | Fix harness scroll; optional `settings_plugins_path` cloud gate |
| `vlm_*_failed` local + cloud agree | Same PNG, both `ok:false` | Device/nav bug, not model — read UI dump + `notes` |
| Gates pass but wrong channel | Model error | **Never rely on VLM alone** — keep a11y allowlists in harness code |
| Cloud API 404 on model | Retired model id | Use defaults in `vlm_cloud.py` or `-latest` aliases |
| Landscape / rotated UI | Switcher mis-docked in screenshot | Portrait lock is automatic in `ScreenControlSession` |
| `screen_lease_foreign_hold` | Another project on glass | `make lease-status`; wait or use another device |

Server log:

```bash
tail -f ~/Library/Logs/ui-tars/server.log
```

---

## Files reference

| Path | Role |
|------|------|
| `scripts/vlm_install.sh` | Brew + Hugging Face download |
| `scripts/vlm_migrate_paths.sh` | Move data out of `~/.config/stayturgid/` |
| `scripts/vlm_service.sh` | Write plist + `launchctl bootstrap` (install only) |
| `PATHS.md` | Directory layout + standard `launchctl` commands |
| `scripts/ui_tars_local.py` | `VlmGate`, prompts, downscale, HTTP client |
| `scripts/vlm_cloud.py` | Cloud vision (OpenAI / Anthropic / Google) + step recommendations |
| `scripts/vlm_check.py` | Health smoke test |
| `scripts/device_qa_qss.py` | QA harness integration |
| `Makefile` | `vlm-install`, `vlm-check`, `qa` (see PATHS.md for launchctl) |

Model weights (not in git):

```
~/.local/share/ui-tars/models/1.5-7b/
  ByteDance-Seed_UI-TARS-1.5-7B-Q4_K_M.gguf
  mmproj-ByteDance-Seed_UI-TARS-1.5-7B.gguf
```

---

## Adding a new check

1. Add a prompt to `CHECK_PROMPTS` in `scripts/ui_tars_local.py` (require JSON schema).
2. Optionally add validation logic in `VlmGate.verify()` (see `safe_test_channel` / `discord_not_launcher`).
3. Call `vlm_require(vlm_capture(serial, "name.png"), "your_check", "label", issues=issues)` from the harness.
4. Test with a saved PNG before running live QA on the device.

Keep checks **narrow** — “Is the switcher open?” not “Navigate to settings and open the plugin.”
