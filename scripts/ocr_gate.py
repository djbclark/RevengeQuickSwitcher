"""Fast, free OCR gates using Tesseract for QSS device QA.

Runs before expensive cloud VLM calls. If OCR yields a conclusive answer,
the VLM call is skipped entirely.

Requires: brew install tesseract && pip3 install pytesseract
"""
from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any

try:
    import pytesseract
    from PIL import Image

    HAVE_TESSERACT = True
except ImportError:
    HAVE_TESSERACT = False

SAFE_CHANNELS = ("dc-general", "dc-games", "ogden", "college")
QSS_LABELS = (
    "Quick Server Switcher",
    "Open switcher",
    "Copy debug logs",
    "Filter servers",
    "Flat Sidebar",
    "Debug Logging",
    "Excluded servers",
    "Custom aliases",
    "Clear recent",
)


def ocr_available() -> bool:
    return HAVE_TESSERACT


def ocr_text(image_path: Path, *, lang: str = "eng") -> str:
    """Extract text from a phone screenshot via Tesseract."""
    try:
        img = Image.open(image_path)
        return pytesseract.image_to_string(img, lang=lang)
    except Exception:
        return ""


def _ocr_contains(text: str, keywords: list[str], *, min_match: int = 1) -> list[str]:
    """Return matched keywords from text (case-insensitive)."""
    low = text.lower()
    found: list[str] = []
    for kw in keywords:
        if kw.lower() in low:
            found.append(kw)
    return found


CHECK_PATTERNS: dict[str, dict[str, Any]] = {
    "discord_not_launcher": {
        "positive": (
            "Discord", "Revenge", "Quick Server Switcher", "Server",
            "Plugins", "Settings", "dc-general", "ogden", "dc-games",
            "college", "Messages", "Channel", "Online",
        ),
        "negative": ("Niagara", "Launcher", "Android System"),
        "min_match": 2,
        "help": "Look for Discord UI elements (channels, QSS, settings)",
    },
    "safe_test_channel": {
        "positive": tuple(f"#{c}" for c in SAFE_CHANNELS),
        "negative": ("Message @", "Message #general"),
        "min_match": 1,
        "help": "Look for safe test channel headers",
    },
    "server_sidebar_visible": {
        "positive": (
            "Danny Clark",
            "LL/DC",
            "dcs",
            "dad",
            "Bee",
            "BetterDiscord",
        ),
        "negative": (),
        "min_match": 1,
        "help": "Look for server names in sidebar",
    },
    "switcher_open": {
        "positive": ("Filter servers", "Close", "Jump to"),
        "negative": (),
        "min_match": 1,
        "help": "Look for Quick Server Switcher overlay",
    },
    "settings_plugins_path": {
        "positive": ("Plugins",),
        "negative": ("Log Out", "About"),
        "min_match": 1,
        "help": "Look for Plugins row in Revenge settings",
    },
    "jump_target_visible": {
        "positive": ("Jump to",),
        "negative": (),
        "min_match": 1,
        "help": "Look for server jump targets in switcher",
    },
    "profile_chip": {
        "positive": ("Online", "Show Settings Drawer", "Profile", "Settings"),
        "negative": ("Disconnect", "Unmute", "Mute"),
        "min_match": 1,
        "help": "Look for profile chip or settings access point",
    },
    "qss_plugin_settings": {
        "positive": QSS_LABELS,
        "negative": (),
        "min_match": 3,
        "help": "Look for QSS plugin settings page elements",
    },
    "plugins_list": {
        "positive": ("Quick Server Switcher", "Plugins", "Settings"),
        "negative": ("Log Out",),
        "min_match": 2,
        "help": "Look for Revenge plugins list with QSS visible",
    },
    "discord_settings": {
        "positive": ("Settings", "Account", "Profile", "Log Out"),
        "negative": ("Quick Server Switcher",),
        "min_match": 2,
        "help": "Look for Discord main settings page",
    },
    "before_type": {
        "positive": tuple(f"#{c}" for c in SAFE_CHANNELS),
        "negative": ("Message @",),
        "min_match": 1,
        "help": "Verify safe channel before typing",
    },
}


class OcrGate:
    """Fast OCR-based screen verification. Returns True when patterns match."""

    def __init__(self) -> None:
        self.ready = HAVE_TESSERACT
        if HAVE_TESSERACT:
            try:
                pytesseract.get_tesseract_version()
            except Exception:
                self.ready = False

    def verify(
        self,
        image_path: Path,
        check: str,
        *,
        min_confidence: float = 0.5,
    ) -> tuple[bool, dict[str, Any]]:
        if not self.ready:
            return False, {"skipped": True, "reason": "tesseract_unavailable", "ok": False}
        patterns = CHECK_PATTERNS.get(check)
        if not patterns:
            return True, {"skipped": True, "reason": "unknown_check"}
        t0 = time.time()
        text = ocr_text(image_path)
        elapsed = time.time() - t0
        text_low = text.lower()
        positives = list(patterns.get("positive", ()))
        negatives = list(patterns.get("negative", ()))
        min_match = int(patterns.get("min_match", 1))
        found_pos = [p for p in positives if p.lower() in text_low]
        found_neg = [n for n in negatives if n.lower() in text_low]
        ok = len(found_pos) >= min_match and not found_neg
        conf = min(1.0, len(found_pos) / max(min_match, 1) * 0.8) if ok else 0.0
        detail: dict[str, Any] = {
            "check": check,
            "backend": "ocr",
            "ok": ok,
            "confidence": round(conf, 2),
            "matched": found_pos,
            "negatives": found_neg,
            "elapsed_s": round(elapsed, 2),
            "text_preview": text[:200].strip(),
        }
        if ok and conf < min_confidence:
            ok = False
            detail["reason"] = "low_confidence"
        if not ok and not found_neg:
            detail["reason"] = "insufficient_matches"
        elif found_neg:
            detail["reason"] = "negative_match"
        detail["ok"] = ok
        return ok, detail
