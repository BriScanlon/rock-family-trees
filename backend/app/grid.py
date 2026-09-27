"""Pete Frame's grid.

Frame's trees are laid out on a grid: every musician takes the same width
(first name over surname, instrument beneath), so a line-up is exactly as
wide as its members; and line-ups of the same era sit side by side on one
row, their names and ruled bars lined up across the page. Each line-up is a
block: the band name and dates, a short paragraph of notes beneath them, then
the bar with the members hanging from it. A band keeps its columns all the
way down, so every musician's line drops straight to their next line-up, and
musicians who move on are traced along the channel under each row and down
the gaps between blocks.

The grid is measured in half-member columns (so the gap beside a block, where
lines run, costs half a member) and rows of one block each. It can be the
sheet itself at the smallest readable print size (`cols`/`rows` given: the
fitting fills it) or grow to hold whatever it is given, to be scaled onto the
paper afterwards.
"""
import math
from collections import defaultdict

from app.cartographer import (DATE_SIZE, FOOTER_H, MARGIN, MAX_MEMBERS, MAX_NOTES, MIN_PRINT_PT, NOTE_LINE,
                              NOTE_SIZE, PAPER_MM, ROLE_LINE, ROLE_SIZE, TICK, TITLE_H, Cartographer, _split_name)
from app.fonts import HAND, text_width, wrap

NOTE_LINES = 4          # most lines of notes in a block, under the band name
ANNOT_LINES = 2         # annotations under a member: "joined Mar 97", "then T. Hawkins"
BRIEF_NAMES = 4         # most names in a "Briefly also" list
NOTE_WIDEN = 2          # a block may be widened by this many members to fit its notes
CHANNEL = 30            # the band under each row where lines run across the page
LINE_STEP = 5           # separation of parallel lines in a channel or gap
PACK_REPAIRS = 40       # rounds of re-placing to turn upward moves downwards
MAX_SPREAD = 0.35       # most the rows may be spread (as a share of a row) to fill a sheet
ERA_WEIGHT = 1.5        # pull towards the row where line-ups of the same date sit
TOP_WEIGHT = 0.3        # pull towards the top: keep the tree compact
NEAR_WEIGHT = 0.08      # pull (per column) towards bands sharing musicians


def _dims(ls):
    """(member slot, title height, title-to-bar, block height) for a lettering style.
    Under each member: the instrument, then up to ANNOT_LINES of annotations."""
    title_h = ls["name_size"] + 6
    bar_dy = title_h + NOTE_LINES * NOTE_LINE + 10
    block_h = bar_dy + TICK + ls["member_size"] * 0.8 + ls["member_line"] + (1 + ANNOT_LINES) * ROLE_LINE + 4
    return ls["col_w"], title_h, bar_dy, block_h


MONTH = 1 / 12


def _short(name):
    """ "Taylor Hawkins" -> "T. Hawkins": fits under one member."""
    parts = name.split()
    return name if len(parts) < 2 else f"{parts[0][0]}. {' '.join(parts[1:])}"


def _year(t):
    return str(int(t))


def _long(label):
    """ "Mar 97" -> "March 1997", as the notes are written in full."""
    from app.cartographer import _long_date
    return _long_date(label) if label else None


def _slack(*labels):
    """How far apart two dates may seem and still be one hand-over: a month,
    or a year when either is known only to the year."""
    return 1.0 if any(l and l.strip().isdigit() for l in labels) else MONTH


