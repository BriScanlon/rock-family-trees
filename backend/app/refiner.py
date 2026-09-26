"""Turns harvested MusicBrainz records into a family-tree model:
bands -> numbered line-ups -> members, plus who died when and which bands
to keep. Times are fractional years (1966.25 == April 1966)."""
from collections import Counter
from datetime import date
from typing import Dict, List, Optional

from pydantic import BaseModel

from app.musicbrainz import is_group

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MIN_SEGMENT = 1 / 24  # line-ups shorter than ~2 weeks are date noise


def now_year():
    t = date.today()
    return t.year + (t.month - 1) / 12


def parse_date(s):
    """'1966-03-12' -> (1966.1667, 'Mar 66'); '1966' -> (1966.0, '1966')."""
    if not s or len(s) < 4 or not s[:4].isdigit():
        return None, None
    year = int(s[:4])
    if len(s) >= 7 and s[5:7].isdigit() and 1 <= int(s[5:7]) <= 12:
        month = int(s[5:7])
        return year + (month - 1) / 12, f"{MONTHS[month - 1]} {year % 100:02d}"
    return float(year), str(year)


def format_time(t):
    year = int(t)
    month = int(round((t - year) * 12))
    if month >= 12:
        year, month = year + 1, 0
    return str(year) if month == 0 else f"{MONTHS[month]} {year % 100:02d}"


# Instruments as Pete Frame writes them under each name: plain lowercase words.
# Most specific MusicBrainz attribute first.
ROLE_WORDS = [
    ("background vocals", "backing vocals"), ("lead vocals", "vocals"), ("vocals", "vocals"), ("vocal", "vocals"),
    ("rhythm guitar", "guitar"), ("lead guitar", "guitar"), ("slide guitar", "guitar"), ("steel guitar", "steel guitar"),
    ("bass guitar", "bass"), ("double bass", "bass"), ("bass", "bass"),
    ("guitar", "guitar"),
    ("drums", "drums"), ("drum", "drums"), ("percussion", "percussion"),
    ("keyboard", "keyboards"), ("synthesizer", "synths"), ("piano", "piano"), ("organ", "organ"),
    ("mellotron", "keyboards"), ("harmonica", "harmonica"), ("saxophone", "sax"), ("violin", "violin"),
    ("fiddle", "fiddle"), ("flute", "flute"), ("trumpet", "trumpet"), ("trombone", "trombone"),
    ("cello", "cello"), ("banjo", "banjo"), ("mandolin", "mandolin"), ("turntables", "decks"),
    ("programming", "programming"), ("dj", "decks"), ("rap", "vocals"), ("mc", "vocals"),
]
NON_ROLE_ATTRIBUTES = {"original", "founder", "additional", "minor", "guest", "support", "touring", "eponymous"}
ROLE_ORDER = ["vocals", "guitar", "steel guitar", "bass", "keyboards", "synths", "piano", "organ", "drums", "percussion"]


def role_words(attributes):
    out = []
    for attr in attributes or []:
        a = (attr or "").lower().strip()
        if not a or a in NON_ROLE_ATTRIBUTES:
            continue
        word = next((w for key, w in ROLE_WORDS if key in a), a)
        if word not in out:
            out.append(word)
    if len(out) > 1 and "backing vocals" in out:
        out.remove("backing vocals")
    return out[:3]


def _role_rank(roles):
    for r in roles:
        if r in ROLE_ORDER:
            return ROLE_ORDER.index(r)
    return len(ROLE_ORDER)


class Stint(BaseModel):
    person_id: str
    name: str
    start: float
    end: float
    roles: List[str] = []
    start_label: Optional[str] = None
    end_label: Optional[str] = None


class LineupMember(BaseModel):
    person_id: str
    name: str
    roles: List[str] = []


class Lineup(BaseModel):
    number: int
    start: float
    end: float
    start_label: str
    end_label: str
    members: List[LineupMember]
    after_gap: bool = False  # band was inactive just before this line-up
    ongoing: bool = False


