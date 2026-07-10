#!/usr/bin/env python3
"""Unattended Quick Server Switcher device QA (D1 Phase 1).

Mirrors stayturgid ``control/bin/gui_audit.py``: one ScreenControlSession, Handsets
primary, screenshots + ``report.json`` per run.

  STAYTURGID_PRESENCE_QUIET=1  — no torch / vibrate / dialogs
  QSS_DEVICE=p7a               — fleet alias (default: p7a)
  QSS_SERIAL=35261JEHN12374    — override ADB serial (USB preferred when online)
  QSS_GUILD=dcs|lldc           — safe test guild to work in (default: dcs)
  QSS_SERVER_NAME=...          — switcher row to jump (must be Danny Clark's / LL/DC)
  QSS_OPEN=settings            — only settings→Open switcher (slash posts to chat!)
  QSS_VLM=1                    — local UI-TARS vision gates (make vlm-server)
  QSS_VLM_STRICT=1             — block QA actions when VLM server is down
  QSS_VLM_PORT=8081            — llama-server port for UI-TARS
  QSS_VLM_TIMEOUT=900          — per-image local VLM budget (seconds; keep high)

UI waits use wait_until (UI_POLL=0.25s, UI_WAIT_* caps). Local VLM inference is
not subject to those caps — each gate may take 10–90s on Metal.
  STAYTURGID_REPO=~/stayturgid — path to stayturgid checkout (control/lib)
  QSS_VLM_CLOUD=openai|anthropic|google — cloud vision (comma-separated fallback chain)
  QSS_VLM_CLOUD_STEP=switcher_open  — provider pick for stuck step (see vlm_cloud.py)
  OPENAI_API_KEY / ANTHROPIC_API_KEY / GOOGLE_API_KEY — operator-provided keys

**Safety:** All UI work happens on operator-owned test guilds only, verified by
channel name (not server title): ``#dc-general``, ``#dc-games`` (preferred),
``#ogden``, ``#college``. Sidebar icons ``DCs`` / ``LL/DC`` are hints only.
Never runs slash commands in-channel. Switcher opens via settings → Plugins → **Open switcher**.

Artifacts: ~/.local/share/RevengeQuickSwitcher/artifacts/qss-qa/<YYYY-MM-DD>/<host>/
Log:       ~/.local/share/RevengeQuickSwitcher/logs/qss-qa.log
Fleet map: ~/.config/stayturgid/devices.conf (stayturgid — STAYTURGID_DEVICES_CONF)

Usage:
  python3 scripts/device_qa_qss.py              # QSS_DEVICE or p7a
  python3 scripts/device_qa_qss.py p7a
  python3 scripts/device_qa_qss.py --dry-reach
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
STAYTURGID_REPO = Path(
    os.environ.get("STAYTURGID_REPO", os.path.expanduser("~/stayturgid"))
)
# stayturgid Mac automation libs live under control/lib/ (see stayturgid/control/lib/README.md).
_ST_LIB = STAYTURGID_REPO / "control" / "lib"
if not _ST_LIB.is_dir():
    sys.stderr.write(
        "stayturgid control/lib not found at %s — set STAYTURGID_REPO\n" % _ST_LIB
    )
    sys.exit(2)
sys.path.insert(0, str(_ST_LIB))

import stayturgid_device as dev  # noqa: E402
import screen_control as sc  # noqa: E402
import ui_driver as uid  # noqa: E402

sys.path.insert(0, str(REPO / "scripts"))
try:
    import ui_tars_local as vlm  # noqa: E402
except ImportError:
    vlm = None  # type: ignore
try:
    import vlm_cloud  # noqa: E402
except ImportError:
    vlm_cloud = None  # type: ignore

_vlm_gate: Any = None
_vlm_dir: Path | None = None
_vlm_records: list[dict[str, Any]] = []

ROOT = Path(
    os.environ.get(
        "QSS_DATA_HOME",
        os.path.expanduser("~/.local/share/RevengeQuickSwitcher"),
    )
)
LOG = ROOT / "logs" / "qss-qa.log"
ART = ROOT / "artifacts" / "qss-qa"
CONF = Path(
    os.environ.get(
        "STAYTURGID_DEVICES_CONF",
        os.path.expanduser("~/.config/stayturgid/devices.conf"),
    )
)

# Revenge-modded Discord vs stock package id.
DISCORD_PACKAGES = ("app.revenge", "com.discord")
DISCORD_LAUNCHERS = {
    "app.revenge": "com.discord.main.MainDefault",
    "com.discord": "com.discord.main.MainActivity",
}

# Safe channels — ground truth for “are we on a test guild?” (not server title).
SAFE_CHANNELS_DC = ("dc-general", "dc-games")
SAFE_CHANNELS_OTHER = ("ogden", "college")
SAFE_CHANNELS = SAFE_CHANNELS_DC + SAFE_CHANNELS_OTHER

# Operator-owned test guilds on p7a — sidebar icon hints; confirm via SAFE_CHANNELS.
SAFE_GUILDS: dict[str, dict[str, Any]] = {
    "dcs": {
        "icon": "DCs",
        "jump_names": ("Danny Clark's server", "Danny Clark", "DCs"),
    },
    "lldc": {
        "icon": "LL",
        "icon_alt": "DC",
        "jump_names": ("LL/DC", "LL", "DC"),
    },
}
# Guild names that must never be used for jumps or channel work.
FORBIDDEN_GUILD_MARKERS = (
    "Bee",
    "Tousi TV",
    "Nous Research",
    "IINE",
    "adafruit",
    "ARTSEY",
)

SWITCHER_MARKERS = (
    "Filter servers",
    "Quick Server Switcher",
    "Servers",
    "Close",
    "/ servers",
)
BAD_NAV_PATTERNS = (
    "selectChannel",
    "CHANNEL_SELECT",
    "GUILD_SELECT",
    "selectGuild",
)
GOOD_NAV_PATTERNS = ("openUrl", "openURL")

# Non-VLM UI timing — animations are off during audit; prefer wait_until over sleep.
# Local VLM (10–90s/image) uses ui_tars_local.QSS_VLM_TIMEOUT — never shorten that path.
UI_POLL = 0.25
UI_WAIT_SHORT = 6.0  # tap feedback, sidebar, profile sheet
UI_WAIT_MED = 10.0  # switcher open, settings nav, guild probe
UI_WAIT_JUMP = 18.0  # post-jump openUrl / async channel (generous; not VLM inference)


def plugin_version() -> str:
    manifest = REPO / "manifest.json"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        return str(data.get("version", "unknown"))
    except (OSError, json.JSONDecodeError):
        return "unknown"


def ts() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg: str) -> None:
    line = "%s  %s\n" % (ts(), msg)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass
    print(line, end="")


def adb_connect(serial: str) -> bool:
    r = subprocess.run(
        ["adb", "connect", serial],
        capture_output=True,
        text=True,
        timeout=20,
    )
    out = ((r.stdout or "") + (r.stderr or "")).lower()
    if "connected" in out or "already connected" in out:
        return True
    probe = subprocess.run(
        ["adb", "-s", serial, "shell", "echo", "ok"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    return probe.returncode == 0 and "ok" in (probe.stdout or "")


def resolve_device_serial(host: str) -> str:
    """Prefer QSS_SERIAL, then USB from devices.conf, else wireless resolve."""
    override = os.environ.get("QSS_SERIAL", "").strip()
    if override:
        return override
    row = dev.device_row(host, str(CONF))
    if row:
        usb = row[0]
        if usb and usb != "-":
            r = subprocess.run(
                ["adb", "devices"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if "%s\tdevice" % usb in (r.stdout or ""):
                return usb
    return dev.resolve_adb(host, str(CONF))


def reachable(host: str) -> tuple[bool, str]:
    try:
        serial = resolve_device_serial(host)
    except Exception as e:  # noqa: BLE001
        return False, "resolve_failed:%s" % e
    if not serial:
        return False, "no_serial"
    if not adb_connect(serial):
        return False, "adb_unreachable"
    return True, serial


def adb_shell(serial: str, *args: str, timeout: int = 30) -> str:
    r = subprocess.run(
        ["adb", "-s", serial, "shell", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return (r.stdout or "").replace("\r", "")


def shot(serial: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        ["adb", "-s", serial, "exec-out", "screencap", "-p"],
        capture_output=True,
        timeout=45,
    )
    path.write_bytes(r.stdout or b"")


def screen_size(serial: str) -> tuple[int, int]:
    out = adb_shell(serial, "wm", "size")
    m = re.search(r"Physical size:\s*(\d+)x(\d+)", out)
    if m:
        return int(m.group(1)), int(m.group(2))
    return 1080, 2340


def resolve_discord_package(serial: str) -> str | None:
    for pkg in DISCORD_PACKAGES:
        out = adb_shell(serial, "pm", "path", pkg)
        if "package:" in out:
            return pkg
    return None


def launch_discord(serial: str, pkg: str) -> None:
    activity = DISCORD_LAUNCHERS.get(pkg, "")
    if activity:
        adb_shell(serial, "am", "start", "-n", "%s/%s" % (pkg, activity))
    else:
        subprocess.run(
            [
                "adb",
                "-s",
                serial,
                "shell",
                "monkey",
                "-p",
                pkg,
                "-c",
                "android.intent.category.LAUNCHER",
                "1",
            ],
            capture_output=True,
            timeout=20,
        )


def read_clipboard(serial: str) -> str:
    """Best-effort clipboard read (Android 10+ often blocks non-foreground UIDs)."""
    for cmd in (
        ["cmd", "clipboard", "get"],
        ["cmd", "clipboard", "get-primary-clip"],
    ):
        out = adb_shell(serial, *cmd, timeout=10).strip()
        if out and "No clipboard" not in out:
            return out
    return ""


def wait_until(
    predicate,
    *,
    timeout: float = UI_WAIT_MED,
    poll: float = UI_POLL,
    label: str = "",
) -> bool:
    """Poll until predicate() is true — prefer over fixed sleep (Appium/UI Automator best practice)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if predicate():
                return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(poll)
    if label:
        log("wait_until timeout: %s" % label)
    return False


def wait_ui(hs: uid.HandsetsSession, *needles: str, timeout: float = UI_WAIT_MED) -> bool:
    return wait_until(
        lambda: all(n in hs.ui() for n in needles),
        timeout=timeout,
        label=",".join(needles),
    )


def wait_discord_ready(hs: uid.HandsetsSession, *, timeout: float = UI_WAIT_MED) -> bool:
    """Discord foreground + bottom bar or channel chrome visible."""

    def ready() -> bool:
        ui = hs.ui()
        if not ui_looks_like_discord(ui):
            return False
        if any(", Online" in ln and "Button" in ln for ln in ui.splitlines()):
            return True
        return "message #" in ui.lower() or "chat_input_edit_text" in ui

    return wait_until(ready, timeout=timeout, label="discord_ready")


def set_animations_enabled(serial: str, enabled: bool) -> None:
    """Disable transitions during QA to reduce flaky taps (ADB best practice)."""
    val = "1" if enabled else "0"
    for key in (
        "window_animation_scale",
        "transition_animation_scale",
        "animator_duration_scale",
    ):
        adb_shell(serial, "settings", "put", "global", key, val, timeout=10)


