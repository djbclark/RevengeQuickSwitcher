# UI-TARS-1.5-7B — local vision gates for Android screenshots

This project uses **UI-TARS-1.5-7B** (ByteDance’s GUI-focused vision-language model) as a **local screenshot verifier** during device QA. It does not drive the phone autonomously. Instead it answers yes/no questions about PNGs captured from ADB (`adb exec-out screencap`) *before* the harness types or taps — for example: “Are we in Discord, not Niagara Launcher?” and “Are we on `#dc-general`?”

Related: [PATHS.md](PATHS.md) (directories, launchctl commands, AI ops) · [TESTING.md](TESTING.md) · [OPTIONS.md](OPTIONS.md) (**D1** harness) · `scripts/ui_tars_local.py` · `scripts/device_qa_qss.py`

---

## When to use it

| Good fit | Poor fit |
|----------|----------|
| Gate checks before typing in a filter/composer | Full autonomous “agent” that plans every tap |
| Confirm safe test channel / switcher open / not launcher | Pixel-perfect coordinate grounding every frame |
| One screenshot → one JSON verdict (~10–90s on Apple Silicon) | Sub-second real-time video |

**Design principle:** use UI-TARS for **high-stakes verification**, not for every navigation step. Handsets + a11y text selectors remain primary; VLM is the safety net.

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
| `before_type` | About to type in filter/composer — Discord focused, not public chat on wrong server |

Harness call sites (`device_qa_qss.py`):

1. After Discord home screenshot → `discord_not_launcher`
2. After safe guild navigation → `safe_test_channel`
3. After switcher opens → `switcher_open`
4. **Before every `handsets_fill` / type into filter** → `before_type`
5. After server jump → `safe_test_channel` again (`post_jump_channel`)

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

## Optional cloud fallback (agent-requested)

Local UI-TARS is preferred (free, offline). The QA agent may ask you for **low-limit API keys** for one or more cloud providers when:

- Local llama-server is down
- A screenshot gate is ambiguous (local vs cloud disagree)
- A **specific navigation step keeps failing** (profile chip, switcher open, settings scroll)

Failed runs write `cloud_vlm_request.json` in the artifact folder with a provider recommendation and rerun command.

### Which provider when (2026 research)

| Situation | Ask for | Model | Why |
|-----------|---------|-------|-----|
| Routine yes/no gates (Discord home, safe channel) | **OpenAI** | `gpt-4o-mini` | ~$0.03–0.05/image; native JSON mode; best cost for volume ([ScrollTest](https://scrolltest.com/ai-visual-testing-gpt-4o-ui-bugs/), [Markaicode](https://markaicode.com/usecases/vision-model-qa-ui-testing/)) |
| Local server down | **OpenAI** | `gpt-4o-mini` | Cheapest cloud fallback |
| Switcher overlay / jump list visible? | **Anthropic** | `claude-3-5-haiku-20241022` | Strong on mobile **software UI** screenshots ([Railwail benchmark](https://railwail.com/mx/blog/claude-gpt-gemini-vision-benchmark)) |
| Settings → Plugins scroll position | **Google** | `gemini-2.0-flash` | Best on **dense UIs** with many controls ([benchr](https://benchr.org/articles/multimodal-capability-ranking)) |
| Profile chip blocked (quest bar, voice UI) | **Google** or **Anthropic** | `gemini-2.0-flash` / Haiku | Identify obstructions and bottom-bar state |
| Local + mini disagree (second opinion) | **Anthropic** | `claude-sonnet-4-20250514` | Higher reasoning; use sparingly |

**Strategy:** keep local UI-TARS for bulk gates; escalate **one cloud call per stuck step** with the screenshot attached. Multi-provider fallback: `QSS_VLM_CLOUD=openai,anthropic,google`.

### Rerun examples

```bash
# Cheap bulk fallback
QSS_VLM=1 QSS_VLM_CLOUD=openai OPENAI_API_KEY=sk-... \
  python3 scripts/device_qa_qss.py p7a --guild dcs

# Stuck on switcher / profile path — Claude for software UI
QSS_VLM=1 QSS_VLM_CLOUD=anthropic QSS_VLM_CLOUD_STEP=switcher_open \
  ANTHROPIC_API_KEY=sk-ant-... python3 scripts/device_qa_qss.py p7a --guild dcs

# Dense settings list — Gemini
QSS_VLM=1 QSS_VLM_CLOUD=google QSS_VLM_CLOUD_STEP=settings_plugins_path \
  GOOGLE_API_KEY=... python3 scripts/device_qa_qss.py p7a --guild dcs
```

| Env | Default | Notes |
|-----|---------|-------|
| `QSS_VLM_CLOUD` | (off) | `openai`, `anthropic`, `google`, or comma-separated chain |
| `QSS_VLM_CLOUD_STEP` | — | Stuck step id → auto-pick provider (`switcher_open`, `profile_chip`, …) |
| `OPENAI_API_KEY` | — | [platform.openai.com](https://platform.openai.com/api-keys) |
| `ANTHROPIC_API_KEY` | — | [console.anthropic.com](https://console.anthropic.com/settings/keys) |
| `GOOGLE_API_KEY` | — | [aistudio.google.com](https://aistudio.google.com/apikey) |
| `QSS_VLM_OPENAI_MODEL` | `gpt-4o-mini` | Override OpenAI model |
| `QSS_VLM_ANTHROPIC_MODEL` | `claude-3-5-haiku-20241022` | Override Anthropic model |
| `QSS_VLM_GOOGLE_MODEL` | `gemini-2.0-flash` | Override Gemini model |

Implementation: `scripts/vlm_cloud.py` (`STEP_RECOMMENDATIONS`, `write_cloud_vlm_request`).

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
| Gates pass but wrong channel | Model error | **Never rely on VLM alone** — keep a11y allowlists in harness code |

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
| `scripts/vlm_cloud.py` | Optional OpenAI vision fallback |
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
