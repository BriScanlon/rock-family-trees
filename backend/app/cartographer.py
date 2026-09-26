"""Lays out a FamilyTree the way Pete Frame drew his Rock Family Trees.

* Time runs down the page. Line-ups that start at the same time share a row;
  rows are spaced roughly in proportion to elapsed time and pushed apart only
  as much as needed to avoid collisions.
* Each band gets a vertical lane; lanes are reused once a band has finished,
  and bands that share members sit next to each other.
* A line-up is not boxed. It is the band name in big lettering with its dates
  stacked alongside, a ruled bar underneath, and the members hanging from the
  bar side by side: first name over surname, instrument beneath.
* Every musician keeps a column within their band (a replacement takes the
  column of the person they replaced), and a line runs straight down from
  their name to their place in the next line-up.
* When a musician moves to another band the line leaves their name, runs
  through the gutters between lanes and drops into the bar of the new band.
* Notes are written as a paragraph of handwriting beside each line-up.
"""
import math
from collections import defaultdict

from app.fonts import HAND, STYLES, text_width, wrap

GUTTER = 64
AXIS_W = 80           # year scale on each side (optional)
MARGIN = 50
TITLE_H = 250
FOOTER_H = 190

DATE_SIZE = 13        # dates stacked beside the band name
HEADER_H = 44         # top of block to the ruled bar
TICK = 9
ROLE_SIZE = 13
ROLE_LINE = 14
NOTE_GAP = 18
NOTE_W = 190
MIN_INLINE_NOTE_W = 140  # notes go in spare room beside a narrow line-up when at least this wide
EDGE_GAP = 52         # room above a line-up for lines arriving from another band
NOTE_SIZE = 14
NOTE_LINE = 17
MAX_MEMBERS = 12
MAX_NOTES = 6

PX_PER_YEAR = 75
MIN_STEP = 14
MAX_STEP = 110
V_GAP = 28            # minimum gap between line-ups in one lane
LANE_REUSE_YEARS = 0.1
TRACK_SPACING = 7
MAX_STRETCH = 1.8     # most the rows may be spread to fill the sheet
STAGGER = 6           # separation of parallel horizontal runs leaving/entering a line-up

MIN_PRINT_PT = 6.5     # smallest comfortable printed text size

PAPER_MM = {"A0": (841, 1189), "A1": (594, 841), "A2": (420, 594), "A3": (297, 420), "A4": (210, 297)}