def read_plugin_debug_blob(hs: uid.HandsetsSession, serial: str) -> str:
    """Capture QSS debug ring — plugin logs dump via logger.info; clipboard often blocked."""
    if "Copy debug logs" in hs.ui():
        hs.tap_text("Copy debug logs", timeout_ms=2500) or hs.tap_desc(
            "Copy debug logs", timeout_ms=2000
        )
        time.sleep(0.5)
    blob = logcat_grep(
        serial,
        r"QuickSwitcher|navigateToGuild|openUrl",
        lines=2500,
    )
    if blob.strip():
        log("collect_debug: logcat %d bytes" % len(blob))
        return blob
    clip = read_clipboard(serial)
    if clip:
        log("collect_debug: clipboard %d bytes" % len(clip))
    else:
        log("collect_debug: no logcat or clipboard text")
    return clip


def logcat_grep(serial: str, pattern: str, *, lines: int = 400) -> str:
    """Pull logcat from host adb (shell logcat is often empty over wireless)."""
    try:
        r = subprocess.run(
            ["adb", "-s", serial, "logcat", "-d", "-t", str(lines)],
            capture_output=True,
            text=True,
            timeout=45,
        )
        out = (r.stdout or "").replace("\r", "")
    except (subprocess.TimeoutExpired, OSError):
        out = ""
    if not out.strip():
        out = adb_shell(serial, "logcat", "-d", "-t", str(lines), timeout=45)
    hits = [
        ln
        for ln in out.splitlines()
        if re.search(pattern, ln, re.I)
    ]
    return "\n".join(hits[-80:])


def clear_logcat(serial: str) -> None:
    subprocess.run(
        ["adb", "-s", serial, "logcat", "-c"],
        capture_output=True,
        timeout=15,
    )


def recover_dest_guild_channel(
    hs: uid.HandsetsSession,
    session: sc.ScreenControlSession,
    serial: str,
    pkg: str,
    guild_key: str,
) -> str | None:
    """Land on a safe channel in the destination guild after a cross-guild jump."""
    want = list(safe_channels_for_guild(guild_key))
    ch = detect_safe_channel(hs.ui(), guild_key)
    if ch and ch in want:
        return ch
    ensure_discord_foreground(serial, pkg, hs)
    open_server_list(hs, session, serial, pkg)
    tap_sidebar_guild(hs, session, serial, pkg, guild_key)
    wait_until(
        lambda: ui_lists_safe_channel(hs.ui(), guild_key)
        or detect_safe_channel(hs.ui(), guild_key) is not None,
        timeout=UI_WAIT_SHORT,
        label="dest_guild_channels_%s" % guild_key,
    )
    for _ in range(6):
        ch = detect_safe_channel(hs.ui(), guild_key)
        if ch and ch in want:
            return ch
        ok, opened = open_safe_channel(hs, guild_key)
        if ok and opened in want:
            return opened
        hs.swipe("up")
        time.sleep(0.6)
    ok, key, ch = probe_sidebar_slots(hs, session, serial, pkg, guild_key)
    if ok and key == guild_key and ch in want:
        return ch
    return detect_safe_channel(hs.ui(), guild_key)


def _ui_has(hs: uid.HandsetsSession | None, *needles: str) -> bool:
    if hs is None:
        return False
    ui = hs.ui()
    return any(n in ui for n in needles)


def _label_y(ui: str, label: str) -> int | None:
    for line in ui.splitlines():
        if label not in line:
            continue
        m = re.search(r"(\d+)\s*,\s*(\d+)", line)
        if m:
            return int(m.group(2))
    return None


def handsets_type(hs: uid.HandsetsSession, text: str) -> bool:
    r = hs.hs("type", text, timeout=20)
    return r.returncode == 0


def init_vlm(artifact_dir: Path) -> bool:
    """Start local UI-TARS gates; optional cloud fallback when configured."""
    global _vlm_gate, _vlm_dir, _vlm_records
    _vlm_dir = artifact_dir / "vlm"
    _vlm_dir.mkdir(parents=True, exist_ok=True)
    _vlm_records = []
    if vlm is None or not vlm.vlm_enabled():
        log("VLM disabled or ui_tars_local missing")
        _vlm_gate = None
        return False
    gate = vlm.VlmGate(autostart=True)
    if gate.ready:
        _vlm_gate = gate
        log("VLM UI-TARS-1.5-7B ready (local llama-server)")
        return True
    if vlm_cloud is not None and vlm_cloud.cloud_configured():
        _vlm_gate = vlm_cloud.CloudVlmGate()
        if _vlm_gate.ready:
            log(
                "VLM cloud ready (%s / %s)"
                % (_vlm_gate.provider, _vlm_gate.model)
            )
            return True
    _vlm_gate = None
    hint = (
        vlm_cloud.suggest_cloud_vlm("local_unavailable")
        if vlm_cloud is not None
        else "VLM UI-TARS unavailable — run: make vlm-install && make vlm-server"
    )
    log(hint)
    if vlm_cloud is not None:
        vlm_cloud.write_cloud_vlm_request(
            artifact_dir, step="local_unavailable", reason="local_unavailable"
        )
    else:
        (artifact_dir / "cloud_vlm_suggested.txt").write_text(hint + "\n", encoding="utf-8")
    return False


def vlm_capture(serial: str, name: str) -> Path | None:
    if _vlm_dir is None:
        return None
    path = _vlm_dir / name
    shot(serial, path)
    return path


def vlm_require(
    image_path: Path | None,
    check: str,
    label: str = "",
    *,
    issues: list[str] | None = None,
) -> bool:
    if _vlm_gate is None or image_path is None or not image_path.is_file():
        return True
    ok, detail = _vlm_gate.verify(image_path, check)
    detail["label"] = label or check
    _vlm_records.append(detail)
    if _vlm_dir is not None:
        safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", label or check)
        (_vlm_dir / ("%s.json" % safe)).write_text(
            json.dumps(detail, indent=2), encoding="utf-8"
        )
    if detail.get("skipped"):
        if os.environ.get("QSS_VLM_STRICT", "1").strip() not in ("0", "false", "no"):
            msg = "vlm_unavailable"
            if issues is not None and msg not in issues:
                issues.append(msg)
            return False
        return True
    if not ok:
        msg = "vlm_%s_failed" % check
        if issues is not None and msg not in issues:
            issues.append(msg)
        notes = ""
        if isinstance(detail.get("parsed"), dict):
            notes = str(detail["parsed"].get("notes", ""))
        log("VLM blocked %s: %s (%.1fs)" % (label or check, notes, detail.get("elapsed_s", 0)))
    return ok


def vlm_flush_report(report: dict[str, Any]) -> None:
    backend = "none"
    if _vlm_gate is not None:
        backend = str(getattr(_vlm_gate, "provider", None) or "local")
    report["vlm"] = {
        "enabled": _vlm_gate is not None,
        "backend": backend,
        "checks": _vlm_records,
    }


def handsets_fill(
    hs: uid.HandsetsSession,
    selector: str,
    text: str,
    *,
    serial: str | None = None,
    issues: list[str] | None = None,
) -> bool:
    if serial and _vlm_gate is not None:
        cap = vlm_capture(serial, "pre_type_%s.png" % re.sub(r"\W+", "_", text[:24]))
        if not vlm_require(cap, "before_type", "type:%s" % text[:40], issues=issues):
            return False
        if "Filter" in selector or "filter" in text.lower():
            vlm_require(cap, "switcher_open", "switcher_before_type", issues=issues)
    r = hs.hs("fill", selector, text, timeout=20)
    return r.returncode == 0


def handsets_type_safe(
    hs: uid.HandsetsSession,
    text: str,
    *,
    serial: str | None = None,
    issues: list[str] | None = None,
) -> bool:
    if serial and _vlm_gate is not None:
        cap = vlm_capture(serial, "pre_type_%s.png" % re.sub(r"\W+", "_", text[:24]))
        if not vlm_require(cap, "before_type", "type:%s" % text[:40], issues=issues):
            return False
    return handsets_type(hs, text)


def tap_profile_chip(
    hs: uid.HandsetsSession, session: sc.ScreenControlSession | None = None
) -> bool:
    """Open profile sheet via footer name row (not the server-list button coords)."""
    ui = hs.ui()
    for line in ui.splitlines():
        if "Button" not in line or "Danny, Online" not in line:
            continue
        pt = _ui_xy(line)
        if not pt or pt[1] < 2100:
            continue
        if hs.hs("tap", str(pt[0]), str(pt[1]), timeout=10).returncode == 0:
            time.sleep(0.9)
            ui = hs.ui()
            if any(
                m in ui
                for m in (
                    "User Settings",
                    "Set Status",
                    "Switch Accounts",
                    "Edit Profile",
                )
            ):
                return True
    if session is not None:
        dismiss_emoji_panels(hs, session)
        unfocus_composer(hs, session)
        time.sleep(0.3)
        w, h = screen_size(session.serial)
        if ui_shows_server_sidebar(hs.ui()):
            session.shell("input", "tap", str(int(w * 0.55)), str(int(h * 0.45)))
            time.sleep(0.5)
        for x_frac in (0.88, 0.78, 0.92, 0.72):
            x, y = int(w * x_frac), int(h * 0.96)
            if hs.hs("tap", str(x), str(y), timeout=10).returncode == 0:
                time.sleep(0.9)
                ui = hs.ui()
                if any(
                    m in ui
                    for m in (
                        "User Settings",
                        "Set Status",
                        "Switch Accounts",
                        "Edit Profile",
                    )
                ):
                    return True
    ui = hs.ui()
    lines = ui.splitlines()
    for i, line in enumerate(lines):
        if "Button" not in line or not re.search(
            r",\s*(Online|Idle|Do Not Disturb|Invisible)", line
        ):
            continue
        for follow in lines[i : i + 4]:
            if "TextView" not in follow or "Danny" not in follow:
                continue
            m = re.search(r"(\d+)\s*,\s*(\d+)", follow)
            if m and int(m.group(1)) < 320:
                if hs.hs("tap", m.group(1), m.group(2), timeout=10).returncode == 0:
                    return True
        m = re.search(r'"([^"]+)"', line)
        if m and hs.tap_text(m.group(1), timeout_ms=3000):
            return True
    return (
        hs.tap_desc("You", timeout_ms=2000)
        or hs.tap_desc("Account", timeout_ms=1500)
        or hs.tap_text("You", timeout_ms=2000)
    )


def dismiss_system_dialogs(
    hs: uid.HandsetsSession, session: sc.ScreenControlSession | None = None
) -> None:
    """Dismiss Android runtime permission / grant dialogs that block Discord taps."""
    for _ in range(4):
        ui = hs.ui()
        if "permission_message" not in ui and "Allow " not in ui:
            if "grant_dialog" not in ui and "grant_singleton" not in ui:
                break
        if hs.tap_text("While using the app", timeout_ms=1200):
            time.sleep(0.6)
            continue
        if hs.tap_text("Only this time", timeout_ms=1200):
            time.sleep(0.6)
            continue
        if hs.tap_text("Don't allow", timeout_ms=1200) or hs.tap_text(
            "Don’t allow", timeout_ms=1200
        ):
            time.sleep(0.6)
            continue
        if session is not None:
            dismiss_keyboard(session)
        break


