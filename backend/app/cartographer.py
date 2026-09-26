"""Lays out a FamilyTree in the manner of Pete Frame's Rock Family Trees.

* Time runs down the page. Every line-up is a numbered box; boxes that start
  at the same time share a row, and rows are spaced roughly in proportion to
  elapsed time, pushed apart only as much as needed to avoid overlaps.
* Each band gets a vertical lane. Lanes are reused once a band has finished,
  and bands that share members are placed next to each other.
* Consecutive line-ups of a band are joined by a thick "trunk" line.
* When a musician moves to another band (or rejoins later), a thin line runs
  from their name in the old box, down the gutters between lanes, into their
  name in the new box.
* Short handwritten-style notes under each box say who left, why, and when.
"""
import math
from collections import defaultdict

from app.fonts import HAND, MARKER, text_width, wrap

LANE_W = 250
GUTTER = 70
AXIS_W = 80           # year scale on each side
MARGIN = 40
TITLE_H = 250
FOOTER_H = 190

PAD = 10
NAME_SIZE = 21        # band name
DATE_SIZE = 13
MEMBER_SIZE = 14
ROLE_SIZE = 11
ROW_H = 19
NOTE_SIZE = 12
NOTE_LINE = 15
MAX_MEMBERS = 14
MAX_NOTES = 4
TRUNK_DX = 16         # trunk runs this far in from the box's left edge

PX_PER_YEAR = 75
MIN_STEP = 14
MAX_STEP = 110
V_GAP = 34            # minimum gap between boxes in one lane
LANE_REUSE_YEARS = 0.1
TRACK_SPACING = 7
SIDESTEP_SLACK = 60   # px a line-up may slip below its date before zig-zagging

PAPER_MM = {"A0": (841, 1189), "A1": (594, 841), "A2": (420, 594), "A3": (297, 420), "A4": (210, 297)}


