#!/usr/bin/env python3
"""Local UI-TARS-1.5-7B vision gates for QSS device QA (llama.cpp server).

Requires: scripts/vlm_install.sh && scripts/vlm_service.sh install (see PATHS.md)

Env:
  QSS_VLM=1|0           — enable gates (default 1 when server reachable)
  QSS_VLM_PORT=8081     — llama-server port
  QSS_VLM_TIMEOUT=600   — seconds per inference (CPU is slow)
  QSS_VLM_THREADS=4     — passed to ui_tars_server.sh
  QSS_VLM_MAX_WIDTH=720 — downscale screenshots before VLM
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
SERVER_SH = REPO / "scripts" / "ui_tars_server.sh"
DEFAULT_PORT = int(os.environ.get("QSS_VLM_PORT", "8081"))
DEFAULT_TIMEOUT = int(os.environ.get("QSS_VLM_TIMEOUT", "900"))
IMAGE_MAX_WIDTH = int(os.environ.get("QSS_VLM_MAX_WIDTH", "720"))

SAFE_CHANNELS = ("dc-general", "dc-games", "ogden", "college")

CHECK_PROMPTS: dict[str, str] = {
    "discord_not_launcher": (
        "You verify Android QA screenshots for the Revenge/Discord app (app.revenge).\n"
        "Is this screenshot showing the Discord/Revenge mobile app — NOT Niagara Launcher, "
        "NOT the Android home screen, NOT another app?\n"
        "Niagara has a minimal vertical app list; Discord has channel lists, servers sidebar, "
        "or chat composer.\n"
        'Reply JSON only: {"ok":true,"screen":"discord|launcher|other","confidence":0.0-1.0,"notes":"..."}'
    ),
    "safe_test_channel": (
        "You verify we are on an operator-owned TEST channel in Discord/Revenge.\n"
        "SAFE channel names (exact): #dc-general, #dc-games, #ogden, #college.\n"
        "NOT safe: bare #general, Bee, BetterDiscord, or any other server.\n"
        "Look at the channel header or message composer hint (e.g. 'Message #dc-general').\n"
        'Reply JSON only: {"ok":true,"channels":["dc-general"],"confidence":0.0-1.0,"notes":"..."}\n'
        "Set ok:true only if viewing one of the four safe channels."
    ),
    "server_sidebar_visible": (
        "Does this screenshot show the Discord server list with a vertical column of "
        "round server icons on the LEFT edge (separate scroll area)?\n"
        'Reply JSON only: {"ok":true,"confidence":0.0-1.0,"notes":"..."}'
    ),
    "switcher_open": (
        "Is the Quick Server Switcher overlay open? Look for top-docked UI: "
        "'Filter servers' field and 'Close' near the top, server jump list.\n"
        'Reply JSON only: {"ok":true,"confidence":0.0-1.0,"notes":"..."}'
    ),
    "settings_plugins_path": (
        "Are we on User Settings with the Revenge section visible, including a plain "
        "'Plugins' row (no icon) just under the Revenge heading/icon row?\n"
        "We should NOT be inside Revenge About, and NOT scrolled to Log Out at the bottom.\n"
        'Reply JSON only: {"ok":true,"confidence":0.0-1.0,"notes":"..."}'
    ),
    "before_type": (
        "We are about to TYPE text into a search/filter field on Android Discord QA.\n"
        "Confirm: (1) we are in Revenge/Discord not launcher, (2) a text field is focused "
        "or visible for typing, (3) we are NOT in a DM composer (Message @username) — "
        "only switcher Filter servers, plugin install URL, or Message #dc-general / "
        "#dc-games / #ogden / #college is acceptable.\n"
        'Reply JSON only: {"ok":true,"confidence":0.0-1.0,"notes":"..."}'
    ),
    "after_type": (
        "We just TYPED into an Android Discord QA field. Inspect the screenshot.\n"
        "Set ok:false if: (1) DM composer (Message @username), (2) channel composer holds "
        "accidental chat text (e.g. //servers, lone comma, partial slash commands), "
        "(3) text would be sent to chat instead of opening switcher/filter UI.\n"
        "Set ok:true if switcher Filter servers shows the query, slash autocomplete shows "
        "/servers (single leading slash), or plugin install URL field has the URL.\n"
        'Reply JSON only: {"ok":true,"confidence":0.0-1.0,"notes":"..."}'
    ),
    "jump_target_visible": (
        "The Quick Server Switcher overlay is open with a filtered server list.\n"
        "Is there a tappable row like 'Jump to LL/DC' or 'Jump to Danny Clark's server' "
        "(allowlisted test guilds only)?\n"
        "NOT acceptable: only unrelated servers (Bee, BetterDiscord) or plugin settings.\n"
        'Reply JSON only: {"ok":true,"target":"LL/DC","confidence":0.0-1.0,"notes":"..."}'
    ),
    "profile_chip": (
        "Can we open user profile or settings from this Discord/Revenge screenshot?\n"
        "Look for: bottom profile chip (name + Online), or 'Show Settings Drawer'.\n"
        "Identify obstructions: Quest Bar, voice call bar (Unmute/Disconnect), "
        "emoji keyboard, permission dialogs, promo banners.\n"
        'Reply JSON only: {"ok":true,"obstruction":"none|quest|voice|emoji|other",'
        '"confidence":0.0-1.0,"notes":"..."}\n'
        "ok:true only if profile/settings is clearly reachable."
    ),
}


def vlm_enabled() -> bool:
    return os.environ.get("QSS_VLM", "1").strip() not in ("0", "false", "no")


def vlm_strict() -> bool:
    return os.environ.get("QSS_VLM_STRICT", "1").strip() not in ("0", "false", "no")


def _base_url() -> str:
    return "http://127.0.0.1:%d" % DEFAULT_PORT


def server_healthy() -> bool:
    try:
        req = urllib.request.Request(_base_url() + "/health")
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError, TimeoutError):
        return False


def ensure_server(start: bool = True) -> bool:
    if server_healthy():
        return True
    if not start:
        return False
    # Prefer launchd agent when installed (PATHS.md).
    plist = Path.home() / "Library/LaunchAgents/homebrew.mxcl.ui-tars.plist"
    if plist.is_file():
        domain = "gui/%d" % os.getuid()
        subprocess.run(
            ["launchctl", "kickstart", "-k", "%s/homebrew.mxcl.ui-tars" % domain],
            check=False,
            timeout=30,
        )
    elif SERVER_SH.is_file():
        subprocess.run(["bash", str(SERVER_SH)], check=False, timeout=200)
    else:
        return False
    deadline = time.time() + 200
    while time.time() < deadline:
        if server_healthy():
            return True
        time.sleep(1)
    return False


def _model_id() -> str:
    try:
        req = urllib.request.Request(_base_url() + "/v1/models")
        with urllib.request.urlopen(req, timeout=5) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        models = payload.get("data") or payload.get("models") or []
        if models:
            return str(models[0].get("id") or models[0].get("name") or "ui-tars")
    except (urllib.error.URLError, OSError, json.JSONDecodeError, KeyError, IndexError):
        pass
    return "ui-tars"


def prepare_image(path: Path, *, max_width: int | None = None) -> Path:
    """Downscale screenshots so CPU vision inference stays tractable."""
    max_width = max_width or IMAGE_MAX_WIDTH
    out = path.with_name(path.stem + ".vlm.png")
    if out.is_file() and out.stat().st_mtime >= path.stat().st_mtime:
        return out
    try:
        subprocess.run(
            ["sips", "-Z", str(max_width), str(path), "--out", str(out)],
            check=True,
            capture_output=True,
            timeout=30,
        )
        return out
    except (subprocess.CalledProcessError, FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return path


def _encode_image(path: Path) -> str:
    data = prepare_image(path).read_bytes()
    return base64.b64encode(data).decode("ascii")


def _parse_json_blob(text: str) -> dict[str, Any] | None:
    text = (text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return None


def ask_image(path: Path, prompt: str, *, timeout: int | None = None) -> tuple[str, dict[str, Any] | None]:
    """Send one screenshot + prompt; return (raw_text, parsed_json)."""
    timeout = timeout or DEFAULT_TIMEOUT
    b64 = _encode_image(path)
    body = {
        "model": _model_id(),
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:image/png;base64," + b64},
                    },
                ],
            }
        ],
        "max_tokens": 256,
        "temperature": 0.1,
    }
    req = urllib.request.Request(
        _base_url() + "/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    raw = ""
    try:
        raw = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raw = json.dumps(payload)
    return raw, _parse_json_blob(raw)


class VlmGate:
    """Vision verification gate using local UI-TARS."""

    def __init__(self, *, autostart: bool = True) -> None:
        self.ready = False
        if not vlm_enabled():
            return
        self.ready = ensure_server(start=autostart)

    def verify(
        self,
        image_path: Path,
        check: str,
        *,
        min_confidence: float = 0.55,
    ) -> tuple[bool, dict[str, Any]]:
        if not self.ready:
            skipped = {"skipped": True, "reason": "vlm_unavailable"}
            if vlm_strict() and vlm_enabled():
                skipped["ok"] = False
                return False, skipped
            return True, skipped
        prompt = CHECK_PROMPTS.get(check)
        if not prompt:
            return True, {"skipped": True, "reason": "unknown_check"}
        t0 = time.time()
        raw, parsed = ask_image(image_path, prompt)
        elapsed = time.time() - t0
        detail: dict[str, Any] = {
            "check": check,
            "raw": raw,
            "parsed": parsed,
            "elapsed_s": round(elapsed, 1),
        }
        if not parsed:
            detail["ok"] = False
            detail["reason"] = "unparseable_response"
            return False, detail
        ok = bool(parsed.get("ok"))
        conf = float(parsed.get("confidence", 0.8 if ok else 0.2))
        detail["confidence"] = conf
        if check == "safe_test_channel" and ok:
            found = [c for c in parsed.get("channels", []) if c in SAFE_CHANNELS]
            ok = bool(found)
            detail["channels"] = found
        if check == "discord_not_launcher" and ok:
            screen = str(parsed.get("screen", "")).lower()
            ok = screen in ("discord", "revenge", "discord_channel", "discord_settings")
            detail["screen"] = screen
        if ok and conf < min_confidence:
            ok = False
            detail["reason"] = "low_confidence"
        detail["ok"] = ok
        return ok, detail

    def require(self, image_path: Path, check: str, label: str = "") -> bool:
        ok, detail = self.verify(image_path, check)
        if not detail.get("skipped") and not ok:
            tag = label or check
            note = detail.get("parsed", {}) or {}
            notes = note.get("notes", detail.get("reason", ""))
            print(
                "VLM BLOCK %s: %s (%.1fs)"
                % (tag, notes, detail.get("elapsed_s", 0)),
                flush=True,
            )
        return ok


def crop_sidebar(src: Path, dest: Path) -> Path:
    """Crop left 18% for sidebar-only VLM queries."""
    try:
        from PIL import Image  # type: ignore
    except ImportError:
        return src
    im = Image.open(src)
    w, h = im.size
    box = (0, 0, max(1, int(w * 0.18)), h)
    im.crop(box).save(dest)
    return dest