class Cartographer:
    def __init__(self, tree, paper="A1", subtitle=None, timeline=False, lettering="classic"):
        self.tree = tree
        self.ls = dict(STYLES.get(lettering, STYLES["classic"]), name=lettering if lettering in STYLES else "classic")
        self.timeline = timeline
        self.axis_w = AXIS_W if timeline else 0
        self.auto_paper = paper == "auto"
        self.paper = paper if paper in PAPER_MM else None
        self.subtitle = subtitle
        self.boxes = {}
        self.box_order = []

    # ------------------------------------------------------------------
    def layout(self):
        bands = sorted(self.tree.bands.values(), key=lambda b: (b.start, b.name))
        if not bands:
            raise ValueError("Nothing to draw: no band line-ups with usable dates were found")
        self.appearances = self._appearances(bands)
        self._make_blocks(bands)
        lanes = self._assign_lanes(bands)
        self.lane_count = max(lanes.values()) + 1
        for box in self.boxes.values():
            box["lane"] = lanes[box["band_id"]]
        self._layout_notes()
        # A strict time grid is only needed when a year scale is drawn; otherwise
        # each lane packs tightly, as Frame's trees do (every line-up is dated).
        anchors = self._assign_rows() if self.timeline else self._compact_rows()
        content_w = self._lane_x(self.lane_count) + self.axis_w + MARGIN
        if self.auto_paper:
            content_h = max(b["y"] + b["footprint"] for b in self.boxes.values()) + 60
            self.paper = self._choose_paper(content_w, content_h + FOOTER_H)
        anchors = self._fill_page(content_w, anchors)
        for box in self.boxes.values():
            self._place(box, self._lane_x(box["lane"]))
        trunks = self._continuity(bands)
        edges = self._route_edges(bands)

        content_h = max(b["y"] + b["footprint"] for b in self.boxes.values()) + 60
        width, height, offset_x = self._paper_size(content_w, content_h + FOOTER_H)
        self._shift(offset_x, trunks, edges)
        years = self._year_marks(anchors)

        return {
            "width": width, "height": height, "paper": self.paper,
            "title": self.tree.title, "subtitle": self.subtitle, "lettering": self.ls,
            "timeline": self.timeline,
            "axis": {"left": offset_x + MARGIN + AXIS_W / 2,
                     "right": offset_x + content_w - MARGIN - AXIS_W / 2,
                     "top": TITLE_H - 20, "bottom": content_h},
            "years": years,
            "boxes": [self.boxes[k] for k in self.box_order],
            "trunks": trunks, "edges": edges,
            "footer_y": height - FOOTER_H + 30,
            "stats": {"bands": len(bands), "lineups": len(self.boxes),
                      "people": len({s.person_id for b in bands for s in b.stints}),
                      **self._print_report(width, height)},
        }

    def _lane_x(self, lane):
        """Left edge of lane `lane` (lanes vary in width)."""
        return MARGIN + self.axis_w + GUTTER + sum(self.lane_w[:lane]) + lane * GUTTER

    def _gutter_x(self, gutter):
        """Centre of gutter i (gutter i sits left of lane i)."""
        return self._lane_x(gutter) - GUTTER / 2

    # ------------------------------------------------------------------
    def _appearances(self, bands):
        """person -> [(band, lineup)] in chronological order."""
        out = defaultdict(list)
        for band in bands:
            for lu in band.lineups:
                for m in lu.members:
                    out[m.person_id].append((band, lu))
        for apps in out.values():
            apps.sort(key=lambda a: (a[1].start, a[0].start, a[0].name))
        return out

    @staticmethod
    def _columns(band):
        """Column for every member of every line-up. People keep their column;
        a newcomer takes the column vacated by someone with the same
        instrument if there is one, else any vacated column, else a new one."""
        out, prev, prev_roles = [], {}, {}
        for lu in band.lineups[:]:
            members = lu.members[:MAX_MEMBERS]
            cur = {m.person_id: prev[m.person_id] for m in members if m.person_id in prev}
            free = sorted(set(prev.values()) - set(cur.values()))
            used = set(prev.values()) | set(cur.values())
            for m in members:
                if m.person_id in cur:
                    continue
                col = next((c for c in free if set(prev_roles.get(c, ())) & set(m.roles)), None)
                if col is None and free:
                    col = free[0]
                if col is None:
                    col = max(used | set(cur.values()), default=-1) + 1
                if col in free:
                    free.remove(col)
                cur[m.person_id] = col
                used.add(col)
            out.append(cur)
            prev = cur
            prev_roles = {c: next(m.roles for m in members if m.person_id == p) for p, c in cur.items()}
        return out

    def _make_blocks(self, bands):
        people = self.tree.people
        for band in bands:
            name = band.name.upper()
            ls, col_w = self.ls, self.ls["col_w"]
            name_size = ls["name_size"]
            while name_size > ls["name_size"] * 0.6 and text_width(name, ls["family"], name_size, ls["weight"]) > 5 * col_w:
                name_size -= 2
            name_w = text_width(name, ls["family"], name_size, ls["weight"])
            columns = self._columns(band)
            ncols = max(max(c.values(), default=0) for c in columns) + 1
            content_w = max(ncols * col_w, name_w + 12 + 60)
            notes_by_lineup = [self._notes(band, lu, band.lineups[i + 1] if i + 1 < len(band.lineups) else None)
                               for i, lu in enumerate(band.lineups)]

            for i, lu in enumerate(band.lineups):
                cols = columns[i]
                members = []
                bottom = HEADER_H
                for m in lu.members[:MAX_MEMBERS]:
                    lines = _split_name(m.name.upper())
                    roles = list(m.roles[:1])  # Frame gives each musician one instrument
                    person = people.get(m.person_id)
                    if person and person.died is not None and lu.start <= person.died <= lu.end + 0.3:
                        roles.append(f"(died {person.died_label})")
                    y_name = HEADER_H + TICK + ls["member_size"] * 0.8
                    y_bottom = y_name + (len(lines) - 1) * ls["member_line"] + len(roles) * ROLE_LINE + 5
                    bottom = max(bottom, y_bottom)
                    members.append({"person_id": m.person_id, "col": cols[m.person_id],
                                    "lines": lines, "roles": roles, "dy_name": y_name, "dy_bottom": y_bottom})
                members.sort(key=lambda m: m["col"])
                overflow = len(lu.members) - len(members)
                notes_text = " ".join(notes_by_lineup[i][:MAX_NOTES])
                h = bottom + (ROLE_LINE if overflow else 0)
                box_id = f"{band.id}#{lu.number}"
                self.boxes[box_id] = {
                    "id": box_id, "band_id": band.id, "band_name": band.name, "number": lu.number,
                    "name": name, "name_size": name_size, "name_w": name_w,
                    "dates": [lu.start_label.upper(), lu.end_label.upper()],
                    "date_label": f"{lu.start_label} – {lu.end_label}".upper(),
                    "start": lu.start, "end": lu.end, "after_gap": lu.after_gap, "ongoing": lu.ongoing,
                    "level": band.level, "content_w": content_w, "h": h, "band_start": band.start,
                    "members_w": (max((m["col"] for m in members), default=0) + 1) * col_w,
                    "members": members, "overflow": overflow, "notes_text": notes_text,
                }
                self.box_order.append(box_id)

    def _place(self, box, x):
        """Fix a block's absolute position and its members' coordinates."""
        box["x"] = x
        box["bar_y"] = box["y"] + HEADER_H
        box["notes_x"] = x + box["notes_dx"]
        for m in box["members"]:
            m["cx"] = x + m["col"] * self.ls["col_w"] + self.ls["col_w"] / 2
            m["y_name"] = box["y"] + m["dy_name"]
            m["bottom"] = box["y"] + m["dy_bottom"]
        cxs = [m["cx"] for m in box["members"]] or [x + self.ls["col_w"] / 2]
        box["bar"] = (min(x, min(cxs) - 12), max(cxs) + 12)

    def _layout_notes(self):
        """Put each line-up's notes in the spare room to the right of its
        members when there is enough, otherwise in a notes column beside the
        lane. Only lanes that need the column get one."""
        lane_content = defaultdict(float)
        for b in self.boxes.values():
            lane_content[b["lane"]] = max(lane_content[b["lane"]], b["content_w"])
        self.lane_w = [0] * self.lane_count
        for b in self.boxes.values():
            lc = lane_content[b["lane"]]
            spare = lc - b["members_w"] - NOTE_GAP
            if not b["notes_text"]:
                b["notes"], b["notes_dx"], width = [], lc, lc
            elif spare >= MIN_INLINE_NOTE_W:
                b["notes"] = wrap(b["notes_text"], HAND, NOTE_SIZE, min(spare, NOTE_W * 1.4))
                b["notes_dx"], width = b["members_w"] + NOTE_GAP, lc
            else:
                b["notes"] = wrap(b["notes_text"], HAND, NOTE_SIZE, NOTE_W)
                b["notes_dx"], width = lc + NOTE_GAP, lc + NOTE_GAP + NOTE_W
            b["footprint"] = max(b["h"], HEADER_H + 2 + len(b["notes"]) * NOTE_LINE)
            b["w"] = width
            self.lane_w[b["lane"]] = max(self.lane_w[b["lane"]], width)

    def _compact_rows(self):
        """Pack each lane tightly. Time order is kept where it matters: a
        line-up sits below the previous one in its lane and below every
        line-up its musicians arrive from."""
        order = sorted(self.boxes.values(), key=lambda b: (b["start"], b["band_start"], b["band_name"], b["number"]))
        sources = defaultdict(list)
        for apps in self.appearances.values():
            for (ba, la), (bb, lb) in zip(apps, apps[1:]):
                a, b = self.boxes[f"{ba.id}#{la.number}"], self.boxes[f"{bb.id}#{lb.number}"]
                if a is not b and a["lane"] != b["lane"]:
                    sources[b["id"]].append(a)
        lane_bottom = defaultdict(lambda: -math.inf)
        for b in order:
            y = max([TITLE_H, lane_bottom[b["lane"]] + V_GAP] +
                    [a["y"] + a["footprint"] + EDGE_GAP for a in sources[b["id"]] if "y" in a])
            b["y"] = y
            lane_bottom[b["lane"]] = y + b["footprint"]
        return sorted((b["start"], b["y"]) for b in order)

    def _choose_paper(self, w, h):
        """Smallest sheet on which the smallest text prints at MIN_PRINT_PT or more."""
        smallest_px = min(ROLE_SIZE, DATE_SIZE, NOTE_SIZE)
        for paper in ("A3", "A2", "A1", "A0"):
            short, long_ = PAPER_MM[paper]
            mm_per_px = min(long_ / w, short / h) if w > h else min(short / w, long_ / h)
            if smallest_px * mm_per_px * 72 / 25.4 >= MIN_PRINT_PT:
                return paper
        return "A0"

    def _print_report(self, width, height):
        """How big the smallest text will actually print on the chosen paper."""
        if not self.paper:
            return {}
        short, long_ = PAPER_MM[self.paper]
        mm_per_px = (long_ if width > height else short) / width
        pt = lambda px: round(px * mm_per_px * 72 / 25.4, 1)
        return {"paper": self.paper, "smallest_text_pt": pt(min(ROLE_SIZE, DATE_SIZE, NOTE_SIZE)),
                "name_text_pt": pt(self.ls["member_size"])}

    def _notes(self, band, lu, nxt):
        """Frame-style annotations about how this line-up ended, as sentences."""
        notes = []
        people = self.tree.people
        leaving = list(lu.members)
        if nxt is not None and not nxt.after_gap:
            staying = {m.person_id for m in nxt.members}
            leaving = [m for m in lu.members if m.person_id not in staying]
        band_over = nxt is None or nxt.after_gap
        for m in leaving:
            person = people.get(m.person_id)
            if person and person.died is not None and lu.start <= person.died <= lu.end + 0.3:
                notes.append(f"{m.name} died in {_long_date(person.died_label)}.")
                continue
            dest = self._next_band(m.person_id, band, lu)
            if dest is not None:
                d_band, d_lu = dest
                verb = "form" if d_lu.number == 1 and abs(d_band.start - lu.end) <= 1.0 else "join"
                notes.append(f"{m.name} {'went on' if band_over else 'left'} to {verb} {d_band.name}.")
            elif not band_over:
                notes.append(f"{m.name} left in {_long_date(lu.end_label)}.")
        if lu.merged:
            n = lu.merged
            notes.insert(0, f"Simplified to fit: {n} brief line-up{'s' if n > 1 else ''} folded in here.")
        if band_over:
            if nxt is not None:
                notes.insert(0, f"Split in {_long_date(lu.end_label)}; re-formed {_long_date(nxt.start_label)}.")
            elif band.ended:
                notes.insert(0, f"Split in {_long_date(lu.end_label)}.")
            else:
                notes.insert(0, "Still going.")
        return notes

    def _next_band(self, person_id, band, lu):
        for b, l in self.appearances.get(person_id, []):
            if b.id != band.id and l.start >= lu.end - 0.75 and l.start <= lu.end + 4:
                return b, l
        return None

    # ------------------------------------------------------------------
    def _assign_lanes(self, bands):
        """Order bands left-to-right so that bands sharing members sit close
        together, then pack that order into as few lanes as possible: a lane
        is reused once its previous band has finished."""
        people = {b.id: {s.person_id for s in b.stints} for b in bands}
        weight = defaultdict(int)
        for a in bands:
            for b in bands:
                if a.id < b.id and people[a.id] & people[b.id]:
                    weight[(a.id, b.id)] = weight[(b.id, a.id)] = len(people[a.id] & people[b.id])
        links = [(a, b, w) for (a, b), w in list(weight.items()) if a < b]
        by_id = {b.id: b for b in bands}

        def cost(seq):
            pos = {bid: i for i, bid in enumerate(seq)}
            return sum(w * abs(pos[a] - pos[b]) for a, b, w in links if a in pos and b in pos)

        # 1. Grow the order from the root band(s), always adding the most
        #    connected band at its cheapest insertion point.
        roots = [b.id for b in bands if b.level == 0] or [bands[0].id]
        seq = roots[:1]
        remaining = [b.id for b in bands if b.id != seq[0]]
        while remaining:
            nxt = max(remaining, key=lambda r: (sum(weight[(r, s)] for s in seq), -by_id[r].level, -by_id[r].start))
            remaining.remove(nxt)
            seq = min((seq[:i] + [nxt] + seq[i:] for i in range(len(seq) + 1)),
                      key=lambda cand: (cost(cand), abs(cand.index(nxt) - len(cand) / 2)))
        # 2. Improve with adjacent swaps and single-band moves.
        best = cost(seq)
        improved = True
        while improved:
            improved = False
            for i in range(len(seq)):
                for j in range(len(seq)):
                    if i == j:
                        continue
                    cand = seq[:]
                    cand.insert(j, cand.pop(i))
                    c = cost(cand)
                    if c < best - 1e-9:
                        seq, best, improved = cand, c, True
        # 3. Pack into lanes: reuse any lane whose bands don't overlap in time,
        #    choosing the lane that keeps connected bands closest together.
        lane_of, lanes = {}, []
        for bid in seq:
            band = by_id[bid]

            def lane_cost(lane):
                return sum(w * abs(lane - lane_of[o]) for o, w in
                           ((o, weight[(bid, o)]) for o in lane_of) if w)

            options = [(lane_cost(len(lanes)) + 1.5, len(lanes))]
            for i, occupants in enumerate(lanes):
                if all(o.end + LANE_REUSE_YEARS <= band.start or band.end + LANE_REUSE_YEARS <= o.start
                       for o in occupants):
                    options.append((lane_cost(i), i))
            _, lane = min(options, key=lambda o: (o[0], -o[1]))
            if lane == len(lanes):
                lanes.append([])
            lanes[lane].append(band)
            lane_of[bid] = lane
        return lane_of

    def _assign_rows(self):
        """Give every row a y: roughly proportional to time, but never letting
        two line-ups in the same lane collide."""
        groups = defaultdict(list)
        for box in self.boxes.values():
            groups[round(box["start"] * 12)].append(box)
        lane_bottom = defaultdict(lambda: -math.inf)
        y_prev, t_prev = None, None
        anchors = []
        for key in sorted(groups):
            group = groups[key]
            t = min(b["start"] for b in group)
            if y_prev is None:
                y = TITLE_H
            else:
                step = min(max((t - t_prev) * PX_PER_YEAR, MIN_STEP), MAX_STEP)
                y = y_prev + step
            y = max([y] + [lane_bottom[b["lane"]] + V_GAP for b in group])
            for b in group:
                b["y"] = y
                lane_bottom[b["lane"]] = y + b["footprint"]
            anchors.append((t, y))
            y_prev, t_prev = y, t
        return anchors

    # ------------------------------------------------------------------
    def _member(self, box, person_id):
        return next((m for m in box["members"] if m["person_id"] == person_id), None)

    def _continuity(self, bands):
        """Each musician's line straight down to their place in the band's next
        line-up (same lane). Lines crossing lanes are routed as edges."""
        lines = []
        for band in bands:
            boxes = [self.boxes[f"{band.id}#{lu.number}"] for lu in band.lineups]
            for a, b in zip(boxes, boxes[1:]):
                if a["lane"] != b["lane"]:
                    continue
                for ma in a["members"]:
                    mb = self._member(b, ma["person_id"])
                    if mb is None:
                        continue
                    pts = [(ma["cx"], ma["bottom"]), (ma["cx"], b["y"] - 6)]
                    if mb["cx"] != ma["cx"]:
                        pts.append((mb["cx"], b["y"] - 6))
                    pts.append((mb["cx"], b["bar_y"]))
                    lines.append({"person_id": ma["person_id"], "points": pts, "dashed": b["after_gap"]})
            last = boxes[-1]
            if last["ongoing"]:
                for m in last["members"]:
                    lines.append({"person_id": m["person_id"], "dashed": False, "arrow": True,
                                  "points": [(m["cx"], m["bottom"]), (m["cx"], m["bottom"] + 26)]})
        return lines

    def _route_edges(self, bands):
        lane_boxes = defaultdict(list)
        for b in self.boxes.values():
            lane_boxes[b["lane"]].append((b["y"] - 12, b["y"] + b["footprint"] + 6))

        pairs = []
        for person_id, apps in self.appearances.items():
            for (ba, la), (bb, lb) in zip(apps, apps[1:]):
                A = self.boxes[f"{ba.id}#{la.number}"]
                B = self.boxes[f"{bb.id}#{lb.number}"]
                if A is B:
                    continue
                if ba.id == bb.id and lb.number == la.number + 1 and A["lane"] == B["lane"]:
                    continue  # drawn as a straight continuity line
                if self._member(A, person_id) is None or self._member(B, person_id) is None:
                    continue  # beyond MAX_MEMBERS
                pairs.append((person_id, A, B, ba.id == bb.id))

        out_count, in_count = defaultdict(int), defaultdict(int)
        edges = []
        for person_id, A, B, same_band in sorted(pairs, key=lambda p: (p[1]["y"], self._member(p[1], p[0])["cx"])):
            k_out = out_count[A["id"]] % 4
            k_in = in_count[B["id"]] % 4
            out_count[A["id"]] += 1
            in_count[B["id"]] += 1
            edges.append(self._route(person_id, A, B, k_out, k_in, lane_boxes, same_band))
        self._assign_tracks(edges)
        return edges

    def _route(self, person_id, A, B, k_out, k_in, lane_boxes, same_band):
        ma, mb = self._member(A, person_id), self._member(B, person_id)
        la, lb = A["lane"], B["lane"]
        if lb > la:
            g1, g2 = la + 1, lb
        elif lb < la:
            g1, g2 = la, lb + 1
        else:
            g1 = g2 = la + 1
        edge = {
            "person_id": person_id, "from": A["id"], "to": B["id"], "same_band": same_band,
            "dashed": same_band and B["after_gap"],
            "sx": ma["cx"], "sy": ma["bottom"], "tx": mb["cx"], "ty": B["bar_y"],
            # leave below the whole line-up (clear of the notes), arrive just above the band name
            "ya": A["y"] + A["footprint"] + 8 + STAGGER * k_out,
            "yb": B["y"] - 8 - STAGGER * k_in,
            "g1": g1, "g2": g2,
        }
        if g1 != g2:
            crossing = range(min(g1, g2), max(g1, g2))
            edge["cy"] = self._crossing_y(crossing, lane_boxes, edge["ya"], edge["yb"], edge["yb"] - 10)
        return edge

    def _crossing_y(self, lanes, lane_boxes, sy, ty, preferred):
        """A y at which a horizontal line can cross `lanes` without hitting a box."""
        busy = sorted(iv for lane in lanes for iv in lane_boxes[lane])
        lo, hi = min(sy, ty) - 200, max(sy, ty)
        free, cursor = [], lo
        for a, b in busy:
            if b < cursor:
                continue
            if a > cursor:
                free.append((cursor, min(a, hi)))
            cursor = max(cursor, b)
            if cursor >= hi:
                break
        if cursor < hi:
            free.append((cursor, hi))
        best = None
        for a, b in free:
            if b - a < 10:
                continue
            y = min(max(preferred, a + 5), b - 5)
            if best is None or abs(y - preferred) < abs(best - preferred):
                best = y
        return best if best is not None else preferred

    def _assign_tracks(self, edges):
        """Spread parallel lines across a gutter so they don't sit on top of each other."""
        per_gutter = defaultdict(list)
        for e in edges:
            if e["g1"] == e["g2"]:
                per_gutter[e["g1"]].append((min(e["ya"], e["yb"]), max(e["ya"], e["yb"]), e, "x1"))
            else:
                per_gutter[e["g1"]].append((min(e["ya"], e["cy"]), max(e["ya"], e["cy"]), e, "x1"))
                per_gutter[e["g2"]].append((min(e["cy"], e["yb"]), max(e["cy"], e["yb"]), e, "x2"))
        max_tracks = max(1, int((GUTTER - 12) // TRACK_SPACING))
        for gutter, segs in per_gutter.items():
            segs.sort(key=lambda s: (s[0], s[1]))
            track_end = []
            for y1, y2, e, key in segs:
                track = next((i for i, end in enumerate(track_end) if end < y1 - 6), None)
                if track is None:
                    track = len(track_end)
                    track_end.append(y2)
                else:
                    track_end[track] = y2
                offset = ((track % max_tracks) - (max_tracks - 1) / 2) * TRACK_SPACING
                e[key] = self._gutter_x(gutter) + offset
        for e in edges:
            if e["g1"] == e["g2"]:
                e["x2"] = e["x1"]
        crossings = sorted((e for e in edges if "cy" in e), key=lambda e: e["cy"])
        placed = []
        for e in crossings:
            xa, xb = sorted((e["x1"], e["x2"]))
            while any(abs(e["cy"] - p["cy"]) < 5 and xa < max(p["x1"], p["x2"]) and xb > min(p["x1"], p["x2"])
                      for p in placed):
                e["cy"] -= 6
            placed.append(e)
        for e in edges:
            pts = [(e["sx"], e["sy"]), (e["sx"], e["ya"]), (e["x1"], e["ya"])]
            if "cy" in e:
                pts += [(e["x1"], e["cy"]), (e["x2"], e["cy"])]
            pts += [(e["x2"], e["yb"]), (e["tx"], e["yb"]), (e["tx"], e["ty"])]
            e["points"] = pts

    def _shift(self, dx, trunks, edges):
        if not dx:
            return
        for b in self.boxes.values():
            b["x"] += dx
            b["notes_x"] += dx
            b["bar"] = (b["bar"][0] + dx, b["bar"][1] + dx)
            for m in b["members"]:
                m["cx"] += dx
        for line in list(trunks) + list(edges):
            line["points"] = [(x + dx, y) for x, y in line["points"]]

    # ------------------------------------------------------------------
    def _fill_page(self, content_w, anchors):
        """If the sheet will be taller than the drawing, spread the rows out to
        use it: gaps grow, line-ups keep their size, so nothing can collide."""
        content_h = max(b["y"] + b["footprint"] for b in self.boxes.values()) + 60
        width, height, _ = self._paper_size(content_w, content_h + FOOTER_H)
        spare = height - (content_h + FOOTER_H)
        if spare <= 0:
            return anchors
        span = max(b["y"] for b in self.boxes.values()) - TITLE_H
        if span <= 0:
            return anchors
        f = min(MAX_STRETCH, 1 + spare / span)
        for b in self.boxes.values():
            b["y"] = TITLE_H + (b["y"] - TITLE_H) * f
        return [(t, TITLE_H + (y - TITLE_H) * f) for t, y in anchors]

    def _paper_size(self, w, h):
        """Grow the canvas to the paper's proportions, in whichever orientation
        wastes less space; the drawing is centred horizontally."""
        if not self.paper:
            return w, h, 0
        short, long_ = PAPER_MM[self.paper]
        ratio = long_ / short
        portrait = (max(w, h / ratio), max(h, max(w, h / ratio) * ratio))
        landscape = (max(w, max(h, w / ratio) * ratio), max(h, w / ratio))
        width, height = min(portrait, landscape, key=lambda s: s[0] * s[1])
        return width, height, (width - w) / 2

    def _year_marks(self, anchors):
        if not anchors:
            return []
        first, last = math.floor(anchors[0][0]), math.ceil(anchors[-1][0])
        ys = {year: _interpolate(anchors, year) for year in range(first, last + 1)}
        ys = {k: v for k, v in ys.items() if v is not None}
        # Decades and half-decades win; other years only where there's room.
        chosen = []
        for step in (10, 5, 1):
            for year, y in ys.items():
                if year % step or year in chosen:
                    continue
                if all(abs(y - ys[c]) >= 34 for c in chosen):
                    chosen.append(year)
        marks = [{"year": year, "y": ys[year]} for year in sorted(chosen)]
        return marks


def _overlap(a, b):
    return a.start < b.end and b.start < a.end


def _interpolate(anchors, t):
    if t < anchors[0][0]:
        return None
    for (t1, y1), (t2, y2) in zip(anchors, anchors[1:]):
        if t1 <= t <= t2:
            return y1 if t2 == t1 else y1 + (y2 - y1) * (t - t1) / (t2 - t1)
    return None


def _split_name(name):
    """'JOHN PAUL JONES' -> ['JOHN PAUL', 'JONES']: first name(s) over surname."""
    parts = name.split()
    if len(parts) < 2:
        return [name]
    return [" ".join(parts[:-1]), parts[-1]]


_MONTHS = {"Jan": "January", "Feb": "February", "Mar": "March", "Apr": "April", "May": "May", "Jun": "June",
           "Jul": "July", "Aug": "August", "Sep": "September", "Oct": "October", "Nov": "November",
           "Dec": "December"}


def _long_date(label):
    """'Mar 66' -> 'March 1966'; '1966' stays."""
    parts = (label or "").split()
    if len(parts) == 2 and parts[0] in _MONTHS and parts[1].isdigit():
        yy = int(parts[1])
        return f"{_MONTHS[parts[0]]} {1900 + yy if yy >= 30 else 2000 + yy}"
    return label