class Cartographer:
    def __init__(self, tree, paper="A1", subtitle=None):
        self.tree = tree
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
        self._make_boxes(bands)
        lanes = self._assign_lanes(bands)
        self.lane_count = max(lanes.values()) + 1
        self.lane_spans = defaultdict(list)
        for band in bands:
            self.lane_spans[lanes[band.id]].append((band.id, band.start, band.end))
        for box in self.boxes.values():
            box["lane"] = box["home_lane"] = lanes[box["band_id"]]
        anchors = self._assign_rows()
        for box in self.boxes.values():
            box["x"] = self._lane_x(box["lane"])
        trunks = self._trunks(bands)
        edges = self._route_edges()

        content_w = self._lane_x(self.lane_count) + AXIS_W + MARGIN
        content_h = max(b["y"] + b["footprint"] for b in self.boxes.values()) + 60
        width, height, offset_x = self._paper_size(content_w, content_h + FOOTER_H)
        self._shift(offset_x, trunks, edges)
        years = self._year_marks(anchors)

        return {
            "width": width, "height": height, "paper": self.paper,
            "title": self.tree.title, "subtitle": self.subtitle,
            "axis": {"left": offset_x + MARGIN + AXIS_W / 2,
                     "right": offset_x + content_w - MARGIN - AXIS_W / 2,
                     "top": TITLE_H - 20, "bottom": content_h},
            "years": years,
            "boxes": [self.boxes[k] for k in self.box_order],
            "trunks": trunks, "edges": edges,
            "footer_y": height - FOOTER_H + 30,
            "stats": {"bands": len(bands), "lineups": len(self.boxes),
                      "people": len({p for b in bands for s in b.stints for p in [s.person_id]})},
        }

    def _lane_x(self, lane):
        return MARGIN + AXIS_W + GUTTER + lane * (LANE_W + GUTTER)

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

    def _make_boxes(self, bands):
        for band in bands:
            name_lines, name_size = self._fit_band_name(band.name.upper())
            for i, lu in enumerate(band.lineups):
                nxt = band.lineups[i + 1] if i + 1 < len(band.lineups) else None
                members = lu.members[:MAX_MEMBERS]
                overflow = len(lu.members) - len(members)
                header_h = PAD + len(name_lines) * (name_size + 3) + DATE_SIZE + 8
                h = header_h + (len(members) + (1 if overflow else 0)) * ROW_H + PAD
                notes = []
                for note in self._notes(band, lu, nxt)[:MAX_NOTES]:
                    notes += wrap(note, HAND, NOTE_SIZE, LANE_W - TRUNK_DX - 16)
                box_id = f"{band.id}#{lu.number}"
                rows = {}
                for j, m in enumerate(members):
                    rows[m.person_id] = header_h + j * ROW_H + ROW_H / 2
                self.boxes[box_id] = {
                    "id": box_id, "band_id": band.id, "band_name": band.name,
                    "name_lines": name_lines, "name_size": name_size,
                    "number": lu.number, "start": lu.start, "end": lu.end,
                    "date_label": f"{lu.start_label} – {lu.end_label}",
                    "after_gap": lu.after_gap, "ongoing": lu.ongoing, "level": band.level,
                    "header_h": header_h, "w": LANE_W, "h": h,
                    "members": [{"person_id": m.person_id, "name": m.name, "roles": ", ".join(m.roles),
                                 "dy": rows[m.person_id]} for m in members],
                    "overflow": overflow,
                    "notes": notes[:MAX_NOTES + 2],
                    "footprint": h + (8 + len(notes[:MAX_NOTES + 2]) * NOTE_LINE if notes else 0),
                }
                self.box_order.append(box_id)

    def _fit_band_name(self, name):
        avail = LANE_W - 2 * PAD - 18
        if text_width(name, MARKER, NAME_SIZE) <= avail:
            return [name], NAME_SIZE
        for size in (19, 17):
            lines = wrap(name, MARKER, size, avail)
            if len(lines) <= 2 and all(text_width(l, MARKER, size) <= avail for l in lines):
                return lines, size
        return wrap(name, MARKER, 15, avail)[:3], 15

    def _notes(self, band, lu, nxt):
        """Frame-style annotations about the end of this line-up."""
        notes = []
        people = self.tree.people
        leaving = [m for m in lu.members]
        if nxt is not None and not nxt.after_gap:
            staying = {m.person_id for m in nxt.members}
            leaving = [m for m in lu.members if m.person_id not in staying]
        band_over = nxt is None or nxt.after_gap
        for m in leaving:
            person = people.get(m.person_id)
            if person and person.died is not None and lu.start <= person.died <= lu.end + 0.3:
                notes.append(f"{m.name} died {person.died_label}")
                continue
            dest = self._next_band(m.person_id, band, lu)
            if dest is not None:
                d_band, d_lu = dest
                verb = "form" if d_lu.number == 1 and abs(d_band.start - lu.end) <= 1.0 else "join"
                if band_over:
                    notes.append(f"{m.name} → {d_band.name}")
                else:
                    notes.append(f"{m.name} left to {verb} {d_band.name}")
            elif not band_over:
                notes.append(f"{m.name} left {lu.end_label}")
        if band_over:
            if nxt is not None:
                notes.insert(0, f"Split {lu.end_label}; re-formed {nxt.start_label}")
            elif band.ended:
                notes.insert(0, f"Split {lu.end_label}")
            else:
                notes.insert(0, "Still going")
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

    def _lane_free(self, lane, band_id, start, end):
        if not 0 <= lane < self.lane_count:
            return False
        return all(b == band_id or e + LANE_REUSE_YEARS <= start or end + LANE_REUSE_YEARS <= s
                   for b, s, e in self.lane_spans[lane])

    def _assign_rows(self):
        """Give every row a y. A long-running band whose line-ups would pile up
        far below their dates zig-zags into a free neighbouring lane, as Frame
        did, instead of stretching the whole poster."""
        groups = defaultdict(list)
        for box in self.boxes.values():
            groups[round(box["start"] * 12)].append(box)
        lane_bottom = defaultdict(lambda: -math.inf)
        side_lane = {}
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
            for b in group:
                home = b["home_lane"]
                if lane_bottom[home] + V_GAP <= y + SIDESTEP_SLACK:
                    continue
                side = side_lane.get(b["band_id"])
                if side is None:
                    side = next((c for c in (home + 1, home - 1)
                                 if self._lane_free(c, b["band_id"], b["start"], b["end"])), None)
                elif not self._lane_free(side, b["band_id"], b["start"], b["end"]):
                    side = None
                if side is not None and lane_bottom[side] < lane_bottom[home]:
                    side_lane[b["band_id"]] = side
                    b["lane"] = side
            y = max([y] + [lane_bottom[b["lane"]] + V_GAP for b in group])
            for b in group:
                b["y"] = y
                lane_bottom[b["lane"]] = y + b["footprint"]
            anchors.append((t, y))
            y_prev, t_prev = y, t
        return anchors

    # ------------------------------------------------------------------
    def _trunks(self, bands):
        trunks = []
        for band in bands:
            boxes = [self.boxes[f"{band.id}#{lu.number}"] for lu in band.lineups]
            for a, b in zip(boxes, boxes[1:]):
                trunks.append({"points": self._trunk_points(a, b), "dashed": b["after_gap"]})
            last = boxes[-1]
            if last["ongoing"]:
                x = last["x"] + TRUNK_DX
                y1 = last["y"] + last["footprint"] + 30
                trunks.append({"points": [(x, last["y"] + last["h"]), (x, y1)], "dashed": False, "arrow": True})
        return trunks

    def _trunk_points(self, a, b):
        if a["lane"] == b["lane"]:
            x = a["x"] + TRUNK_DX
            return [(x, a["y"] + a["h"]), (x, b["y"])]
        # zig-zag: leave from the side of the box, through the gutter, into the next box
        rightward = b["lane"] > a["lane"]
        gx = self._gutter_x(max(a["lane"], b["lane"]))
        yb = b["y"] + b["header_h"] / 2
        ya = min(a["y"] + a["h"] - 14, yb)
        xa = a["x"] + (LANE_W if rightward else 0)
        xb = b["x"] + (0 if rightward else LANE_W)
        return [(xa, ya), (gx, ya), (gx, yb), (xb, yb)]

    def _route_edges(self):
        lane_boxes = defaultdict(list)
        for b in self.boxes.values():
            lane_boxes[b["lane"]].append((b["y"] - 6, b["y"] + b["footprint"] + 4))

        edges = []
        for person_id, apps in self.appearances.items():
            for (ba, la), (bb, lb) in zip(apps, apps[1:]):
                if ba.id == bb.id and lb.number == la.number + 1:
                    continue  # carried by the trunk
                A = self.boxes[f"{ba.id}#{la.number}"]
                B = self.boxes[f"{bb.id}#{lb.number}"]
                if A is B:
                    continue
                edges.append(self._route(person_id, A, B, lane_boxes))

        self._assign_tracks(edges)
        return edges

    def _route(self, person_id, A, B, lane_boxes):
        ma = next((m for m in A["members"] if m["person_id"] == person_id), None)
        mb = next((m for m in B["members"] if m["person_id"] == person_id), None)
        sy = A["y"] + (ma["dy"] if ma else A["h"] - PAD)
        ty = B["y"] + (mb["dy"] if mb else B["header_h"])
        la, lb = A["lane"], B["lane"]
        if lb > la:
            g1, g2, sx, tx = la + 1, lb, A["x"] + LANE_W, B["x"]
        elif lb < la:
            g1, g2, sx, tx = la, lb + 1, A["x"], B["x"] + LANE_W
        else:
            g1 = g2 = la + 1
            sx, tx = A["x"] + LANE_W, B["x"] + LANE_W

        edge = {"person_id": person_id, "from": A["id"], "to": B["id"],
                "sx": sx, "sy": sy, "tx": tx, "ty": ty, "g1": g1, "g2": g2}
        if g1 != g2:
            crossing = range(min(g1, g2), max(g1, g2))
            edge["cy"] = self._crossing_y(crossing, lane_boxes, sy, ty, B["y"] - 14)
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
        """Spread parallel lines across the gutter so they don't sit on top of each other."""
        per_gutter = defaultdict(list)
        for e in edges:
            if e["g1"] == e["g2"]:
                per_gutter[e["g1"]].append((min(e["sy"], e["ty"]), max(e["sy"], e["ty"]), e, "x1"))
            else:
                per_gutter[e["g1"]].append((min(e["sy"], e["cy"]), max(e["sy"], e["cy"]), e, "x1"))
                per_gutter[e["g2"]].append((min(e["cy"], e["ty"]), max(e["cy"], e["ty"]), e, "x2"))
        max_tracks = max(1, int((GUTTER - 14) // TRACK_SPACING))
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
        # Nudge horizontal crossings that would run on top of one another.
        crossings = sorted((e for e in edges if "cy" in e), key=lambda e: e["cy"])
        placed = []
        for e in crossings:
            xa, xb = sorted((e["x1"], e["x2"]))
            while any(abs(e["cy"] - p["cy"]) < 5 and xa < max(p["x1"], p["x2"]) and xb > min(p["x1"], p["x2"])
                      for p in placed):
                e["cy"] -= 6
            placed.append(e)
        for e in edges:
            pts = [(e["sx"], e["sy"]), (e["x1"], e["sy"])]
            if "cy" in e:
                pts += [(e["x1"], e["cy"]), (e["x2"], e["cy"])]
            pts += [(e["x2"], e["ty"]), (e["tx"], e["ty"])]
            e["points"] = pts

    # ------------------------------------------------------------------
    def _paper_size(self, w, h):
        if not self.paper:
            return w, h, 0
        short, long_ = PAPER_MM[self.paper]
        ratio = long_ / short
        if h >= w:   # portrait
            width = max(w, h / ratio)
            height = max(h, width * ratio)
        else:        # landscape
            height = max(h, w / ratio)
            width = max(w, height * ratio)
        return width, height, (width - w) / 2

    def _shift(self, dx, trunks, edges):
        if not dx:
            return
        for b in self.boxes.values():
            b["x"] += dx
        for t in trunks:
            t["points"] = [(x + dx, y) for x, y in t["points"]]
        for e in edges:
            e["points"] = [(x + dx, y) for x, y in e["points"]]

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
