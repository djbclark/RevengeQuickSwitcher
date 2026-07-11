#!/usr/bin/env python3
"""Unattended Quick Server Switcher device QA (D1 Phase 1).

Mirrors stayturgid ``control/bin/gui_audit.py``: one ScreenControlSession, Handsets
primary, screenshots + ``report.json`` per run.

  STAYTURGID_PRESENCE_QUIET=1  — no torch / vibrate / dialogs
  QSS_DEVICE=s24               — fleet alias (default: s24)
  QSS_SERIAL=35261JEHN12374    — override ADB serial (USB preferred when online)
  QSS_GUILD=dcs|lldc           — safe test guild to work in (default: dcs)
  QSS_SERVER_NAME=...          — switcher row to jump (must be Danny Clark's / LL/DC)
  QSS_OPEN=settings            — only settings→Open switcher (slash posts to chat!)
  QSS_VLM=1                    — local UI-TARS vision gates (make vlm-server)
  QSS_VLM_STRICT=1             — block QA actions when VLM server is down
  QSS_SAFE_MODE=1              — never type without VLM + a11y proof (default on)
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
Never runs slash commands in-channel unless ``QSS_ALLOW_SLASH=1``. Switcher opens
via settings → Plugins → **Open switcher**. With ``QSS_SAFE_MODE=1`` (default),
no ``handsets type/fill`` runs on DM threads or without VLM ``before_type`` gate.

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
sys.path.insert(0, str(REPO / "scripts"))
try:
    from load_qss_secrets import load_secrets_env  # noqa: E402

    load_secrets_env()
except ImportError:
    pass

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
import device_screen_lease as dsl  # noqa: E402
import screen_control as sc  # noqa: E402
import ui_driver as uid  # noqa: E402

# DSCL v1 — distinct project slug so stayturgid and QSS do not fight silently.
os.environ.setdefault("DEVICE_SCREEN_CONTROL_PROJECT", "RevengeQuickSwitcher")
os.environ.setdefault("STAYTURGID_SCREEN_PURPOSE", "qss-qa")

sys.path.insert(0, str(REPO / "scripts"))
try:
    import ui_tars_local as vlm  # noqa: E402
except ImportError:
    vlm = None  # type: ignore
try:
    import vlm_cloud  # noqa: E402
except ImportError:
    vlm_cloud = None  # type: ignore
try:
    import ocr_gate  # noqa: E402
except ImportError:
    ocr_gate = None  # type: ignore

_vlm_gate: Any = None
_vlm_dir: Path | None = None
_vlm_records: list[dict[str, Any]] = []
_ocr_gate: Any = None

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


def device_ids_for_lease(host: str, serial: str) -> list[str]:
    """Aliases/serials for DSCL v1 lease matching (see stayturgid screen-control-lease.md)."""
    ids = [host, serial]
    try:
        row = dev.device_row(host)
        if row:
            usb, ts_ip, lan = row
            if usb and usb != "-":
                ids.append(usb)
            if ts_ip and ts_ip != "-":
                ids.append("%s:5555" % ts_ip)
            if lan and lan != "-":
                ids.append("%s:5555" % lan)
    except (OSError, ValueError, TypeError):
        pass
    seen: set[str] = set()
    out: list[str] = []
    for i in ids:
        s = str(i).strip()
        if s and s.lower() not in seen:
            seen.add(s.lower())
            out.append(s)
    return out


def preflight_screen_lease(host: str, serial: str) -> str | None:
    """Return holder summary if another project holds the glass (DSCL v1)."""
    lease = dsl.find_active_lease(*device_ids_for_lease(host, serial))
    if lease and not dsl.ours(lease):
        return dsl.format_holder(lease)
    return None


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
    for attempt in range(3):
        r = subprocess.run(
            ["adb", "-s", serial, "exec-out", "screencap", "-p"],
            capture_output=True,
            timeout=45,
        )
        path.write_bytes(r.stdout or b"")
        if path.stat().st_size > 200 and path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n":
            return
        time.sleep(0.5 if attempt < 2 else 0)


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


def dismiss_blocking_screens(
    hs: uid.HandsetsSession, session: sc.ScreenControlSession | None = None
) -> None:
    """Dismiss modal overlays (e.g. sponsored video, Wordle pill) that block Discord chrome."""
    ui = hs.ui()
    if any(
        m in ui
        for m in ("Visit Advertiser", "Sponsored", "Advertiser", "3:00", "3:01")
    ):
        dismiss_sponsored_video_overlay(hs, session)
    if ui_wordle_quest_prompt(ui):
        dismiss_wordle_quest_prompt(hs, session)
    for _ in range(6):
        ui = hs.ui()
        if dismiss_top_alert(hs, session):
            continue
        if ui_has_button(ui, "Okay") and tap_button_by_label(hs, session, "Okay"):
            time.sleep(0.6)
            continue
        if ui_has_button(ui, "OK") and tap_button_by_label(hs, session, "OK"):
            time.sleep(0.6)
            continue
        if tap_button_by_label(hs, session, "Dismiss alert"):
            time.sleep(0.5)
            continue
        if not ui_has_button(ui, "Okay") and not ui_has_button(ui, "OK"):
            break
    dismiss_system_dialogs(hs, session)


def wait_discord_ready(
    hs: uid.HandsetsSession,
    *,
    timeout: float = UI_WAIT_MED,
    session: sc.ScreenControlSession | None = None,
) -> bool:
    """Discord foreground + bottom bar, channel chrome, or voice view visible."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        dismiss_blocking_screens(hs, session)
        ui = hs.ui()
        if ui_looks_like_discord(ui) and (
            any(", Online" in ln and "Button" in ln for ln in ui.splitlines())
            or "message #" in ui.lower()
            or "chat_input_edit_text" in ui
            or ("disconnect" in ui.lower() and "unmute" in ui.lower())
            or "voice connected" in ui.lower()
        ):
            return True
        time.sleep(UI_POLL)
    log("wait_until timeout: discord_ready")
    return False


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


