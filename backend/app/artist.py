"""Renders a Cartographer layout as a self-contained SVG poster in the style of
Pete Frame's Rock Family Trees: black ink on white paper, tall hand-lettered
capitals, unboxed line-ups with members hanging from a ruled bar, a line for
every musician, and paragraphs of handwritten notes.

Optional extras (off by default, as they aren't in the originals): an aged
paper tint, a slight ink wobble, a year scale and coloured lines."""
from datetime import date
from xml.sax.saxutils import escape

from app.cartographer import DATE_SIZE, NOTE_LINE, NOTE_SIZE, PAPER_MM, ROLE_LINE, ROLE_SIZE, TICK
from app.fonts import HAND, STYLES, font_face_css, text_width

WHITE = "#ffffff"
AGED = "#f4ecd8"
INK = "#000000"
LINE_COLOURS = ["#8c2f1f", "#1f4e79", "#2e6b3a", "#7a4b12", "#5b2a6e", "#1f6f6b", "#9a3a5e", "#4a4a1a"]


def _attrs(**kw):
    return " ".join(f'{k.rstrip("_").replace("_", "-")}="{escape(str(v), {chr(34): "&quot;"})}"'
                    for k, v in kw.items() if v is not None)


class Artist:
    def __init__(self, layout, output_path=None, hand_drawn=False, coloured_lines=False, aged_paper=False,
                 credit=None):
        self.L = layout
        self.ls = layout.get("lettering") or STYLES["classic"]
        self.output_path = output_path
        self.hand_drawn = hand_drawn
        self.coloured = coloured_lines
        self.aged = aged_paper
        self.paper = AGED if aged_paper else WHITE
        self.credit = credit
        self.parts = []
        self._colour_of = {}

    def _add(self, s):
        self.parts.append(s)

    def _text(self, x, y, content, size, anchor="start", fit=None, bold=False, family=HAND, weight=400,
              halo=False, **kw):
        extra = {}
        if fit and text_width(content, family, size, weight) > fit:
            extra = {"textLength": f"{fit:.1f}", "lengthAdjust": "spacingAndGlyphs"}
        if bold:  # thicken the pen stroke rather than switching font
            extra.update(stroke=INK, stroke_width=f"{size / 28:.2f}", stroke_linejoin="round")
        if halo:  # paper-coloured outline so lines appear to pass behind the lettering
            extra.update(stroke=self.paper, stroke_width="7", stroke_linejoin="round", paint_order="stroke")
        # inline style, as the stylesheet default would override presentation attributes
        style = [kw.pop("style")] if "style" in kw else []
        if family != HAND:
            style.append(f"font-family:'{family}'")
        if weight != 400:
            style.append(f"font-weight:{weight}")
        if style:
            extra["style"] = ";".join(style)
        self._add(f'<text {_attrs(x=f"{x:.1f}", y=f"{y:.1f}", font_size=size, text_anchor=anchor, **extra, **kw)}>'
                  f"{escape(content)}</text>")

    def _colour(self, person_id):
        if not self.coloured:
            return INK
        if person_id not in self._colour_of:
            self._colour_of[person_id] = LINE_COLOURS[len(self._colour_of) % len(LINE_COLOURS)]
        return self._colour_of[person_id]

    # ------------------------------------------------------------------
    def render(self):
        L = self.L
        W, H = L["width"], L["height"]
        size = {}
        if L.get("paper"):
            short, long_ = PAPER_MM[L["paper"]]
            size = {"width": f"{long_ if W > H else short}mm", "height": f"{short if W > H else long_}mm"}
        self._add(f'<svg xmlns="http://www.w3.org/2000/svg" {_attrs(viewBox=f"0 0 {W:.0f} {H:.0f}", **size)}>')
        self._add(f"<title>{escape(L['title'])}</title>")
        self._defs()
        self._add(f'<rect width="100%" height="100%" fill="{self.paper}"/>')
        if self.aged:
            self._add('<rect width="100%" height="100%" filter="url(#paper)" opacity="0.5"/>')
        self._frame(W, H)
        self._title(W)
        if L.get("timeline"):
            self._axes()
        wobble = ' filter="url(#rough)"' if self.hand_drawn else ""
        self._add(f'<g id="lines" fill="none" stroke-linecap="square" stroke-linejoin="miter"{wobble}>')
        self._edges()
        self._trunks()
        self._add("</g>")
        self._boxes(wobble)
        self._footer(W, H)
        self._add("</svg>")
        return "\n".join(self.parts)

    def save(self, svg=None):
        svg = svg or self.render()
        with open(self.output_path, "w", encoding="utf-8") as f:
            f.write(svg)
        return self.output_path

    # ------------------------------------------------------------------
    def _defs(self):
        self._add("<defs><style>")
        self._add(font_face_css(frozenset({(HAND, 400), (self.ls["family"], self.ls["weight"])})))
        self._add(f"text{{fill:{INK};font-family:'{HAND}','Comic Sans MS',cursive;}}")
        self._add("</style>")
        self._add('<filter id="rough" x="-2%" y="-2%" width="104%" height="104%">'
                  '<feTurbulence type="fractalNoise" baseFrequency="0.035" numOctaves="2" seed="7"/>'
                  '<feDisplacementMap in="SourceGraphic" scale="1.8"/></filter>')
        if self.aged:
            self._add('<filter id="paper" x="0" y="0" width="100%" height="100%">'
                      '<feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="3" seed="3"/>'
                      '<feColorMatrix values="0 0 0 0 0.45  0 0 0 0 0.38  0 0 0 0 0.25  0 0 0 0.18 0"/></filter>')
        self._add(f'<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" '
                  f'orient="auto-start-reverse"><path d="M0,1 L10,5 L0,9 z" fill="{INK}"/></marker>')
        self._add("</defs>")

    def _frame(self, W, H):
        self._add(f'<rect x="18" y="18" width="{W - 36:.0f}" height="{H - 36:.0f}" fill="none" stroke="{INK}" stroke-width="2.5"/>')

    def _title(self, W):
        """Big open (outlined) hand-drawn capitals with a solid drop shadow."""
        title = self.L["title"].upper()
        fam, wt = self.ls["family"], self.ls["weight"]
        fit = W - 200
        size = 130 if self.ls["title"] == "plain" else 96
        while size > 44 and text_width(title, fam, size, wt) > fit:
            size -= 4
        y = 40 + size * 0.85
        if self.ls["title"] == "outline":  # open capitals with a solid drop shadow
            self._text(W / 2 + 5, y + 5, title, size, "middle", fit=fit, family=fam, weight=wt, letter_spacing="3",
                       stroke=INK, stroke_width="3", stroke_linejoin="round")
            self._text(W / 2, y, title, size, "middle", fit=fit, family=fam, weight=wt, letter_spacing="3",
                       style=f"fill:{self.paper}", stroke=INK, stroke_width="2.5", stroke_linejoin="round",
                       paint_order="stroke")
        else:
            self._text(W / 2, y, title, size, "middle", fit=fit, family=fam, weight=wt, letter_spacing="4")
        tw = min(text_width(title, fam, size, wt) + 4 * len(title), fit)
        ly = y + 22
        self._add(f'<line x1="{W / 2 - tw / 2:.0f}" y1="{ly}" x2="{W / 2 + tw / 2:.0f}" y2="{ly}" stroke="{INK}" stroke-width="3"/>')
        self._add(f'<line x1="{W / 2 - tw / 2:.0f}" y1="{ly + 7}" x2="{W / 2 + tw / 2:.0f}" y2="{ly + 7}" stroke="{INK}" stroke-width="1"/>')
        sub = (self.L.get("subtitle") or "").upper()
        if sub:
            self._text(W / 2, ly + 42, sub, 22, "middle")

    def _axes(self):
        ax = self.L["axis"]
        for x in (ax["left"], ax["right"]):
            self._add(f'<line x1="{x:.1f}" y1="{ax["top"]:.0f}" x2="{x:.1f}" y2="{ax["bottom"]:.0f}" stroke="{INK}" stroke-width="0.8" stroke-dasharray="2 6"/>')
            for m in self.L["years"]:
                self._add(f'<line x1="{x - 6:.1f}" y1="{m["y"]:.1f}" x2="{x + 6:.1f}" y2="{m["y"]:.1f}" stroke="{INK}" stroke-width="1"/>')
                self._add(f'<rect x="{x - 24:.1f}" y="{m["y"] - 22:.1f}" width="48" height="16" fill="{self.paper}"/>')
                self._text(x, m["y"] - 9, str(m["year"]), 15, "middle")

    def _edges(self):
        radius = 6 if self.hand_drawn else 0
        for e in self.L["edges"]:
            colour = self._colour(e["person_id"])
            d = _rounded_path(e["points"], radius)
            dash = ' stroke-dasharray="8 5"' if e.get("dashed") else ""
            self._add(f'<path d="{d}" stroke="{self.paper}" stroke-width="4"/>')
            self._add(f'<path d="{d}" stroke="{colour}" stroke-width="1.2"{dash}/>')

    def _trunks(self):
        for t in self.L["trunks"]:
            dash = ' stroke-dasharray="8 5"' if t.get("dashed") else ""
            marker = ' marker-end="url(#arrow)"' if t.get("arrow") else ""
            colour = self._colour(t["person_id"])
            self._add(f'<path d="{_rounded_path(t["points"], 0)}" stroke="{colour}" stroke-width="1.3"{dash}{marker}/>')

    def _boxes(self, wobble):
        for b in self.L["boxes"]:
            x, y = b["x"], b["y"]
            # band name, big, with its dates stacked alongside
            ls = self.ls
            self._text(x, y + b["name_size"] * 0.8, b["name"], b["name_size"], family=ls["family"],
                       weight=ls["weight"], bold=ls["bold"], halo=True)
            dx = x + b["name_w"] + 10
            for i, d in enumerate(b["dates"]):
                self._text(dx, y + 16 + i * (DATE_SIZE + 3), d, DATE_SIZE, halo=True)
            # the ruled bar the members hang from
            bar_y = b["bar_y"]
            weight = 2.2 if b["level"] == 0 else 1.5
            self._add(f'<line x1="{b["bar"][0]:.1f}" y1="{bar_y:.1f}" x2="{b["bar"][1]:.1f}" y2="{bar_y:.1f}" '
                      f'stroke="{INK}" stroke-width="{weight}"{wobble}/>')
            for m in b["members"]:
                cx = m["cx"]
                self._add(f'<line x1="{cx:.1f}" y1="{bar_y:.1f}" x2="{cx:.1f}" y2="{bar_y + TICK - 2:.1f}" '
                          f'stroke="{INK}" stroke-width="1.2"/>')
                for i, line in enumerate(m["lines"]):
                    self._text(cx, m["y_name"] + i * ls["member_line"], line, ls["member_size"], "middle",
                               fit=ls["col_w"] - 6, family=ls["family"], weight=ls["weight"])
                ry = m["y_name"] + (len(m["lines"]) - 1) * ls["member_line"] + ROLE_LINE + 1
                for i, role in enumerate(m["roles"]):
                    self._text(cx, ry + i * ROLE_LINE, role, ROLE_SIZE, "middle", fit=ls["col_w"] - 4)
            if b["overflow"]:
                last = max(b["members"], key=lambda m: m["cx"])
                self._text(last["cx"] + ls["col_w"] / 2, b["y"] + b["h"], f"+ {b['overflow']} more", ROLE_SIZE, "end")
            # a paragraph of notes beside the line-up
            for i, note in enumerate(b["notes"]):
                self._text(b["notes_x"], bar_y + 6 + i * NOTE_LINE, note, NOTE_SIZE)

    def _footer(self, W, H):
        fy = self.L["footer_y"]
        x0 = 60
        self._text(x0, fy, "KEY", 20, bold=True)
        items = [
            ("trunk", "A MUSICIAN'S LINE, FROM ONE LINE-UP TO THE NEXT"),
            ("dashed", "BAND SPLIT, LATER RE-FORMED"),
            ("move", "MUSICIAN MOVES ON TO ANOTHER BAND"),
        ]
        for i, (kind, label) in enumerate(items):
            y = fy + 30 + i * 26
            if kind == "move":
                self._add(f'<path d="M{x0},{y - 12} h24 v8 h24" fill="none" stroke="{INK}" stroke-width="1.2"/>')
            else:
                dash = ' stroke-dasharray="8 5"' if kind == "dashed" else ""
                self._add(f'<line x1="{x0}" y1="{y - 6}" x2="{x0 + 50}" y2="{y - 6}" stroke="{INK}" stroke-width="1.3"{dash}/>')
            self._text(x0 + 64, y, label, 15)
        stats = self.L.get("stats", {})
        credit = self.credit or "RESEARCHED FROM MUSICBRAINZ · DRAWN BY THE ROCK FAMILY TREE GENERATOR"
        lines = [
            f"{stats.get('bands', 0)} BANDS · {stats.get('lineups', 0)} LINE-UPS · {stats.get('people', 0)} MUSICIANS",
            credit.upper(),
            f"IN HOMAGE TO PETE FRAME'S ROCK FAMILY TREES · {date.today():%B %Y}".upper(),
        ]
        for i, line in enumerate(lines):
            self._text(W - 60, fy + 30 + i * 24, line, 15, "end", fit=W / 2 - 80)


def _rounded_path(points, r):
    pts = [p for i, p in enumerate(points) if i == 0 or p != points[i - 1]]
    if len(pts) < 2:
        return ""
    d = [f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"]
    for i in range(1, len(pts) - 1):
        (x0, y0), (x1, y1), (x2, y2) = pts[i - 1], pts[i], pts[i + 1]
        l1 = max(abs(x1 - x0), abs(y1 - y0))
        l2 = max(abs(x2 - x1), abs(y2 - y1))
        rr = min(r, l1 / 2, l2 / 2)
        if rr < 0.5:
            d.append(f"L{x1:.1f},{y1:.1f}")
            continue
        ax = x1 - rr * _sign(x1 - x0)
        ay = y1 - rr * _sign(y1 - y0)
        bx = x1 + rr * _sign(x2 - x1)
        by = y1 + rr * _sign(y2 - y1)
        d.append(f"L{ax:.1f},{ay:.1f} Q{x1:.1f},{y1:.1f} {bx:.1f},{by:.1f}")
    d.append(f"L{pts[-1][0]:.1f},{pts[-1][1]:.1f}")
    return " ".join(d)


def _sign(v):
    return (v > 0) - (v < 0)
