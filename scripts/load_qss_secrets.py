#!/usr/bin/env python3
"""Load QSS API keys from a gitignored secrets file (never commit secrets.env)."""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_PATHS = (
    Path.home() / ".config" / "RevengeQuickSwitcher" / "secrets.env",
    Path.home() / ".local/share" / "RevengeQuickSwitcher" / "secrets.env",
)


def load_secrets_env(*, override: bool = False) -> Path | None:
    """Parse KEY=VALUE lines into os.environ. Returns path loaded, or None."""
    custom = os.environ.get("QSS_SECRETS", "").strip()
    paths: list[Path] = []
    if custom:
        paths.append(Path(custom).expanduser())
    paths.extend(DEFAULT_PATHS)
    seen: set[Path] = set()
    for path in paths:
        path = path.resolve()
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].strip()
            if "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip("'").strip('"')
            if not key or not val:
                continue
            if override or key not in os.environ or not str(os.environ[key]).strip():
                os.environ[key] = val
        return path
    return None


if __name__ == "__main__":
    loaded = load_secrets_env()
    print(loaded or "no secrets file found")
