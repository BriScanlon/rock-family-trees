"""Turns harvested MusicBrainz records into a family-tree model:
bands -> numbered line-ups -> members, plus who died when and which bands
to keep. Times are fractional years (1966.25 == April 1966)."""
import math
from collections import Counter, defaultdict
from datetime import date
from typing import Dict, List, Optional

from pydantic import BaseModel

from app.charts import apply_chart
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
PRINCIPAL_ROLES = {"vocals", "guitar", "bass", "keyboards", "piano", "organ", "synths", "drums"}


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
    # a principal instrument first (Frame gives each musician one): MusicBrainz
    # lists Ian Gillan as "harmonica, lead vocals, percussion". Among principal
    # instruments MusicBrainz's order stands: Glenn Hughes is "bass, vocals".
    out.sort(key=lambda r: 0 if r in PRINCIPAL_ROLES else 1)
    return out[:3]


def _role_rank(roles):
    for r in roles:
        if r in ROLE_ORDER:
            return ROLE_ORDER.index(r)
    return len(ROLE_ORDER)


FOUNDER_YEARS = 10   # a founder's minimum tenure in the band they founded
MOVE_YEARS = 2       # left one band and joined the other within this: a direct move
MOVE_BONUS = 2.0
SIDE_PROJECT = 0.3
UNDATED_YEARS = 0.25
STANDING_POWER = 0.5  # damping of a band's standing (Wikipedias covering it) relative to the family's median
STANDING_MIN, STANDING_MAX = 0.5, 2.0
MOSTLY_DATED = 0.5    # leave undated members out of the line-ups only when at least this share are dated  # what an undated membership counts for when ranking bands


class Stint(BaseModel):
    person_id: str
    name: str
    start: float
    end: float
    roles: List[str] = []
    start_label: Optional[str] = None
    end_label: Optional[str] = None
    original: bool = False  # a founder member (MusicBrainz "original")


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
    merged: int = 0          # brief line-ups folded into this one to fit the page
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
    undated: List[str] = []  # members MusicBrainz gives no dates for, left out of the line-ups
    stories: List[dict] = []  # dated notes written from Wikipedia (app/narrative.py)
    albums: List[str] = []  # studio albums, "1972-03-25 Machine Head" (MusicBrainz), notes on their line-ups
    genres: List[str] = []
    events: List[dict] = []  # dated events from its albums' and tours' articles (app/events.py)
    standing: Optional[int] = None  # Wikipedias with an article on the band (Wikidata sitelinks)


