"""Renders a Cartographer layout as a self-contained SVG poster in the style of
Pete Frame's hand-drawn Rock Family Trees: ink on aged paper, hand-lettered
text, numbered line-up boxes, family lines and marginal notes."""
from datetime import date
from xml.sax.saxutils import escape

from app.cartographer import NOTE_LINE, NOTE_SIZE, PAD, ROLE_SIZE, ROW_H, MEMBER_SIZE, DATE_SIZE, TRUNK_DX
from app.fonts import HAND, MARKER, POSTER, font_face_css, text_width

PAPER = "#f5efdf"
INK = "#1d1a16"
FADED = "#6b6255"
LINE_COLOURS = ["#8c2f1f", "#1f4e79", "#2e6b3a", "#7a4b12", "#5b2a6e", "#1f6f6b", "#9a3a5e", "#4a4a1a"]


def _attrs(**kw):
    return " ".join(f'{k.rstrip("_").replace("_", "-")}="{escape(str(v), {chr(34): "&quot;"})}"'
                    for k, v in kw.items() if v is not None)


class Artist:
    def __init__(self, layout, output_path=None, hand_drawn=True, coloured_lines=False, credit=None):
        self.L = layout
        self.output_path = output_path
        self.hand_drawn = hand_drawn
        self.coloured = coloured_lines
        self.credit = credit
        self.parts = []
        self._colour_of = {}

    def _add(self, s):
        self.parts.append(s)

    def _text(self, x, y, content, size, family=HAND, anchor="start", fit=None, cls=None, **kw):
        extra = {}
        if fit and text_width(content, family, size) > fit:
            extra = {"textLength": f"{fit:.1f}", "lengthAdjust": "spacingAndGlyphs"}
        self._add(f'<text {_attrs(x=f"{x:.1f}", y=f"{y:.1f}", font_size=size, font_family=family, text_anchor=anchor, class_=cls, **extra, **kw)}>'
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
            from app.cartographer import PAPER_MM
            short, long_ = PAPER_MM[L["paper"]]
            size = {"width": f"{long_ if W > H else short}mm", "height": f"{short if W > H else long_}mm"}
        self._add(f'<svg xmlns="http://www.w3.org/2000/svg" {_attrs(viewBox=f"0 0 {W:.0f} {H:.0f}", **size)}>')
        self._add(f"<title>{escape(L['title'])}</title>")
        self._defs()
        self._add(f'<rect width="100%" height="100%" fill="{PAPER}"/>')
        self._add(f'<rect width="100%" height="100%" filter="url(#paper)" opacity="0.5"/>')
        self._frame(W, H)
        self._title(W)
        self._axes()
        rough = ' filter="url(#rough)"' if self.hand_drawn else ""
        self._add(f'<g id="lines" fill="none" stroke-linecap="round" stroke-linejoin="round"{rough}>')
        self._edges()
        self._trunks()
        self._add("</g>")
        self._boxes(rough)
        self._footer(W, H)
        self._add("</svg>")
        return "\n".join(self.parts)

    def save(self, svg=None):
        svg = svg or self.render()
        with open(self.output_path, "w", encoding="utf-8") as f:
            f.write(svg)
        return self.output_path

    def draw_all(self):  # backwards compatible entry point
        return self.render()

    # ------------------------------------------------------------------
    def _defs(self):
        self._add("<defs><style>")
        self._add(font_face_css())
        self._add(f"text{{fill:{INK};}} .faded{{fill:{FADED};}} .note{{fill:#3a342c;}}")
        self._add("</style>")
        self._add('<filter id="rough" x="-2%" y="-2%" width="104%" height="104%">'
                  '<feTurbulence type="fractalNoise" baseFrequency="0.035" numOctaves="2" seed="7"/>'
                  '<feDisplacementMap in="SourceGraphic" scale="2.2"/></filter>')
        self._add('<filter id="paper" x="0" y="0" width="100%" height="100%">'
                  '<feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="3" seed="3"/>'
                  '<feColorMatrix values="0 0 0 0 0.45  0 0 0 0 0.38  0 0 0 0 0.25  0 0 0 0.18 0"/></filter>')
        self._add(f'<marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" '
                  f'orient="auto-start-reverse"><path d="M1,1 L9,5 L1,9" fill="none" stroke="{INK}" stroke-width="1.6"/></marker>')
        self._add("</defs>")

    def _frame(self, W, H):
        self._add(f'<rect x="14" y="14" width="{W - 28:.0f}" height="{H - 28:.0f}" fill="none" stroke="{INK}" stroke-width="3"/>')
        self._add(f'<rect x="22" y="22" width="{W - 44:.0f}" height="{H - 44:.0f}" fill="none" stroke="{INK}" stroke-width="1"/>')

    def _title(self, W):
        title = self.L["title"]
        size = 84
        while size > 40 and text_width(title, POSTER, size) > W - 160:
            size -= 4
        self._text(W / 2, 40 + size, title, size, POSTER, "middle", fit=W - 160, letter_spacing="2")
        tw = min(text_width(title, POSTER, size), W - 160)
        y = 40 + size + 22
        self._add(f'<path d="M{W / 2 - tw / 2:.0f},{y} q{tw / 4:.0f},-8 {tw / 2:.0f},0 t{tw / 2:.0f},0" '
                  f'fill="none" stroke="{INK}" stroke-width="2"/>')
        sub = self.L.get("subtitle") or ""
        if sub:
            self._text(W / 2, y + 36, sub, 20, HAND, "middle", cls="faded")

    def _axes(self):
        ax = self.L["axis"]
        top, bottom = ax["top"], ax["bottom"]
        for x in (ax["left"], ax["right"]):
            self._add(f'<line x1="{x:.1f}" y1="{top:.0f}" x2="{x:.1f}" y2="{bottom:.0f}" stroke="{FADED}" stroke-width="1" stroke-dasharray="2 5"/>')
            for m in self.L["years"]:
                self._add(f'<line x1="{x - 6:.1f}" y1="{m["y"]:.1f}" x2="{x + 6:.1f}" y2="{m["y"]:.1f}" stroke="{FADED}" stroke-width="1.2"/>')
                self._add(f'<rect x="{x - 24:.1f}" y="{m["y"] - 22:.1f}" width="48" height="16" fill="{PAPER}"/>')
                self._text(x, m["y"] - 9, str(m["year"]), 15, HAND, "middle", cls="faded")

    def _edges(self):
        for e in self.L["edges"]:
            colour = self._colour(e["person_id"])
            d = _rounded_path(e["points"], 7)
            self._add(f'<path d="{d}" stroke="{PAPER}" stroke-width="4.5"/>')
            self._add(f'<path d="{d}" stroke="{colour}" stroke-width="1.3" marker-end="url(#arrow)"/>')
            sx, sy = e["points"][0]
            self._add(f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="2.6" fill="{colour}" stroke="none"/>')

    def _trunks(self):
        for t in self.L["trunks"]:
            dash = ' stroke-dasharray="9 7"' if t.get("dashed") else ""
            marker = ' marker-end="url(#arrow)"' if t.get("arrow") else ""
            self._add(f'<path d="{_rounded_path(t["points"], 10)}" stroke="{INK}" stroke-width="3.2"{dash}{marker}/>')

    def _boxes(self, rough):
        for b in self.L["boxes"]:
            x, y, w, h = b["x"], b["y"], b["w"], b["h"]
            weight = 2.6 if b["level"] == 0 else 1.6
            self._add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w}" height="{h:.1f}" rx="3" fill="{PAPER}" '
                      f'stroke="{INK}" stroke-width="{weight}"{rough}/>')
            if b["level"] == 0:
                self._add(f'<rect x="{x + 4:.1f}" y="{y + 4:.1f}" width="{w - 8}" height="{h - 8:.1f}" rx="2" '
                          f'fill="none" stroke="{INK}" stroke-width="0.8"{rough}/>')
            # line-up number, sitting on the trunk
            cx = x + TRUNK_DX
            self._add(f'<circle cx="{cx:.1f}" cy="{y:.1f}" r="12" fill="{PAPER}" stroke="{INK}" stroke-width="1.6"/>')
            self._text(cx, y + 5, str(b["number"]), 14, MARKER, "middle")
            # band name + dates
            ty = y + PAD
            for line in b["name_lines"]:
                ty += b["name_size"] + 3
                self._text(x + w / 2, ty - 3, line, b["name_size"], MARKER, "middle", fit=w - 2 * PAD - 18)
            ty += DATE_SIZE + 4
            self._text(x + w / 2, ty - 2, b["date_label"], DATE_SIZE, HAND, "middle", cls="faded")
            # members
            inner = w - 2 * PAD
            for m in b["members"]:
                my = y + m["dy"] + MEMBER_SIZE / 2 - 2
                roles_w = text_width(m["roles"], HAND, ROLE_SIZE) if m["roles"] else 0
                if m["roles"]:
                    self._text(x + w - PAD, my, m["roles"], ROLE_SIZE, HAND, "end", cls="faded")
                self._text(x + PAD, my, m["name"], MEMBER_SIZE, HAND, fit=inner - roles_w - 8)
            if b["overflow"]:
                oy = y + b["header_h"] + len(b["members"]) * ROW_H + MEMBER_SIZE / 2 + 7
                self._text(x + PAD, oy, f"+ {b['overflow']} more", ROLE_SIZE, HAND, cls="faded")
            # notes hanging off the trunk
            ny = y + h + 8
            for note in b["notes"]:
                ny += NOTE_LINE
                self._text(x + TRUNK_DX + 10, ny - 3, note, NOTE_SIZE, HAND, cls="note", font_style="italic")

    def _footer(self, W, H):
        fy = self.L["footer_y"]
        x0 = 60
        self._text(x0, fy, "KEY", 18, MARKER)
        items = [
            ("trunk", "Line-up changes within a band"),
            ("dashed", "Band split, later re-formed"),
            ("move", "Musician moves on (dot = leaves, arrow = arrives)"),
        ]
        for i, (kind, label) in enumerate(items):
            y = fy + 28 + i * 26
            if kind == "move":
                self._add(f'<path d="M{x0 + 4},{y - 12} h24 v10 h20" fill="none" stroke="{INK}" stroke-width="1.3" marker-end="url(#arrow)"/>')
                self._add(f'<circle cx="{x0 + 4}" cy="{y - 12}" r="2.6" fill="{INK}"/>')
            else:
                dash = ' stroke-dasharray="9 7"' if kind == "dashed" else ""
                self._add(f'<line x1="{x0}" y1="{y - 6}" x2="{x0 + 50}" y2="{y - 6}" stroke="{INK}" stroke-width="3.2"{dash}/>')
            self._text(x0 + 64, y, label, 15, HAND)
        stats = self.L.get("stats", {})
        credit = self.credit or "Researched from MusicBrainz (CC0) · drawn by the Rock Family Tree Generator"
        lines = [
            f"{stats.get('bands', 0)} bands · {stats.get('lineups', 0)} line-ups · {stats.get('people', 0)} musicians",
            credit,
            f"In homage to Pete Frame's Rock Family Trees · {date.today():%B %Y}",
        ]
        for i, line in enumerate(lines):
            self._text(W - 60, fy + 28 + i * 24, line, 15, HAND, "end", cls="faded", fit=W / 2 - 80)


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
