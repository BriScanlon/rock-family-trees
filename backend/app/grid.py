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
from app.narrative import lineup_for

NOTE_LINES = 4          # most lines of notes in a block, under the band name
ANNOT_LINES = 2         # annotations under a member: "joined Mar 97", "then T. Hawkins"
CAREERS = 12            # a band's longest-serving members whose other bands (off this poster) are told
EVENT_WIDTHS = (6, 8, 10, 12, 16)  # an event block's width in half-member columns, narrowest that holds it
EVENT_PAD = 10          # margin inside an event block's cells
NOTE_ROWS = 3           # a floating note sits within this many rows of its line-up (tied to it)
MAX_WIDEN = 1.8         # a block may stretch to this many times its width into free columns beside it
FLOAT_SCALE = 1.4       # floating notes print larger than a block's: Frame lettered his asides big
TIME_COLUMNS = False    # time runs down each band and along each move; not every column (the user's choice: a fuller page)
DRIFT = 4               # half-member columns a line-up may shift from the one before it (Frame's jogs)
DRIFT_WEIGHT = 0.15     # cost per column of shift: straight lines unless drifting packs better
RESERVE_ROOT = 3        # reservations for the poster's own band (one for each other band)
RESERVE_SIGNIFICANCE = 4  # events this significant get room kept beside their line-up while packing
SUB = 4                 # sub-rows per row: a line-up starts at any quarter row, so each column keeps
                        # its own pace (the user chose this over rows level across the page)
BRIEF_NAMES = 4         # most names in a "Briefly also" list
NOTE_WIDEN = 2          # a block may be widened by this many members to fit its notes
CHANNEL = 30            # the band under each row where lines run across the page
LINE_STEP = 5           # separation of parallel lines in a gap
CHANNEL_STEP = 4        # and in a channel, where more lines meet (seven tracks in a 30px channel)
PACK_REPAIRS = 40       # rounds of re-placing to turn upward moves downwards
MAX_HSPREAD = 1.15      # most the columns may be spread sideways to reach the sheet's edges
MAX_GROW = 1.5         # most a drawing may be enlarged to fill its sheet
MAX_SPREAD = 0.0         # rows are not spread apart to reach the bottom: spare height is left for notes, not gaps
HINT_WEIGHT = 0.2       # pull (per column) towards a band's preferred column, when the optimiser gives one
ERA_WEIGHT = 0.5        # pull towards the row where line-ups of the same date sit
TOP_WEIGHT = 1.0        # pull towards the top: keep the tree compact
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


def album_time(album):
    """ "1972-03-25 Machine Head" -> 1972.23; a year alone sits mid-year."""
    when = album.split(" ", 1)[0]
    if not when[:4].isdigit():
        return None
    year = int(when[:4])
    if len(when) >= 7 and when[5:7].isdigit():
        day = int(when[8:10]) if len(when) >= 10 and when[8:10].isdigit() else 15
        return year + (int(when[5:7]) - 1) / 12 + (day - 1) / 365
    return year + 0.5


def _albums_of(band, lineup):
    """The albums released while this line-up was together: each album is a
    dated note on its band, told on the line-up that made it (the user's
    instruction: in the band's history, never a list apart)."""
    from app.narrative import lineup_for
    return [a for a in band.albums if album_time(a) is not None and lineup_for(band.lineups, album_time(a)) is lineup]


def _recorded(albums, shown=None):
    """ "Recorded Machine Head (1972), Who Do We Think We Are (1973)." -
    the first `shown` of them, and how many more, when the block is short of room."""
    if not albums:
        return None
    shown = len(albums) if shown is None else max(1, shown)
    text = ", ".join(f"{a.split(' ', 1)[1]} ({a[:4]})" for a in albums[:shown])
    more = len(albums) - shown
    return f"Recorded {text}{f' and {more} more' if more > 0 else ''}."


def coverage(layout):
    """Share of the drawing area (inside the margins, below the title, above the
    key) covered by line-ups: how full the page is."""
    area = (layout["width"] - 2 * MARGIN) * (layout["footer_y"] - 30 - TITLE_H)
    ink = sum(b["w"] * b["h"] for b in layout["boxes"])
    ink += sum(e["w"] * e["h"] for e in layout.get("events", []))
    return ink / area if area > 0 else 0.0


