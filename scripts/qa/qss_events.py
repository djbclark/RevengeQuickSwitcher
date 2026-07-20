"""QA-bridge event parsing (QA-REENGINEERING.md Layer 2).

Python mirror of the contract in src/qabridge.ts: find the ``QSSQA|`` prefix
anywhere in a logcat line, JSON-parse the remainder, require ``msg``.

Typical use:
    adb logcat -s ReactNativeJS  ->  lines  ->  scan_lines(lines)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Iterable, Iterator, Optional

QA_BRIDGE_PREFIX = "QSSQA|"


@dataclass
class QaEvent:
    version: str
    msg: str
    args: list = field(default_factory=list)
    raw_line: str = ""


def parse_line(line: str) -> Optional[QaEvent]:
    """Parse one logcat line; return None for non-bridge or malformed lines."""
    idx = line.find(QA_BRIDGE_PREFIX)
    if idx < 0:
        return None
    payload = line[idx + len(QA_BRIDGE_PREFIX):].strip()
    try:
        parsed = json.loads(payload)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(parsed, dict) or not isinstance(parsed.get("msg"), str):
        return None
    args = parsed.get("args", [])
    return QaEvent(
        version=str(parsed.get("v", "")),
        msg=parsed["msg"],
        args=args if isinstance(args, list) else [args],
        raw_line=line,
    )


def scan_lines(lines: Iterable[str]) -> Iterator[QaEvent]:
    """Yield every bridge event found in an iterable of logcat lines."""
    for line in lines:
        event = parse_line(line)
        if event is not None:
            yield event


def find_event(lines: Iterable[str], msg_prefix: str, version: str | None = None) -> Optional[QaEvent]:
    """First event whose msg starts with msg_prefix (optionally version-pinned).

    Version pinning matters after plugin updates: old ring lines from a prior
    build must not satisfy a new build's assertion.
    """
    for event in scan_lines(lines):
        if not event.msg.startswith(msg_prefix):
            continue
        if version is not None and event.version != version:
            continue
        return event
    return None