def safe_mode_enabled() -> bool:
    return os.environ.get("QSS_SAFE_MODE", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def ui_dm_thread(ui: str) -> bool:
    """True when the message composer targets a DM (@user), not a #channel."""
    low = ui.lower()
    if re.search(r"message\s+#", low):
        return False
    if re.search(r"message\s+@", low):
        return True
    for line in ui.splitlines():
        if "chat_input" not in line.lower() and "fill" not in line.lower():
            continue
        if re.search(r'message\s+@', line, re.I):
            return True
    # In-thread: header shows user name without #channel (e.g. kuriboh, Idle, Member List).
    if re.search(r",\s*member list", low) and "message #" not in low:
        if re.search(r"\(channel\)", low) is None and re.search(
            r"message\s+#", low
        ) is None:
            for line in ui.splitlines():
                if "member list" in line.lower() and "#" not in line:
                    if "dc-general" not in line and "dc-games" not in line:
                        if "ogden" not in line and "college" not in line:
                            return True
    return False


def typing_safety_gate(
    hs: uid.HandsetsSession,
    purpose: str,
    text: str,
    *,
    serial: str | None = None,
    issues: list[str] | None = None,
) -> bool:
    """Hard stop before any handsets type/fill — DM surfaces and misfocused fields."""
    ui = hs.ui()
    if ui_dm_thread(ui):
        log(
            "SAFETY: refuse type %r — DM composer active (purpose=%s)"
            % (text[:24], purpose)
        )
        if issues is not None and "safety_dm_thread" not in issues:
            issues.append("safety_dm_thread")
        return False
    if purpose == "switcher_filter" and not ui_switcher_open(ui):
        log("SAFETY: refuse filter type %r — switcher not open" % text[:24])
        if issues is not None and "safety_switcher_closed" not in issues:
            issues.append("safety_switcher_closed")
        return False
    if purpose == "plugin_install" and not (
        "Install a plugin" in ui or "Type in the source URL" in ui
    ):
        log("SAFETY: refuse plugin URL type — install dialog not visible")
        if issues is not None and "safety_not_plugin_install" not in issues:
            issues.append("safety_not_plugin_install")
        return False
    if purpose == "slash_command" and not ui_on_safe_channel(ui):
        log("SAFETY: refuse slash type — not on allowlisted test channel")
        if issues is not None and "safety_not_safe_channel" not in issues:
            issues.append("safety_not_safe_channel")
        return False
    if safe_mode_enabled() and serial and _vlm_gate is None:
        log("SAFETY: refuse type — QSS_SAFE_MODE requires VLM (start UI-TARS)")
        if issues is not None and "safety_vlm_required" not in issues:
            issues.append("safety_vlm_required")
        return False
    if serial and _vlm_gate is not None:
        cap = vlm_capture(
            serial, "pre_type_%s.png" % re.sub(r"\W+", "_", text[:24])
        )
        if not vlm_require(
            cap, "before_type", "type:%s" % text[:40], issues=issues
        ):
            return False
        if purpose == "switcher_filter" and not vlm_require(
            cap, "switcher_open", "switcher_before_type", issues=issues
        ):
            return False
    return True


def composer_draft_text(ui: str) -> str | None:
    """Best-effort read of channel composer draft from Handsets dump."""
    for line in ui.splitlines():
        low = line.lower()
        if "chat_input" not in low and "fill" not in low:
            continue
        lbl = _ui_label(line)
        if lbl and not lbl.startswith("Message "):
            return lbl
        if line.strip().lower().startswith("fill"):
            m = re.search(r'fill\s+\S+\s+"([^"]*)"', line, re.I)
            if m and not m.group(1).startswith("Message "):
                return m.group(1)
    return None


def verify_after_type(
    hs: uid.HandsetsSession,
    serial: str,
    text: str,
    label: str,
    *,
    issues: list[str] | None = None,
    surface: str = "composer",
    purpose: str = "unknown",
) -> bool:
    """Screenshot + a11y check immediately after type/fill — catch //servers-style misfires."""
    ui = hs.ui()
    draft = composer_draft_text(ui) if surface == "composer" else None
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "_", label or text[:24])
    cap = vlm_capture(serial, "after_type_%s.png" % slug)
    log(
        "after_type %s: typed=%r composer=%r"
        % (label, text[:40], (draft[:60] if draft else None))
    )
    if surface == "composer" and draft is not None:
        if "//" in draft and "/" in text:
            log("SAFETY: double-slash in composer after type: %r" % draft)
            if issues is not None and "safety_double_slash" not in issues:
                issues.append("safety_double_slash")
            return False
        if purpose == "slash_command" and draft.startswith("//"):
            log("SAFETY: slash command typo %r — would post to chat" % draft)
            if issues is not None and "safety_slash_typo" not in issues:
                issues.append("safety_slash_typo")
            return False
        if text and text not in draft and not draft.startswith(text.rstrip("/")):
            if len(text) > 1 or text not in ("/",):
                log(
                    "SAFETY: composer mismatch — typed %r, saw %r"
                    % (text[:40], draft[:60])
                )
                if issues is not None and "safety_type_mismatch" not in issues:
                    issues.append("safety_type_mismatch")
                return False
    if cap and _vlm_gate is not None:
        if not vlm_require(cap, "after_type", label or text[:20], issues=issues):
            return False
    return True


def discard_composer_draft(
    hs: uid.HandsetsSession,
    session: sc.ScreenControlSession,
    serial: str,
) -> None:
    """Clear channel composer without sending — recover from slash/type misfires."""
    if not ui_on_safe_channel(hs.ui()) and ui_dm_thread(hs.ui()):
        log("SAFETY: refuse discard_composer_draft on DM thread")
        return
    hs.tap_id("chat_input_edit_text", timeout_ms=1500)
    time.sleep(0.25)
    for _ in range(48):
        session.shell("input", "keyevent", "KEYCODE_DEL")
    time.sleep(0.3)
    unfocus_composer(hs, session)
    cap = vlm_capture(serial, "after_discard_composer.png")
    log("discard_composer_draft: cleared (composer=%r)" % composer_draft_text(hs.ui()))
    if cap and _vlm_gate is not None:
        vlm_require(cap, "after_type", "discard_composer", issues=None)


def tap_ui_line_containing(
    hs: uid.HandsetsSession,
    session: sc.ScreenControlSession,
    needle: str,
) -> bool:
    """Tap a tappable line by coord — avoids tap_text re-typing into composer."""
    for line in hs.ui().splitlines():
        if needle not in line:
            continue
        if "Button" not in line and not line.strip().lower().startswith("tap"):
            continue
        pt = _ui_xy(line)
        if pt:
            session.shell("input", "tap", str(pt[0]), str(pt[1]))
            time.sleep(0.4)
            return True
    return False


def init_vlm(artifact_dir: Path) -> bool:
    """Start cloud or local vision gates for QA verification."""
    global _vlm_gate, _vlm_dir, _vlm_records, _ocr_gate
    _vlm_dir = artifact_dir / "vlm"
    _vlm_dir.mkdir(parents=True, exist_ok=True)
    _vlm_records = []

    # Free OCR gate — always init when tesseract is available.
    _ocr_gate = None
    if ocr_gate is not None and ocr_gate.ocr_available():
        _ocr_gate = ocr_gate.OcrGate()
        log("OCR gate ready (Tesseract)")

    if vlm is None or not vlm.vlm_enabled():
        log("VLM disabled or ui_tars_local missing")
        _vlm_gate = None
        return False

    # Cloud VLM takes priority when configured with valid API keys.
    if vlm_cloud is not None and vlm_cloud.cloud_configured():
        _vlm_gate = vlm_cloud.CloudVlmGate()
        if _vlm_gate.ready:
            log(
                "VLM cloud ready (%s / %s)"
                % (_vlm_gate.provider, _vlm_gate.model)
            )
            return True

    # Local UI-TARS fallback.
    gate = vlm.VlmGate(autostart=True)
    if gate.ready:
        _vlm_gate = gate
        log("VLM UI-TARS-1.5-7B ready (local llama-server)")
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


def ocr_require(
    image_path: Path | None,
    check: str,
    label: str = "",
    *,
    issues: list[str] | None = None,
) -> bool | None:
    """Try fast OCR gate before VLM. Returns True/False if conclusive, None to skip."""
    if _ocr_gate is None or image_path is None or not image_path.is_file():
        return None
    ok, detail = _ocr_gate.verify(image_path, check)
    detail["label"] = label or check
    _vlm_records.append(detail)
    if _vlm_dir is not None:
        safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", "ocr_" + (label or check))
        (_vlm_dir / ("%s.json" % safe)).write_text(
            json.dumps(detail, indent=2), encoding="utf-8"
        )
    if ok:
        log("OCR passed %s (%.2fs)" % (label or check, detail.get("elapsed_s", 0)))
        return True
    if detail.get("confidence", 0) >= 0.3:
        log("OCR blocked %s: matched=%s neg=%s (%.2fs)" % (
            label or check, detail.get("matched"), detail.get("negatives"), detail.get("elapsed_s", 0)))
        msg = "ocr_%s_failed" % check
        if issues is not None and msg not in issues:
            issues.append(msg)
        return False
    return None


def vlm_require(
    image_path: Path | None,
    check: str,
    label: str = "",
    *,
    issues: list[str] | None = None,
) -> bool:
    """Verify screenshot via OCR first (fast/free), then VLM if OCR inconclusive."""
    if image_path is None or not image_path.is_file():
        return True
    ocr_result = ocr_require(image_path, check, label, issues=issues)
    if ocr_result is not None:
        return ocr_result
    if _vlm_gate is None:
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
        if vlm_cloud is not None and vlm_cloud.cloud_configured():
            cloud = vlm_cloud.CloudVlmGate()
            if cloud.ready:
                log("VLM cloud retry for %s (%s)" % (check, cloud.model))
                c_ok, c_detail = cloud.verify(image_path, check)
                c_detail["label"] = (label or check) + "_cloud"
                _vlm_records.append(c_detail)
                if _vlm_dir is not None:
                    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", (label or check) + "_cloud")
                    (_vlm_dir / ("%s.json" % safe)).write_text(
                        json.dumps(c_detail, indent=2), encoding="utf-8"
                    )
                if c_ok:
                    if issues is not None and msg in issues:
                        issues.remove(msg)
                    return True
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
    purpose: str = "unknown",
) -> bool:
    if purpose == "unknown":
        if "Filter" in selector or "filter" in text.lower():
            purpose = "switcher_filter"
        elif "github" in text.lower() or text.startswith("http"):
            purpose = "plugin_install"
    if not typing_safety_gate(
        hs, purpose, text, serial=serial, issues=issues
    ):
        return False
    r = hs.hs("fill", selector, text, timeout=20)
    if r.returncode != 0:
        return False
    if serial:
        surface = (
            "filter"
            if purpose == "switcher_filter"
            else "composer"
            if purpose in ("slash_command", "unknown")
            else "any"
        )
        if not verify_after_type(
            hs,
            serial,
            text,
            "fill:%s" % text[:20],
            issues=issues,
            surface=surface,
            purpose=purpose,
        ):
            return False
    return True