def dismiss_discord_chrome(
    hs: uid.HandsetsSession, session: sc.ScreenControlSession
) -> None:
    """Close promos / thread chrome that steal taps (avoid backing out of Discord)."""
    dismiss_system_dialogs(hs, session)
    for _ in range(3):
        if hs.tap_text("Dismiss", timeout_ms=800):
            time.sleep(0.5)
            continue
        ui = hs.ui()
        if "Thread" in ui and "Started by" in ui:
            if hs.tap_desc("Back", timeout_ms=800) or hs.tap_text("Back", timeout_ms=600):
                time.sleep(0.5)
                continue
        break


def open_user_settings(
    hs: uid.HandsetsSession, session: sc.ScreenControlSession | None = None
) -> bool:
    """Bottom profile chip → User Settings."""
    if not tap_profile_chip(hs, session):
        return False
    if not wait_until(
        lambda: "User Settings" in hs.ui()
        or "Set Status" in hs.ui()
        or "Switch Accounts" in hs.ui(),
        timeout=UI_WAIT_SHORT,
        label="profile_sheet",
    ):
        return False
    if hs.tap_text("User Settings", timeout_ms=2500) or hs.tap_desc(
        "User Settings", timeout_ms=2000
    ):
        wait_until(
            lambda: "Plugins" in hs.ui() or "Log Out" in hs.ui(),
            timeout=UI_WAIT_SHORT,
            label="user_settings_open",
        )
        return True
    return False


def unfocus_composer(
    hs: uid.HandsetsSession, session: sc.ScreenControlSession
) -> None:
    """Leave chat composer without KEYCODE_BACK (can open emoji/sticker panels)."""
    w, h = screen_size(session.serial)
    session.shell("input", "tap", str(int(w * 0.5)), str(int(h * 0.35)))
    time.sleep(0.35)


def dismiss_channel_promos(
    hs: uid.HandsetsSession, session: sc.ScreenControlSession
) -> None:
    """Scroll chat and dismiss promos that cover the profile chip."""
    w, h = screen_size(session.serial)
    session.shell(
        "input", "swipe", str(int(w * 0.5)), str(int(h * 0.55)), str(int(w * 0.5)), str(int(h * 0.25)), "350"
    )
    time.sleep(0.4)
    for label in ("Dismiss", "Not now", "Skip", "Close"):
        if hs.tap_text(label, timeout_ms=800):
            time.sleep(0.4)


def ui_quest_overlay(ui: str) -> bool:
    return any(m in ui for m in ("Quest Bar", "Watch 3m", "Get Reward!", "Unlock 1.2x"))


def dismiss_emoji_panels(
    hs: uid.HandsetsSession, session: sc.ScreenControlSession
) -> None:
    """Close sticker/emoji overlays that block profile chip taps."""
    for _ in range(3):
        ui = hs.ui()
        if "Filter servers" in ui:
            return
        if not any(
            m in ui
            for m in (
                "Yantra Launcher",
                "emoji",
                "Emoji",
                "Stickers",
                "GIF",
                "chat_input_emoji",
            )
        ):
            break
        if hs.tap_desc("Back", timeout_ms=800) or hs.tap_text("Back", timeout_ms=600):
            time.sleep(0.4)
            continue
        unfocus_composer(hs, session)
        session.shell("input", "keyevent", "KEYCODE_BACK")
        time.sleep(0.4)


def dismiss_keyboard(session: sc.ScreenControlSession) -> None:
    session.shell("input", "keyevent", "KEYCODE_BACK")
    time.sleep(0.4)


def _ui_xy(line: str) -> tuple[int, int] | None:
    m = re.search(r"(\d+)\s*,\s*(\d+)", line)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def _ui_label(line: str) -> str | None:
    m = re.search(r'"([^"]+)"', line)
    return m.group(1).strip() if m else None


SIDEBAR_X = 94


def safe_channels_for_guild(guild_key: str) -> tuple[str, ...]:
    """Channels that identify each test guild (not server title)."""
    if guild_key == "lldc":
        return SAFE_CHANNELS_OTHER
    return SAFE_CHANNELS_DC


def guild_for_jump_name(name: str) -> str | None:
    """Map a switcher row label to dcs or lldc."""
    for key, cfg in SAFE_GUILDS.items():
        for n in cfg["jump_names"]:
            if name == n:
                return key
    return None


def is_cross_guild_jump(active_guild: str, tapped: str) -> bool:
    dest = guild_for_jump_name(tapped)
    return bool(dest and dest != active_guild)


def expected_channels_for_jump(tapped: str) -> list[str]:
    key = guild_for_jump_name(tapped)
    if not key:
        return []
    return list(safe_channels_for_guild(key))


def wait_for_target_channel(
    hs: uid.HandsetsSession, tapped: str, *, timeout: float = 20.0
) -> str | None:
    """After a jump row tap, wait for a safe channel on the destination guild."""
    want = expected_channels_for_jump(tapped)
    dest = guild_for_jump_name(tapped)
    if not want:
        return None
    deadline = time.time() + timeout
    while time.time() < deadline:
        ch = detect_safe_channel(hs.ui(), dest)
        if ch and ch in want:
            return ch
        time.sleep(UI_POLL)
    return None


def ui_lists_safe_channel(ui: str, guild_key: str | None = None) -> bool:
    """Channel list includes at least one known test channel for this guild."""
    low = ui.lower()
    if guild_key:
        return any(ch in low for ch in safe_channels_for_guild(guild_key))
    return any(ch in low for ch in SAFE_CHANNELS)


def ui_in_voice_channel(ui: str) -> bool:
    """Voice/stage UI without an active text-channel composer."""
    low = ui.lower()
    if re.search(r"message\s+#", low):
        return False
    voice_markers = (
        "voice connected",
        "disconnect",
        "join voice",
        "stream room",
        "share screen",
        "voice channel",
        "stage channel",
    )
    return any(m in low for m in voice_markers)


def leave_voice_channel(
    hs: uid.HandsetsSession,
    session: sc.ScreenControlSession,
    serial: str,
    pkg: str,
    guild_key: str,
) -> None:
    """Exit voice/stage view so text-channel navigation can proceed."""
    if not ui_in_voice_channel(hs.ui()):
        return
    log("voice channel open — leaving for text channel")
    for _ in range(3):
        if hs.tap_text("Disconnect", timeout_ms=1200) or hs.tap_desc(
            "Disconnect", timeout_ms=1000
        ):
            time.sleep(0.6)
            break
        if hs.tap_desc("Back", timeout_ms=1000) or hs.tap_text("Back", timeout_ms=800):
            time.sleep(0.6)
            continue
        session.shell("input", "keyevent", "KEYCODE_BACK")
        time.sleep(0.5)
    ensure_discord_foreground(serial, pkg, hs)
    ok, _ch = open_safe_channel(hs, guild_key)
    if not ok:
        open_server_list(hs, session, serial, pkg)
        open_safe_channel(hs, guild_key)


def detect_safe_channel(ui: str, guild_key: str | None = None) -> str | None:
    """Return the active safe channel name, or None (never bare #general)."""
    if ui_in_voice_channel(ui):
        return None
    low = ui.lower()
    order: tuple[str, ...]
    if guild_key:
        order = safe_channels_for_guild(guild_key)
    else:
        order = SAFE_CHANNELS
    for ch in order:
        esc = re.escape(ch)
        if re.search(r"message\s+#%s\b" % esc, low):
            return ch
        if re.search(r"welcome to #%s\b" % esc, low):
            return ch
        if re.search(r"message\s+\"%s\"" % esc, low):
            return ch
        if re.search(r"channel\s+header.*#%s\b" % esc, low):
            return ch
    return None


def ui_on_safe_channel(ui: str, guild_key: str | None = None) -> bool:
    """Currently viewing a known test channel (header or composer hint)."""
    return detect_safe_channel(ui, guild_key) is not None


def open_safe_channel(
    hs: uid.HandsetsSession, guild_key: str
) -> tuple[bool, str]:
    """Open a test channel for this guild; verify active composer/header, not sidebar text."""
    channels = safe_channels_for_guild(guild_key)

    def try_labels() -> tuple[bool, str]:
        for ch in channels:
            for label in (
                ch,
                "%s (text channel)" % ch,
                "#%s" % ch,
                " #%s" % ch,
            ):
                if not hs.tap_text(label, timeout_ms=2000):
                    continue
                for _ in range(8):
                    time.sleep(0.5)
                    found = detect_safe_channel(hs.ui(), guild_key)
                    if found:
                        return True, found
        return False, ""

    ok, ch = try_labels()
    if ok:
        return ok, ch

    ui = hs.ui()
    for ch in channels:
        esc = re.escape(ch)
        for line in ui.splitlines():
            if ch not in line.lower() and ("#%s" % ch) not in line.lower():
                continue
            if not any(t in line for t in ("Button", "channel", "TextView")):
                continue
            pt = _ui_xy(line)
            if pt and hs.hs("tap", str(pt[0]), str(pt[1]), timeout=10).returncode == 0:
                for _ in range(8):
                    time.sleep(0.5)
                    found = detect_safe_channel(hs.ui(), guild_key)
                    if found:
                        return True, found

    if hs.tap_text("Browse Channels", timeout_ms=2000):
        time.sleep(0.8)
        ok, ch = try_labels()
        if ok:
            return ok, ch

    return False, ""


def foreground_package(serial: str) -> str | None:
    comp = sc.get_foreground_component(serial)
    if not comp or "/" not in comp:
        return None
    return comp.split("/", 1)[0]


def foreground_is_discord(serial: str) -> bool:
    pkg = foreground_package(serial)
    return pkg in DISCORD_PACKAGES if pkg else False


def ui_looks_like_discord(ui: str) -> bool:
    markers = (
        "Danny, Online",
        "Browse Channels",
        "message #",
        "Filter servers",
        "Quick Server Switcher",
        "chat_input_edit_text",
        "Unread messages,",
        "(text channel)",
        "Notifications,",
    )
    return any(m in ui for m in markers)


def ui_looks_like_launcher(ui: str) -> bool:
    low = ui.lower()
    return any(
        m in low
        for m in ("niagara", "bitpit", "launcher", "swipe up to unlock")
    )


def ensure_discord_foreground(
    serial: str, pkg: str, hs: uid.HandsetsSession | None
) -> bool:
    """Stay in Revenge/Discord — relaunch if we landed on Niagara or another app."""
    if foreground_is_discord(serial) and hs is not None and ui_looks_like_discord(hs.ui()):
        return True
    if hs is not None and ui_looks_like_launcher(hs.ui()):
        log("launcher detected — relaunching %s" % pkg)
    launch_discord(serial, pkg)
    if hs is None:
        return foreground_is_discord(serial)
    return wait_discord_ready(hs, timeout=UI_WAIT_MED) or foreground_is_discord(serial)


