"""OCR word-box locator (QA-REENGINEERING.md Layer 3, rung 2).

Turns `tesseract <img> - tsv` output into tappable coordinates: parse word
boxes, group into lines, match a target phrase case/whitespace-insensitively,
return the phrase's bounding-box center.

Pure logic over TSV text — unit-testable without a device or tesseract. The
capture side is one subprocess call:

    tesseract screenshot.png - --psm 11 tsv   ->  locate_phrase(tsv, "Filter servers")
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import List, Optional

DEFAULT_MIN_CONF = 40.0


@dataclass
class WordBox:
    text: str
    left: int
    top: int
    width: int
    height: int
    conf: float
    line_key: tuple = ()

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height


@dataclass
class Match:
    text: str
    center: tuple
    box: tuple  # (left, top, right, bottom)
    conf: float


def parse_tsv(tsv_text: str, min_conf: float = DEFAULT_MIN_CONF) -> List[WordBox]:
    """Parse tesseract TSV output into confident word boxes."""
    words: List[WordBox] = []
    lines = tsv_text.splitlines()
    if not lines:
        return words
    header = lines[0].split("\t")
    idx = {name: i for i, name in enumerate(header)}
    required = ("text", "left", "top", "width", "height", "conf", "block_num", "par_num", "line_num")
    if any(k not in idx for k in required):
        return words
    for row_text in lines[1:]:
        row = row_text.split("\t")
        if len(row) < len(header):
            continue
        text = row[idx["text"]].strip()
        if not text:
            continue
        try:
            conf = float(row[idx["conf"]])
            if conf < min_conf:
                continue
            words.append(
                WordBox(
                    text=text,
                    left=int(row[idx["left"]]),
                    top=int(row[idx["top"]]),
                    width=int(row[idx["width"]]),
                    height=int(row[idx["height"]]),
                    conf=conf,
                    line_key=(row[idx["block_num"]], row[idx["par_num"]], row[idx["line_num"]]),
                )
            )
        except ValueError:
            continue
    return words


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def locate_phrase(tsv_text: str, phrase: str, min_conf: float = DEFAULT_MIN_CONF) -> Optional[Match]:
    """Find phrase as consecutive words on one OCR line; return its box center.

    Returns the highest-confidence match when the phrase appears more than once.
    """
    target = _norm(phrase).split(" ")
    if not target:
        return None
    words = parse_tsv(tsv_text, min_conf)

    by_line: dict = {}
    for w in words:
        by_line.setdefault(w.line_key, []).append(w)

    best: Optional[Match] = None
    for line_words in by_line.values():
        line_words.sort(key=lambda w: w.left)
        texts = [_norm(w.text) for w in line_words]
        for start in range(len(texts) - len(target) + 1):
            if texts[start:start + len(target)] != target:
                continue
            span = line_words[start:start + len(target)]
            left = min(w.left for w in span)
            top = min(w.top for w in span)
            right = max(w.right for w in span)
            bottom = max(w.bottom for w in span)
            conf = sum(w.conf for w in span) / len(span)
            match = Match(
                text=" ".join(w.text for w in span),
                center=((left + right) // 2, (top + bottom) // 2),
                box=(left, top, right, bottom),
                conf=conf,
            )
            if best is None or match.conf > best.conf:
                best = match
    return best


def ocr_tsv(image_path: str, psm: int = 11, timeout_s: float = 20.0) -> str:
    """Run tesseract on an image, return raw TSV (thin shell; not unit-tested)."""
    return subprocess.run(
        ["tesseract", image_path, "-", "--psm", str(psm), "tsv"],
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=True,
    ).stdout