def handsets_type_safe(
    hs: uid.HandsetsSession,
    text: str,
    *,
    serial: str | None = None,
    issues: list[str] | None = None,
    purpose: str = "switcher_filter",
) -> bool:
    if not typing_safety_gate(
        hs, purpose, text, serial=serial, issues=issues
    ):
        return False
    if not handsets_type(hs, text):
        return False
    if serial:
        surface = "filter" if purpose == "switcher_filter" else "composer"
        if not verify_after_type(
            hs,
            serial,
            text,
            "type:%s" % text[:20],
            issues=issues,
            surface=surface,
            purpose=purpose,
        ):
            return False
    return True


def reveal_bottom_nav_bar(
    hs: uid.HandsetsSession, session: sc.ScreenControlSession
) -> None:
    """Discord hides the bottom profile strip while chat is scrolled — reveal it."""
    ui = hs.ui()
    if "Danny, Online" in ui or "Danny, Idle" in ui or "Show Settings Drawer" in ui:
        return
    if not ui_in_channel_chat(ui):
        return
    unfocus_composer(hs, session)
    w, h = screen_size(session.serial)
    # Scroll chat upward so the bottom bar (profile chip) is exposed.
    for y1, y2 in ((0.55, 0.78), (0.45, 0.72)):
        session.shell(
            "input",
            "swipe",
            str(int(w * 0.5)),
            str(int(h * y1)),
            str(int(w * 0.5)),
            str(int(h * y2)),
            "280",
        )
        time.sleep(0.35)
        if "Danny, Online" in hs.ui() or "Danny, Idle" in hs.ui():
            return
    if hs.tap_text("Jump To Present", timeout_ms=800):
        time.sleep(0.4)


def _profile_sheet_open(ui: str) -> bool:
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
    # Revenge profile sheet — top-right Settings tab (S24) without "User Settings" row.
    return "Edit Profile" in ui and re.search(
        r'Button\s+"Settings"\s+\d+,\d+', ui
    ) is not None


def _after_profile_tap(
    hs: uid.HandsetsSession, session: sc.ScreenControlSession | None = None
) -> bool:
    time.sleep(0.9)
    if session is not None:
        dismiss_system_dialogs(hs, session)
    return _profile_sheet_open(hs.ui())


def tap_profile_chip(
    hs: uid.HandsetsSession, session: sc.ScreenControlSession | None = None
) -> bool:
    """Open profile sheet via footer name row (not the server-list button coords)."""
    if session is not None:
        prepare_profile_access(hs, session)
    ui = hs.ui()
    if (
        session is not None
        and "Danny, Online" not in ui
        and "Danny, Idle" not in ui
        and "Show Settings Drawer" not in ui
    ):
        reveal_bottom_nav_bar(hs, session)
        ui = hs.ui()
    if hs.tap_desc("Show Settings Drawer", timeout_ms=2500) or hs.tap_text(
        "Show Settings Drawer", timeout_ms=2000
    ):
        if _after_profile_tap(hs, session):
            return True
    w, h = screen_size(session.serial) if session is not None else (1080, 2340)
    chip_max_y = int(h * 0.90)
    for line in ui.splitlines():
        if "Button" not in line:
            continue
        label = _ui_label(line) or ""
        if label not in ("Danny, Online", "Danny, Idle") and not label.startswith(
            "Danny,"
        ):
            continue
        pt = _ui_xy(line)
        if pt and pt[1] > chip_max_y and session is not None:
            session.shell("input", "tap", str(pt[0]), str(pt[1]))
            if _after_profile_tap(hs, session):
                return True
    if session is not None and _tap_danny_profile_text(hs, session):
        if _after_profile_tap(hs, session):
            return True
    if hs.tap_text("Danny, Online", timeout_ms=3000) or hs.tap_text(
        "Danny, Idle", timeout_ms=2000
    ):
        if _after_profile_tap(hs, session):
            return True
    ui = hs.ui()
    for line in ui.splitlines():
        if "TextView" not in line or "Danny" not in line or "Online" in line:
            continue
        pt = _ui_xy(line)
        if pt and pt[1] > chip_max_y and pt[0] < 400:
            if hs.hs("tap", str(pt[0]), str(pt[1]), timeout=10).returncode == 0:
                if _after_profile_tap(hs, session):
                    return True
    ui = hs.ui()
    for line in ui.splitlines():
        if "Button" not in line or "Danny, Online" not in line:
            continue
        pt = _ui_xy(line)
        if not pt or pt[1] < chip_max_y:
            continue
        if hs.hs("tap", str(pt[0]), str(pt[1]), timeout=10).returncode == 0:
            if _after_profile_tap(hs, session):
                return True
    if session is not None:
        dismiss_emoji_panels(hs, session)
        if ui_in_channel_chat(hs.ui()):
            unfocus_composer(hs, session)
        time.sleep(0.3)
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
                    if _after_profile_tap(hs, session):
                        return True
        m = re.search(r'"([^"]+)"', line)
        if m and hs.tap_text(m.group(1), timeout_ms=3000):
            if _after_profile_tap(hs, session):
                return True
    for label in ("You", "Account"):
        if hs.tap_desc(label, timeout_ms=2000) or hs.tap_text(label, timeout_ms=2000):
            if _after_profile_tap(hs, session):
                return True
    return False


def quest_bar_blocks_profile(hs: uid.HandsetsSession) -> bool:
    """Quest/promo strip covers the bottom profile chip (common on S24)."""
    return ui_quest_overlay(hs.ui()) and not _profile_sheet_open(hs.ui())