class Band(BaseModel):
    id: str
    name: str
    level: int = 0
    start: float
    end: float
    ended: bool = True
    stints: List[Stint] = []
    lineups: List[Lineup] = []


class Person(BaseModel):
    id: str
    name: str
    died: Optional[float] = None
    died_label: Optional[str] = None


class FamilyTree(BaseModel):
    root_id: str
    root_name: str
    title: str
    bands: Dict[str, Band]
    people: Dict[str, Person]


class Refiner:
    def __init__(self, max_bands=30, max_lineups_per_band=20, today=None):
        self.max_bands = max_bands
        self.max_lineups = max_lineups_per_band
        self.today = today or now_year()

    def build(self, harvest, title=None):
        records = harvest["records"]
        levels = harvest.get("band_levels", {})

        people = {}
        for rec in records.values():
            if is_group(rec):
                continue
            died, died_label = parse_date(rec.get("end")) if rec.get("ended") else (None, None)
            people[rec["mbid"]] = Person(id=rec["mbid"], name=rec["name"], died=died, died_label=died_label)

        bands = {}
        for band_id, level in levels.items():
            rec = records.get(band_id)
            if not rec or not is_group(rec):
                continue
            band = self._build_band(rec, level)
            if band and band.lineups:
                bands[band_id] = band
            for s in (band.stints if band else []):
                people.setdefault(s.person_id, Person(id=s.person_id, name=s.name))

        selected = self._select(bands, harvest.get("root_bands", []))
        root_name = harvest.get("root_name", "")
        return FamilyTree(
            root_id=harvest.get("root_id", ""),
            root_name=root_name,
            title=title or default_title(root_name),
            bands=selected,
            people=people,
        )

    # -- bands -----------------------------------------------------------
    def _build_band(self, rec, level):
        raw = [m for m in rec["memberships"] if m["band_id"] == rec["mbid"]]
        b_start, b_start_label = parse_date(rec.get("begin"))
        b_end, b_end_label = parse_date(rec.get("end"))

        parsed = []
        for m in raw:
            s, sl = parse_date(m.get("begin"))
            e, el = parse_date(m.get("end"))
            parsed.append((m, s, sl, e, el))

        if b_start is None:
            starts = [p[1] for p in parsed if p[1] is not None]
            if not starts:
                return None
            b_start = min(starts)
        ended = bool(rec.get("ended")) or b_end is not None
        if b_end is None:
            if ended:
                ends = [p[3] for p in parsed if p[3] is not None]
                b_end = max(ends) if ends else b_start + 1
            else:
                b_end = self.today
        if b_end <= b_start:
            b_end = b_start + 0.5

        labels = {b_start: b_start_label or format_time(b_start), b_end: b_end_label or format_time(b_end)}
        stints = []
        for m, s, sl, e, el in parsed:
            if s is None:
                s = b_start
            if e is None:
                e = b_end if (not m.get("ended") or ended) else min(b_end, s + 1)
            if e <= s:
                e = s + 0.5  # joined and left within the same (year-precision) period
            s, e = max(s, b_start), min(e, b_end)
            if e - s < MIN_SEGMENT:
                continue
            for t, lab in ((s, sl), (e, el)):
                if lab and t not in labels:
                    labels[t] = lab
            stints.append(Stint(
                person_id=m["person_id"], name=m["person_name"] or "?", start=s, end=e,
                roles=role_words(m.get("attributes")), start_label=sl, end_label=el,
            ))

        band = Band(id=rec["mbid"], name=rec["name"], level=level, start=b_start, end=b_end,
                    ended=ended, stints=stints)
        band.lineups = self._lineups(band, labels)
        return band

    def _lineups(self, band, labels):
        if not band.stints:
            return []
        # Stable member order: order of joining, then vocals/guitar/bass/drums.
        first_seen = {}
        for s in sorted(band.stints, key=lambda s: (s.start, _role_rank(s.roles), s.name)):
            first_seen.setdefault(s.person_id, len(first_seen))

        points = sorted({band.start, band.end} | {t for s in band.stints for t in (s.start, s.end)})
        bounds = [points[0]]
        for t in points[1:]:
            if t - bounds[-1] >= MIN_SEGMENT:
                bounds.append(t)
        bounds[-1] = max(bounds[-1], points[-1])

        lineups: List[Lineup] = []
        gap = False
        for a, b in zip(bounds, bounds[1:]):
            mid = (a + b) / 2
            active = {}
            for s in band.stints:
                if s.start <= mid < s.end:
                    m = active.setdefault(s.person_id, LineupMember(person_id=s.person_id, name=s.name, roles=[]))
                    m.roles += [r for r in s.roles if r not in m.roles]
            if not active:
                gap = bool(lineups)
                continue
            members = sorted(active.values(), key=lambda m: first_seen[m.person_id])
            ids = [m.person_id for m in members]
            if lineups and not gap and [m.person_id for m in lineups[-1].members] == ids:
                lineups[-1].end = b
                continue
            lineups.append(Lineup(number=len(lineups) + 1, start=a, end=b, start_label="", end_label="",
                                  members=members, after_gap=gap))
            gap = False

        self._tidy_lineups(lineups)
        for i, lu in enumerate(lineups):
            lu.number = i + 1
            lu.start_label = labels.get(lu.start) or format_time(lu.start)
            lu.ongoing = not band.ended and abs(lu.end - band.end) < 1e-6
            lu.end_label = "present" if lu.ongoing else (labels.get(lu.end) or format_time(lu.end))
            for m in lu.members:
                m.roles = m.roles[:3]
        return lineups

    def _tidy_lineups(self, lineups):
        # A brief line-up that is just the previous one minus somebody is a
        # vacancy caused by imprecise dates, not a real line-up: fold it back.
        i = 1
        while i < len(lineups):
            prev, cur = lineups[i - 1], lineups[i]
            prev_ids = {m.person_id for m in prev.members}
            cur_ids = {m.person_id for m in cur.members}
            if not cur.after_gap and cur.end - cur.start <= 0.26 and cur_ids < prev_ids:
                prev.end = cur.end
                del lineups[i]
            else:
                i += 1
        # Too many line-ups to draw: merge the shortest into its neighbour,
        # keeping whichever membership lasted longer.
        while len(lineups) > self.max_lineups:
            i = min(range(1, len(lineups)), key=lambda k: lineups[k].end - lineups[k].start)
            prev, cur = lineups[i - 1], lineups[i]
            if cur.end - cur.start > prev.end - prev.start:
                prev.members = cur.members
            prev.end = cur.end
            del lineups[i]

    # -- selection ------------------------------------------------------
    def _select(self, bands, root_bands):
        chosen = {b: bands[b] for b in root_bands if b in bands}
        if not chosen:
            return {}
        people_in = lambda b: {s.person_id for s in b.stints}
        chosen_people = set().union(*(people_in(b) for b in chosen.values()))

        rest = [b for b in bands.values() if b.id not in chosen]
        for level in sorted({b.level for b in rest}):
            candidates = []
            for b in rest:
                if b.level != level:
                    continue
                shared = people_in(b) & chosen_people
                if shared:
                    candidates.append((len(shared), b))
            candidates.sort(key=lambda c: (-c[0], c[1].start, c[1].name))
            for _, b in candidates:
                if len(chosen) >= self.max_bands:
                    return chosen
                chosen[b.id] = b
                chosen_people |= people_in(b)
        return chosen


def default_title(root_name):
    name = (root_name or "").upper()
    if name.startswith("THE "):
        return f"THE {name[4:]} FAMILY TREE"
    return f"THE {name} FAMILY TREE"