class _Tracks:
    """Parallel tracks in the channels and gaps: each run of line takes the
    track nearest the centre that's free along its whole length, so lines
    never lie on one another (a cycle of five tracks let the sixth line in a
    gap sit on the first). In a channel, a line leaving the row above drops
    from a member to its track, and one arriving in the row below drops from
    its track to a member: in the same column, the departure's track must be
    above the arrival's or the two drops lie on one another. Departures
    prefer the upper tracks and arrivals the lower."""

    def __init__(self, room, step=LINE_STEP):
        n = max(0, int(room // step))
        self.step = step
        self.offsets = [0.0] + [sign * k * step for k in range(1, n + 1) for sign in (1, -1)]
        self.used = defaultdict(list)   # key -> [(offset, lo, hi)]
        self.drops = defaultdict(list)  # key -> [(x, +1 departure / -1 arrival, offset)]

    def take(self, key, a, b, side=0, leaves=None, arrives=None):
        """The track for a run from a to b; side -1 prefers the upper (or left)
        tracks, +1 the lower, 0 the centre. `leaves`/`arrives`: the x where
        the run's line drops in from the row above / down to the row below."""
        lo, hi = min(a, b), max(a, b)
        runs, drops = self.used[key], self.drops[key]
        mine = [(x, 1) for x in [leaves] if x is not None] + [(x, -1) for x in [arrives] if x is not None]

        def clashes(off):
            n = sum(1 for o, l, h in runs if o == off and l < hi + self.step and lo < h + self.step)
            for x, kind in mine:  # a departure must sit above (less than) an arrival in its column
                n += sum(1 for dx, dk, do in drops if abs(dx - x) < 1 and dk != kind and
                         (do <= off if kind == 1 else do >= off))
            return n

        order = sorted(self.offsets, key=lambda o: (side * o < 0, abs(o))) if side else self.offsets
        off = next((o for o in order if not clashes(o)), None)
        if off is None:  # a crowded channel: the least shared track
            off = min(order, key=clashes)
        runs.append((off, lo, hi))
        drops.extend((x, kind, off) for x, kind in mine)
        return off


class GridLayout(Cartographer):
    def __init__(self, tree, paper="auto", subtitle=None, lettering="classic", cols=None, rows=None,
                 weights=None, mirror=False, hints=None, scale=1.0):
        super().__init__(tree, paper=paper, subtitle=subtitle, timeline=False, lettering=lettering)
        self.slot, self.title_h, self.bar_dy, self.block_h = _dims(self.ls)
        self.unit = self.slot / 2
        self.row_h = self.block_h + CHANNEL
        self.max_cols, self.max_rows = cols, rows
        # (era, top, near) pulls on placement, and whether to fill from the right:
        # the fitting tries several and keeps the fullest page
        self.era_w, self.top_w, self.near_w = weights or (ERA_WEIGHT, TOP_WEIGHT, NEAR_WEIGHT)
        self.mirror = mirror
        self.hints = hints or {}  # band id -> preferred column (the optimiser moves bands about with these)
        self.scale = scale        # text size, as a multiple of the smallest readable

    # ------------------------------------------------------------------
    @staticmethod
    def sheet(paper, lettering_style, scale=1.0):
        """The sheet with the smallest text printing at MIN_PRINT_PT x scale:
        (cols, rows, width px, height px), in whichever orientation holds more.
        A larger scale means larger text, so fewer columns and rows."""
        slot, _, _, block_h = _dims(lettering_style)
        unit, row_h = slot / 2, block_h + CHANNEL
        px_per_mm = min(ROLE_SIZE, DATE_SIZE, NOTE_SIZE) / (MIN_PRINT_PT * scale * 25.4 / 72)
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
        self.info = self._info_notes()
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
            # the notes written from Wikipedia (what the lines can't show) come first
            told_here = [s["text"].rstrip(".") + "." for s in band.stories if lineup_for(band.lineups, s["year"]) is lu]
            # what's known of the band and its musicians beyond this poster, at its time
            info = [n["text"] for n in self.info.get(band.id, []) if lineup_for(band.lineups, n["year"]) is lu]
            albums = _albums_of(band, lu)  # this line-up's albums, told in its block as Frame did

            recorded = _recorded(albums)
            # most telling first; what the block can't hold whole floats beside it (_place_notes)
            items = ([(t, "story", 4) for t in told_here] + ([(recorded, "albums", 3)] if recorded else [])
                     + [(t, "told", 2) for t in said + extra]
                     + [(t, "style" if t.startswith("Style:") else "career", 0 if t.startswith("Style:") else 1)
                        for t in info])

            def too_long(text, n):
                return len(wrap(text, HAND, NOTE_SIZE, n * slot - 8)) > NOTE_LINES

            widest = span + NOTE_WIDEN
            story = " ".join(t for t, kind, _ in items if kind in ("story", "albums"))
            while span < widest and too_long(story, span):  # widen for the story and the albums
                span += 1
            shown, floating = [], []
            for text, kind, priority in items:  # whole sentences only, never cut off with "..."
                if not too_long(" ".join(shown + [text]), span):
                    shown.append(text)
                else:
                    floating.append({"text": text, "kind": kind, "priority": priority})
            notes = " ".join(shown)
            box = {"id": f"{band.id}#{lu.number}", "band_id": band.id, "band_name": band.name, "number": lu.number,
                   "start": lu.start, "end": lu.end, "after_gap": lu.after_gap, "ongoing": lu.ongoing,
                   "level": band.level, "band_start": band.start, "name": name, "name_size": size, "name_w": name_w,
                   "dates": dates, "date_label": f"{lu.start_label} – {lu.end_label}".upper(),
                   "cols": columns[i], "span": span, "notes_text": notes, "marks": marks, "lineup": lu,
                   "recorded": recorded, "floating": floating, "items": items,
                   "reserve": self._reserve(band, lu, told_here)}
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
        n_sub = None if n_rows is None else n_rows * SUB
        for _ in range(PACK_REPAIRS):
            placed = self._pack_once(n_cols, n_sub, floors)
            if placed is None:
                return None
            # a move goes down: the line-up it goes to starts below the bottom of the one it left
            upward = [(a, b) for _, a, b in self.moves if self._tier[b["id"]] < self._tier[a["id"]] + SUB]
            if not upward:
                return placed
            for a, b in upward:
                floors[b["id"]] = max(floors.get(b["id"], 0), self._tier[a["id"]] + SUB)
        return None

    def _pack_once(self, n_cols, n_rows, floors):
        units = self._units_cache
        occ = defaultdict(list)  # column -> [(first sub-row, end, earliest start, latest start)] of what's there
        band_end = {}            # band id -> the sub-row below its last line-up so far: a re-formed band goes below
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
                lims.append(max([tier[a["id"]] + SUB for a in into[b["id"]] if a["id"] in tier]
                                + [floors.get(b["id"], 0), band_end.get(u["band"].id, 0)]))
            era_rows = [self._era_row(eras, b["start"]) for b in u["boxes"]]
            links = [(c, self.linked.get((u["band"].id, bid), 0)) for bid, cs in cols_of.items()
                     for c in cs if bid != u["band"].id and self.linked.get((u["band"].id, bid))]
            own = cols_of.get(u["band"].id, [])
            best = None
            # each line-up its own width (a lone member is narrow), plus the room kept for its big event
            widths = [2 * b["span"] + 1 + b["reserve"] for b in u["boxes"]]

            def fits_at(cb, bw, r, when, keep=None):
                """Room for a line-up dated `when` at sub-row r in columns cb..: nothing
                there, nothing later above it or earlier below it (time runs down every
                column), and `keep` - the drop from the line-up before - clear too."""
                for c in range(cb, cb + bw):
                    for r0, r1, smin, smax in occ[c]:
                        if r0 < r + SUB and r < r1:
                            return False
                        if TIME_COLUMNS and ((r1 <= r and smax > when) or (r0 >= r + SUB and smin < when)):
                            return False
                for c, lo_r, hi_r in keep or []:
                    if any(r0 < hi_r and lo_r < r1 for r0, r1, _, _ in occ[c]):
                        return False
                return True

            for c0 in range(n_cols - widths[0] + 1):
                rows, cols, r_prev = [], [], None
                for i, (b, bw, lo) in enumerate(zip(u["boxes"], widths, lims)):
                    # the first where the run starts; each after it straight below, or shifted a little
                    options = [c0] if i == 0 else [cols[-1] + d for d in range(-DRIFT, DRIFT + 1)]
                    lo_r = max([lo] + ([r_prev + SUB] if r_prev is not None else []))
                    pick = None
                    for cb in options:
                        if cb < 0 or cb + bw > n_cols:
                            continue
                        # the first free spot from lo_r down: holes above others included
                        starts = sorted({lo_r} | {r1 for c in range(cb, cb + bw) for _, r1, _, _ in occ[c] if r1 > lo_r})
                        for r in starts:
                            if n_rows is not None and r + SUB > n_rows:
                                break
                            keep = ([(c, r_prev + SUB, r) for c in range(cols[-1], cols[-1] + widths[i - 1])]
                                    if i and r > r_prev + SUB else None)
                            if fits_at(cb, bw, r, b["start"], keep):
                                key = (r, abs(cb - cols[-1]) if cols else 0)
                                if pick is None or key < pick[0]:
                                    pick = (key, cb, r)
                                break
                    if pick is None:
                        rows = None
                        break
                    rows.append(pick[2])
                    cols.append(pick[1])
                    r_prev = pick[2]
                if rows is None:
                    continue
                drift = sum(abs(a - b) for a, b in zip(cols, cols[1:]))
                era = sum(abs(r - e) for r, e in zip(rows, era_rows)) / len(rows)
                near = sum(k * abs(c0 - c) for c, k in links) / max(1, sum(k for _, k in links))
                near += 3 * min((abs(c0 - c) for c in own), default=0)  # a re-formed band returns to its columns
                hint = self.hints.get(u["band"].id)
                cost = ((rows[-1] - rows[0]) / SUB + self.top_w * rows[0] / SUB + self.era_w * era / SUB
                        + self.near_w * near + DRIFT_WEIGHT * drift
                        + 0.001 * ((n_cols - w - c0) if self.mirror else c0)
                        + (HINT_WEIGHT * abs(c0 - hint) if hint is not None else 0.0))
                if best is None or cost < best[0]:
                    best = (cost, c0, rows, cols)
            if best is None:
                return None
            _, c0, rows, cols = best
            boxes_u = u["boxes"]
            for i, (b, r, cb, bw) in enumerate(zip(boxes_u, rows, cols, widths)):
                for c in range(cb, cb + bw):
                    occ[c].append((r, r + SUB, b["start"], b["start"]))
                    for t in range(r, r + SUB):
                        cell[(t, c)] = "gap" if c == cb + bw - 1 else u["band"].id
                if i + 1 < len(rows) and rows[i + 1] > r + SUB:  # the members' lines drop to the next line-up: keep clear
                    for c in range(cb, cb + bw):
                        occ[c].append((r + SUB, rows[i + 1], b["start"], boxes_u[i + 1]["start"]))
                tier[b["id"]], col0[b["id"]] = r, cb
                eras.append((b["start"], r))
                placed.append(b)
                band_end[u["band"].id] = max(band_end.get(u["band"].id, 0), r + SUB)
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
            used_rows = math.ceil((max(self._tier.values()) + SUB) / SUB)
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
        used_rows = math.ceil((max(self._tier.values()) + SUB) / SUB)
        content_w = 2 * MARGIN + used_cols * unit
        content_h = TITLE_H + used_rows * self.row_h + FOOTER_H
        if self.max_cols is not None:  # the sheet itself, at the smallest readable size
            width, height = self._sheet_px()
            # Where the drawing doesn't need the whole sheet, draw it larger to
            # fill it, rather than leave strips down the sides too narrow to use:
            # the canvas shrinks to the drawing (paper-shaped), so everything prints bigger.
            grow = min(width / content_w, height / content_h, MAX_GROW)
            if grow > 1:
                width, height = width / grow, height / grow
            pitch = self.row_h + min(MAX_SPREAD * self.row_h,
                                     max(0.0, (height - content_h) / max(1, used_rows)))
        else:
            if self.auto_paper:
                self.paper = self._choose_paper(content_w, content_h)
            width, height, _ = self._paper_size(content_w, content_h)
            pitch = self.row_h + min(MAX_SPREAD * self.row_h,
                                     max(0.0, (height - content_h) / max(1, used_rows)))
        # spread the columns sideways (wider gutters, blocks unchanged) to reach the
        # sheet's edges rather than leave strips down the sides too narrow to use
        self.hs = min(MAX_HSPREAD, max(1.0, (width - 2 * MARGIN) / (used_cols * unit)))
        x0 = (width - used_cols * unit * self.hs) / 2
        self.x0 = x0
        row_y = lambda t: TITLE_H + t * pitch / SUB  # t in sub-rows
        self.pitch = pitch

        stretch = self._widen(placed, row_y, width)
        boxes = []
        for b in placed:
            t, c0 = self._tier[b["id"]], self._col0[b["id"]]
            x, y = self._col_x(c0), row_y(t)
            lu = b["lineup"]
            k = 1.0 if b["reserve"] else stretch[b["id"]]  # the room beside it is its event's
            slot = self.slot * k  # members spread across the widened block
            if k > 1:  # wider: it holds more of its notes, fewer float beside it
                self._refit_notes(b, b["span"] * slot)
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
            notes = wrap(b["notes_text"], HAND, NOTE_SIZE, b["span"] * slot - 8)[:NOTE_LINES]
            step = self.unit * self.hs
            b.update({"c_lo": c0, "c_hi": c0 + math.ceil(b["span"] * slot / step)})  # columns it now covers
            b.update({"x": x, "y": y, "w": b["span"] * slot, "h": self.block_h, "footprint": self.block_h,
                      "lane": c0, "row": t, "bar_y": y + self.bar_dy, "bar": (min(x, min(cxs) - 12), max(cxs) + 12),
                      "members": members, "overflow": max(0, len(lu.members) - MAX_MEMBERS),
                      "notes": notes, "notes_x": x, "notes_y": y + self.title_h})
            boxes.append(b)

        slot = self.slot
        trunks, edges = self._route(placed, x0, row_y)
        events = self._place_notes(boxes, trunks, edges, x0, row_y, width, height, (self.max_rows or used_rows) * SUB)
        years = []
        for t in sorted(set(self._tier.values())):
            starts = [b["start"] for b in placed if self._tier[b["id"]] == t]
            years.append({"year": int(min(starts)), "y": row_y(t) + 4})
        layout = {
            "width": width, "height": height, "paper": self.paper,
            "title": self.tree.title, "subtitle": self.subtitle, "lettering": self.ls, "timeline": False,
            "axis": {"left": MARGIN / 2, "right": width - MARGIN / 2, "top": TITLE_H - 20,
                     "bottom": row_y(used_rows * SUB)},
            "years": years,
            "boxes": [{k: v for k, v in b.items() if k not in ("lineup", "cols")} | {"cols": dict(b["cols"])}
                      for b in boxes],
            "trunks": trunks, "edges": edges, "events": events,
            "footer_y": height - FOOTER_H + 30,
            "grid": {"cols": self.max_cols or used_cols, "rows": self.max_rows or used_rows,
                     "used_cols": used_cols, "used_rows": used_rows, "unit": unit, "row_h": pitch},
            "stats": {"bands": len(self.tree.bands), "lineups": len(boxes),
                      "people": len({m["person_id"] for b in boxes for m in b["members"]}),
                      **self._print_report(width, height)},
        }
        return layout

    def _reserve(self, band, lu, told_here):
        """Half-member columns to keep beside this line-up for its biggest
        event (significance RESERVE_SIGNIFICANCE+), so the best stories -
        the Montreux fire - get their room before lesser bands take it
        (the user's instruction). The root band's best three, every other
        band's best one; 0 if this line-up hasn't one, or the notes tell it."""
        from app.events import same_story
        told = [s["text"] for s in band.stories] + told_here
        rank = lambda e: (e["significance"], e.get("sitelinks", 0), -e["year"])
        big = [e for e in band.events if e.get("significance", 1) >= RESERVE_SIGNIFICANCE
               and not same_story(e["text"], [s["text"] for s in band.stories])]
        if not big:
            return 0
        # the poster's own band its three best stories, every other band its best:
        # the room goes round the family
        root = next(iter(self.tree.bands))
        best = sorted(big, key=rank, reverse=True)[:RESERVE_ROOT if band.id == root else 1]
        mine = [e for e in best if lineup_for(band.lineups, e["year"]) is lu and not same_story(e["text"], told)]
        if not mine:
            return 0
        e = mine[0]
        heading = f"{(e.get('subject') or '').upper()} · {e.get('date', '')[:4]}"
        for w in EVENT_WIDTHS:
            text_w = w * self.unit - 2 * EVENT_PAD
            lines = wrap(e["text"], HAND, NOTE_SIZE * FLOAT_SCALE, text_w)
            tall = NOTE_LINE * FLOAT_SCALE * (len(lines) + 1) + EVENT_PAD
            if tall <= self.row_h and text_width(heading, HAND, DATE_SIZE * FLOAT_SCALE) <= text_w:
                return w + 1  # and a column's gutter
        return 0

    def _widen(self, placed, row_y, width):
        """How far each block stretches into the free columns to its right:
        {box id: factor}. Frame's blocks vary in width and fill the space;
        a block stretches until the next block that shares any of its height
        (keeping a column's gutter for lines), or the sheet's edge, at most
        MAX_WIDEN. Blocks only grow rightwards, and each stops short of where
        its neighbours start, so none can meet."""
        step = self.unit * self.hs
        ch = self.pitch - self.block_h
        rects = {b["id"]: (self._col_x(self._col0[b["id"]]), row_y(self._tier[b["id"]]), b["span"] * self.slot, b["start"])
                 for b in placed}
        out = {}
        for bid, (x, y, w, start) in rects.items():
            limit = width - MARGIN
            for oid, (ox, oy, ow, ostart) in rects.items():
                if oid == bid or ox < x + w - 1:
                    continue
                beside = oy < y + self.block_h + ch and y < oy + self.block_h + ch
                # time runs down every column: never reach over an earlier line-up below, or a later one above
                out_of_time = (oy > y and ostart < start) or (oy < y and ostart > start)
                if beside or out_of_time:
                    limit = min(limit, ox - step)
            out[bid] = max(1.0, min(MAX_WIDEN, (limit - x) / w))
        return out

    def _refit_notes(self, b, width):
        """Which of a block's note items it holds whole at its (widened)
        width; the rest float beside it."""
        shown, floating = [], []
        for text, kind, priority in b["items"]:
            if len(wrap(" ".join(shown + [text]), HAND, NOTE_SIZE, width - 8)) <= NOTE_LINES:
                shown.append(text)
            else:
                floating.append({"text": text, "kind": kind, "priority": priority})
        b["notes_text"], b["floating"] = " ".join(shown), floating

    def _col_x(self, c):
        """Left edge of grid column c on the page."""
        return self.x0 + c * self.unit * self.hs

    def _sheet_px(self):
        cols, rows, W, H = GridLayout.sheet(self.paper, self.ls, self.scale)
        return W, H

    # ------------------------------------------------------------------
    def _free_cells(self, boxes, trunks, edges, x0, row_y, width, height, n_rows):
        """The grid cells (row, half-member column) no line-up or line passes
        through: where an event can go."""
        step = self.unit * self.hs
        c_lo = -int((x0 - MARGIN) // step)
        c_hi = int((width - MARGIN - x0) // step)
        rows = [t for t in range(n_rows) if row_y(t + 1) <= height - FOOTER_H + 1]
        # the blocks themselves, not the width their band reserves (a band's
        # narrower line-ups leave room beside them), and every line's path
        blocks, busy = set(), set()
        for b in boxes:  # a block's own sub-rows (not its channel below), and its gap column for lines
            depth = math.ceil(self.block_h / (self.pitch / SUB) - 0.01)
            for t in range(b["row"], b["row"] + depth):
                for c in range(b["c_lo"], b["c_hi"] + 1):
                    busy.add((t, c))
                blocks.update((t, c) for c in range(b["c_lo"], b["c_hi"]))
        for line in list(trunks) + list(edges):
            pts = line["points"]
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                if ax == bx and abs(by - ay) > self.pitch:  # a long drop may pass behind a note, as behind a block's
                    continue
                lx, hx, ly, hy = min(ax, bx) - 6, max(ax, bx) + 6, min(ay, by) - 6, max(ay, by) + 6
                for t in rows:
                    if not (ly < row_y(t + 1) and row_y(t) < hy):
                        continue
                    for c in range(c_lo, c_hi):
                        if lx < self._col_x(c + 1) and self._col_x(c) < hx:
                            busy.add((t, c))
        free = {(t, c) for t in rows for c in range(c_lo, c_hi) if (t, c) not in busy}
        return free, blocks, rows, c_lo, c_hi

    def _place_notes(self, boxes, trunks, edges, x0, row_y, width, height, n_rows):
        """Floating notes, each its own small block in free cells near the
        line-up it belongs to, tied to it with a dotted line: the events from
        its albums and tours (app/events.py) and whatever its block couldn't
        hold whole - story, albums, careers, style. Most telling first, as
        close as there's room: the line-up's own row, else up to NOTE_ROWS
        rows away (the page is to be full, with everything in its place in
        the history - the user's instructions). A tie runs along the row and
        down a column, crossing lines but never a block."""
        from app.events import MIN_SIGNIFICANCE, same_story
        from app.refiner import MONTHS
        free, blocks, rows, c_lo, c_hi = self._free_cells(boxes, trunks, edges, x0, row_y, width, height, n_rows)
        by_id = {b["id"]: b for b in boxes}
        told = {band.id: [s["text"] for s in band.stories] for band in self.tree.bands.values()}
        for b in boxes:
            told.setdefault(b["band_id"], []).append(b["notes_text"])
        pending = []
        for band in self.tree.bands.values():
            for e in band.events:
                if e.get("significance", 1) < MIN_SIGNIFICANCE:
                    continue
                lu = lineup_for(band.lineups, e["year"])
                box = by_id.get(f"{band.id}#{lu.number}") if lu else None
                if box is None:
                    continue
                when = e.get("date") or ""
                month = int(when[5:7]) if len(when) >= 7 and when[5:7].isdigit() else 0
                label = (f"{MONTHS[month - 1]} {when[:4]}" if 1 <= month <= 12 else when[:4]).upper()  # "1978-00": the year
                heading = f"{e['subject'].upper()} · {label}" if e.get("subject") else label
                pending.append({"text": e["text"], "kind": "event", "priority": 4 + e["significance"],
                                "heading": heading, "box": box, "band": band, "year": e["year"],
                                "significance": e["significance"]})
        for b in boxes:
            for n in b.get("floating", []):
                pending.append(dict(n, heading=None, box=b, band=self.tree.bands[b["band_id"]], year=b["start"]))
        pending.sort(key=lambda n: (-n["priority"], n["year"]))
        placed = []
        for n in pending:
            band, box = n["band"], n["box"]
            if n["kind"] == "event" and same_story(n["text"], told[band.id]):
                continue
            spot = self._note_spot(n, box, free, blocks, rows, c_lo, c_hi, row_y)
            if spot is None:
                continue
            t, c, w, lines, path_cells, tie = spot
            k_rows = math.ceil((NOTE_LINE * FLOAT_SCALE * (len(lines) + (1 if n["heading"] else 0)) + EVENT_PAD) / (self.pitch / SUB))
            for i in range(k_rows):
                for k in range(c, c + w):
                    free.discard((t + i, k))
                    blocks.add((t + i, k))
            for cell in path_cells:  # a later note mustn't sit on this tie
                free.discard(cell)
            x, y = self._col_x(c) + EVENT_PAD / 2, row_y(t) + EVENT_PAD / 2
            ew = self._col_x(c + w) - self._col_x(c) - EVENT_PAD
            eh = NOTE_LINE * FLOAT_SCALE * (len(lines) + (1 if n["heading"] else 0)) + EVENT_PAD
            placed.append({"band_id": band.id, "lineup": box["id"], "year": n["year"], "kind": n["kind"],
                           "x": x, "y": y, "w": ew, "h": eh, "heading": n["heading"], "lines": lines,
                           "significance": n.get("significance"), "tie": tie, "scale": FLOAT_SCALE})
            told[band.id].append(n["text"])
        return placed

    def _note_spot(self, n, box, free, blocks, rows, c_lo, c_hi, row_y):
        """(row, column, width, lines, cells the tie crosses, tie points) for a
        floating note, or None: the narrowest block that holds it, nearest
        its line-up, with a tie that crosses no block."""
        bl, br = box["c_lo"], box["c_hi"] + 1
        home = box["row"]
        sub_h = self.pitch / SUB
        depth = math.ceil(self.block_h / sub_h - 0.01)
        mid = lambda t: row_y(t) + min(self.title_h, sub_h) / 2
        colx = lambda k: (self._col_x(k) + self._col_x(k + 1)) / 2
        own = {(r, k) for r in range(home, home + depth) for k in range(bl, br)}
        clear = lambda cells: all(cell not in blocks or cell in own for cell in cells)
        best = None
        row_set = set(rows)
        for t in sorted(rows, key=lambda r: abs(r - home)):
            if abs(t - home) > NOTE_ROWS * SUB or (best is not None and abs(t - home) * 6 / SUB > best[0][0]):
                continue
            for w in EVENT_WIDTHS:
                text_w = self._col_x(w) - self._col_x(0) - 2 * EVENT_PAD
                lines = wrap(n["text"], HAND, NOTE_SIZE * FLOAT_SCALE, text_w)
                if n["heading"] and text_width(n["heading"], HAND, DATE_SIZE * FLOAT_SCALE) > text_w:
                    continue
                k_rows = math.ceil((NOTE_LINE * FLOAT_SCALE * (len(lines) + (1 if n["heading"] else 0)) + EVENT_PAD) / sub_h)
                if k_rows > 2 * SUB or any(t + i not in row_set for i in range(k_rows)):
                    continue
                for c in range(c_lo, c_hi - w + 1):
                    if not all((t + i, k) in free for i in range(k_rows) for k in range(c, c + w)):
                        continue
                    right = c >= br
                    edge_x = box["x"] + box["w"] + 4 if right else box["x"] - 4
                    near_x = self._col_x(c) + EVENT_PAD / 2 if c >= bl else self._col_x(c + w) - EVENT_PAD / 2
                    if t <= home < t + k_rows:  # level with the line-up's name: tied along its sub-row
                        if not right and c + w > bl:
                            continue
                        between = range(br, c) if right else range(c + w, bl)
                        cells = [(home, k) for k in between]
                        if not clear(cells):
                            continue
                        cost = len(cells)
                        tie = [(edge_x, mid(home)), (near_x, mid(home))]
                    else:
                        step = 1 if t > home else -1
                        start = home + depth if t > home else home - 1  # below (or above) the block
                        lo_c, hi_c = min(bl, c), max(br - 1, c + w - 1)
                        route = None
                        # straight out of the block's bottom (or top), down its own column, along to the note
                        tc = min(max(c if c > bl else c + w - 1, bl), br - 1)  # its gap column at most
                        down = [(r, tc) for r in range(start, t, step)]
                        along = [(t, k) for k in range(min(tc, c), max(tc, c + w - 1) + 1) if not (c <= k < c + w)]
                        if clear(down + along):
                            y0 = box["y"] + box["h"] if t > home else box["y"]
                            route = (down + along, [(colx(tc), y0), (colx(tc), mid(t)),
                                                    (near_x if not (c <= tc < c + w) else colx(tc), mid(t))])
                        if route is None:  # else along the home row to a column beside the block first
                            tc = br if right or c >= bl else bl - 1
                            leg1 = [(home, k) for k in (range(br, tc + 1) if tc >= br else range(tc, bl))]
                            leg2 = [(r, tc) for r in range(home + step, t, step) if (r, tc) not in own]
                            leg3 = [(t, k) for k in range(min(tc, c), max(tc, c + w - 1) + 1) if not (c <= k < c + w)]
                            if clear(leg1 + leg2 + leg3):
                                route = (leg1 + leg2 + leg3, [(edge_x, mid(home)), (colx(tc), mid(home)), (colx(tc), mid(t)),
                                                              (near_x if not (c <= tc < c + w) else colx(tc), mid(t))])
                        if route is None:
                            continue
                        cells, tie = route
                        cost = 6 * abs(t - home) / SUB + len(cells)
                    score = (cost, w)
                    if best is None or score < best[0]:
                        best = (score, (t, c, w, lines, cells, tie))
                break  # the narrowest width that holds the text
        return best[1] if best else None

    def _info_notes(self):
        """Info notes, each attached to the band and the time it belongs to
        (the user's instruction: part of the layout, never a list apart):
        {band id: [{"text", "year"}]}.

        - A band's style, on its first line-up.
        - Where its longest-serving musicians played off this poster, each
          other band told once, on the poster band they were in at the time:
          "also with" one they joined while a member, "went on to" one they
          joined after leaving (on their last line-up), "previously with" one
          from before (on their first). A move to a band on the poster is a
          line, and needs no words."""
        from app.narrative import lineup_for
        info = {}
        for band in self.tree.bands.values():
            if band.genres:
                info.setdefault(band.id, []).append({"text": f"Style: {', '.join(band.genres)}.", "year": band.start})
        on_poster = {b.name for b in self.tree.bands.values()}
        people = set()
        for band in self.tree.bands.values():
            tenure = {}
            for st in band.stints:
                tenure[st.person_id] = tenure.get(st.person_id, 0) + st.end - st.start
            people |= set(sorted(tenure, key=lambda p: -tenure[p])[:CAREERS])
        told = {}  # (band id, year, person, kind) -> [other band names]
        for pid in people:
            person = self.tree.people.get(pid)
            if person is None:
                continue
            stints = sorted(((st.start, st.end, band) for band in self.tree.bands.values()
                             for st in band.stints if st.person_id == pid), key=lambda s: (s[0], s[1], s[2].name))
            if not stints:
                continue
            for other, year in sorted(person.joined.items(), key=lambda kv: kv[1]):
                if other in on_poster:
                    continue
                during = [s for s in stints if s[0] <= year < s[1]]
                before = [s for s in stints if s[1] <= year]
                if during:
                    s, kind, at = during[-1], "also with", year
                elif before:
                    s, kind, at = before[-1], "went on to", before[-1][1] - 0.01
                else:
                    s, kind, at = stints[0], "previously with", stints[0][0]
                # one sentence per musician per line-up: "Dave LaRue also with Steve
                # Morse Trio (2003), Flying Colors (2011)", dated by the first
                lu = lineup_for(s[2].lineups, at)
                key = (s[2].id, lu.number if lu else 0, person.name, kind)
                told.setdefault(key, [at, []])[1].append(f"{other} ({int(year)})")
        for (band_id, _, name, kind), (at, others) in told.items():
            shown = others[:BRIEF_NAMES]
            more = len(others) - len(shown)
            info.setdefault(band_id, []).append(
                {"text": f"{name} {kind} {', '.join(shown)}{f' and {more} more' if more > 0 else ''}.", "year": at})
        return info

    # ------------------------------------------------------------------
    def _route(self, placed, x0, row_y):
        """Each musician's line straight down to their next line-up in the
        same run; every other move drops into the channel under its line-up,
        along to a clear gap, down it, along the channel over the line-up it
        goes to and into place. With each column at its own pace the channels
        don't run level across the page, so every run is checked against the
        blocks themselves and the gap chosen is the shortest way round them.
        Each run takes the nearest free track (_Tracks), so no two lines share
        a stretch of ink."""
        member = {(b["id"], m["person_id"]): m for b in placed for m in b["members"]}
        unit_of = {}
        for u in self._units_cache:
            for b in u["boxes"]:
                unit_of[b["id"]] = id(u)
        ch = self.pitch - self.block_h
        rects = [(b["x"] - 2, b["y"], b["x"] + b["w"] + 2, b["y"] + self.block_h, b["id"]) for b in placed]
        below = lambda b: b["y"] + self.block_h + ch / 2
        above = lambda b: b["y"] - ch / 2
        channels = _Tracks(ch / 2 - 2, CHANNEL_STEP)  # horizontal runs, keyed by their level
        gaps = _Tracks(self.unit * self.hs / 2 - 3)   # vertical runs, keyed by their x
        step = self.unit * self.hs
        n_cols = int((max(r[2] for r in rects) - x0) / step) + 2
        gap_xs = [self._col_x(c + 0.5) for c in range(-1, n_cols + 1)]

        def blocked(x1, y1, x2, y2, skip=()):
            lx, hx, ly, hy = min(x1, x2), max(x1, x2), min(y1, y2), max(y1, y2)
            return any(rx0 < hx and lx < rx1 and ry0 < hy and ly < ry1 and bid not in skip
                       for rx0, ry0, rx1, ry1, bid in rects) if (hx > lx or hy > ly) else False

        trunks, edges = [], []
        for person_id, a, b in self.moves:
            ma, mb = member.get((a["id"], person_id)), member.get((b["id"], person_id))
            if ma is None or mb is None:
                continue  # beyond MAX_MEMBERS
            skip = (a["id"], b["id"])
            y1, y2 = below(a), above(b)
            pts = None
            if unit_of[a["id"]] == unit_of[b["id"]] and b["number"] == a["number"] + 1:
                # the band's next line-up: straight down, jogging just above it or just below this one
                for level in (y2, y1):
                    if not (blocked(ma["cx"], ma["bottom"], ma["cx"], level, skip)
                            or blocked(ma["cx"], level, mb["cx"], level, skip)
                            or blocked(mb["cx"], level, mb["cx"], b["bar_y"], skip)):
                        pts = [(ma["cx"], ma["bottom"])]
                        if mb["cx"] != ma["cx"]:
                            y = level + channels.take(round(level), ma["cx"], mb["cx"], leaves=ma["cx"], arrives=mb["cx"])
                            pts += [(ma["cx"], y), (mb["cx"], y)]
                        pts.append((mb["cx"], b["bar_y"]))
                        break
                if pts is not None:
                    trunks.append({"person_id": person_id, "points": pts, "dashed": b["after_gap"]})
                    continue
            if abs(y2 - y1) < 1 and not blocked(ma["cx"], y1, mb["cx"], y1, skip):
                level = round(y1)
                y = y1 + channels.take(level, ma["cx"], mb["cx"], leaves=ma["cx"], arrives=mb["cx"])
                pts = [(ma["cx"], ma["bottom"]), (ma["cx"], y), (mb["cx"], y), (mb["cx"], b["bar_y"])]
            if pts is None:
                best = None
                for xg in gap_xs + [ma["cx"], mb["cx"]]:
                    if (blocked(ma["cx"], y1, xg, y1, skip) or blocked(xg, y1, xg, y2, skip)
                            or blocked(xg, y2, mb["cx"], y2, skip) or blocked(mb["cx"], y2, mb["cx"], b["bar_y"], skip)
                            or blocked(ma["cx"], ma["bottom"], ma["cx"], y1, skip)):
                        continue
                    d = abs(xg - ma["cx"]) + abs(xg - mb["cx"])
                    if best is None or d < best[0]:
                        best = (d, xg)
                xg = best[1] if best else x0 - MARGIN / 2  # no way round: down the margin
                xg += gaps.take(round(xg), y1, y2) if xg not in (ma["cx"], mb["cx"]) else 0
                ya = y1 + channels.take(round(y1), ma["cx"], xg, side=-1, leaves=ma["cx"])
                yb = y2 + channels.take(round(y2), xg, mb["cx"], side=1, arrives=mb["cx"])
                pts = [(ma["cx"], ma["bottom"]), (ma["cx"], ya), (xg, ya), (xg, yb), (mb["cx"], yb),
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