def dismiss_system_dialogs(
    hs: uid.HandsetsSession, session: sc.ScreenControlSession | None = None
) -> None:
    """Dismiss Android runtime permission / grant dialogs that block Discord taps."""
    for _ in range(6):
        ui = hs.ui()
        if dismiss_top_alert(hs, session):
            time.sleep(0.6)
            continue
        if ui_has_button(ui, "Okay") and tap_button_by_label(hs, session, "Okay"):
            time.sleep(0.6)
            continue
        if ui_has_button(ui, "OK") and tap_button_by_label(hs, session, "OK"):
            time.sleep(0.6)
            continue
        if "Discard your feedback?" in ui:
            if hs.tap_text("Discard", timeout_ms=1200) or hs.tap_desc(
                "Discard", timeout_ms=1000
            ):
                time.sleep(0.7)
                continue
            if session is not None:
                session.shell("input", "keyevent", "KEYCODE_BACK")
                time.sleep(0.6)
                continue
        if "Send feedback to Google" in ui or "Close Feedback" in ui:
            if hs.tap_desc("Close Feedback", timeout_ms=1200) or hs.tap_text(
                "Close Feedback", timeout_ms=1000
            ):
                time.sleep(0.6)
                continue
            if session is not None:
                session.shell("input", "keyevent", "KEYCODE_BACK")
                time.sleep(0.6)
                continue
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
            dismiss_keyboard(session, hs)
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
    ui = hs.ui()
    if ui_in_user_settings(ui):
        return True
    if not tap_profile_chip(hs, session):
        return False
    if not wait_until(
        lambda: (
            "User Settings" in hs.ui()
            or "Set Status" in hs.ui()
            or "Switch Accounts" in hs.ui()
            or "Edit Profile" in hs.ui()
            or "Settings" in hs.ui()
            or ui_in_user_settings(hs.ui())
        ),
        timeout=UI_WAIT_SHORT,
        label="profile_sheet",
    ):
        return False
    ui = hs.ui()
    if ui_in_user_settings(ui):
        return True
    for line in ui.splitlines():
        if "Button" not in line or _ui_label(line) != "Settings":
            continue
        pt = _ui_xy(line)
        if pt and pt[1] < 400 and session is not None:
            session.shell("input", "tap", str(pt[0]), str(pt[1]))
            time.sleep(0.8)
            if ui_in_user_settings(hs.ui()):
                return True
    if hs.tap_text("User Settings", timeout_ms=2500) or hs.tap_desc(
        "User Settings", timeout_ms=2000
    ) or hs.tap_text("Settings", timeout_ms=2500) or hs.tap_desc(
        "Settings", timeout_ms=2000
    ):
        wait_until(
            lambda: ui_in_user_settings(hs.ui()),
            timeout=UI_WAIT_SHORT,
            label="user_settings_open",
        )
        return ui_in_user_settings(hs.ui())
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
    if ui_shows_server_sidebar(hs.ui()) and not ui_in_channel_chat(hs.ui()):
        return
    w, h = screen_size(session.serial)
    session.shell(
        "input", "swipe", str(int(w * 0.5)), str(int(h * 0.55)), str(int(w * 0.5)), str(int(h * 0.25)), "350"
    )
    time.sleep(0.4)
    for label in ("Dismiss", "Not now", "Skip", "Close"):
        if hs.tap_text(label, timeout_ms=800):
            time.sleep(0.4)


def ui_quest_overlay(ui: str) -> bool:
    return any(
        m in ui
        for m in (
            "Quest Bar",
            "Watch 3m",
            "Get Reward!",
            "Unlock 1.2x",
            "Watch to earn rewards",
            "How's Wordle",
            "Hows Wordle",
            "Wordle go",
        )
    )


WORDLE_PROMPT_MARKERS = ("How's Wordle", "Hows Wordle", "Wordle go?")


def ui_wordle_quest_prompt(ui: str) -> bool:
    return any(m in ui for m in WORDLE_PROMPT_MARKERS)


def _wordle_prompt_close_coords(serial: str) -> tuple[int, int]:
    """X on the Wordle activity pill — right of \"How's Wordle go?\" (S24 1080×2340)."""
    return _wordle_prompt_close_coord_candidates(serial)[0]


def _sponsored_overlay_close_coords(serial: str) -> tuple[int, int]:
    """Top-left X on sponsored in-app video overlays (often missing from Handsets dump)."""
    w, h = screen_size(serial)
    return int(w * 0.07), int(h * 0.09)


def _wordle_prompt_close_coord_candidates(serial: str) -> tuple[tuple[int, int], ...]:
    w, h = screen_size(serial)
    # Pill is bottom-center; X is on the right edge of the pill (not screen edge).
    return (
        (int(w * 0.72), int(h * 0.968)),
        (int(w * 0.68), int(h * 0.965)),
        (int(w * 0.76), int(h * 0.962)),
    )


def dismiss_sponsored_video_overlay(
    hs: uid.HandsetsSession,
    session: sc.ScreenControlSession | None,
    *,
    force: bool = False,
) -> bool:
    """Close sponsored video card — large X in the top-left."""
    if session is None:
        return False
    ui = hs.ui()
    if not force and not any(
        m in ui
        for m in ("Visit Advertiser", "Sponsored", "Advertiser", "3:00", "3:01")
    ):
        return False
    x, y = _sponsored_overlay_close_coords(session.serial)
    log("dismiss_sponsored_video_overlay: tap top-left X at %d,%d" % (x, y))
    session.shell("input", "tap", str(x), str(y))
    time.sleep(0.7)
    return True


def _close_control_right_of_text(
    ui: str, *text_markers: str, y_slop: int = 120, min_x_gap: int = 80
) -> tuple[int, int] | None:
    """Find a close/X control to the right of prompt text (Handsets dump)."""
    anchor_x: int | None = None
    anchor_y: int | None = None
    for marker in text_markers:
        for line in ui.splitlines():
            if marker not in line:
                continue
            pt = _ui_xy(line)
            if pt:
                anchor_x, anchor_y = pt
                break
        if anchor_y is not None:
            break
    if anchor_y is None:
        return None
    best: tuple[int, int, int] | None = None
    for line in ui.splitlines():
        if not any(k in line for k in ("Button", "ImageButton")):
            continue
        pt = _ui_xy(line)
        if not pt:
            continue
        x, y = pt
        if abs(y - anchor_y) > y_slop:
            continue
        if x <= (anchor_x or 0) + min_x_gap:
            continue
        lbl = (_ui_label(line) or "").lower()
        score = x
        if lbl in ("close", "dismiss", "x") or "close" in lbl:
            score += 10_000
        if "ImageButton" in line and not lbl:
            score += 5_000
        if best is None or score > best[0]:
            best = (score, x, y)
    if best is None:
        return None
    return best[1], best[2]


def dismiss_wordle_quest_prompt(
    hs: uid.HandsetsSession, session: sc.ScreenControlSession | None
) -> bool:
    """Dismiss Wordle activity pill — tap X to the right of \"How's Wordle go?\"."""
    if session is None:
        return False
    ui = hs.ui()
    on_safe = ui_on_safe_channel(ui)
    if not ui_wordle_quest_prompt(ui) and not (
        on_safe and "Quest Bar" in ui and ui_quest_overlay(ui)
    ):
        return False
    if ui_dm_thread(ui) and not on_safe:
        log(
            "dismiss_wordle_quest_prompt: skip coord tap on DM thread "
            "(navigate to safe channel first)"
        )
        return False
    pt = _close_control_right_of_text(ui, *WORDLE_PROMPT_MARKERS)
    if pt is None:
        pt = _wordle_prompt_close_coords(session.serial)
        log(
            "dismiss_wordle_quest_prompt: coord X at %d,%d (pill often absent from a11y)"
            % pt
        )
    else:
        log("dismiss_wordle_quest_prompt: tap close at %d,%d" % pt)
    session.shell("input", "tap", str(pt[0]), str(pt[1]))
    time.sleep(0.6)
    return True


def prepare_profile_access(
    hs: uid.HandsetsSession, session: sc.ScreenControlSession
) -> None:
    """Quest/emoji/chrome cleanup before tapping the profile chip."""
    ui = hs.ui()
    if ui_shows_server_sidebar(ui) and (
        "Danny, Online" in ui or "Danny, Idle" in ui or "Show Settings Drawer" in ui
    ):
        dismiss_quest_overlay(hs, session)
        return
    if ui_keyboard_or_ime_visible(ui):
        dismiss_emoji_keyboard(hs, session)
    reveal_bottom_nav_bar(hs, session)
    dismiss_quest_overlay(hs, session)
    if ui_keyboard_or_ime_visible(hs.ui()):
        dismiss_emoji_keyboard(hs, session)


def _tap_midscreen_promo_dismiss(
    hs: uid.HandsetsSession, session: sc.ScreenControlSession
) -> bool:
    """Dismiss in-chat promo banner (Handsets: Button \"Dismiss\" around y=1100–1700)."""
    for line in hs.ui().splitlines():
        if "Button" not in line or _ui_label(line) != "Dismiss":
            continue
        pt = _ui_xy(line)
        if not pt or not (900 < pt[1] < 1900):
            continue
        session.shell("input", "tap", str(pt[0]), str(pt[1]))
        time.sleep(0.5)
        return True
    return False


def _tap_danny_profile_text(
    hs: uid.HandsetsSession, session: sc.ScreenControlSession
) -> bool:
    """Tap footer name TextView above quest bar (S24: Danny ~247,2206)."""
    _w, h = screen_size(session.serial)
    danny_min_y = int(h * 0.92)
    for line in hs.ui().splitlines():
        if "TextView" not in line or _ui_label(line) != "Danny":
            continue
        pt = _ui_xy(line)
        if pt and pt[1] > danny_min_y and pt[0] < 400:
            session.shell("input", "tap", str(pt[0]), str(pt[1]))
            time.sleep(0.5)
            return True
    return False