class Person(BaseModel):
    id: str
    name: str
    died: Optional[float] = None
    died_label: Optional[str] = None
    bands: List[str] = []  # every band they played in, as MusicBrainz knows it (earliest first)
    joined: Dict[str, float] = {}  # band name -> the year they first joined it (their career, dated)


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
        # Wikipedia's member chart, where the band has one, in place of
        # MusicBrainz's memberships for the members it lists (app/charts.py)
        records = {k: dict(r, memberships=apply_chart(r["memberships"], r["chart"], r["mbid"], r["name"]))
                   if r.get("chart") and is_group(r) else r
                   for k, r in harvest["records"].items()}
        levels = harvest.get("band_levels", {})

        people = {}
        for rec in records.values():
            if is_group(rec):
                continue
            died, died_label = parse_date(rec.get("end")) if rec.get("ended") else (None, None)
            people[rec["mbid"]] = Person(id=rec["mbid"], name=rec["name"], died=died, died_label=died_label)

        # A musician's instrument where MusicBrainz leaves it off one membership
        # but gives it on another (Dio: none in Rainbow, "lead vocals" in Black Sabbath)
        self.known_roles = defaultdict(Counter)
        for rec in records.values():
            for m in rec.get("memberships", []):
                for r in role_words(m.get("attributes"))[:1]:
                    self.known_roles[m["person_id"]][r] += 1

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

        # each musician's whole career, for the notes in the gaps ("also played with ...")
        career = defaultdict(dict)
        for rec in records.values():
            for m in rec.get("memberships", []):
                year = parse_date(m.get("begin"))[0] or 9999
                career[m["person_id"]][m["band_name"]] = min(year, career[m["person_id"]].get(m["band_name"], 9999))
        for pid, person in people.items():
            person.bands = [n for n, _ in sorted(career.get(pid, {}).items(), key=lambda kv: (kv[1], kv[0])) if n]
            person.joined = {n: y for n, y in career.get(pid, {}).items() if n and y < 9999}

        selected = self._select(bands, harvest.get("root_bands", []))
        root_name = harvest.get("root_name", "")
        return FamilyTree(
            root_id=harvest.get("root_id", ""),
            root_name=root_name,
            title=title or default_title(root_name),
            bands=selected,
            people=people,
        )

    def _role_for(self, person_id):
        known = getattr(self, "known_roles", {}).get(person_id)
        return [known.most_common(1)[0][0]] if known else []

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
        # MusicBrainz leaves many long-gone bands without an end date (MI5, 1966-67):
        # only call a band current if someone's dated membership is still open
        still_open = any(s is not None and e is None and not m.get("ended") for m, s, sl, e, el in parsed)
        if not ended and not still_open:
            ended = True
        if b_end is None:
            if ended:
                known = [t for p in parsed for t in (p[1], p[3]) if t is not None]
                b_end = max(known) if known else b_start + 1
            else:
                b_end = self.today
        if b_end <= b_start:
            b_end = b_start + 0.5

        labels = {b_start: b_start_label or format_time(b_start), b_end: b_end_label or format_time(b_end)}
        # An undated membership would span the band's whole life: David Stone
        # (Rainbow keyboards 1977-78) turned up in every Rainbow line-up and hid
        # its 1984-93 break. Where other members are dated, leave the undated
        # ones out of the line-ups (and say so) - unless they founded the band
        # or it's named after them (Ian Gillan in Gillan).
        # Only when they're the exception: where most members are undated (MI5:
        # only Ian Paice has dates) the undated ones are the band, so keep them.
        dated_share = sum(s is not None or e is not None for m, s, sl, e, el in parsed) / max(1, len(parsed))
        any_dated = dated_share >= MOSTLY_DATED
        undated = []
        stints = []
        for m, s, sl, e, el in parsed:
            if any_dated and s is None and e is None and not _anchors(m, rec["name"]):
                role = role_words(m.get("attributes"))[:1] or list(self._role_for(m["person_id"]))
                undated.append(f"{m['person_name']}{f' ({role[0]})' if role else ''}")
                continue
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
                roles=role_words(m.get("attributes")) or self._role_for(m["person_id"]),
                start_label=sl, end_label=el,
                original="original" in [(a or "").lower() for a in m.get("attributes") or []],
            ))

        band = Band(id=rec["mbid"], name=rec["name"], level=level, start=b_start, end=b_end,
                    ended=ended, stints=stints, undated=list(dict.fromkeys(undated)),
                    genres=list(rec.get("genres") or [])[:3], standing=rec.get("sitelinks"))
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
            prev.merged += 1 + cur.merged
            del lineups[i]

    # -- selection ------------------------------------------------------
    def _select(self, bands, root_bands):
        """The root band(s), then the bands most strongly linked to those
        already chosen, a generation at a time. A link is a musician both
        bands share, worth more the longer they served on each side (the
        geometric mean of the two tenures), double if they moved straight
        from one band to the other (the family's lineage: Nirvana to Foo
        Fighters) and less than a third if the candidate was a side project
        running alongside the chosen band. A founder counts as long-serving
        in the band they founded even if their dates say otherwise."""
        chosen = {b: bands[b] for b in root_bands if b in bands}
        if not chosen:
            return {}
        tenure = defaultdict(float)   # years each musician served in the bands chosen so far
        served = defaultdict(list)    # their stints in those bands

        def add(band):
            for st in band.stints:
                years = st.end - st.start
                if st.original:
                    years = max(years, min(FOUNDER_YEARS, band.end - band.start))
                tenure[st.person_id] += years
                served[st.person_id].append(st)

        for b in chosen.values():
            add(b)

        def strength(band):
            total = 0.0
            for pid in {s.person_id for s in band.stints} & set(tenure):
                here = [s for s in band.stints if s.person_id == pid]
                # an undated membership is filled in with the band's whole life
                # when drawn; as evidence of a link it is worth only a little
                years_here = sum(s.end - s.start if (s.start_label or s.end_label) else UNDATED_YEARS
                                 for s in here)
                link = math.sqrt(tenure[pid] * max(years_here, 0.25))
                there = served[pid]
                direct = any(0 <= t.start - h.end <= MOVE_YEARS or 0 <= h.start - t.end <= MOVE_YEARS
                             for h in here for t in there)
                alongside = any(min(h.end, t.end) - max(h.start, t.start) > 1 for h in here for t in there)
                total += link * (MOVE_BONUS if direct else SIDE_PROJECT if alongside else 1.0)
            return total

        # A band's standing (how many Wikipedias cover it) scales its link, damped
        # so lineage still beats fame: Nirvana (106) over No Use for a Name (22)
        # for the Foo Fighters, but Scream (17), which fed straight into them,
        # isn't swamped. Relative to the family's median; unknown is neutral.
        known = sorted(b.standing for b in bands.values() if b.standing is not None)
        median = known[len(known) // 2] if known else None

        def standing(band):
            if band.standing is None or median is None:
                return 1.0
            return min(STANDING_MAX, max(STANDING_MIN, ((band.standing + 1) / (median + 1)) ** STANDING_POWER))

        rest = [b for b in bands.values() if b.id not in chosen]
        for level in sorted({b.level for b in rest}):
            candidates = [(strength(b) * standing(b), b) for b in rest if b.level == level]
            candidates = [c for c in candidates if c[0] > 0]
            candidates.sort(key=lambda c: (-c[0], c[1].start, c[1].name))
            for _, b in candidates:
                if len(chosen) >= self.max_bands:
                    return chosen
                chosen[b.id] = b
                add(b)
        return chosen


def _anchors(membership, band_name):
    """A member whose undated membership may still span the band's life: a
    founder, or the one the band is named after."""
    if "original" in [(a or "").lower() for a in membership.get("attributes") or []]:
        return True
    name = (membership.get("person_name") or "").lower()
    surname = name.split()[-1] if name.split() else ""
    band = band_name.lower()
    return bool(name) and (name in band or (len(surname) > 3 and surname in band.split()))


def default_title(root_name):
    name = (root_name or "").upper()
    if name.startswith("THE "):
        return f"THE {name[4:]} FAMILY TREE"
    return f"THE {name} FAMILY TREE"