def ui_in_channel_chat(ui: str) -> bool:
    """Inside a channel composer / chat — one Back reveals the server icon column."""
    if "message #" in ui.lower() or "chat_input_edit_text" in ui:
        return True
    for line in ui.splitlines():
        if "fill" in line.lower() and "chat_input" in line:
            return True
    return False


def ui_shows_server_sidebar(ui: str) -> bool:
    """True when the guild icon column is visible (not inside a channel chat)."""
    count = 0
    for line in ui.splitlines():
        if "Button" not in line:
            continue
        pt = _ui_xy(line)
        if pt and pt[0] <= 140:
            count += 1
    return count >= 3


def open_server_list(
    hs: uid.HandsetsSession,
    session: sc.ScreenControlSession,
    serial: str,
    pkg: str,
) -> bool:
    """From channel chat, one top-left Back reveals the server icon column."""
    ensure_discord_foreground(serial, pkg, hs)
    if ui_shows_server_sidebar(hs.ui()):
        return True
    if not ui_in_channel_chat(hs.ui()):
        return ui_shows_server_sidebar(hs.ui())

    ui = hs.ui()
    tapped = False
    for line in ui.splitlines():
        if "Button" not in line:
            continue
        label = _ui_label(line) or ""
        if not (label == "Back" or label.startswith("Back ")):
            continue
        pt = _ui_xy(line)
        if pt and pt[0] < 120 and pt[1] < 300:
            if hs.hs("tap", str(pt[0]), str(pt[1]), timeout=10).returncode == 0:
                tapped = True
                break
    if not tapped:
        hs.tap_desc("Back", timeout_ms=1000)
    wait_until(
        lambda: ui_shows_server_sidebar(hs.ui()),
        timeout=UI_WAIT_SHORT,
        label="sidebar_after_back",
    )
    if not ui_shows_server_sidebar(hs.ui()):
        session.shell("input", "keyevent", "KEYCODE_BACK")
        wait_until(
            lambda: ui_shows_server_sidebar(hs.ui()),
            timeout=UI_WAIT_SHORT,
            label="sidebar_after_keyback",
        )
    if not foreground_is_discord(serial):
        log("Back left Discord — relaunching")
        ensure_discord_foreground(serial, pkg, hs)
        return False
    return ui_shows_server_sidebar(hs.ui())


def scroll_sidebar_to_top(
    hs: uid.HandsetsSession,
    session: sc.ScreenControlSession,
    serial: str,
    pkg: str,
    *,
    passes: int = 18,
) -> None:
    """Guild icons scroll independently — swipe down on the left column to reach the top."""
    if not ensure_discord_foreground(serial, pkg, hs):
        return
    if not ui_shows_server_sidebar(hs.ui()):
        return
    _w, h = screen_size(serial)
    x = str(SIDEBAR_X)
    y1 = str(int(h * 0.18))
    y2 = str(int(h * 0.82))
    session.shell("input", "tap", x, str(int(h * 0.45)))
    time.sleep(0.25)
    for _ in range(passes):
        if not foreground_is_discord(serial):
            ensure_discord_foreground(serial, pkg, hs)
            return
        session.shell("input", "swipe", x, y1, x, y2, "400")
        time.sleep(0.3)
    time.sleep(0.4)


def probe_sidebar_slots(
    hs: uid.HandsetsSession,
    session: sc.ScreenControlSession,
    serial: str,
    pkg: str,
    guild_key: str,
) -> tuple[bool, str, str]:
    """Tap early sidebar icon rows; accept only when a safe channel list appears."""
    if not ensure_discord_foreground(serial, pkg, hs):
        return False, "", ""
    scroll_sidebar_to_top(hs, session, serial, pkg)
    _w, h = screen_size(serial)
    slot_ys = [int(h * p) for p in (0.06, 0.08, 0.10, 0.12, 0.14, 0.16, 0.18, 0.20, 0.22, 0.24)]
    for y in slot_ys:
        if not foreground_is_discord(serial):
            return False, "", ""
        session.shell("input", "tap", str(SIDEBAR_X), str(y))
        time.sleep(0.7)
        ui = hs.ui()
        if not ui_lists_safe_channel(ui, guild_key):
            continue
        ok, ch = open_safe_channel(hs, guild_key)
        if ok:
            return True, guild_key, ch
    return False, "", ""


def scroll_sidebar_down(
    hs: uid.HandsetsSession,
    session: sc.ScreenControlSession,
    serial: str,
    pkg: str,
    *,
    passes: int = 1,
) -> None:
    """Nudge the guild icon column down (finger up) without scrolling the main pane."""
    if not foreground_is_discord(serial) or not ui_shows_server_sidebar(hs.ui()):
        return
    _w, h = screen_size(serial)
    x = str(SIDEBAR_X)
    y1 = str(int(h * 0.72))
    y2 = str(int(h * 0.28))
    for _ in range(passes):
        session.shell("input", "swipe", x, y1, x, y2, "350")
        time.sleep(0.35)


def _sidebar_needles(guild_key: str) -> list[str]:
    cfg = SAFE_GUILDS[guild_key]
    raw: list[str] = []
    for n in cfg["jump_names"] + (cfg["icon"],):
        if n and n not in raw:
            raw.append(n)
    # Avoid ultra-short needles ("LL", "DC") that false-match unrelated servers.
    out: list[str] = []
    for n in raw:
        if len(n) < 4 and n != "DCs":
            continue
        out.append(n)
    out.sort(key=len, reverse=True)
    return out


def tap_sidebar_guild(
    hs: uid.HandsetsSession,
    session: sc.ScreenControlSession,
    serial: str,
    pkg: str,
    guild_key: str,
) -> bool:
    """Find and tap a test guild in the server sidebar (top of icon column first)."""
    if not ensure_discord_foreground(serial, pkg, hs):
        return False
    needles = _sidebar_needles(guild_key)
    if not needles:
        return False

    def try_tap() -> bool:
        ui = hs.ui()
        for line in ui.splitlines():
            if "Button" not in line:
                continue
            pt = _ui_xy(line)
            if not pt or pt[0] > 140:
                continue
            if any(bad in line for bad in FORBIDDEN_GUILD_MARKERS):
                continue
            for name in needles:
                if name not in line:
                    continue
                if hs.hs("tap", str(SIDEBAR_X), str(pt[1]), timeout=10).returncode == 0:
                    return True
        return False

    cfg = SAFE_GUILDS[guild_key]
    icon = str(cfg.get("icon", ""))
    icon_alt = str(cfg.get("icon_alt", ""))

    scroll_sidebar_to_top(hs, session, serial, pkg)
    if try_tap():
        return True
    if icon and tap_sidebar_icon(hs, icon, icon_alt):
        return True
    for _ in range(3):
        scroll_sidebar_down(hs, session, serial, pkg)
        if try_tap():
            return True
        if icon and tap_sidebar_icon(hs, icon, icon_alt):
            return True
    return False


def navigate_to_safe_guild(
    hs: uid.HandsetsSession,
    session: sc.ScreenControlSession,
    serial: str,
    pkg: str,
    guild_key: str,
) -> tuple[bool, str, str]:
    """Find a test guild by channel list, open a safe channel. Returns (ok, guild, channel)."""
    if not ensure_discord_foreground(serial, pkg, hs):
        return False, "", ""

    dismiss_discord_chrome(hs, session)
    leave_voice_channel(hs, session, serial, pkg, guild_key)

    if not ui_on_safe_channel(hs.ui(), guild_key) and not ui_shows_server_sidebar(
        hs.ui()
    ):
        open_server_list(hs, session, serial, pkg)
        wait_until(
            lambda: ui_shows_server_sidebar(hs.ui())
            or ui_on_safe_channel(hs.ui(), guild_key),
            timeout=10,
            label="reveal_server_sidebar",
        )

    active = detect_safe_channel(hs.ui(), guild_key)
    if active:
        return True, guild_key, active

    # Wrong guild — switch before probing slots.
    for other in ("lldc", "dcs"):
        if other == guild_key:
            continue
        wrong = detect_safe_channel(hs.ui(), other)
        if wrong:
            log("on guild %s #%s — switching to %s" % (other, wrong, guild_key))
            tap_sidebar_guild(hs, session, serial, pkg, guild_key)
            wait_until(
                lambda: detect_safe_channel(hs.ui(), guild_key) is not None,
                timeout=UI_WAIT_SHORT,
                label="guild_switch_%s" % guild_key,
            )
            active = detect_safe_channel(hs.ui(), guild_key)
            if active:
                return True, guild_key, active
            break

    if not open_server_list(hs, session, serial, pkg):
        log("server sidebar not visible — relaunch and retry")
        ensure_discord_foreground(serial, pkg, hs)

    ok, key, ch = probe_sidebar_slots(hs, session, serial, pkg, guild_key)
    if ok and key == guild_key:
        log("safe channel #%s on guild %s (sidebar slot)" % (ch, key))
        return True, key, ch

    if not tap_sidebar_guild(hs, session, serial, pkg, guild_key):
        log("could not tap sidebar guild %s — retry after sidebar scroll" % guild_key)
        scroll_sidebar_down(hs, session, serial, pkg, passes=6)
        scroll_sidebar_to_top(hs, session, serial, pkg, passes=10)
        if not tap_sidebar_guild(hs, session, serial, pkg, guild_key):
            log("could not tap sidebar guild %s" % guild_key)
            return False, "", ""
    wait_until(
        lambda: ui_lists_safe_channel(hs.ui(), guild_key)
        or detect_safe_channel(hs.ui(), guild_key) is not None,
        timeout=UI_WAIT_SHORT,
        label="guild_channel_list_%s" % guild_key,
    )
    for _ in range(4):
        ok, ch = open_safe_channel(hs, guild_key)
        if ok:
            log("safe channel #%s on guild %s" % (ch, guild_key))
            return True, guild_key, ch
        ui = hs.ui()
        if ui_lists_safe_channel(ui, guild_key):
            ok, ch = open_safe_channel(hs, guild_key)
            if ok:
                log("safe channel #%s on guild %s" % (ch, guild_key))
                return True, guild_key, ch
        hs.swipe("up")
        time.sleep(0.6)

    log(
        "guild %s: no safe channels (%s) in list"
        % (guild_key, ", ".join(safe_channels_for_guild(guild_key)))
    )
    return False, "", ""


def tap_sidebar_icon(hs: uid.HandsetsSession, icon: str, icon_alt: str = "") -> bool:
    """Tap a guild icon in the left sidebar by its on-icon label (e.g. DCs, LL)."""
    ui = hs.ui()
    lines = ui.splitlines()
    for line in lines:
        if icon not in line:
            continue
        m = re.search(r"(\d+)\s*,\s*(\d+)", line)
        if not m or int(m.group(1)) > 140:
            continue
        y = m.group(2)
        if hs.hs("tap", "94", y, timeout=10).returncode == 0:
            return True
        if hs.tap_text(icon, timeout_ms=2000):
            return True
    if icon_alt:
        for line in lines:
            if icon_alt not in line:
                continue
            m = re.search(r"(\d+)\s*,\s*(\d+)", line)
            if m and int(m.group(1)) <= 140:
                y = m.group(2)
                if hs.hs("tap", "94", y, timeout=10).returncode == 0:
                    return True
    return False