class GridLayout(Cartographer):
    def __init__(self, tree, paper="auto", subtitle=None, lettering="classic", cols=None, rows=None):
        super().__init__(tree, paper=paper, subtitle=subtitle, timeline=False, lettering=lettering)
        self.slot, self.title_h, self.bar_dy, self.block_h = _dims(self.ls)
        self.unit = self.slot / 2
        self.row_h = self.block_h + CHANNEL
        self.max_cols, self.max_rows = cols, rows

    # ------------------------------------------------------------------
    @staticmethod
    def sheet(paper, lettering_style):
        """The sheet at the smallest readable print size: (cols, rows, width px, height px),
        in whichever orientation holds more."""
        slot, _, _, block_h = _dims(lettering_style)
        unit, row_h = slot / 2, block_h + CHANNEL
        px_per_mm = min(ROLE_SIZE, DATE_SIZE, NOTE_SIZE) / (MIN_PRINT_PT * 25.4 / 72)
        short, long_ = PAPER_MM[paper]
        best = None
        for w_mm, h_mm in ((short, long_), (long_, short)):
            W, H = w_mm * px_per_mm, h_mm * px_per_mm
            cols = int((W - 2 * MARGIN) // unit)
            rows = int((H - TITLE_H - FOOTER_H) // row_h)
            if best is None or cols * rows > best[0] * best[1]:
                best = (cols, rows, W, H)
        return best

    def fits(self):
        """Whether everything fits the bounded grid (no geometry, for the fitting)."""
        self._prepare()
        return self._pack(self.max_cols, self.max_rows) is not None

    def layout(self):
        self._prepare()
        if self.max_cols is not None:
            placed = self._pack(self.max_cols, self.max_rows)
            if placed is None:
                raise ValueError("The line-ups do not fit this sheet")
        else:
            placed = self._pack_to_shape()
        return self._geometry(placed)

    # ------------------------------------------------------------------
    def _prepare(self):
        if getattr(self, "_units_cache", None) is not None:
            return
        bands = sorted(self.tree.bands.values(), key=lambda b: (b.start, b.name))
        if not bands:
            raise ValueError("Nothing to draw: no band line-ups with usable dates were found")
        self.appearances = self._appearances(bands)
        self.boxes, self.box_order = {}, []
        units = []
        for band in bands:
            for u in self._band_units(band):
                units.append(u)
        self.moves = self._moves()
        people = {b.id: {s.person_id for s in b.stints} for b in bands}
        self.linked = {(a, b): len(people[a] & people[b]) for a in people for b in people
                       if a != b and people[a] & people[b]}
        self._units_cache = sorted(units, key=lambda u: (u["boxes"][0]["start"], u["band"].name))

    def _band_units(self, band):
        """The band's line-up blocks, measured in members, grouped into runs
        with no break (a band that split and re-formed is two runs)."""
        ls, slot = self.ls, self.slot
        columns = self._columns(band)
        ncols = max(max(c.values(), default=0) for c in columns) + 1
        name = band.name.upper()
        size = ls["name_size"]
        while size > ls["name_size"] * 0.6 and text_width(name, ls["family"], size, ls["weight"]) > 6 * slot:
            size -= 2
        name_w = text_width(name, ls["family"], size, ls["weight"])
        units = []
        for i, lu in enumerate(band.lineups):
            nxt = band.lineups[i + 1] if i + 1 < len(band.lineups) else None
            dates = [lu.start_label.upper(), lu.end_label.upper()]
            title_w = name_w + 10 + max(text_width(d, HAND, DATE_SIZE) for d in dates)
            span = max(min(ncols, MAX_MEMBERS), math.ceil(title_w / slot))
            marks, extra = self._annotations(band, lu)
            # a leaving told under the member (with its own date) isn't repeated
            # in the notes, which would give it the line-up's end date instead
            told = {m.name for m in lu.members if any(k.startswith(("then", "left")) for k in marks.get(m.person_id, []))}
            said = [n for n in self._notes(band, lu, nxt) if not n.startswith("Simplified to fit")
                    and not any(n.startswith(f"{who} left in ") for who in told)]
            if i == 0 and band.undated:  # left out of the line-ups: MusicBrainz has no dates
                extra = extra + [f"Also, dates unknown: {', '.join(band.undated[:BRIEF_NAMES])}"
                                 f"{f' and {len(band.undated) - BRIEF_NAMES} others' if len(band.undated) > BRIEF_NAMES else ''}."]
            notes = " ".join((said + extra)[:MAX_NOTES])
            widest = span + NOTE_WIDEN
            while span < widest and len(wrap(notes, HAND, NOTE_SIZE, span * slot - 8)) > NOTE_LINES:
                span += 1
            box = {"id": f"{band.id}#{lu.number}", "band_id": band.id, "band_name": band.name, "number": lu.number,
                   "start": lu.start, "end": lu.end, "after_gap": lu.after_gap, "ongoing": lu.ongoing,
                   "level": band.level, "band_start": band.start, "name": name, "name_size": size, "name_w": name_w,
                   "dates": dates, "date_label": f"{lu.start_label} – {lu.end_label}".upper(),
                   "cols": columns[i], "span": span, "notes_text": notes, "marks": marks, "lineup": lu}
            self.boxes[box["id"]] = box
            self.box_order.append(box["id"])
            if i == 0 or lu.after_gap:
                units.append({"band": band, "boxes": []})
            units[-1]["boxes"].append(box)
        for u in units:
            u["span"] = max(b["span"] for b in u["boxes"])
            u["w"] = 2 * u["span"] + 1  # half-member columns, with a half-member gap for lines
        return units

    def _annotations(self, band, lu):
        """What happened inside a line-up's span that the block itself
        doesn't show (a condensed line-up stands for several), told as Frame
        did under the members: "joined Mar 97", "left Sep 97", "then
        T. Hawkins" / "after W. Goldsmith" for whoever filled the same place
        in between. Anyone with no place to go under a member is listed in
        the notes. Returns ({person id: [annotations]}, [note sentences])."""
        shown = {m.person_id: m for m in lu.members}
        active = [s for s in band.stints if s.start < lu.end - MONTH and s.end > lu.start + MONTH]
        spans = {}
        for s in active:
            if s.person_id in shown:
                a, e = spans.get(s.person_id, (s, s))
                spans[s.person_id] = (min(a, s, key=lambda x: x.start), max(e, s, key=lambda x: x.end))
        # who held the same place before or after a member: these come first,
        # as "then T. Hawkins" says more than "left Mar 97" (and implies it)
        links, extra, joins = defaultdict(list), [], []
        for s in sorted((s for s in active if s.person_id not in shown), key=lambda s: s.start):
            role = s.roles[0] if s.roles else None
            host = None
            for pid, (first, last) in spans.items():
                if role is None or role not in shown[pid].roles[:1] or len(links[pid]) >= ANNOT_LINES:
                    continue
                # a date known only to the year could be any month of it
                if s.end <= first.start + _slack(s.end_label, first.start_label):
                    host = (pid, f"after {_short(s.name)}")
                elif s.start >= last.end - _slack(s.start_label, last.end_label):
                    host = (pid, f"then {_short(s.name)}")
                if host:
                    break
            if host:
                links[host[0]].append(host[1])
            elif s.end >= lu.end - MONTH:  # stayed on into the next line-up
                again = any(o.person_id == s.person_id and o.end <= s.start for o in band.stints)
                joins.append(f"{s.name} {'rejoined' if again else 'joined'} in "
                             f"{_long(s.start_label) or _year(s.start)}.")
            elif s.start <= lu.start + MONTH:  # was there at the start
                joins.append(f"{s.name} left in {_long(s.end_label) or _year(s.end)}.")
            else:  # came and went within the line-up
                extra.append(f"{s.name}{f' ({role})' if role else ''}")
        marks = {}
        for pid, (first, last) in spans.items():
            dates = []
            if first.start > lu.start + MONTH and not any(l.startswith("after") for l in links[pid]):
                dates.append(f"joined {first.start_label or _year(first.start)}")
            if last.end < lu.end - MONTH and not any(l.startswith("then") for l in links[pid]):
                dates.append(f"left {last.end_label or _year(last.end)}")
            if links[pid] or dates:
                marks[pid] = (links[pid] + dates)[:ANNOT_LINES]
        extra = list(dict.fromkeys(extra))  # one mention each, however many stints
        if len(extra) > BRIEF_NAMES:  # a wall of names says less than a count
            extra = extra[:BRIEF_NAMES] + [f"and {len(extra) - BRIEF_NAMES} others"]
        notes = list(dict.fromkeys(joins)) + ([f"Briefly also: {', '.join(extra)}."] if extra else [])
        return marks, notes

    # ------------------------------------------------------------------
    def _pack(self, n_cols, n_rows):
        """Place every run of line-ups, in date order, each whole in its own
        columns. Every line-up sits below the line-ups its musicians came
        from, below everything already in its columns (time runs down every
        column), as near its era's row and the bands it shares musicians with
        as it can. A run placed early fixes the rows of its later line-ups
        before the bands feeding them are placed, so any move left pointing
        upwards gives its target a lower minimum row and the page is placed
        again. None if it won't fit."""
        floors = {}
        for _ in range(PACK_REPAIRS):
            placed = self._pack_once(n_cols, n_rows, floors)
            if placed is None:
                return None
            upward = [(a, b) for _, a, b in self.moves if self._tier[b["id"]] <= self._tier[a["id"]]]
            if not upward:
                return placed
            for a, b in upward:
                floors[b["id"]] = max(floors.get(b["id"], 0), self._tier[a["id"]] + 1)
        return None

    def _pack_once(self, n_cols, n_rows, floors):
        units = self._units_cache
        sky = [0] * n_cols
        latest = [-math.inf] * n_cols  # the latest start drawn in each column
        cell = {}
        tier, col0 = {}, {}
        placed = []
        eras = []
        cols_of = defaultdict(list)
        into = defaultdict(list)   # box id -> boxes its musicians came from
        for _, a, b in self.moves:
            into[b["id"]].append(a)
        for u in units:
            w = u["w"]
            if w > n_cols:
                return None
            lims = []
            for b in u["boxes"]:
                # (moves into line-ups already placed can't be honoured here: _pack repairs them)
                lims.append(max([tier[a["id"]] + 1 for a in into[b["id"]] if a["id"] in tier]
                                + [floors.get(b["id"], 0)]))
            era_rows = [self._era_row(eras, b["start"]) for b in u["boxes"]]
            links = [(c, self.linked.get((u["band"].id, bid), 0)) for bid, cs in cols_of.items()
                     for c in cs if bid != u["band"].id and self.linked.get((u["band"].id, bid))]
            own = cols_of.get(u["band"].id, [])
            best = None
            first = u["boxes"][0]["start"]
            for c0 in range(n_cols - w + 1):
                if max(latest[c0:c0 + w]) > first:
                    continue  # time runs down every column: nothing later above it
                floor = max(sky[c0:c0 + w])
                rows, r = [], floor - 1
                for lo in lims:
                    r = max(lo, r + 1)
                    if n_rows is not None and r >= n_rows:
                        rows = None
                        break
                    rows.append(r)
                if rows is None:
                    continue
                era = sum(abs(r - e) for r, e in zip(rows, era_rows)) / len(rows)
                near = sum(k * abs(c0 - c) for c, k in links) / max(1, sum(k for _, k in links))
                near += 3 * min((abs(c0 - c) for c in own), default=0)  # a re-formed band returns to its columns
                cost = ((rows[-1] - rows[0]) + TOP_WEIGHT * rows[0] + ERA_WEIGHT * era
                        + NEAR_WEIGHT * near + 0.001 * c0)
                if best is None or cost < best[0]:
                    best = (cost, c0, rows)
            if best is None:
                return None
            _, c0, rows = best
            for c in range(c0, c0 + w):
                sky[c] = rows[-1] + 1
                latest[c] = max(latest[c], u["boxes"][-1]["start"])
                for t in range(rows[0], rows[-1] + 1):
                    cell[(t, c)] = "gap" if c == c0 + w - 1 else u["band"].id
            for b, r in zip(u["boxes"], rows):
                tier[b["id"]], col0[b["id"]] = r, c0
                eras.append((b["start"], r))
                placed.append(b)
            cols_of[u["band"].id].append(c0)
        self._cells = cell
        self._tier, self._col0 = tier, col0
        return placed

    @staticmethod
    def _era_row(eras, t):
        """The row line-ups dated t belong on, from those already placed.
        Later than everything so far: the latest row used, not further down."""
        if not eras:
            return 0
        lower = [p for p in eras if p[0] <= t]
        upper = [p for p in eras if p[0] >= t]
        if lower and upper:
            (t0, r0), (t1, r1) = max(lower), min(upper)
            return r0 if t1 == t0 else r0 + (r1 - r0) * (t - t0) / (t1 - t0)
        return min(r for _, r in eras) if not lower else max(r for s, r in lower)

    def _pack_to_shape(self):
        """No sheet to fill: try grid widths and keep the one whose drawing
        best suits a sheet of paper (least area once grown to A-proportions)."""
        widest = max(u["w"] for u in self._units_cache)
        total = sum(u["w"] for u in self._units_cache)
        best = None
        for n_cols in sorted({max(widest, int(widest + (total - widest) * k / 12)) for k in range(13)}):
            placed = self._pack(n_cols, None)
            if placed is None:
                continue
            used_cols = max(self._col0[b["id"]] + 2 * b["span"] + 1 for b in placed)
            used_rows = max(self._tier.values()) + 1
            w = 2 * MARGIN + used_cols * self.unit
            h = TITLE_H + used_rows * self.row_h + FOOTER_H
            area = min(max(w, h / 2 ** 0.5) * max(h, w * 2 ** 0.5), max(w, h * 2 ** 0.5) * max(h, w / 2 ** 0.5))
            if best is None or area < best[0]:
                best = (area, n_cols)
        if best is None:
            raise ValueError("Could not arrange the line-ups so every move runs down the page")
        return self._pack(best[1], None)

    # ------------------------------------------------------------------
    def _geometry(self, placed):
        ls, slot, unit = self.ls, self.slot, self.unit
        used_cols = max(self._col0[b["id"]] + 2 * b["span"] for b in placed)
        used_rows = max(self._tier.values()) + 1
        content_w = 2 * MARGIN + used_cols * unit
        content_h = TITLE_H + used_rows * self.row_h + FOOTER_H
        if self.max_cols is not None:  # the sheet itself, at the smallest readable size
            width, height = self._sheet_px()
            pitch = self.row_h + min(MAX_SPREAD * self.row_h,
                                     max(0.0, (height - content_h) / max(1, used_rows)))
        else:
            if self.auto_paper:
                self.paper = self._choose_paper(content_w, content_h)
            width, height, _ = self._paper_size(content_w, content_h)
            pitch = self.row_h + min(MAX_SPREAD * self.row_h,
                                     max(0.0, (height - content_h) / max(1, used_rows)))
        x0 = (width - used_cols * unit) / 2
        row_y = lambda t: TITLE_H + t * pitch
        self.pitch = pitch

        boxes = []
        for b in placed:
            t, c0 = self._tier[b["id"]], self._col0[b["id"]]
            x, y = x0 + c0 * unit, row_y(t)
            lu = b["lineup"]
            members = []
            for m in lu.members[:MAX_MEMBERS]:
                lines = _split_name(m.name.upper())
                roles = list(m.roles[:1])  # Frame gives each musician one instrument
                person = self.tree.people.get(m.person_id)
                if person and person.died is not None and lu.start <= person.died <= lu.end + 0.3:
                    roles.append(f"(died {person.died_label})")
                roles += b["marks"].get(m.person_id, [])
                roles = roles[:1 + ANNOT_LINES]
                cx = x + min(b["cols"][m.person_id], MAX_MEMBERS - 1) * slot + slot / 2
                y_name = y + self.bar_dy + TICK + ls["member_size"] * 0.8
                bottom = y_name + (len(lines) - 1) * ls["member_line"] + len(roles) * ROLE_LINE + 5
                members.append({"person_id": m.person_id, "col": b["cols"][m.person_id], "cx": cx,
                                "y_name": y_name, "lines": lines, "roles": roles, "bottom": bottom})
            members.sort(key=lambda m: m["col"])
            cxs = [m["cx"] for m in members] or [x + slot / 2]
            notes = wrap(b["notes_text"], HAND, NOTE_SIZE, b["span"] * slot - 8)
            if len(notes) > NOTE_LINES:
                notes = notes[:NOTE_LINES]
                notes[-1] = notes[-1].rstrip(" .,;") + "…"
            b.update({"x": x, "y": y, "w": b["span"] * slot, "h": self.block_h, "footprint": self.block_h,
                      "lane": c0, "row": t, "bar_y": y + self.bar_dy, "bar": (min(x, min(cxs) - 12), max(cxs) + 12),
                      "members": members, "overflow": max(0, len(lu.members) - MAX_MEMBERS),
                      "notes": notes, "notes_x": x, "notes_y": y + self.title_h})
            boxes.append(b)

        trunks, edges = self._route(placed, x0, row_y)
        years = []
        for t in range(used_rows):
            starts = [b["start"] for b in placed if self._tier[b["id"]] == t]
            if starts:
                years.append({"year": int(min(starts)), "y": row_y(t) + 4})
        layout = {
            "width": width, "height": height, "paper": self.paper,
            "title": self.tree.title, "subtitle": self.subtitle, "lettering": self.ls, "timeline": False,
            "axis": {"left": MARGIN / 2, "right": width - MARGIN / 2, "top": TITLE_H - 20,
                     "bottom": row_y(used_rows)},
            "years": years,
            "boxes": [{k: v for k, v in b.items() if k not in ("lineup", "cols")} | {"cols": dict(b["cols"])}
                      for b in boxes],
            "trunks": trunks, "edges": edges,
            "footer_y": height - FOOTER_H + 30,
            "grid": {"cols": self.max_cols or used_cols, "rows": self.max_rows or used_rows,
                     "used_cols": used_cols, "used_rows": used_rows, "unit": unit, "row_h": pitch},
            "stats": {"bands": len(self.tree.bands), "lineups": len(boxes),
                      "people": len({m["person_id"] for b in boxes for m in b["members"]}),
                      **self._print_report(width, height)},
        }
        return layout

    def _sheet_px(self):
        cols, rows, W, H = GridLayout.sheet(self.paper, self.ls)
        return W, H

    # ------------------------------------------------------------------
    def _route(self, placed, x0, row_y):
        """Each musician's line straight down to their next line-up in the
        same run; every other move along the channel under the source row,
        down the nearest clear gap, along the channel above the target row
        and into place. Parallel lines are spread so none sit on each other."""
        member = {(b["id"], m["person_id"]): m for b in placed for m in b["members"]}
        unit_of = {}
        for u in self._units_cache:
            for b in u["boxes"]:
                unit_of[b["id"]] = id(u)
        channel_y = lambda t: row_y(t) + self.block_h + (self.pitch - self.block_h) / 2
        in_channel, in_gap = defaultdict(int), defaultdict(int)
        spread = lambda k: ((k % 5) - 2) * LINE_STEP

        trunks, edges = [], []
        for person_id, a, b in self.moves:
            ma, mb = member.get((a["id"], person_id)), member.get((b["id"], person_id))
            if ma is None or mb is None:
                continue  # beyond MAX_MEMBERS
            ta, tb = self._tier[a["id"]], self._tier[b["id"]]
            if unit_of[a["id"]] == unit_of[b["id"]] and b["number"] == a["number"] + 1:
                pts = [(ma["cx"], ma["bottom"])]
                if mb["cx"] != ma["cx"]:
                    y = channel_y(tb - 1)
                    pts += [(ma["cx"], y), (mb["cx"], y)]
                pts.append((mb["cx"], b["bar_y"]))
                trunks.append({"person_id": person_id, "points": pts, "dashed": b["after_gap"]})
                continue
            y1 = channel_y(ta) + spread(in_channel[ta])
            in_channel[ta] += 1
            if tb == ta + 1:
                pts = [(ma["cx"], ma["bottom"]), (ma["cx"], y1), (mb["cx"], y1), (mb["cx"], b["bar_y"])]
            else:
                c = self._clear_gap(ta + 1, tb - 1, (mb["cx"] - x0) / self.unit, (ma["cx"] - x0) / self.unit)
                xg = (x0 + (c + 0.5) * self.unit if c is not None else x0 - MARGIN / 2) + spread(in_gap[c])
                in_gap[c] += 1
                y2 = channel_y(tb - 1) + spread(in_channel[tb - 1])
                in_channel[tb - 1] += 1
                pts = [(ma["cx"], ma["bottom"]), (ma["cx"], y1), (xg, y1), (xg, y2), (mb["cx"], y2),
                       (mb["cx"], b["bar_y"])]
            edges.append({"person_id": person_id, "from": a["id"], "to": b["id"],
                          "same_band": a["band_id"] == b["band_id"],
                          "dashed": a["band_id"] == b["band_id"] and b["after_gap"], "points": pts})
        for b in placed:
            if b["ongoing"]:
                for m in b["members"]:
                    trunks.append({"person_id": m["person_id"], "dashed": False, "arrow": True,
                                   "points": [(m["cx"], m["bottom"]), (m["cx"], m["bottom"] + 20)]})
        return trunks, edges

    def _clear_gap(self, t1, t2, near, also):
        """A column clear of line-ups from row t1 to t2 (gaps beside blocks, or
        empty cells), nearest the target and then the source."""
        n_cols = max(c for _, c in self._cells) + 2 if self._cells else 1
        best = None
        for c in range(-1, n_cols + 1):
            if all(self._cells.get((t, c)) in (None, "gap") for t in range(t1, t2 + 1)):
                d = abs(c - near) + 0.5 * abs(c - also)
                if best is None or d < best[0]:
                    best = (d, c)
        return best[1] if best else None
