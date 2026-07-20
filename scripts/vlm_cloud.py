#!/usr/bin/env python3
"""Optional paid cloud vision gates when local UI-TARS is slow, down, or inconclusive.

The QA agent may ask the operator for low-limit API keys for one or more providers.
Use cloud vision sparingly — local UI-TARS is free and offline.

Env (provider — comma-separated for fallback chain):
  QSS_VLM_CLOUD=openai              — openai only
  QSS_VLM_CLOUD=anthropic           — Anthropic only
  QSS_VLM_CLOUD=google              — Google Gemini only
  QSS_VLM_CLOUD=openai,anthropic    — try OpenAI, then Claude on failure

Keys (provider-specific or generic):
  QSS_VLM_CLOUD_API_KEY=...         — fallback key for any provider
  OPENAI_API_KEY / ANTHROPIC_API_KEY / GOOGLE_API_KEY / GEMINI_API_KEY

Models (override per provider):
  QSS_VLM_CLOUD_MODEL=...           — default model for primary provider
  QSS_VLM_OPENAI_MODEL=gpt-4o-mini
  QSS_VLM_ANTHROPIC_MODEL=claude-haiku-4-5-20251001
  QSS_VLM_GOOGLE_MODEL=gemini-flash-latest

Escalation for a stuck nav step (agent re-run):
  QSS_VLM_CLOUD_STEP=switcher_open  — pick provider from STEP_RECOMMENDATIONS
  QSS_VLM_CLOUD=anthropic ANTHROPIC_API_KEY=sk-ant-... python3 scripts/device_qa_qss.py ...

See VLM.md for when to use which provider (research-backed).
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from load_qss_secrets import load_secrets_env as _load_secrets_env
except ImportError:
    _load_secrets_env = None  # type: ignore

if _load_secrets_env is not None:
    _load_secrets_env()

import base64
import json
import re
import time
import urllib.error
import urllib.request
from typing import Any

try:
    import ui_tars_local as _local
except ImportError:
    _local = None  # type: ignore

IMAGE_MAX_WIDTH = int(os.environ.get("QSS_VLM_CLOUD_MAX_WIDTH", "720"))

# Default models — cheap tier unless overridden.
# Anthropic: Haiku 4.5 (fast vision, JSON gates). Google: flash-latest alias
# auto-tracks the current Flash tier (gemini-3.5-flash as of 2026-07).
ANTHROPIC_HAIKU = "claude-haiku-4-5-20251001"
GOOGLE_FLASH = "gemini-3.5-flash"
ANTHROPIC_SONNET = "claude-sonnet-4-6"

PROVIDERS: dict[str, dict[str, Any]] = {
    "openai": {
        "label": "OpenAI",
        "default_model": "gpt-4o-mini",
        "model_env": "QSS_VLM_OPENAI_MODEL",
        "key_envs": ("OPENAI_API_KEY", "QSS_VLM_CLOUD_API_KEY"),
        "signup": "https://platform.openai.com/api-keys",
    },
    "anthropic": {
        "label": "Anthropic",
        "default_model": ANTHROPIC_HAIKU,
        "model_env": "QSS_VLM_ANTHROPIC_MODEL",
        "key_envs": ("ANTHROPIC_API_KEY", "QSS_VLM_CLOUD_API_KEY"),
        "signup": "https://console.anthropic.com/settings/keys",
    },
    "google": {
        "label": "Google Gemini",
        "default_model": GOOGLE_FLASH,
        "model_env": "QSS_VLM_GOOGLE_MODEL",
        "key_envs": ("GOOGLE_API_KEY", "GEMINI_API_KEY", "QSS_VLM_CLOUD_API_KEY"),
        "signup": "https://aistudio.google.com/apikey",
    },
}

# Research-backed picks for QSS device QA (mobile Discord screenshots).
# Sources: benchr multimodal ranking (dense UI → Gemini), Railwail 2026 benchmark
# (mobile UI screenshots → Claude), ScrollTest/Markaicode (gpt-4o-mini for cheap gates).
STEP_RECOMMENDATIONS: dict[str, dict[str, Any]] = {
    "default": {
        "primary": "openai",
        "model": "gpt-4o-mini",
        "why": "Cheapest high-volume JSON yes/no gates; native JSON schema mode.",
    },
    "local_unavailable": {
        "primary": "openai",
        "model": "gpt-4o-mini",
        "why": "Local llama-server down — gpt-4o-mini is the standard cheap cloud fallback.",
    },
    "discord_not_launcher": {
        "primary": "openai",
        "model": "gpt-4o-mini",
        "why": "Simple screen-classification gate; mini is sufficient.",
    },
    "safe_test_channel": {
        "primary": "openai",
        "model": "gpt-4o-mini",
        "alt": ("anthropic", ANTHROPIC_HAIKU),
        "why": "Read channel header/composer; escalate to Claude if mini mis-reads voice vs text.",
    },
    "switcher_open": {
        "primary": "anthropic",
        "model": ANTHROPIC_HAIKU,
        "alt": ("google", GOOGLE_FLASH),
        "why": "Software overlay UI — Claude/Gemini read mobile app chrome better than budget GPT.",
    },
    "settings_plugins_path": {
        "primary": "google",
        "model": GOOGLE_FLASH,
        "alt": ("anthropic", ANTHROPIC_HAIKU),
        "why": "Dense settings lists with subtle scroll position — Gemini strong on dense UIs.",
    },
    "profile_chip": {
        "primary": "google",
        "model": GOOGLE_FLASH,
        "alt": ("anthropic", ANTHROPIC_HAIKU),
        "why": "Bottom bar + promos/quest overlays — need dense control reading and obstruction ID.",
    },
    "jump_target_visible": {
        "primary": "anthropic",
        "model": ANTHROPIC_HAIKU,
        "alt": ("openai", "gpt-4o"),
        "why": "Filtered list rows in switcher overlay — Claude best at software list UIs.",
    },
    "before_type": {
        "primary": "openai",
        "model": "gpt-4o-mini",
        "why": "Pre-type safety gate; keep cost low.",
    },
    "after_type": {
        "primary": "openai",
        "model": "gpt-4o-mini",
        "why": "Post-type screenshot verify — catch //servers and DM composer misfires.",
    },
    "ambiguous": {
        "primary": "anthropic",
        "model": ANTHROPIC_SONNET,
        "alt": ("google", GOOGLE_FLASH),
        "why": "Second opinion when local + mini disagree — use sparingly (higher cost).",
    },
}


def cloud_providers() -> list[str]:
    raw = os.environ.get("QSS_VLM_CLOUD", "").strip().lower()
    if not raw or raw in ("0", "false", "no"):
        return []
    if raw in ("1", "true", "yes"):
        return ["openai"]
    out: list[str] = []
    for part in raw.replace(";", ",").split(","):
        name = part.strip()
        if name in PROVIDERS and name not in out:
            out.append(name)
    return out


def cloud_enabled() -> bool:
    return bool(cloud_providers())


def _provider_key(provider: str) -> str:
    meta = PROVIDERS.get(provider, {})
    for env_name in meta.get("key_envs", ()):
        val = os.environ.get(env_name, "").strip()
        if val:
            return val
    return ""


def cloud_configured() -> bool:
    return cloud_enabled() and any(_provider_key(p) for p in cloud_providers())


def provider_model(provider: str) -> str:
    meta = PROVIDERS.get(provider, {})
    override = os.environ.get(meta.get("model_env", ""), "").strip()
    if override:
        return override
    step = os.environ.get("QSS_VLM_CLOUD_STEP", "").strip()
    if step and step in STEP_RECOMMENDATIONS:
        rec = STEP_RECOMMENDATIONS[step]
        if rec.get("primary") == provider and rec.get("model"):
            return str(rec["model"])
        alt = rec.get("alt")
        if isinstance(alt, (list, tuple)) and len(alt) >= 2 and alt[0] == provider:
            return str(alt[1])
    global_model = os.environ.get("QSS_VLM_CLOUD_MODEL", "").strip()
    if global_model and len(cloud_providers()) == 1:
        return global_model
    return str(meta.get("default_model", ""))


def recommend_for_step(step: str) -> dict[str, Any]:
    """Return provider/model suggestion for a stuck QA step."""
    key = step if step in STEP_RECOMMENDATIONS else "default"
    rec = dict(STEP_RECOMMENDATIONS[key])
    primary = str(rec.get("primary", "openai"))
    rec["provider"] = primary
    rec["model"] = rec.get("model") or provider_model(primary)
    meta = PROVIDERS.get(primary, {})
    rec["signup"] = meta.get("signup", "")
    rec["key_env"] = (meta.get("key_envs") or ("QSS_VLM_CLOUD_API_KEY",))[0]
    return rec


def suggest_cloud_vlm(reason: str = "local_unavailable", *, step: str = "") -> str:
    """Human-readable hint for agents to request operator API keys."""
    step_key = step or os.environ.get("QSS_VLM_CLOUD_STEP", "") or reason
    rec = recommend_for_step(step_key if step_key in STEP_RECOMMENDATIONS else reason)
    provider = str(rec.get("provider", "openai"))
    model = str(rec.get("model", "gpt-4o-mini"))
    key_env = str(rec.get("key_env", "QSS_VLM_CLOUD_API_KEY"))
    lines = [
        "CLOUD_VLM_SUGGESTED (%s): %s" % (reason, rec.get("why", "")),
        "Recommended: QSS_VLM_CLOUD=%s %s=... QSS_VLM_CLOUD_MODEL=%s" % (provider, key_env, model),
        "Signup: %s" % rec.get("signup", ""),
        "Multi-provider fallback: QSS_VLM_CLOUD=openai,anthropic,google",
    ]
    alt = rec.get("alt")
    if isinstance(alt, (list, tuple)) and len(alt) >= 2:
        lines.append("Alternate: QSS_VLM_CLOUD=%s (model %s)" % (alt[0], alt[1]))
    return "\n".join(lines)


def write_cloud_vlm_request(
    artifact_dir: Path,
    *,
    step: str,
    reason: str,
    screenshot: Path | None = None,
    extra: dict[str, Any] | None = None,
) -> Path:
    """Write agent/operator request file when a nav step keeps failing."""
    rec = recommend_for_step(step)
    payload: dict[str, Any] = {
        "step": step,
        "reason": reason,
        "recommendation": rec,
        "allProviders": {
            name: {
                "label": meta["label"],
                "defaultModel": meta["default_model"],
                "keyEnv": (meta.get("key_envs") or ("QSS_VLM_CLOUD_API_KEY",))[0],
                "signup": meta.get("signup", ""),
            }
            for name, meta in PROVIDERS.items()
        },
        "rerunExample": (
            "QSS_VLM=1 QSS_VLM_CLOUD=%s QSS_VLM_CLOUD_STEP=%s %s=... "
            "python3 scripts/device_qa_qss.py p7a --guild dcs" % (rec["provider"], step, rec["key_env"])
        ),
        "hint": suggest_cloud_vlm(reason, step=step),
    }
    if screenshot and screenshot.is_file():
        payload["screenshot"] = str(screenshot)
    if extra:
        payload["context"] = extra
    out = artifact_dir / "cloud_vlm_request.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (artifact_dir / "cloud_vlm_suggested.txt").write_text(payload["hint"] + "\n", encoding="utf-8")
    return out


def _prepare_image(path: Path) -> Path:
    if _local is not None:
        return _local.prepare_image(path, max_width=IMAGE_MAX_WIDTH)
    out = path.with_name(path.stem + ".vlm.png")
    if out.is_file() and out.stat().st_mtime >= path.stat().st_mtime:
        return out
    try:
        import subprocess

        subprocess.run(
            ["sips", "-Z", str(IMAGE_MAX_WIDTH), str(path), "--out", str(out)],
            check=True,
            capture_output=True,
            timeout=30,
        )
        return out
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return path


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


def _check_prompts() -> dict[str, str]:
    if _local is not None and hasattr(_local, "CHECK_PROMPTS"):
        return _local.CHECK_PROMPTS
    return {}


def _image_b64(path: Path) -> str:
    return base64.b64encode(_prepare_image(path).read_bytes()).decode("ascii")


def ask_image_openai(
    path: Path, prompt: str, *, model: str, api_key: str, timeout: int = 120
) -> tuple[str, dict[str, Any] | None]:
    b64 = _image_b64(path)
    body = {
        "model": model,
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
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + api_key,
        },
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


def ask_image_anthropic(
    path: Path, prompt: str, *, model: str, api_key: str, timeout: int = 120
) -> tuple[str, dict[str, Any] | None]:
    b64 = _image_b64(path)
    body = {
        "model": model,
        "max_tokens": 256,
        "temperature": 0.1,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": b64,
                        },
                    },
                    {"type": "text", "text": prompt + "\nReply JSON only."},
                ],
            }
        ],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    raw = ""
    for block in payload.get("content") or []:
        if block.get("type") == "text":
            raw += block.get("text", "")
    if not raw:
        raw = json.dumps(payload)
    return raw, _parse_json_blob(raw)


def ask_image_google(
    path: Path, prompt: str, *, model: str, api_key: str, timeout: int = 120
) -> tuple[str, dict[str, Any] | None]:
    b64 = _image_b64(path)
    url = "https://generativelanguage.googleapis.com/v1beta/models/" + model + ":generateContent?key=" + api_key
    body = {
        "contents": [
            {
                "parts": [
                    {"text": prompt + "\nReply JSON only."},
                    {"inline_data": {"mime_type": "image/png", "data": b64}},
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 1024,
            "responseMimeType": "application/json",
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    raw = ""
    try:
        parts = payload["candidates"][0]["content"]["parts"]
        raw = "".join(p.get("text", "") for p in parts)
    except (KeyError, IndexError, TypeError):
        raw = json.dumps(payload)
    return raw, _parse_json_blob(raw)


def ask_image(
    provider: str,
    path: Path,
    prompt: str,
    *,
    model: str | None = None,
    timeout: int = 120,
) -> tuple[str, dict[str, Any] | None]:
    api_key = _provider_key(provider)
    if not api_key:
        raise ValueError("no API key for provider %s" % provider)
    model = model or provider_model(provider)
    if provider == "openai":
        return ask_image_openai(path, prompt, model=model, api_key=api_key, timeout=timeout)
    if provider == "anthropic":
        return ask_image_anthropic(path, prompt, model=model, api_key=api_key, timeout=timeout)
    if provider == "google":
        return ask_image_google(path, prompt, model=model, api_key=api_key, timeout=timeout)
    raise ValueError("unknown provider %s" % provider)


def _apply_check_rules(check: str, ok: bool, parsed: dict[str, Any], detail: dict[str, Any]) -> bool:
    conf = float(parsed.get("confidence", 0.8 if ok else 0.2))
    detail["confidence"] = conf
    safe_channels = getattr(_local, "SAFE_CHANNELS", ())
    if check == "safe_test_channel" and ok and safe_channels:
        found = [c for c in parsed.get("channels", []) if c in safe_channels]
        ok = bool(found)
        detail["channels"] = found
    if check == "discord_not_launcher" and ok:
        screen = str(parsed.get("screen", "")).lower()
        ok = screen in ("discord", "revenge", "discord_channel", "discord_settings")
        detail["screen"] = screen
    return ok


class CloudVlmGate:
    """Vision verification via OpenAI / Anthropic / Google (fallback chain)."""

    def __init__(self) -> None:
        self.providers = [p for p in cloud_providers() if _provider_key(p)]
        self.ready = bool(self.providers)
        self.provider = self.providers[0] if self.providers else ""
        self.model = provider_model(self.provider) if self.provider else ""

    def verify(
        self,
        image_path: Path,
        check: str,
        *,
        min_confidence: float = 0.55,
    ) -> tuple[bool, dict[str, Any]]:
        if not self.ready:
            return False, {"skipped": True, "reason": "cloud_vlm_unconfigured", "ok": False}
        prompts = _check_prompts()
        prompt = prompts.get(check)
        if not prompt:
            return True, {"skipped": True, "reason": "unknown_check"}
        errors: list[str] = []
        for provider in self.providers:
            model = provider_model(provider)
            t0 = time.time()
            try:
                raw, parsed = ask_image(provider, image_path, prompt, model=model)
            except (urllib.error.URLError, OSError, TimeoutError, ValueError, json.JSONDecodeError) as e:
                errors.append("%s: %s" % (provider, e))
                continue
            elapsed = time.time() - t0
            detail: dict[str, Any] = {
                "check": check,
                "raw": raw,
                "parsed": parsed,
                "elapsed_s": round(elapsed, 1),
                "backend": provider,
                "model": model,
            }
            if not parsed:
                detail["ok"] = False
                detail["reason"] = "unparseable_response"
                errors.append("%s: unparseable" % provider)
                continue
            ok = bool(parsed.get("ok"))
            ok = _apply_check_rules(check, ok, parsed, detail)
            conf = float(detail.get("confidence", 0.2))
            if ok and conf < min_confidence:
                ok = False
                detail["reason"] = "low_confidence"
            detail["ok"] = ok
            return ok, detail
        return False, {
            "ok": False,
            "check": check,
            "reason": "cloud_api_error",
            "errors": errors,
            "backend": ",".join(self.providers),
        }