def is_allowed_jump_line(line: str, name: str) -> bool:
    """Only tap switcher rows for allowlisted test guilds — never Bee, etc."""
    if any(bad in line for bad in FORBIDDEN_GUILD_MARKERS):
        return False
    if "Jump to" not in line:
        return False
    jump = "Jump to %s" % name
    if jump in line:
        return True
    # Exact server title match on the jump row only.
    if name in line and "Button" in line:
        label = _ui_label(line)
        if label and (label == name or label == jump):
            return True
    return False


def ensure_debug_logging(hs: uid.HandsetsSession) -> None:
    """Turn on plugin debug logging when on QSS settings (for logcat/clipboard)."""
    ui = hs.ui()
    if "Debug Logging" not in ui:
        return
    for line in ui.splitlines():
        if "Debug Logging" not in line:
            continue
        if "Switch" in line and ("[check]" in line or "checked" in line.lower()):
            return  # already on
    for line in ui.splitlines():
        if "Debug Logging" not in line or "Switch" not in line:
            continue
        pt = _ui_xy(line)
        if pt:
            hs.hs("tap", str(pt[0]), str(pt[1]), timeout=10)
            time.sleep(0.4)
            return


def ui_switcher_open(ui: str) -> bool:
    if "Filter servers" not in ui:
        return False
    return any(
        m in ui for m in ("Close switcher", "Close", "73 servers", "tap to jump")
    )


def ui_on_plugin_settings(ui: str) -> bool:
    low = ui.lower()
    if "message #" in low or "message #ogden" in low or "message #dc-" in low:
        return False
    return "Open switcher" in ui and "Quick Server Switcher" in ui


def switcher_shows_jump(ui: str, name: str) -> bool:
    return any(is_allowed_jump_line(line, name) for line in ui.splitlines())


def tap_switcher_jump_row(hs: uid.HandsetsSession, name: str) -> bool:
    """Tap an allowlisted Jump row in the open switcher."""
    variants = ("Jump to %s" % name, "Jump to %s" % name.strip())
    for variant in variants:
        if hs.tap_text(variant, timeout_ms=2500):
            return True
    for line in hs.ui().splitlines():
        if not is_allowed_jump_line(line, name):
            continue
        pt = _ui_xy(line)
        if pt and pt[1] > 0:
            if hs.hs("tap", str(pt[0]), str(pt[1]), timeout=10).returncode == 0:
                return True
    return False


def reopen_switcher_from_settings(hs: uid.HandsetsSession) -> bool:
    """Re-open the overlay when still on the QSS plugin page."""
    if ui_switcher_open(hs.ui()):
        return True
    if not ui_on_plugin_settings(hs.ui()):
        return False
    if hs.tap_text("Open switcher", timeout_ms=3000) or hs.tap_desc(
        "Open server switcher", timeout_ms=2500
    ):
        time.sleep(0.8)
    return ui_switcher_open(hs.ui())


def tap_filter_edit(hs: uid.HandsetsSession) -> bool:
    for line in hs.ui().splitlines():
        if "EditText" not in line or "Filter servers" not in line:
            continue
        pt = _ui_xy(line)
        if pt:
            return hs.hs("tap", str(pt[0]), str(pt[1]), timeout=10).returncode == 0
    return hs.tap_text("Filter servers", timeout_ms=2500)


def find_jump_on_pages(hs: uid.HandsetsSession, name: str, *, max_pages: int = 12) -> bool:
    """Paginate the server list until an allowlisted jump row appears."""
    for _ in range(max_pages):
        if switcher_shows_jump(hs.ui(), name):
            return True
        if not (
            hs.tap_text("Next page", timeout_ms=1500)
            or hs.tap_text("Next", timeout_ms=1200)
        ):
            break
        time.sleep(0.65)
    return switcher_shows_jump(hs.ui(), name)


def filter_switcher_query(
    hs: uid.HandsetsSession,
    query: str,
    *,
    serial: str | None = None,
    issues: list[str] | None = None,
) -> bool:
    """Type into the switcher filter only — never generic EditText (hits settings behind overlay)."""
    if not tap_filter_edit(hs):
        return False
    time.sleep(0.35)
    dismiss_keyboard_if_needed(hs)
    for selector in (
        'EditText:has-text("Filter servers")',
        "Filter servers",
    ):
        if handsets_fill(hs, selector, query, serial=serial, issues=issues):
            return True
    if tap_filter_edit(hs):
        time.sleep(0.25)
        return handsets_type_safe(hs, query, serial=serial, issues=issues)
    return False


def dismiss_keyboard_if_needed(hs: uid.HandsetsSession) -> None:
    hs.tap_text("Filter servers", timeout_ms=800)