def _tap_quest_bar_more(
    hs: uid.HandsetsSession, session: sc.ScreenControlSession
) -> bool:
    """Tap the quest strip's More control (S24: collapses bar; text tap hits wrong More)."""
    ui = hs.ui()
    if "Quest Bar" not in ui:
        return False
    for line in ui.splitlines():
        if "Button" not in line or _ui_label(line) != "More":
            continue
        pt = _ui_xy(line)
        if pt and pt[1] > 1800:
            session.shell("input", "tap", str(pt[0]), str(pt[1]))
            time.sleep(0.5)
            return True
    w, h = screen_size(session.serial)
    session.shell("input", "tap", str(int(w * 0.7)), str(int(h * 0.925)))
    time.sleep(0.5)
    return True


def _dismiss_top_quest_strip(
    hs: uid.HandsetsSession, session: sc.ScreenControlSession
) -> bool:
    """Dismiss quest promo docked at the top of the channel view (S24)."""
    ui = hs.ui()
    if not any(m in ui for m in ("Watch 3m", "Get Reward!", "Unlock 1.2x", "Watch to earn")):
        return False
    pt = _close_control_right_of_text(
        ui, "Watch 3m", "Get Reward!", "Unlock 1.2x", y_slop=80, min_x_gap=40
    )
    if pt is None:
        for line in ui.splitlines():
            if not any(m in line for m in ("Watch 3m", "Get Reward!", "Unlock 1.2x")):
                continue
            anchor = _ui_xy(line)
            if not anchor or anchor[1] > 500:
                continue
            pt = _close_control_right_of_text(
                ui, "Watch 3m", "Get Reward!", "Unlock 1.2x", y_slop=80, min_x_gap=40
            )
            break
    if pt is None or pt[1] > 500:
        return False
    log("dismiss_top_quest_strip: tap at %d,%d" % pt)
    session.shell("input", "tap", str(pt[0]), str(pt[1]))
    time.sleep(0.6)
    return True


def dismiss_quest_overlay(
    hs: uid.HandsetsSession, session: sc.ScreenControlSession
) -> None:
    """Collapse Discord quest/promo bar that covers the profile chip."""
    ui = hs.ui()
    if any(
        m in ui
        for m in ("Visit Advertiser", "Sponsored", "Advertiser", "3:00", "3:01")
    ):
        dismiss_sponsored_video_overlay(hs, session)
    _dismiss_top_quest_strip(hs, session)
    dismiss_wordle_quest_prompt(hs, session)
    _tap_midscreen_promo_dismiss(hs, session)
    for _ in range(5):
        ui = hs.ui()
        if not ui_quest_overlay(ui):
            return
        if _tap_quest_bar_more(hs, session):
            time.sleep(0.5)
            dismiss_wordle_quest_prompt(hs, session)
            _tap_midscreen_promo_dismiss(hs, session)
            if not ui_quest_overlay(hs.ui()):
                return
        if ui_has_button(hs.ui(), "Okay") and tap_button_by_label(
            hs, session, "Okay"
        ):
            time.sleep(0.5)
            if not ui_quest_overlay(hs.ui()):
                return
            continue
        if _tap_midscreen_promo_dismiss(hs, session):
            continue
        if hs.tap_text("Dismiss", timeout_ms=1000):
            time.sleep(0.5)
            continue
        w, h = screen_size(session.serial)
        # Tap channel header to steal focus from quest strip.
        session.shell("input", "tap", str(int(w * 0.5)), str(int(h * 0.12)))
        time.sleep(0.4)
        # Swipe quest strip down.
        session.shell(
            "input",
            "swipe",
            str(int(w * 0.5)),
            str(int(h * 0.92)),
            str(int(w * 0.5)),
            str(int(h * 0.99)),
            "300",
        )
        time.sleep(0.45)
        if not ui_quest_overlay(hs.ui()):
            return
        unfocus_composer(hs, session)
        time.sleep(0.3)


def dismiss_emoji_keyboard(
    hs: uid.HandsetsSession, session: sc.ScreenControlSession
) -> None:
    """Close emoji/GIF panel or soft keyboard covering the profile chip."""
    ui = hs.ui()
    if not ui_keyboard_or_ime_visible(ui):
        return
    if any(
        m in ui for m in ("Find the perfect emoji", "GIFs", "Stickers", "Emoji")
    ):
        for line in ui.splitlines():
            if "Toggle emoji keyboard" not in line:
                continue
            pt = _ui_xy(line)
            if pt:
                session.shell("input", "tap", str(pt[0]), str(pt[1]))
                time.sleep(0.5)
                break
    dismiss_keyboard(session, hs)
    if "Toggle emoji keyboard" in hs.ui():
        for line in hs.ui().splitlines():
            if "Toggle emoji keyboard" not in line:
                continue
            pt = _ui_xy(line)
            if pt:
                session.shell("input", "tap", str(pt[0]), str(pt[1]))
                time.sleep(0.4)
                break


def dismiss_emoji_panels(
    hs: uid.HandsetsSession, session: sc.ScreenControlSession
) -> None:
    """Close sticker/emoji/attachment overlays that block navigation taps."""
    for _ in range(3):
        ui = hs.ui()
        if "Filter servers" in ui:
            return
        if not any(
            m in ui
            for m in (
                "Bottom sheet backdrop",
                "Yantra Launcher",
                "emoji",
                "Emoji",
                "Stickers",
                "GIF",
                "chat_input_emoji",
                "Photos",
                "Poll",
                "Files",
            )
        ):
            break
        if hs.tap_desc("Back", timeout_ms=800) or hs.tap_text("Back", timeout_ms=600):
            time.sleep(0.4)
            continue
        unfocus_composer(hs, session)
        dismiss_keyboard(session, hs)
        time.sleep(0.4)


def ui_keyboard_or_ime_visible(ui: str) -> bool:
    """True when the chat composer or emoji panel likely has focus."""
    if any(
        m in ui
        for m in ("Find the perfect emoji", "GIFs", "Stickers", "Emoji", "Toggle emoji keyboard")
    ):
        return True
    for line in ui.splitlines():
        low = line.lower()
        if "chat_input" in line and "fill" in low:
            return True
    return False


def dismiss_keyboard(
    session: sc.ScreenControlSession, hs: uid.HandsetsSession | None = None
) -> None:
    """Hide soft keyboard — never BACK out of Discord from the server sidebar."""
    if hs is not None:
        ui = hs.ui()
        if not ui_keyboard_or_ime_visible(ui) and not ui_in_channel_chat(ui):
            return
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


def ui_has_button(ui: str, label: str) -> bool:
    """True when a Button line's quoted label equals `label` (not substring in chat)."""
    for line in ui.splitlines():
        if "Button" in line and _ui_label(line) == label:
            return True
    return False


def tap_button_by_label(
    hs: uid.HandsetsSession,
    session: sc.ScreenControlSession | None,
    label: str,
    *,
    min_y: int | None = None,
    max_y: int | None = None,
) -> bool:
    """Tap a Button whose quoted accessibility label equals `label`."""
    for line in hs.ui().splitlines():
        if "Button" not in line:
            continue
        if _ui_label(line) != label:
            continue
        pt = _ui_xy(line)
        if not pt:
            continue
        if min_y is not None and pt[1] < min_y:
            continue
        if max_y is not None and pt[1] > max_y:
            continue
        if session is not None:
            session.shell("input", "tap", str(pt[0]), str(pt[1]))
        elif not (hs.tap_text(label, timeout_ms=1200) or hs.tap_desc(label, timeout_ms=1000)):
            return False
        time.sleep(0.35)
        return True
    return bool(hs.tap_text(label, timeout_ms=1500) or hs.tap_desc(label, timeout_ms=1200))


