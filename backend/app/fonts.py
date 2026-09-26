"""Bundled fonts: embedded into SVGs as data URIs, and measured with
fontTools so text can be fitted to boxes without a browser."""
import base64
import os
from functools import lru_cache

FONT_DIR = os.path.join(os.path.dirname(__file__), "assets", "fonts")

# family -> woff2 files (latin first, then extended coverage)
FAMILIES = {
    "Architects Daughter": ["architects-daughter-latin-400-normal.woff2",
                            "architects-daughter-latin-ext-400-normal.woff2"],
}

# Pete Frame lettered everything in neat architect's capitals; one hand does it all.
HAND = "Architects Daughter"


class _Metrics:
    def __init__(self, family):
        self.widths = {}
        self.upm = 1000
        self.fallback = 0.55
        try:
            from fontTools.ttLib import TTFont
            for fname in reversed(FAMILIES[family]):
                font = TTFont(os.path.join(FONT_DIR, fname))
                self.upm = font["head"].unitsPerEm
                hmtx = font["hmtx"].metrics
                for cp, glyph in font.getBestCmap().items():
                    self.widths[cp] = hmtx[glyph][0] / self.upm
            if self.widths:
                self.fallback = sum(self.widths.get(ord(c), 0.55) for c in "etaoinshrdlu") / 12
        except Exception as e:  # fonts missing or fontTools not installed
            print(f"Font metrics unavailable for {family}: {e}")

    def width(self, text, size):
        return sum(self.widths.get(ord(c), self.fallback) for c in text) * size


@lru_cache(maxsize=None)
def metrics(family):
    return _Metrics(family)


def text_width(text, family, size):
    return metrics(family).width(text or "", size)


def wrap(text, family, size, max_width):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if line and text_width(trial, family, size) > max_width:
            lines.append(line)
            line = word
        else:
            line = trial
    if line:
        lines.append(line)
    return lines


@lru_cache(maxsize=None)
def font_face_css():
    rules = []
    for family, files in FAMILIES.items():
        for fname in files:
            path = os.path.join(FONT_DIR, fname)
            if not os.path.exists(path):
                continue
            with open(path, "rb") as f:
                data = base64.b64encode(f.read()).decode("ascii")
            rules.append(f"@font-face{{font-family:'{family}';src:url(data:font/woff2;base64,{data}) format('woff2');}}")
    return "\n".join(rules)
