#!/usr/bin/env python3
"""Smoke-test local UI-TARS vision gate."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import ui_tars_local as vlm  # noqa: E402


def main() -> int:
    if not vlm.ensure_server(start=True):
        print(
            "UI-TARS server not healthy — see PATHS.md\n"
            "  curl -sf http://127.0.0.1:8081/health\n"
            "  launchctl print gui/$(id -u)/homebrew.mxcl.ui-tars\n"
            "  launchctl kickstart -k gui/$(id -u)/homebrew.mxcl.ui-tars",
            file=sys.stderr,
        )
        return 1
    gate = vlm.VlmGate(autostart=False)
    if not gate.ready:
        print("VlmGate not ready", file=sys.stderr)
        return 1
    print("UI-TARS-1.5-7B ready on %s" % vlm._base_url())
    print("Expect ~15-90s per screenshot gate on Apple Silicon (CPU-only hosts: much slower).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