def dismiss_top_alert(
    hs: uid.HandsetsSession, session: sc.ScreenControlSession | None
) -> bool:
    """Dismiss the thin alert strip at the top of Revenge (Handsets: Button \"Dismiss\" y<250)."""
    for line in hs.ui().splitlines():
        if "Button" not in line:
            continue
        lbl = _ui_label(line)
        if lbl not in ("Dismiss alert", "Dismiss"):
            continue
        pt = _ui_xy(line)
        if not pt or pt[1] > 280:
            continue
        if session is not None:
            session.shell("input", "tap", str(pt[0]), str(pt[1]))
            time.sleep(0.4)
            return True
    return bool(
        hs.tap_text("Dismiss alert", timeout_ms=1200)
        or hs.tap_desc("Dismiss alert", timeout_ms=1000)
    )


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


QSS_INSTALL_URL = os.environ.get(
    "QSS_INSTALL_URL",
    "https://raw.githubusercontent.com/djbclark/RevengeQuickSwitcher/main/",
)


def install_qss_plugin(
    hs: uid.HandsetsSession,
    session: sc.ScreenControlSession,
    serial: str,
    pkg: str,
) -> bool:
    """Install QSS from raw URL when the Plugins list is empty (unproxied Continue flow)."""
    if not ensure_discord_foreground(serial, pkg, hs):
        return False
    dismiss_quest_overlay(hs, session)
    dismiss_emoji_panels(hs, session)
    unfocus_composer(hs, session)
    dismiss_system_dialogs(hs, session)
    open_server_list(hs, session, serial, pkg)
    reveal_bottom_nav_bar(hs, session)
    if not open_user_settings(hs, session):
        log("install_qss_plugin: could not open user settings")
        return False
    if not tap_plugins_settings(hs, session):
        log("install_qss_plugin: could not open Plugins list")
        return False
    ui = hs.ui()
    if "Quick Server Switcher" in ui:
        log("install_qss_plugin: already installed")
        return True
    if not ui_plugins_empty(ui):
        log("install_qss_plugin: Plugins list not empty but QSS missing")
        return False
    if not hs.tap_text("Install a plugin", timeout_ms=3500):
        log("install_qss_plugin: Install a plugin button not found")
        return False
    time.sleep(0.9)
    url = QSS_INSTALL_URL.rstrip("/") + "/"
    adb_shell(serial, "cmd", "clipboard", "set", url)
    time.sleep(0.25)
    if not hs.tap_text("Import from clipboard", timeout_ms=3000):
        handsets_fill(
            hs,
            "EditText",
            url,
            serial=serial,
            purpose="plugin_install",
        )
    time.sleep(0.5)
    if not hs.tap_text("Install", timeout_ms=3500):
        log("install_qss_plugin: Install confirm not found")
        return False
    time.sleep(1.2)
    for label in ("Continue", "OK", "Okay", "Allow", "Install"):
        if hs.tap_text(label, timeout_ms=2500):
            log("install_qss_plugin: tapped %s on install dialog" % label)
            time.sleep(2.0)
    for attempt in range(15):
        time.sleep(2)
        ui = hs.ui()
        if "Quick Server Switcher" in ui:
            log("install_qss_plugin: Quick Server Switcher appeared (attempt %d)" % (attempt + 1))
            hs.tap_text("Quick Server Switcher", timeout_ms=3000)
            time.sleep(0.8)
            return True
        hs.tap_text("Dismiss alert", timeout_ms=800)
        if not ui_plugins_empty(ui) and attempt > 3:
            log("install_qss_plugin: plugins list changed but QSS not listed")
            break
    ok = "Quick Server Switcher" in hs.ui()
    if not ok:
        log("install_qss_plugin: failed — enable manually on device")
    return ok


def ui_plugins_empty(ui: str) -> bool:
    """Revenge Plugins list with no plugins installed yet."""
    return "Nothing to see here" in ui and "Install a plugin" in ui


def ui_on_direct_messages_home(ui: str) -> bool:
    """DM list / Friends home — sidebar visible but no guild channel list yet."""
    low = ui.lower()
    if "direct messages" not in low:
        return False
    if "(direct message)" in low or "add friends" in low:
        return True
    return False


def ui_in_voice_channel(ui: str) -> bool:
    """True when voice UI blocks navigation (not merely connected in sidebar)."""
    low = ui.lower()
    # Text channel composer visible — safe to navigate even if voice is connected.
    if re.search(r"message\s+#", low):
        return False
    for ch in SAFE_CHANNELS:
        esc = re.escape(ch)
        if re.search(r"%s,\s*member list" % esc, low):
            return False
        if re.search(r"\"%s\"\s+.*member list" % esc, low):
            return False
    if "disconnect" in low and any(
        m in low
        for m in (
            "unmute",
            "turn camera",
            "share your screen",
            "open soundboard",
        )
    ):
        return True
    if "show chat" in low and "unmute" in low:
        return True
    if "stream room" in low and "voice channel" in low:
        if re.search(r"member list", low):
            return False
        return True
    voice_markers = (
        "voice connected",
        "join voice",
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
    ui = hs.ui()
    if ui_on_safe_channel(ui):
        return
    if not ui_in_voice_channel(ui):
        return
    log("voice channel open — leaving for text channel")
    if hs.tap_text("Show Chat", timeout_ms=1500) or hs.tap_desc("Show Chat", timeout_ms=1200):
        time.sleep(0.8)
        if not ui_in_voice_channel(hs.ui()):
            ensure_discord_foreground(serial, pkg, hs)
            return
    for _ in range(4):
        ui = hs.ui()
        if not ui_in_voice_channel(ui):
            break
        if hs.tap_text("Disconnect", timeout_ms=1500) or hs.tap_desc(
            "Disconnect", timeout_ms=1200
        ):
            time.sleep(0.8)
            continue
        if hs.tap_text("Minimize", timeout_ms=1200) or hs.tap_desc(
            "Minimize", timeout_ms=1000
        ):
            time.sleep(0.6)
            continue
        if hs.tap_desc("Back", timeout_ms=1000) or hs.tap_text("Back", timeout_ms=800):
            time.sleep(0.6)
            continue
        session.shell("input", "keyevent", "KEYCODE_BACK")
        time.sleep(0.5)
    ensure_discord_foreground(serial, pkg, hs)
    if detect_safe_channel(hs.ui(), guild_key):
        return
    ok, _ch = open_safe_channel(hs, guild_key)
    if not ok:
        open_server_list(hs, session, serial, pkg)
        open_safe_channel(hs, guild_key)


def detect_safe_channel(ui: str, guild_key: str | None = None) -> str | None:
    """Return the active safe channel name, or None (never bare #general)."""
    low = ui.lower()
    order: tuple[str, ...]
    if guild_key:
        order = safe_channels_for_guild(guild_key)
    else:
        order = SAFE_CHANNELS
    for ch in order:
        esc = re.escape(ch)
        if re.search(r"%s,\s*member list" % esc, low):
            return ch
        if re.search(r"\"%s\"\s+.*member list" % esc, low):
            return ch
    if ui_in_voice_channel(ui):
        return None
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
        ui = hs.ui()
        for ch in channels:
            for line in ui.splitlines():
                if "text channel" not in line.lower() or ch not in line:
                    continue
                pt = _ui_xy(line)
                if pt and pt[1] > 0:
                    if hs.hs("tap", str(pt[0]), str(pt[1]), timeout=10).returncode == 0:
                        for _ in range(8):
                            time.sleep(0.5)
                            found = detect_safe_channel(hs.ui(), guild_key)
                            if found:
                                return True, found
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
        "Log Out",
        "Install a plugin",
        "Nothing to see here",
        "Show Chat",
        "Disconnect",
        "Voice Connected",
    )
    return any(m in ui for m in markers)


def ui_foreign_app(ui: str) -> bool:
    """Clipboard managers and other apps that steal focus during QA."""
    return any(
        m in ui
        for m in (
            "Clip History",
            "Octoclip",
            "navigation_clip",
            "Search Clip History",
            "BuiltIn Alias",
        )
    )


