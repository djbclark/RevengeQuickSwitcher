# Paths and naming

Where runtime files live on the Mac. **Nothing QSS-specific belongs under `~/.config/stayturgid/`** (that tree is the [stayturgid](https://github.com/djbclark/stayturgid) fleet project). **UI-TARS / llama-server** use vendor-neutral names. **RevengeQuickSwitcher** QA output uses its own data root.

---

## Initial setup (fresh Mac — for humans and other AIs)

Prerequisites: macOS (Apple Silicon recommended), Homebrew, ~6 GB disk, ~16 GB RAM, git clone of **RevengeQuickSwitcher** (e.g. `~/src/RevengeQuickSwitcher`).

### 1. Install llama.cpp + UI-TARS weights

```bash
cd /path/to/RevengeQuickSwitcher
scripts/vlm_install.sh
```

This runs `brew install llama.cpp` and downloads GGUF + mmproj to `~/.local/share/ui-tars/models/1.5-7b/`.

### 2. Install launchd agent (persists across login)

```bash
scripts/vlm_service.sh install
```

Writes `~/Library/LaunchAgents/homebrew.mxcl.ui-tars.plist`, runs `launchctl bootstrap`, waits for `/health`.

### 3. Verify

```bash
curl -sf http://127.0.0.1:8081/health && echo OK
launchctl print "gui/$(id -u)/homebrew.mxcl.ui-tars" | head -15
python3 scripts/vlm_check.py
scripts/vlm_smoke.sh          # stop → start → health
```

### 4. Optional: device QA harness

Requires **stayturgid** (`~/stayturgid`), Handsets, wireless ADB to test phone (e.g. `p7a`), Revenge app.

```bash
export STAYTURGID_REPO=~/stayturgid
export STAYTURGID_DEVICES_CONF=~/.config/stayturgid/devices.conf
QSS_VLM=1 python3 scripts/device_qa_qss.py p7a --guild lldc
```

QA artifacts: `~/.local/share/RevengeQuickSwitcher/artifacts/qss-qa/<date>/p7a/`

### 5. Upgrading from old layout

If models or logs were under `~/.config/stayturgid/`:

```bash
scripts/vlm_migrate_paths.sh
scripts/vlm_service.sh install
```

---

## UI-TARS + llama-server (third-party stack)

Shared local vision server — usable by any project, not branded after QSS or stayturgid.

| What | Default path | Override env |
|------|----------------|--------------|
| Home | `~/.local/share/ui-tars/` | `UI_TARS_HOME` |
| Model weights (GGUF + mmproj) | `~/.local/share/ui-tars/models/1.5-7b/` | `UI_TARS_MODEL_DIR` |
| Server working dir / manual pid | `~/.local/share/ui-tars/server/` | `UI_TARS_PID_FILE` |
| Server log (macOS) | `~/Library/Logs/ui-tars/server.log` | `UI_TARS_LOG` |
| HTTP health | `http://127.0.0.1:8081/health` | `UI_TARS_PORT` or `QSS_VLM_PORT` |
| `llama-server` binary | `$(brew --prefix llama.cpp)/bin/llama-server` | `UI_TARS_LLAMA_SERVER` |
| LaunchAgent label | `homebrew.mxcl.ui-tars` | — |
| LaunchAgent plist | `~/Library/LaunchAgents/homebrew.mxcl.ui-tars.plist` | — |
| Install script | `RevengeQuickSwitcher/scripts/vlm_install.sh` | — |
| Run script (launchd entry) | `RevengeQuickSwitcher/scripts/ui_tars_server_run.sh` | — |

Model files (after `scripts/vlm_install.sh`):

```
~/.local/share/ui-tars/models/1.5-7b/
  ByteDance-Seed_UI-TARS-1.5-7B-Q4_K_M.gguf
  mmproj-ByteDance-Seed_UI-TARS-1.5-7B.gguf
```

One-time migration from old `~/.config/stayturgid/models/ui-tars-*` layout:

```bash
/path/to/RevengeQuickSwitcher/scripts/vlm_migrate_paths.sh
```

---

## RevengeQuickSwitcher (this project)

| What | Default path | Override env |
|------|----------------|--------------|
| Data home | `~/.local/share/RevengeQuickSwitcher/` | `QSS_DATA_HOME` |
| QA artifacts | `~/.local/share/RevengeQuickSwitcher/artifacts/qss-qa/<date>/<host>/` | — |
| QA log | `~/.local/share/RevengeQuickSwitcher/logs/qss-qa.log` | — |
| Cloud VLM API keys | `~/.config/RevengeQuickSwitcher/secrets.env` (`chmod 600`) | `QSS_SECRETS` |

Copy `secrets.env.example` → `~/.config/RevengeQuickSwitcher/secrets.env`. **Never commit** real keys. Loaded automatically by `scripts/load_qss_secrets.py` when running QA or `vlm_cloud.py`.

| Source / scripts | git checkout (e.g. `~/src/RevengeQuickSwitcher/`) | — |

VLM gate JSON from QA runs: `…/artifacts/qss-qa/<date>/<host>/vlm/`.

---

## stayturgid (separate project — read only)

| What | Path |
|------|------|
| Fleet device map | `~/.config/stayturgid/devices.conf` |
| stayturgid logs/state | `~/.config/stayturgid/logs/`, `state/` |

QSS harness reads `devices.conf` via `STAYTURGID_DEVICES_CONF` but does **not** write QA artifacts there.

---

## Standard macOS commands (UI-TARS server)

Install once (download weights separately via `scripts/vlm_install.sh`):

```bash
/path/to/RevengeQuickSwitcher/scripts/vlm_service.sh install
```

**Check status**

```bash
curl -sf http://127.0.0.1:8081/health
launchctl print "gui/$(id -u)/homebrew.mxcl.ui-tars"
tail -20 ~/Library/Logs/ui-tars/server.log
```

**Start** (after install; also runs at login)

```bash
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/homebrew.mxcl.ui-tars.plist
launchctl kickstart -k "gui/$(id -u)/homebrew.mxcl.ui-tars"
```

**Stop**

```bash
launchctl bootout "gui/$(id -u)" ~/Library/LaunchAgents/homebrew.mxcl.ui-tars.plist
```

**Restart**

```bash
launchctl kickstart -k "gui/$(id -u)/homebrew.mxcl.ui-tars"
```

**Uninstall**

```bash
/path/to/RevengeQuickSwitcher/scripts/vlm_service.sh uninstall
```

---

## Operations guide (for humans and other AIs)

### What is running

- **Process:** `llama-server` (Homebrew `llama.cpp`) serving **UI-TARS-1.5-7B** on port **8081**.
- **Supervisor:** macOS **launchd** user agent `homebrew.mxcl.ui-tars`.
- **Consumer:** `RevengeQuickSwitcher/scripts/ui_tars_local.py` during `device_qa_qss.py` when `QSS_VLM=1`.

### Is it up?

```bash
curl -sf http://127.0.0.1:8081/health && echo OK
launchctl print "gui/$(id -u)/homebrew.mxcl.ui-tars" 2>&1 | head -15
```

Healthy = HTTP 200 from `/health` and launchd `state = running`.

### If down — recovery order

1. `scripts/vlm_smoke.sh` — stop → start → health (requires launchctl on the Mac, not a sandbox).
2. `tail -50 ~/Library/Logs/ui-tars/server.log` — OOM, missing model, port conflict.
2. Confirm weights exist under `~/.local/share/ui-tars/models/1.5-7b/`. If not: `scripts/vlm_install.sh`.
3. `launchctl kickstart -k "gui/$(id -u)/homebrew.mxcl.ui-tars"`.
4. If plist missing or repo moved: `scripts/vlm_service.sh install` (rewrites plist paths).
5. Port conflict: `lsof -i :8081` — stop other listener or set `UI_TARS_PORT` and reinstall.
6. `brew install llama.cpp` if `llama-server` missing.

### Bypass vision gates (emergency QA)

```bash
QSS_VLM=0 python3 scripts/device_qa_qss.py p7a --guild dcs
```

### Do not

- Put UI-TARS models or server logs under `~/.config/stayturgid/`.
- Use `make` for start/stop in automation — use **launchctl** above.
- Confuse stayturgid fleet logs with QSS QA artifacts.
