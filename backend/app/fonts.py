"""Bundled fonts: embedded into SVGs as data URIs, and measured with
fontTools so text can be fitted without a browser.

LETTERING (Amatic SC) stands in for Pete Frame's tall, narrow, thin-stroked
capitals used for band and musician names; HAND (Architects Daughter) is the
smaller handwriting used for instruments, dates and notes."""
import base64
import os
from functools import lru_cache

FONT_DIR = os.path.join(os.path.dirname(__file__), "assets", "fonts")

LETTERING = "Amatic SC"
HAND = "Architects Daughter"

# (family, weight) -> woff2 files, latin first then extended coverage
FACES = {
    (LETTERING, 400): ["amatic-sc-latin-400-normal.woff2", "amatic-sc-latin-ext-400-normal.woff2"],
    (LETTERING, 700): ["amatic-sc-latin-700-normal.woff2", "amatic-sc-latin-ext-700-normal.woff2"],
    (HAND, 400): ["architects-daughter-latin-400-normal.woff2", "architects-daughter-latin-ext-400-normal.woff2"],
}


# Frame varied his lettering with the music. "classic" is the neat architect's
# hand of his 60s/70s rock trees; "heavy" is the tall, narrow, thin-stroked
# capitals of trees like Black Sabbath / Ozzy Osbourne.
STYLES = {
    "classic": {"family": HAND, "weight": 400, "bold": True, "name_size": 30, "member_size": 17,
                "member_line": 19, "col_w": 118, "title": "outline"},
    "heavy": {"family": LETTERING, "weight": 700, "bold": False, "name_size": 46, "member_size": 25,
              "member_line": 21, "col_w": 92, "title": "plain"},
}

HEAVY_GENRES = ("metal", "hard rock", "doom", "thrash", "stoner", "sludge", "grunge", "hardcore", "punk",
                "industrial", "nu metal", "metalcore", "grindcore", "black metal", "death metal")


def lettering_for(genres):
    """Pick a lettering style from MusicBrainz genre/tag names."""
    names = [g.lower() for g in genres or []]
    return "heavy" if any(h in g for g in names for h in HEAVY_GENRES) else "classic"


class _Metrics:
    def __init__(self, family, weight):
        self.widths = {}
        self.fallback = 0.55
        try:
            from fontTools.ttLib import TTFont
            for fname in reversed(FACES[(family, weight)]):
                font = TTFont(os.path.join(FONT_DIR, fname))
                upm = font["head"].unitsPerEm
                hmtx = font["hmtx"].metrics
                for cp, glyph in font.getBestCmap().items():
                    self.widths[cp] = hmtx[glyph][0] / upm
            if self.widths:
                self.fallback = sum(self.widths.get(ord(c), 0.55) for c in "etaoinshrdlu") / 12
        except Exception as e:  # fonts missing or fontTools not installed
            print(f"Font metrics unavailable for {family} {weight}: {e}")

    def width(self, text, size):
        return sum(self.widths.get(ord(c), self.fallback) for c in text) * size


@lru_cache(maxsize=None)
def metrics(family, weight=400):
    return _Metrics(family, weight)


def text_width(text, family, size, weight=400):
    return metrics(family, weight).width(text or "", size)


def wrap(text, family, size, max_width, weight=400):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if line and text_width(trial, family, size, weight) > max_width:
            lines.append(line)
            line = word
        else:
            line = trial
    if line:
        lines.append(line)
    return lines


@lru_cache(maxsize=None)
def font_face_css(faces=None):
    """@font-face rules for the given (family, weight) pairs (default: all)."""
    rules = []
    for (family, weight), files in FACES.items():
        if faces is not None and (family, weight) not in faces:
            continue
        for fname in files:
            path = os.path.join(FONT_DIR, fname)
            if not os.path.exists(path):
                continue
            with open(path, "rb") as f:
                data = base64.b64encode(f.read()).decode("ascii")
            rules.append(f"@font-face{{font-family:'{family}';font-weight:{weight};"
                         f"src:url(data:font/woff2;base64,{data}) format('woff2');}}")
    return "\n".join(rules)