def ui_in_user_settings(ui: str) -> bool:
    if "Log Out" in ui or "Account" in ui:
        return True
    return find_plugins_row(ui) is not None


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
    if hs is not None and ui_foreign_app(hs.ui()):
        log("foreign app detected (e.g. Clips) — relaunching %s" % pkg)
        launch_discord(serial, pkg)
        time.sleep(1.2)
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
    low = ui.lower()
    if "message #" in low or "chat_input_edit_text" in ui:
        return True
    if "bottom sheet backdrop" in ui:
        return True
    if re.search(r",\s*member list", low):
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
    """From channel chat, reveal the server icon column."""
    ensure_discord_foreground(serial, pkg, hs)
    ui = hs.ui()
    if not ui_in_channel_chat(ui) and ui_shows_server_sidebar(ui):
        return True

    w, h = screen_size(serial)
    # Prefer edge swipe — header Back can leave Discord entirely on S24.
    session.shell(
        "input", "swipe", "5", str(int(h * 0.5)), str(int(w * 0.78)), str(int(h * 0.5)), "450"
    )
    if wait_until(
        lambda: ui_shows_server_sidebar(hs.ui()) and not ui_in_channel_chat(hs.ui()),
        timeout=UI_WAIT_SHORT,
        label="sidebar_after_swipe",
    ):
        return True

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
    if not tapped and foreground_is_discord(serial):
        session.shell("input", "tap", "73", "191")
    if wait_until(
        lambda: ui_shows_server_sidebar(hs.ui()) and not ui_in_channel_chat(hs.ui()),
        timeout=UI_WAIT_SHORT,
        label="sidebar_after_back",
    ):
        return True

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
        for name in needles:
            if len(name) >= 8 and (
                hs.tap_text(name, timeout_ms=2500)
                or hs.tap_desc(name, timeout_ms=2000)
            ):
                time.sleep(0.8)
                return True
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
                session.shell("input", "tap", str(pt[0]), str(pt[1]))
                time.sleep(0.8)
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

    ui = hs.ui()
    if ui_on_direct_messages_home(ui) or (
        ui_shows_server_sidebar(ui)
        and not ui_lists_safe_channel(ui, guild_key)
        and not ui_in_channel_chat(ui)
    ):
        if tap_sidebar_guild(hs, session, serial, pkg, guild_key):
            wait_until(
                lambda: ui_lists_safe_channel(hs.ui(), guild_key)
                or detect_safe_channel(hs.ui(), guild_key) is not None,
                timeout=UI_WAIT_SHORT,
                label="guild_channel_list_%s" % guild_key,
            )
            for _ in range(4):
                ok, ch = open_safe_channel(hs, guild_key)
                if ok:
                    log("safe channel #%s on guild %s (DM home → guild)" % (ch, guild_key))
                    return True, guild_key, ch
                hs.swipe("up")
                time.sleep(0.6)

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

    if tap_sidebar_guild(hs, session, serial, pkg, guild_key):
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
        label="guild_channel_list_%s_retry" % guild_key,
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


def _on_screen(pt: tuple[int, int] | None, serial: str | None, slack: int = 0) -> bool:
    """True when a coordinate pair falls within the visible screen area."""
    if pt is None:
        return False
    w, h = screen_size(serial) if serial else (1080, 2340)
    return slack <= pt[0] < w - slack and slack <= pt[1] < h + max(slack, 0)


def scroll_settings_toward_top(
    hs: uid.HandsetsSession,
    session: sc.ScreenControlSession | None = None,
    *,
    passes: int = 3,
) -> None:
    """Recover when settings was scrolled to the bottom (Log Out / Developer visible)."""
    for _ in range(passes):
        hs.swipe("up")
        time.sleep(0.35)


def settings_scrolled_past_revenge(ui: str) -> bool:
    """True when the viewport shows the tail of settings (we overshot Revenge/Plugins)."""
    for line in ui.splitlines():
        label = _ui_label(line)
        if label not in ("Log Out", "Developer Settings", "App Version"):
            continue
        pt = _ui_xy(line)
        if pt and 0 < pt[1] < 3200:
            return True
    return False


def ui_on_plugins_list(ui: str) -> bool:
    """Revenge Plugins sub-page (installed list or empty state)."""
    if "Quick Server Switcher" in ui or ui_plugins_empty(ui):
        return True
    for line in ui.splitlines():
        if "View" not in line or _ui_label(line) != "Plugins":
            continue
        pt = _ui_xy(line)
        if pt and pt[1] < 280:
            return True
    return False


def find_plugins_row(
    ui: str, *, max_y: int = 3200
) -> tuple[int, int] | None:
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
        if y < 280:
            continue
        if max_y and y > max_y + 150:
            continue
        if revenge_y is not None and (y <= revenge_y or y - revenge_y > 350):
            continue
        return x, y
    return None


def tap_plugins_settings(
    hs: uid.HandsetsSession, session: sc.ScreenControlSession | None = None
) -> bool:
    """Tap Plugins under the Revenge heading — plain row, no icon. Do not open Revenge."""
    serial = session.serial if session is not None else None
    _w, max_h = screen_size(serial) if serial else (1080, 3120)
    max_y = int(max_h * 0.96)

    def open_plugins_list() -> bool:
        if wait_until(
            lambda: ui_on_plugins_list(hs.ui()),
            timeout=UI_WAIT_SHORT,
            label="plugins_list",
        ):
            return True
        return ui_on_plugins_list(hs.ui())

    def tap_plugins_row() -> bool:
        """Tap the Plugins row, verifying it is on-screen first."""
        if hs.tap_text("Plugins", timeout_ms=3000) or hs.tap_desc("Plugins", timeout_ms=2500):
            return open_plugins_list()
        pt = find_plugins_row(hs.ui(), max_y=max_y)
        if pt and _on_screen(pt, serial, slack=-80) and hs.hs("tap", str(pt[0]), str(pt[1]), timeout=10).returncode == 0:
            return open_plugins_list()
        return False

    ui = hs.ui()
    if ui_on_plugins_list(ui):
        return True
    if settings_scrolled_past_revenge(ui):
        scroll_settings_toward_top(hs, session)
        ui = hs.ui()

    if tap_plugins_row():
        return True

    # Scroll down (hs swipe up = reveal lower content) in short steps.
    for _ in range(4):
        hs.swipe("up")
        time.sleep(0.5)
        if tap_plugins_row():
            return True
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
        xn, yn = int(x), row_y
        if hs.hs("tap", x, str(yn), timeout=10).returncode == 0:
            time.sleep(0.8)
            if "Open switcher" in hs.ui():
                return True
    return False