def wait_for_jump_settle(
    hs: uid.HandsetsSession,
    *,
    timeout: float = UI_WAIT_MED,
) -> tuple[str, str | None]:
    """Wait after tapping a jump row. Returns (state, channel_if_safe)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        ui = hs.ui()
        ch = detect_safe_channel(ui)
        if ch:
            return "safe", ch
        if ui_switcher_open(ui):
            time.sleep(UI_POLL)
            continue
        if ui_on_plugin_settings(ui):
            time.sleep(UI_POLL)
            continue
        if ui_looks_like_discord(ui) and "User Settings" not in ui:
            if "Message #" in ui or detect_safe_channel(ui):
                return "channel", detect_safe_channel(ui)
            if "Plugins" in ui and "Quick Server Switcher" in ui:
                time.sleep(UI_POLL)
                continue
        time.sleep(UI_POLL)
    ui = hs.ui()
    if ui_switcher_open(ui):
        return "switcher", None
    if ui_on_plugin_settings(ui):
        return "plugin_settings", None
    return "timeout", None


def back_to_channel_view(
    hs: uid.HandsetsSession,
    session: sc.ScreenControlSession,
    serial: str,
    pkg: str,
    *,
    max_backs: int = 10,
) -> str | None:
    """Pop settings/plugins stack until a channel composer or safe channel is visible."""
    for _ in range(max_backs):
        ui = hs.ui()
        ch = detect_safe_channel(ui)
        if ch:
            return ch
        if "Message #" in ui and "Plugins" not in ui:
            return detect_safe_channel(ui)
        if ui_switcher_open(ui):
            hs.tap_text("Close", timeout_ms=1200) or hs.tap_desc(
                "Close switcher", timeout_ms=1000
            )
            time.sleep(0.6)
            continue
        session.shell("input", "keyevent", "KEYCODE_BACK")
        time.sleep(0.7)
        ensure_discord_foreground(serial, pkg, hs)
    return detect_safe_channel(hs.ui())


def copy_plugin_debug_if_visible(hs: uid.HandsetsSession, serial: str) -> str:
    if "Copy debug logs" not in hs.ui():
        return ""
    return read_plugin_debug_blob(hs, serial)


def dismiss_switcher_and_settings(
    hs: uid.HandsetsSession,
    session: sc.ScreenControlSession,
    serial: str,
    pkg: str,
) -> None:
    """Close switcher overlay and back out of plugin settings to a channel view."""
    for _ in range(6):
        ui = hs.ui()
        if ui_on_safe_channel(ui):
            return
        if "Filter servers" in ui and "Close" in ui:
            hs.tap_text("Close", timeout_ms=1500) or hs.tap_desc(
                "Close switcher", timeout_ms=1200
            )
            time.sleep(0.8)
            continue
        if "Open switcher" in ui and "Quick Server Switcher" in ui:
            session.shell("input", "keyevent", "KEYCODE_BACK")
            time.sleep(0.7)
            ensure_discord_foreground(serial, pkg, hs)
            continue
        if ui_looks_like_discord(ui) and "User Settings" not in ui:
            return
        session.shell("input", "keyevent", "KEYCODE_BACK")
        time.sleep(0.7)
        ensure_discord_foreground(serial, pkg, hs)


def assert_post_jump_safe(
    hs: uid.HandsetsSession,
    issues: list[str],
    *,
    serial: str | None = None,
    guild_key: str | None = None,
) -> str | None:
    """After a server jump, confirm we landed on an allowlisted test channel."""
    deadline = time.time() + UI_WAIT_SHORT
    while time.time() < deadline:
        ch = detect_safe_channel(hs.ui(), guild_key)
        if ch:
            return ch
        time.sleep(UI_POLL)
    ui = hs.ui()
    ch = detect_safe_channel(ui, guild_key)
    if ch:
        return ch
    issues.append("post_jump_unsafe_channel")
    log(
        "post-jump not on safe channel — need #dc-general/#dc-games/#ogden/#college "
        "(got unrelated channel; will not type)"
    )
    return None


def cross_guild_jump_names(guild_key: str, preferred: str) -> list[str]:
    """Allowlisted jump rows for the *other* test guild only — prefer full labels."""
    primary = (preferred or default_jump_server(guild_key)).strip()
    dest = guild_for_jump_name(primary)
    if not dest or dest == guild_key:
        return []
    # Use the canonical long name (LL/DC, Danny Clark's server) — not short LL/DC needles.
    for n in SAFE_GUILDS[dest]["jump_names"]:
        if "/" in n or len(n) >= 10:
            return [n]
    return [SAFE_GUILDS[dest]["jump_names"][0]]


def filter_query_variants(name: str) -> list[str]:
    """Short filter strings first — long queries can dismiss the switcher."""
    if name == "Danny Clark's server":
        return ["DCs", "Danny Clark", name]
    if name == "LL/DC":
        return ["LL/DC", "LL", "DC"]
    return [name]


def safe_jump_names(guild_key: str, preferred: str) -> list[str]:
    """Names allowed for switcher tap — test guilds only."""
    names: list[str] = []
    if preferred:
        names.append(preferred)
    for key in ("lldc", "dcs"):
        if key == guild_key:
            continue
        for n in SAFE_GUILDS[key]["jump_names"]:
            names.append(n)
    for n in SAFE_GUILDS.get(guild_key, SAFE_GUILDS["dcs"])["jump_names"]:
        names.append(n)
    out: list[str] = []
    seen: set[str] = set()
    for n in names:
        if not n or n in seen:
            continue
        if any(bad in n for bad in FORBIDDEN_GUILD_MARKERS):
            continue
        seen.add(n)
        out.append(n)
    return out


def tap_bottom_bar_button(hs: uid.HandsetsSession, label: str) -> bool:
    # Prefer text tap — coord tap on profile Settings can dismiss the sheet (p7a).
    if hs.tap_text(label, timeout_ms=3000) or hs.tap_desc(label, timeout_ms=2000):
        return True
    ui = hs.ui()
    for line in ui.splitlines():
        if label not in line or "Button" not in line:
            continue
        m = re.search(r"(\d+)\s*,\s*(\d+)", line)
        if m:
            r = hs.hs("tap", m.group(1), m.group(2), timeout=10)
            if r.returncode == 0:
                return True
    return False


def tap_revenge_settings(hs: uid.HandsetsSession) -> bool:
    """Tap Revenge in User Settings — not the Revenge guild in the sidebar."""
    ui = hs.ui()
    # Settings row is Button "Revenge, (commit-main)" — not View "Revenge" header.
    for line in ui.splitlines():
        if "Button" not in line or "Revenge" not in line:
            continue
        if "Unread" in line or "messages" in line:
            continue
        if "Revenge," in line or re.search(r"Revenge,\s*\([^)]+\)", line):
            m = re.search(r"(\d+)\s*,\s*(\d+)", line)
            if m:
                return hs.hs("tap", m.group(1), m.group(2), timeout=10).returncode == 0
    for line in ui.splitlines():
        low = line.lower()
        if "unread" in low or "messages" in low:
            continue
        if "Revenge" not in line or "Button" not in line:
            continue
        m = re.search(r"(\d+)\s*,\s*(\d+)", line)
        if m and int(m.group(1)) > 200:
            if hs.hs("tap", m.group(1), m.group(2), timeout=10).returncode == 0:
                return True
    return False


def scroll_settings_toward_top(hs: uid.HandsetsSession, *, passes: int = 8) -> None:
    """Recover when settings was scrolled to the bottom (Log Out / Developer visible)."""
    for _ in range(passes):
        hs.swipe("down")
        time.sleep(0.35)


def settings_scrolled_past_revenge(ui: str) -> bool:
    """True when the viewport shows the tail of settings (we overshot Revenge/Plugins)."""
    for line in ui.splitlines():
        label = _ui_label(line)
        if label not in ("Log Out", "Developer Settings", "App Version"):
            continue
        pt = _ui_xy(line)
        if pt and 0 < pt[1] < 2300:
            return True
    return False


def find_plugins_row(ui: str) -> tuple[int, int] | None:
    """Plugins button just under the Revenge heading — must be on-screen (positive y)."""
    lines = ui.splitlines()
    revenge_y: int | None = None
    for line in lines:
        if "Revenge" not in line or "Unread" in line:
            continue
        label = _ui_label(line)
        if label == "Revenge" and "View" in line:
            pt = _ui_xy(line)
            if pt and pt[1] > 0:
                revenge_y = pt[1]
                break
        if label and label.startswith("Revenge,") and "Button" in line:
            pt = _ui_xy(line)
            if pt and pt[1] > 0:
                revenge_y = pt[1]
                break

    for line in lines:
        if "Button" not in line or _ui_label(line) != "Plugins":
            continue
        pt = _ui_xy(line)
        if not pt or pt[1] <= 0:
            continue
        x, y = pt
        if y < 280 or y > 2280:
            continue
        if revenge_y is not None and (y <= revenge_y or y - revenge_y > 350):
            continue
        return x, y
    return None


def tap_plugins_settings(hs: uid.HandsetsSession) -> bool:
    """Tap Plugins under the Revenge heading — plain row, no icon. Do not open Revenge."""
    ui = hs.ui()
    if settings_scrolled_past_revenge(ui):
        scroll_settings_toward_top(hs)
        ui = hs.ui()

    pt = find_plugins_row(ui)
    if pt:
        return hs.hs("tap", str(pt[0]), str(pt[1]), timeout=10).returncode == 0

    # Revenge/Plugins sit a little below Account — small scrolls, not to the list end.
    for _ in range(6):
        hs.swipe("up")
        time.sleep(0.45)
        pt = find_plugins_row(hs.ui())
        if pt:
            return hs.hs("tap", str(pt[0]), str(pt[1]), timeout=10).returncode == 0
    return False


def tap_qss_plugin(hs: uid.HandsetsSession) -> bool:
    """Open Quick Server Switcher settings from the Plugins list."""
    ui = hs.ui()
    row_y: int | None = None
    for line in ui.splitlines():
        if "Quick Server Switcher" not in line and "Quick server switcher" not in line:
            continue
        pt = _ui_xy(line)
        if pt and pt[1] > 0:
            row_y = pt[1]
            break
    if row_y is None:
        for label in ("Quick Server Switcher", "Quick server switcher"):
            if hs.tap_text(label, timeout_ms=2000):
                time.sleep(0.6)
                if "Open switcher" in hs.ui():
                    return True
        return False

    # Prefer the row's settings button (same y band), then the title.
    settings_x: str | None = None
    for line in ui.splitlines():
        if "Button" not in line:
            continue
        pt = _ui_xy(line)
        if not pt or abs(pt[1] - row_y) > 40:
            continue
        if 650 <= pt[0] <= 850:
            settings_x = str(pt[0])
            break

    tap_order = [x for x in (settings_x, "335", "540", "706") if x]
    for x in tap_order:
        if hs.hs("tap", x, str(row_y), timeout=10).returncode == 0:
            time.sleep(0.8)
            if "Open switcher" in hs.ui():
                return True
    return False


def open_switcher_via_settings(hs: uid.HandsetsSession, session: sc.ScreenControlSession) -> bool:
    """Profile → Settings → Plugins → Quick Server Switcher → Open switcher."""
    if not navigate_to_qss_plugin(hs, session):
        return False
    ensure_debug_logging(hs)
    if not (
        hs.tap_text("Open switcher", timeout_ms=4000)
        or hs.tap_desc("Open switcher", timeout_ms=3000)
    ):
        return False
    return wait_until(
        lambda: ui_switcher_open(hs.ui()),
        timeout=UI_WAIT_MED,
        label="switcher_open",
    )


def open_switcher_via_slash(
    hs: uid.HandsetsSession,
    session: sc.ScreenControlSession,
    *,
    serial: str | None = None,
    issues: list[str] | None = None,
) -> bool:
    """Channel composer → pick /servers from slash UI → send (no free-text args)."""
    dismiss_discord_chrome(hs, session)
    dismiss_keyboard(session)
    if not hs.tap_id("chat_input_edit_text", timeout_ms=2500):
        w, h = screen_size(session.serial)
        session.tap(w // 2, int(h * 0.92))
    time.sleep(0.35)
    handsets_fill(
        hs,
        "EditText#chat_input_edit_text",
        "/",
        serial=serial or session.serial,
        issues=issues,
    )
    time.sleep(0.5)
    if not (hs.tap_text("/ servers", timeout_ms=3000) or hs.tap_text("servers", timeout_ms=2000)):
        return False
    if wait_until(
        lambda: _ui_has(hs, "Filter servers", "Close"),
        timeout=UI_WAIT_SHORT,
        label="slash_switcher",
    ):
        return True
    # Slash form with optional query/page — send bare command.
    if hs.tap_desc("Send", timeout_ms=2000) or hs.tap_id("chat_input_send_button", timeout_ms=2000):
        pass
    else:
        session.shell("input", "keyevent", "KEYCODE_ENTER")
    return wait_until(
        lambda: _ui_has(hs, "Filter servers", "Close", "Quick Server Switcher"),
        timeout=UI_WAIT_MED,
        label="slash_switcher_send",
    )


def default_jump_server(guild_key: str) -> str:
    """Cross-jump between operator test guilds."""
    if guild_key == "lldc":
        return "Danny Clark's server"
    return "LL/DC"


def settle_on_target_channel(
    hs: uid.HandsetsSession,
    tapped: str,
    *,
    timeout: float = 15.0,
    session: sc.ScreenControlSession | None = None,
    serial: str | None = None,
    pkg: str | None = None,
) -> str | None:
    """Wait for a destination safe channel, or open one in the target guild."""
    want = expected_channels_for_jump(tapped)
    dest = guild_for_jump_name(tapped)
    ch = wait_for_target_channel(hs, tapped, timeout=timeout)
    if ch and want and ch in want:
        return ch
    if dest and session and serial and pkg:
        recovered = recover_dest_guild_channel(hs, session, serial, pkg, dest)
        if recovered and (not want or recovered in want):
            log("pick_server: recovered #%s on %s" % (recovered, dest))
            return recovered
    return wait_for_target_channel(hs, tapped, timeout=5.0)


def pick_server_name(
    hs: uid.HandsetsSession,
    preferred: str,
    active_guild: str,
    *,
    serial: str | None = None,
    session: sc.ScreenControlSession | None = None,
    pkg: str | None = None,
    issues: list[str] | None = None,
    artifact_dir: Path | None = None,
) -> str | None:
    """Tap only allowlisted cross-guild test rows in the switcher."""
    target = preferred or default_jump_server(active_guild)
    names = cross_guild_jump_names(active_guild, target)
    if not names:
        log("pick_server: no cross-guild jump names for guild=%s" % active_guild)
        return None

    if not ui_switcher_open(hs.ui()):
        log("pick_server: switcher not open before jump tap")
        return None

    for name in names:
        ui = hs.ui()
        if switcher_shows_jump(ui, name) or find_jump_on_pages(hs, name):
            if serial and _vlm_gate is not None:
                cap = vlm_capture(serial, "pre_jump_%s.png" % re.sub(r"\W+", "_", name[:20]))
                vlm_require(cap, "jump_target_visible", "jump:%s" % name, issues=issues)
            if not tap_switcher_jump_row(hs, name):
                log("pick_server: failed to tap Jump to %s" % name)
                continue
        else:
            tapped_filter = False
            for query in filter_query_variants(name):
                log("pick_server: filtering switcher for %s" % query)
                if not filter_switcher_query(
                    hs, query, serial=serial, issues=issues
                ):
                    log("pick_server: could not type into switcher filter")
                    reopen_switcher_from_settings(hs)
                    continue
                time.sleep(0.9)
                if not ui_switcher_open(hs.ui()):
                    log("pick_server: switcher closed after filter type (%s)" % query)
                    reopen_switcher_from_settings(hs)
                    continue
                tapped_filter = True
                break
            if not tapped_filter:
                if find_jump_on_pages(hs, name):
                    tapped_filter = True
                else:
                    continue
            if serial and _vlm_gate is not None:
                cap = vlm_capture(serial, "pre_jump_%s.png" % re.sub(r"\W+", "_", name[:20]))
                vlm_require(cap, "jump_target_visible", "jump:%s" % name, issues=issues)
            if not tap_switcher_jump_row(hs, name):
                if hs.tap_text("Next page", timeout_ms=1500) or hs.tap_text(
                    "Next", timeout_ms=1200
                ):
                    time.sleep(0.6)
                    if not tap_switcher_jump_row(hs, name):
                        continue
                else:
                    continue
        log("pick_server: tapped Jump to %s — waiting for navigation" % name)
        state, ch = wait_for_jump_settle(hs, timeout=16.0)
        log("pick_server: post-tap state=%s channel=%s" % (state, ch))
        if state == "channel" and not ch:
            ch = wait_for_target_channel(hs, name, timeout=UI_WAIT_JUMP)
            if ch:
                state = "safe"
                log("pick_server: async channel settle #%s" % ch)
        if ui_switcher_open(hs.ui()):
            hs.tap_text("Close", timeout_ms=1200) or hs.tap_desc(
                "Close switcher", timeout_ms=1000
            )
            time.sleep(0.8)
        want = expected_channels_for_jump(name)
        if state == "plugin_settings":
            clip = copy_plugin_debug_if_visible(hs, serial or "")
            if clip:
                log("pick_server: debug log snippet: %s" % clip[:200])
                if artifact_dir is not None:
                    (artifact_dir / "clipboard_pre_back.txt").write_text(
                        clip, encoding="utf-8"
                    )
        if state in ("safe", "channel", "plugin_settings"):
            settle_timeout = (
                UI_WAIT_JUMP
                if state == "channel"
                else 16.0
                if state == "plugin_settings"
                else UI_WAIT_MED
            )
            dest_ch = settle_on_target_channel(
                hs, name, timeout=settle_timeout, session=session, serial=serial, pkg=pkg
            )
            if dest_ch and want and dest_ch in want:
                log("pick_server: settled on #%s" % dest_ch)
                if artifact_dir is not None and serial and session and pkg:
                    clip = copy_plugin_debug_if_visible(hs, serial)
                    if not clip and navigate_to_qss_plugin(hs, session):
                        ensure_debug_logging(hs)
                        clip = read_plugin_debug_blob(hs, serial)
                        back_to_channel_view(hs, session, serial, pkg)
                    if clip:
                        (artifact_dir / "clipboard_pre_back.txt").write_text(
                            clip, encoding="utf-8"
                        )
                        log("pick_server: captured nav debug (%d bytes)" % len(clip))
                if session and serial and pkg:
                    if ui_switcher_open(hs.ui()):
                        hs.tap_text("Close", timeout_ms=1200) or hs.tap_desc(
                            "Close switcher", timeout_ms=1000
                        )
                        time.sleep(0.6)
                    elif ui_on_plugin_settings(hs.ui()):
                        back_to_channel_view(hs, session, serial, pkg)
                return name
            if state == "channel" and session and serial and pkg:
                # Jump likely succeeded but landed on a non-test channel (#life, etc.).
                if ui_switcher_open(hs.ui()):
                    hs.tap_text("Close", timeout_ms=1200) or hs.tap_desc(
                        "Close switcher", timeout_ms=1000
                    )
                    time.sleep(0.6)
                dest_ch = settle_on_target_channel(
                    hs, name, timeout=20.0, session=session, serial=serial, pkg=pkg
                )
                if dest_ch and want and dest_ch in want:
                    log("pick_server: settled on #%s (after close)" % dest_ch)
                    return name
            if state == "plugin_settings" and session and serial and pkg:
                back_to_channel_view(hs, session, serial, pkg)
                dest_ch = settle_on_target_channel(
                    hs, name, timeout=8.0, session=session, serial=serial, pkg=pkg
                )
                if dest_ch and want and dest_ch in want:
                    return name
        if state in ("switcher", "plugin_settings", "timeout"):
            continue
    return None


def assert_switcher_top_docked(
    hs: uid.HandsetsSession, issues: list[str], screen_h: int
) -> None:
    ui = hs.ui()
    if not any(m in ui for m in SWITCHER_MARKERS):
        issues.append("switcher_not_visible")
        return
    for marker in ("Filter servers", "Close", "Servers"):
        y = _label_y(ui, marker)
        if y is not None and y > int(screen_h * 0.55):
            issues.append("keyboard_cover")
            return
    # Top-docked: primary chrome should sit in upper half.
    ys = [y for m in ("Filter servers", "Close") if (y := _label_y(ui, m)) is not None]
    if ys and max(ys) > int(screen_h * 0.45):
        issues.append("switcher_not_top_docked")


def assert_overlay_gone(hs: uid.HandsetsSession | None, issues: list[str]) -> None:
    if hs is None:
        return
    ui = hs.ui()
    if "Filter servers" in ui and "Close" in ui:
        issues.append("overlay_stuck")


def assert_taps_alive(
    hs: uid.HandsetsSession,
    session: sc.ScreenControlSession,
    issues: list[str],
) -> None:
    w, h = screen_size(session.serial)
    probes = (
        ("Message", "composer"),
        ("Channels", "channels"),
        ("Servers", "sidebar"),
    )
    for label, _tag in probes:
        if hs.tap_desc(label, timeout_ms=1200) or hs.tap_text(label, timeout_ms=1200):
            time.sleep(0.4)
            return
    # Fallback: tap composer region.
    session.tap(w // 2, int(h * 0.92))
    time.sleep(0.5)
    ui = hs.ui()
    if "Filter servers" in ui and "Close" in ui:
        issues.append("dead_taps")


def navigate_to_qss_plugin(
    hs: uid.HandsetsSession, session: sc.ScreenControlSession
) -> bool:
    """Profile → Settings → Plugins → Quick Server Switcher plugin page."""
    ui = hs.ui()
    if "Quick Server Switcher" in ui and (
        "Copy debug logs" in ui or "Open switcher" in ui
    ):
        return True
    if ui_switcher_open(ui):
        hs.tap_text("Close", timeout_ms=1200) or hs.tap_desc(
            "Close switcher", timeout_ms=1000
        )
        wait_until(lambda: not ui_switcher_open(hs.ui()), timeout=6, label="close_switcher")
    dismiss_emoji_panels(hs, session)
    dismiss_channel_promos(hs, session)
    unfocus_composer(hs, session)
    dismiss_discord_chrome(hs, session)
    for attempt in range(2):
        if open_user_settings(hs, session):
            break
        log("navigate_to_qss_plugin: open_user_settings attempt %d failed" % (attempt + 1))
        dismiss_emoji_panels(hs, session)
        unfocus_composer(hs, session)
    else:
        if ui_quest_overlay(hs.ui()):
            log("navigate_to_qss_plugin: quest/promo overlay may block profile chip")
        log("navigate_to_qss_plugin: profile chip not found")
        return False
    if not wait_until(
        lambda: "Plugins" in hs.ui() or settings_scrolled_past_revenge(hs.ui()),
        timeout=UI_WAIT_MED,
        label="user_settings",
    ):
        if not tap_plugins_settings(hs):
            return False
    if not wait_until(
        lambda: "Quick Server Switcher" in hs.ui() and "Copy debug logs" in hs.ui(),
        timeout=UI_WAIT_SHORT,
        label="qss_plugin",
    ):
        if not tap_qss_plugin(hs):
            for _ in range(3):
                hs.swipe("up")
                time.sleep(0.4)
                if tap_qss_plugin(hs):
                    break
            else:
                return False
    return "Quick Server Switcher" in hs.ui()


def open_plugin_settings(hs: uid.HandsetsSession, session: sc.ScreenControlSession) -> bool:
    """Profile → Settings → Plugins → Quick Server Switcher."""
    return navigate_to_qss_plugin(hs, session)


def collect_debug_via_clipboard(
    hs: uid.HandsetsSession,
    session: sc.ScreenControlSession,
    serial: str,
) -> str:
    """Plugin settings → Copy debug logs; prefer logcat (Android 10+ clipboard privacy)."""
    if not navigate_to_qss_plugin(hs, session):
        log("collect_debug: could not open plugin settings")
        return logcat_grep(serial, r"QuickSwitcher|navigateToGuild|openUrl", lines=2500)
    ensure_debug_logging(hs)
    return read_plugin_debug_blob(hs, serial)


def analyze_nav_logs(log_text: str, clip: str, expected_version: str, issues: list[str]) -> dict[str, Any]:
    blob = (log_text or "") + " | " + (clip or "")
    nav: dict[str, Any] = {
        "expectedVersion": expected_version,
        "openUrl": False,
        "badNavApi": [],
        "logcatBytes": len((log_text or "").encode("utf-8")),
        "clipboardBytes": len((clip or "").encode("utf-8")),
    }
    for pat in GOOD_NAV_PATTERNS:
        if re.search(pat, blob, re.I):
            nav["openUrl"] = True
            break
    # Plugin debug ring uses prose like "navigateToGuild openUrl ok".
    if not nav["openUrl"] and re.search(r"navigateToGuild\s+openUrl\s+ok", blob, re.I):
        nav["openUrl"] = True
    for pat in BAD_NAV_PATTERNS:
        if re.search(pat, blob, re.I):
            nav["badNavApi"].append(pat)
            issues.append("wrong_nav_api")
    ver_re = re.compile(r"\[v(\d+\.\d+\.\d+)", re.I)
    ver_re2 = re.compile(r"debug log v(\d+\.\d+\.\d+)", re.I)
    versions = ver_re.findall(blob) + ver_re2.findall(blob)
    nav["versionsInLogs"] = sorted(set(versions))
    if versions and expected_version not in versions:
        issues.append("version_mismatch")
    if not nav["openUrl"]:
        has_clip = bool((clip or "").strip())
        has_log = bool((log_text or "").strip())
        if has_clip or has_log:
            issues.append("openurl_missing")
        else:
            nav["evidenceUnavailable"] = True
            log("nav: no logcat or clipboard evidence")
    return nav


def merge_nav_clipboards(out: Path, clip: str) -> str:
    """Combine post-jump clipboard with any in-run debug captures."""
    parts: list[str] = []
    if clip.strip():
        parts.append(clip.strip())
    for name in ("clipboard_pre_back.txt", "clipboard_jump_fail.txt"):
        p = out / name
        if p.is_file():
            text = p.read_text(encoding="utf-8").strip()
            if text and text not in parts:
                parts.append(text)
    return " | ".join(parts)


def audit_host(
    host: str,
    day_dir: Path,
    *,
    guild_key: str,
    server_name: str,
) -> dict[str, Any]:
    ok, serial_or = reachable(host)
    report: dict[str, Any] = {
        "host": host,
        "serial": serial_or if ok else None,
        "reachable": ok,
        "expectedVersion": plugin_version(),
        "issues": [],
        "artifacts": str(day_dir / host),
        "serverTapped": None,
        "safeGuild": guild_key,
        "safeChannel": None,
        "nav": {},
    }
    if not ok:
        log("%s unreachable — skip (%s)" % (host, serial_or))
        report["skipReason"] = serial_or
        return report

    serial = serial_or
    out = day_dir / host
    out.mkdir(parents=True, exist_ok=True)
    issues: list[str] = report["issues"]

    pkg = resolve_discord_package(serial)
    if not pkg:
        issues.append("discord_missing")
        log("%s no Discord/Revenge package (app.revenge or com.discord)" % host)
        report["issues"] = issues
        return report
    report["discordPackage"] = pkg

    log("%s start serial=%s pkg=%s quiet=1" % (host, serial, pkg))
    clear_logcat(serial)
    set_animations_enabled(serial, False)
    vlm_on = init_vlm(out)

    try:
        with sc.ScreenControlSession(host, label="QSS QA") as session:
            with uid.try_handsets(serial, host) as hs:
                if hs is None:
                    issues.append("handsets_unavailable")

                # Do not force-stop — cold start breaks profile-chip hit targets on p7a.
                launch_discord(serial, pkg)
                if hs is not None:
                    wait_discord_ready(hs, timeout=UI_WAIT_MED)
                    ensure_discord_foreground(serial, pkg, hs)
                shot(serial, out / "00_discord_home.png")
                if vlm_on:
                    vlm_require(
                        vlm_capture(serial, "00_discord_home_vlm.png"),
                        "discord_not_launcher",
                        "discord_home",
                        issues=issues,
                    )

                if hs is not None:
                    dismiss_system_dialogs(hs, session)
                    nav_ok, active_guild, active_ch = navigate_to_safe_guild(
                        hs, session, serial, pkg, guild_key
                    )
                    if not nav_ok:
                        log("nav retry after relaunch for guild %s" % guild_key)
                        launch_discord(serial, pkg)
                        if hs is not None:
                            wait_discord_ready(hs, timeout=UI_WAIT_MED)
                        ensure_discord_foreground(serial, pkg, hs)
                        nav_ok, active_guild, active_ch = navigate_to_safe_guild(
                            hs, session, serial, pkg, guild_key
                        )
                    if nav_ok and not active_ch:
                        active_ch = detect_safe_channel(
                            hs.ui(), active_guild or guild_key
                        )
                    if not nav_ok or not active_ch:
                        issues.append("safe_guild_nav_failed")
                        log(
                            "%s abort — not on a safe channel "
                            "(need #dc-general/#dc-games or #ogden/#college)" % host
                        )
                    else:
                        report["safeGuild"] = active_guild or guild_key
                        report["safeChannel"] = active_ch
                        shot(serial, out / "00b_safe_guild.png")
                        channel_ok = True
                        if vlm_on:
                            channel_ok = vlm_require(
                                vlm_capture(serial, "00b_safe_guild_vlm.png"),
                                "safe_test_channel",
                                "safe_channel",
                                issues=issues,
                            )
                        if not channel_ok:
                            log("safe channel VLM/a11y mismatch — re-navigating")
                            leave_voice_channel(
                                hs, session, serial, pkg, guild_key
                            )
                            nav_ok, active_guild, active_ch = navigate_to_safe_guild(
                                hs, session, serial, pkg, guild_key
                            )
                            if not nav_ok or not active_ch:
                                issues.append("safe_guild_nav_failed")
                            else:
                                report["safeGuild"] = active_guild or guild_key
                                report["safeChannel"] = active_ch
                                if "safe_guild_nav_failed" in issues:
                                    issues.remove("safe_guild_nav_failed")
                                if "vlm_safe_test_channel_failed" in issues:
                                    issues.remove("vlm_safe_test_channel_failed")
                                shot(serial, out / "00b_safe_guild_retry.png")
                                if vlm_on:
                                    vlm_require(
                                        vlm_capture(
                                            serial, "00b_safe_guild_retry_vlm.png"
                                        ),
                                        "safe_test_channel",
                                        "safe_channel_retry",
                                        issues=issues,
                                    )

                opened = False
                nav_ready = (
                    hs is not None
                    and "safe_guild_nav_failed" not in issues
                    and report.get("safeChannel")
                    and "vlm_safe_test_channel_failed" not in issues
                )
                if nav_ready:
                    leave_voice_channel(hs, session, serial, pkg, guild_key)
                    dismiss_system_dialogs(hs, session)
                    # Settings → Open switcher only (slash posts to chat on misfire).
                    opened = open_switcher_via_settings(hs, session)
                    if not opened and os.environ.get("QSS_ALLOW_SLASH") == "1":
                        opened = open_switcher_via_slash(
                            hs, session, serial=serial, issues=issues
                        )
                    if not opened:
                        issues.append("switcher_open_failed")
                        if vlm_cloud is not None:
                            vlm_cloud.write_cloud_vlm_request(
                                out,
                                step="profile_chip",
                                reason="switcher_open_failed",
                                screenshot=out / "00b_safe_guild.png",
                                extra={
                                    "hint": "Profile → Settings → Plugins path failed; "
                                    "cloud VLM can read obstruction (quest bar, voice UI).",
                                },
                            )
                            log(vlm_cloud.suggest_cloud_vlm("switcher_open_failed", step="profile_chip"))

                if nav_ready:
                    shot(serial, out / "01_switcher.png")
                    if vlm_on:
                        vlm_require(
                            vlm_capture(serial, "01_switcher_vlm.png"),
                            "switcher_open",
                            "switcher_open",
                            issues=issues,
                        )
                    if "switcher_open_failed" in issues and vlm_cloud is not None:
                        vlm_cloud.write_cloud_vlm_request(
                            out,
                            step="switcher_open",
                            reason="switcher_not_visible",
                            screenshot=out / "01_switcher.png",
                            extra={"uiDump": "01_switcher_ui.txt"},
                        )
                    if hs is not None:
                        ui = hs.ui()
                        (out / "01_switcher_ui.txt").write_text(ui, encoding="utf-8")
                        w, screen_h = screen_size(serial)
                        assert_switcher_top_docked(hs, issues, screen_h)

                tapped = None
                if nav_ready and hs is not None and "switcher_open_failed" not in issues:
                    hs.tap_text("Dismiss alert", timeout_ms=800)
                    time.sleep(0.3)
                    active_guild = report.get("safeGuild", guild_key)
                    jump_target = server_name or default_jump_server(active_guild)
                    tapped = pick_server_name(
                        hs,
                        jump_target,
                        active_guild,
                        serial=serial,
                        session=session,
                        pkg=pkg,
                        issues=issues,
                        artifact_dir=out,
                    )
                    if not tapped:
                        issues.append("server_tap_failed")
                        clip_fail = copy_plugin_debug_if_visible(hs, serial)
                        if clip_fail:
                            (out / "clipboard_jump_fail.txt").write_text(
                                clip_fail, encoding="utf-8"
                            )
                            log(
                                "jump failed — plugin debug (%d bytes): %s"
                                % (len(clip_fail), clip_fail[:180])
                            )
                    else:
                        report["serverTapped"] = tapped
                        dest_guild = guild_for_jump_name(tapped) or active_guild
                        settled = detect_safe_channel(hs.ui(), dest_guild)
                        if not settled:
                            if ui_switcher_open(hs.ui()):
                                hs.tap_text("Close", timeout_ms=1200) or hs.tap_desc(
                                    "Close switcher", timeout_ms=1000
                                )
                                time.sleep(0.6)
                            elif ui_on_plugin_settings(hs.ui()):
                                back_to_channel_view(hs, session, serial, pkg)
                            settled = settle_on_target_channel(
                                hs,
                                tapped,
                                timeout=15.0,
                                session=session,
                                serial=serial,
                                pkg=pkg,
                            )
                        time.sleep(0.8)
                        shot(serial, out / "02_after_jump.png")
                        if vlm_on:
                            vlm_require(
                                vlm_capture(serial, "02_after_jump_vlm.png"),
                                "safe_test_channel",
                                "post_jump_channel",
                                issues=issues,
                            )
                        post_ch = assert_post_jump_safe(
                            hs,
                            issues,
                            serial=serial,
                            guild_key=dest_guild,
                        )
                        if post_ch:
                            report["postJumpChannel"] = post_ch
                        tapped_name = report.get("serverTapped")
                        if (
                            tapped_name
                            and post_ch
                            and is_cross_guild_jump(active_guild, tapped_name)
                        ):
                            want = expected_channels_for_jump(tapped_name)
                            if post_ch == report.get("safeChannel") or (
                                want and post_ch not in want
                            ):
                                issues.append("jump_no_guild_change")
                                log(
                                    "cross-guild jump to %s — still on #%s "
                                    "(expected one of %s)"
                                    % (
                                        tapped_name,
                                        post_ch,
                                        ",".join(want) if want else "?",
                                    )
                                )
                        nav_clip = collect_debug_via_clipboard(hs, session, serial)
                        if nav_clip:
                            (out / "clipboard_debug.txt").write_text(
                                nav_clip, encoding="utf-8"
                            )
                        assert_overlay_gone(hs, issues)
                        assert_taps_alive(hs, session, issues)

                log_text = logcat_grep(
                    serial, r"QuickSwitcher|openUrl|navigateToGuild|selectChannel"
                )
                (out / "logcat.txt").write_text(log_text, encoding="utf-8")
                clip = ""
                clip_path = out / "clipboard_debug.txt"
                if clip_path.is_file():
                    clip = clip_path.read_text(encoding="utf-8")
                elif hs is not None and report.get("serverTapped"):
                    clip = collect_debug_via_clipboard(hs, session, serial)
                    if clip:
                        clip_path.write_text(clip, encoding="utf-8")
                elif hs is not None and "server_tap_failed" in issues:
                    log("collect_debug: skipped (no successful jump)")
                clip = merge_nav_clipboards(out, clip)
                report["nav"] = analyze_nav_logs(
                    log_text, clip, report["expectedVersion"], issues
                )

    except sc.ScreenControlError as e:
        issues.append("screen_control_failed")
        log("%s screen_control_error: %s" % (host, e))
    except Exception as e:  # noqa: BLE001
        issues.append("audit_exception")
        log("%s exception: %s" % (host, e))
    finally:
        set_animations_enabled(serial, True)

    seen: set[str] = set()
    uniq: list[str] = []
    for i in issues:
        if i not in seen:
            seen.add(i)
            uniq.append(i)
    report["issues"] = uniq
    vlm_flush_report(report)
    report_path = out / "report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    tag = ",".join(uniq) if uniq else "none"
    log("%s done issues=%s report=%s" % (host, tag, report_path))
    return report


def main(argv: list[str] | None = None) -> int:
    if not STAYTURGID_REPO.is_dir():
        sys.stderr.write(
            "stayturgid not found at %s — set STAYTURGID_REPO\n" % STAYTURGID_REPO
        )
        return 2

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "hosts",
        nargs="*",
        help="Fleet alias (default: QSS_DEVICE or p7a)",
    )
    ap.add_argument(
        "--dry-reach",
        action="store_true",
        help="Only check ADB reachability",
    )
    ap.add_argument(
        "--guild",
        choices=tuple(SAFE_GUILDS.keys()),
        default=os.environ.get("QSS_GUILD", "dcs"),
        help="Safe test guild to work in (dcs=Danny Clark's/DCs, lldc=LL/DC)",
    )
    ap.add_argument(
        "--server",
        default=os.environ.get("QSS_SERVER_NAME", ""),
        help="Switcher row to jump (must be Danny Clark's or LL/DC)",
    )
    args = ap.parse_args(argv)
    server_name = args.server.strip() or default_jump_server(args.guild)

    os.environ["STAYTURGID_PRESENCE_QUIET"] = "1"
    os.environ.pop("STAYTURGID_SKIP_PRESENCE", None)

    default_host = os.environ.get("QSS_DEVICE", "p7a")
    hosts = args.hosts or [default_host]

    if args.dry_reach:
        any_fail = False
        for h in hosts:
            ok, detail = reachable(h)
            pkg = resolve_discord_package(detail) if ok else None
            log(
                "%s reach=%s serial=%s discord=%s"
                % (h, ok, detail if ok else detail, pkg or "missing")
            )
            if ok and not pkg:
                any_fail = True
        return 1 if any_fail else 0

    day = dt.datetime.now().strftime("%Y-%m-%d")
    day_dir = ART / day
    day_dir.mkdir(parents=True, exist_ok=True)
    log("qss-qa start hosts=%s version=%s" % (",".join(hosts), plugin_version()))

    any_issues = False
    for host in hosts:
        rep = audit_host(host, day_dir, guild_key=args.guild, server_name=server_name)
        if rep.get("issues"):
            any_issues = True

    log("qss-qa finish assert_fail=%s" % int(any_issues))
    return 1 if any_issues else 0


if __name__ == "__main__":
    sys.exit(main())