def open_switcher_via_settings(
    hs: uid.HandsetsSession,
    session: sc.ScreenControlSession,
    *,
    guild_key: str = "dcs",
    pkg: str | None = None,
) -> bool:
    """Profile → Settings → Plugins → Quick Server Switcher → Open switcher."""
    if not navigate_to_qss_plugin(
        hs, session, guild_key=guild_key, pkg=pkg, serial=session.serial
    ):
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
    """Channel composer → /servers autocomplete only — never Send //servers to chat."""
    serial = serial or session.serial
    if not ui_on_safe_channel(hs.ui()):
        log("slash: not on safe test channel — abort")
        return False
    dismiss_discord_chrome(hs, session)
    dismiss_keyboard(session, hs)
    if not hs.tap_id("chat_input_edit_text", timeout_ms=2500):
        w, h = screen_size(session.serial)
        session.shell("input", "tap", str(w // 2), str(int(h * 0.92)))
    time.sleep(0.35)
    if not handsets_fill(
        hs,
        "EditText#chat_input_edit_text",
        "/servers",
        serial=serial,
        issues=issues,
        purpose="slash_command",
    ):
        discard_composer_draft(hs, session, serial)
        return False
    time.sleep(0.6)
    if ui_switcher_open(hs.ui()):
        return True
    for needle in ("/ servers", "/servers", "servers"):
        if tap_ui_line_containing(hs, session, needle):
            time.sleep(0.8)
            break
    if wait_until(
        lambda: ui_switcher_open(hs.ui()),
        timeout=UI_WAIT_SHORT,
        label="slash_switcher",
    ):
        return True
    log("slash: switcher not open — discarding composer draft (will not tap Send)")
    discard_composer_draft(hs, session, serial)
    return False


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
    hs: uid.HandsetsSession,
    session: sc.ScreenControlSession,
    *,
    guild_key: str = "dcs",
    pkg: str | None = None,
    serial: str | None = None,
) -> bool:
    """Profile → Settings → Plugins → Quick Server Switcher plugin page."""
    serial = serial or session.serial
    pkg = pkg or resolve_discord_package(serial) or "app.revenge"
    ensure_discord_foreground(serial, pkg, hs)
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
    if ui_in_user_settings(ui):
        if tap_plugins_settings(hs, session):
            if ui_on_plugins_list(hs.ui()) or "Quick Server Switcher" in hs.ui():
                if "Quick Server Switcher" not in hs.ui():
                    tap_qss_plugin(hs)
                return "Quick Server Switcher" in hs.ui()

    for attempt in range(2):
        if attempt > 0:
            log("navigate_to_qss_plugin: retry %d — cold restart" % (attempt + 1))
            launch_discord(serial, pkg)
            wait_discord_ready(hs, timeout=UI_WAIT_MED)
            open_safe_channel(hs, guild_key)

        if not detect_safe_channel(hs.ui(), guild_key):
            leave_voice_channel(hs, session, serial, pkg, guild_key)
        dismiss_system_dialogs(hs, session)
        dismiss_emoji_keyboard(hs, session)
        if not open_server_list(hs, session, serial, pkg):
            log("navigate_to_qss_plugin: server drawer not open")
            continue
        prepare_profile_access(hs, session)
        if ui_in_channel_chat(hs.ui()):
            dismiss_channel_promos(hs, session)
            unfocus_composer(hs, session)
        dismiss_discord_chrome(hs, session)
        if not ensure_discord_foreground(serial, pkg, hs):
            log("navigate_to_qss_plugin: Discord not foreground before profile")
            continue
        if not (
            ui_shows_server_sidebar(hs.ui())
            and ("Danny, Online" in hs.ui() or "Danny, Idle" in hs.ui())
        ):
            open_server_list(hs, session, serial, pkg)
            prepare_profile_access(hs, session)

        for sub in range(2):
            debug_dir = Path(os.environ.get("QSS_DEBUG_DIR", "")).expanduser()
            if str(debug_dir) and str(debug_dir) != ".":
                try:
                    debug_dir.mkdir(parents=True, exist_ok=True)
                    (debug_dir / ("profile_attempt_%d_before.txt" % (sub + 1))).write_text(
                        hs.ui(), encoding="utf-8"
                    )
                    shot(serial, debug_dir / ("profile_attempt_%d_before.png" % (sub + 1)))
                except OSError:
                    pass
            if open_user_settings(hs, session):
                break
            debug_dir = Path(os.environ.get("QSS_DEBUG_DIR", "")).expanduser()
            if str(debug_dir) and str(debug_dir) != ".":
                try:
                    (debug_dir / ("profile_attempt_%d_after.txt" % (sub + 1))).write_text(
                        hs.ui(), encoding="utf-8"
                    )
                    shot(serial, debug_dir / ("profile_attempt_%d_after.png" % (sub + 1)))
                except OSError:
                    pass
            log("navigate_to_qss_plugin: open_user_settings attempt %d failed" % (sub + 1))
            ensure_discord_foreground(serial, pkg, hs)
            open_server_list(hs, session, serial, pkg)
            prepare_profile_access(hs, session)
        else:
            if ui_quest_overlay(hs.ui()):
                log("navigate_to_qss_plugin: quest/promo overlay may block profile chip")
            log("navigate_to_qss_plugin: profile chip not found")
            continue

        if not wait_until(
            lambda: "Log Out" in hs.ui()
            or "Account" in hs.ui()
            or find_plugins_row(hs.ui()) is not None,
            timeout=UI_WAIT_MED,
            label="user_settings",
        ):
            continue

        if not tap_plugins_settings(hs, session):
            continue

        if ui_plugins_empty(hs.ui()):
            log(
                "navigate_to_qss_plugin: Quick Server Switcher not installed — "
                "install from raw.githubusercontent.com/.../main/ on this device"
            )
            return False

        if not wait_until(
            lambda: "Quick Server Switcher" in hs.ui() and "Copy debug logs" in hs.ui(),
            timeout=UI_WAIT_SHORT,
            label="qss_plugin",
        ):
            if not tap_qss_plugin(hs):
                for _ in range(4):
                    hs.swipe("down")
                    time.sleep(0.5)
                    if tap_qss_plugin(hs):
                        break
                else:
                    continue

        if "Quick Server Switcher" in hs.ui():
            return True

    log("navigate_to_qss_plugin: all attempts failed")
    return False


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
    foreign = preflight_screen_lease(host, serial)
    if foreign:
        issues.append("screen_lease_foreign_hold")
        log(
            "%s blocked — foreign screen lease (%s). "
            "Run: python3 ~/stayturgid/control/bin/screen_lease.py status"
            % (host, foreign)
        )
        report["issues"] = issues
        report["screenLease"] = {"held": True, "holder": foreign}
        return report
    clear_logcat(serial)
    set_animations_enabled(serial, False)
    vlm_on = init_vlm(out)

    try:
        os.environ["STAYTURGID_SCREEN_LEASE_FORCE"] = "1"
        with sc.ScreenControlSession(host, label="QSS QA", restore_screen=False) as session:
            # Screen-control clearance may temporarily surface Android settings/feedback.
            # Relaunch after acquiring the lease so Handsets starts from Discord.
            launch_discord(serial, pkg)
            time.sleep(1.2)
            with uid.try_handsets(serial, host) as hs:
                if hs is None:
                    issues.append("handsets_unavailable")

                # Do not force-stop — cold start breaks profile-chip hit targets on p7a.
                launch_discord(serial, pkg)
                if hs is not None:
                    wait_discord_ready(hs, timeout=UI_WAIT_MED, session=session)
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
                    if ui_dm_thread(hs.ui()):
                        log(
                            "SAFETY: session started on DM thread — "
                            "navigating to test guild before any typing"
                        )
                    dismiss_system_dialogs(hs, session)
                    nav_ok, active_guild, active_ch = navigate_to_safe_guild(
                        hs, session, serial, pkg, guild_key
                    )
                    if not nav_ok:
                        log("nav retry after relaunch for guild %s" % guild_key)
                        launch_discord(serial, pkg)
                        if hs is not None:
                            wait_discord_ready(hs, timeout=UI_WAIT_MED, session=session)
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
                    if os.environ.get("QSS_AUTO_INSTALL", "").strip() in ("1", "true", "yes"):
                        install_qss_plugin(hs, session, serial, pkg)
                    # Settings → Open switcher only (slash posts to chat on misfire).
                    opened = open_switcher_via_settings(
                        hs, session, guild_key=guild_key, pkg=pkg
                    )
                    if not opened and os.environ.get("QSS_ALLOW_SLASH") == "1":
                        opened = open_switcher_via_slash(
                            hs, session, serial=serial, issues=issues
                        )
                    if not opened:
                        if ui_plugins_empty(hs.ui()):
                            issues.append("qss_plugin_not_installed")
                            log(
                                "Quick Server Switcher not installed on %s — "
                                "Revenge → Plugins → Install: "
                                "https://raw.githubusercontent.com/djbclark/RevengeQuickSwitcher/main/"
                                % host
                            )
                        elif quest_bar_blocks_profile(hs):
                            issues.append("quest_bar_blocks_profile")
                            log(
                                "%s — Quest Bar covers profile chip; dismiss quest on device "
                                "then re-run (S24 Jul 2026)" % host
                            )
                        issues.append("switcher_open_failed")
                        shot(serial, out / "01_profile_fail.png")
                        plugin_missing = "qss_plugin_not_installed" in issues
                        if vlm_on and not plugin_missing:
                            vlm_require(
                                vlm_capture(serial, "01_profile_fail_vlm.png"),
                                "profile_chip",
                                "profile_chip",
                                issues=issues,
                            )
                        elif plugin_missing:
                            log("skip profile_chip VLM — plugin not installed on device")
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
                    if vlm_on and "qss_plugin_not_installed" not in issues:
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

    default_host = os.environ.get("QSS_DEVICE", "s24")
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
