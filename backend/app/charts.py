"""Wikipedia's band member charts, as a check on MusicBrainz (issue #7, stage 2).

Most well-known bands' Wikipedia articles (or their "List of ... members"
pages) carry a member chart: an EasyTimeline block with every member's
stints to the day and a colour per instrument. Where MusicBrainz is thin -
Tommy Bolin down as vocals, a membership dated to the year, members missing
- the chart is usually right. It's read from the wikitext, stored on the
band's record (Neo4j) beside the MusicBrainz memberships, never over them,
and applied when the line-ups are worked out (app/refiner.py), so either
source can be corrected on its own.

Facts (who played what, when) aren't copyright; the chart is used as data,
never reproduced.
"""
import html
import re
import unicodedata
from datetime import date

PARSER = "charts-7"  # stored with each chart: one read by an older parser is read again
MIN_DAYS = 30    # shorter than this is a stand-in or a slip (Blackmore "rejoined" 12-13 Aug 2026);
                 # Dale Crover's 43 days in Nirvana (a demo and shows, 1988) count
JOIN_DAYS = 31   # stints closer than this are one stint (a change of instrument, not a departure)


def find_timeline(wikitext):
    """The EasyTimeline source in an article's wikitext, or None."""
    if not wikitext:
        return None
    m = re.search(r"<timeline>(.*?)</timeline>", wikitext, re.S | re.I)
    if m:
        return m.group(1)
    i = wikitext.find("{{#tag:timeline")
    if i < 0:
        return None
    depth, j = 0, i
    while j < len(wikitext) - 1:  # to the matching }} (the block holds {{#time:...}} templates)
        pair = wikitext[j:j + 2]
        if pair == "{{":
            depth += 1
            j += 2
        elif pair == "}}":
            depth -= 1
            j += 2
            if depth == 0:
                return wikitext[i + len("{{#tag:timeline|"):j - 2]
        else:
            j += 1
    return None


def _fields(line):
    """'bar:Ian from:05/07/1969 till:end text:"Ian Gillan"' -> {bar, from, till, text}.
    A text may be unquoted and run to the next key (Whitesnake's chart:
    'text:David Coverdale'), else it's cut to "David" and matches no one."""
    out = {}
    for key, quoted, plain in re.findall(r'(\w+):\s*(?:"([^"]*)"|(\S*))', line):
        out[key.lower()] = quoted if quoted else plain
    unquoted = re.search(r'\btext:\s*(?!")(.+?)(?=\s+\w+:|$)', line)
    if unquoted:
        out["text"] = unquoted.group(1).strip()
    return out


def _date(s, fmt, period, today):
    """A chart date as a date, or None for an open end."""
    s = (s or "").strip()
    if s in ("start", ""):
        return period[0] if s == "start" else None
    if s == "end":
        return period[1]
    if "{{" in s:  # {{#time:d/m/Y}}, today
        return None
    try:
        if fmt == "x.y" or re.fullmatch(r"\d{4}(\.\d+)?", s):
            y = float(s)
            year = int(y)
            day = int(round((y - year) * 365))
            return date(year, 1, 1).fromordinal(date(year, 1, 1).toordinal() + min(day, 364))
        a, b, c = (int(p) for p in re.split(r"[/.-]", s))
        if fmt.startswith("mm"):
            return date(c, a, b)
        if fmt.startswith("yyyy"):
            return date(a, b, c)
        return date(c, b, a)
    except (ValueError, TypeError):
        return None


def parse_timeline(source, today=None):
    """{bar id: {"name", "periods": [(start date, end date or None, role, principal)]}}
    from EasyTimeline source. An end of None is still going."""
    today = today or date.today()
    defines = {}
    section, fmt, period = None, "dd/mm/yyyy", [None, None]
    roles, bars, plots = {}, {}, []
    colour, width, default_width = None, None, None
    for raw in source.splitlines():
        line = raw.split("#", 1)[0].strip() if not raw.strip().startswith("#") else ""
        for k, v in defines.items():
            line = line.replace(k, v)
        if not line:
            continue
        head = re.match(r"(\w+)\s*=\s*(.*)", line)
        if head and ":" not in head.group(1):
            key, rest = head.group(1).lower(), head.group(2)
            if key == "define":
                d = re.match(r"(\$\w+)\s*=\s*(.*)", rest)
                if d:
                    defines[d.group(1)] = d.group(2).strip()
                continue
            section = key
            if key == "dateformat":
                fmt = rest.strip().lower()
            elif key == "period":
                f = _fields(rest)
                period = [_date(f.get("from"), fmt, [None, None], today), _date(f.get("till"), fmt, [None, None], today)]
            line = rest.strip()
            if not line:
                continue
        f = _fields(line)
        if section == "colors" and "id" in f and "legend" in f:
            roles[f["id"].lower()] = f["legend"].replace("_", " ").strip().lower()  # "bass, occasional vocals"
        elif section == "bardata" and "bar" in f:
            name = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", f.get("text") or f["bar"])
            bars[f["bar"]] = _clean_name(name)
        elif section == "plotdata":
            if "width" in f and "bar" not in f and default_width is None:
                default_width = _num(f["width"])
            if "bar" not in f:  # a line of defaults for the lines below
                colour = f.get("color", colour)
                width = _num(f["width"]) if "width" in f else (width if "color" not in f else None)
                continue
            if "from" not in f:
                continue
            plots.append((f["bar"], f.get("from"), f.get("till"), f.get("color", colour),
                          _num(f["width"]) if "width" in f else width))
    out = {}
    for bar, start, end, col, w in plots:
        role = roles.get((col or "").lower())  # colour names aren't case-sensitive (Episode Six: "Bass", "bass")
        if not _instrument(role):  # a band-era bar (Gillan's chart), touring or session work, releases
            continue
        s, e = _date(start, fmt, period, today), _date(end, fmt, period, today)
        if s is None or (e is not None and e <= s):
            continue
        principal = w is None or default_width is None or w >= default_width
        out.setdefault(bar, {"name": bars.get(bar) or _clean_name(bar.replace("_", " ")), "periods": []})["periods"].append((s, e, role, principal))
    return out


def _clean_name(name):
    """'Rod&nbsp;Evans', 'Craig Gruber †', bold markup -> the plain name."""
    name = html.unescape(re.sub(r"<[^>]+>|'{2,3}", "", name)).replace("\xa0", " ")
    name = re.sub(r"[†‡*]|\((?:died|d\.)[^)]*\)", "", name)
    return re.sub(r"\s+", " ", name).strip()


NOT_MEMBERSHIP = re.compile(r"touring|session|live|album|release|single|\bband\b|\bera\b|\bbars?\b")


def _instrument(role):
    """Whether a chart colour is an instrument played as a member: not the
    band's own era bars, touring or session work, or record releases (Black
    Sabbath's chart has touring and session colours, Gillan's band-era bars)."""
    from app.refiner import ROLE_WORDS  # the refiner imports this module
    return bool(role) and not NOT_MEMBERSHIP.search(role) and any(key in role for key, _ in ROLE_WORDS)


def _num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def chart_members(source, today=None):
    """The chart as members: [{"name", "stints": [{"begin", "end", "roles"}]}],
    dates ISO, end None while still going; roles principal first, then by time
    spent. Guest spots and slips shorter than MIN_DAYS are left out."""
    today = today or date.today()
    members = []
    for bar, m in parse_timeline(source, today).items():
        spans = sorted((s, e or today) for s, e, _, _ in m["periods"])
        merged = []
        for s, e in spans:
            if merged and (s - merged[-1][1]).days <= JOIN_DAYS:
                merged[-1][1] = max(merged[-1][1], e)
            else:
                merged.append([s, e])
        stints = []
        for s, e in merged:
            if (e - s).days < MIN_DAYS:
                continue
            weight = {}
            for ps, pe, role, principal in m["periods"]:
                overlap = (min(pe or today, e) - max(ps, s)).days
                if overlap > 0:
                    weight[role] = max(weight.get(role, 0), overlap + (100000 if principal else 0))
            open_ = any(pe is None and ps < e for ps, pe, _, _ in m["periods"]) and e >= today
            stints.append({"begin": s.isoformat(), "end": None if open_ else e.isoformat(),
                           "roles": _split(sorted(weight, key=lambda r: -weight[r]))})
        # a member with only stand-in spells is still the chart's: MusicBrainz's
        # dates for them (Crover in Nirvana, 1987 and 1990) mustn't come back
        members.append({"name": m["name"], "stints": stints})
    return members


def _split(legends):
    """One instrument per entry: "Bass, occasional vocals" is bass, then vocals
    (else "vocals" matches first and Krist Novoselic is the singer)."""
    out = []
    for legend in legends:
        for part in re.split(r",|/| and |&", legend):
            part = re.sub(r"^(occasional|additional|some)\s+", "", part.strip())
            if part and part not in out:
                out.append(part)
    return out


def name_key(name):
    """'Ronnie James Dio' / 'ronnie james dio' / 'Rönnie  James Dio' -> 'ronniejamesdio'."""
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


def apply_chart(memberships, chart, band_id, band_name, band_begin=None):
    """A band's memberships with the chart's in place of MusicBrainz's for
    every member the chart has: the chart's stints, dates and instruments.
    A chart member MusicBrainz lacks joins under a 'wiki:' id; MusicBrainz's
    members the chart doesn't have are kept as they are."""
    if not chart:
        return memberships
    mine = [m for m in memberships if m["band_id"] == band_id]
    others = [m for m in memberships if m["band_id"] != band_id]
    by_name = {}
    for m in mine:
        by_name.setdefault(name_key(m["person_name"]), []).append(m)
    first = min((s["begin"] for c in chart for s in c["stints"]), default=None)
    out, used = [], set()
    for c in chart:
        key = name_key(c["name"])
        mb = by_name.get(key) or _by_surname(by_name, c["name"])
        if mb:
            used.update(id(m) for m in mb)
        pid = mb[0]["person_id"] if mb else f"wiki:{key}"
        pname = mb[0]["person_name"] if mb else c["name"]
        founder = any("original" in [(a or "").lower() for a in m.get("attributes") or []] for m in mb or [])
        for s in c["stints"]:
            attrs = list(s["roles"])
            if founder or s["begin"] == first:
                attrs.append("original")
            out.append({"person_id": pid, "person_name": pname, "band_id": band_id, "band_name": band_name,
                        "begin": s["begin"], "end": s["end"], "ended": s["end"] is not None,
                        "attributes": attrs, "source": "wikipedia"})
    # MusicBrainz's word for anyone the chart doesn't name - unless they're dated
    # within the chart's own years, where the chart is the authority on who was a
    # member (Joey Waronker, Oasis's touring drummer in 2025); or the band is named
    # after them (Johnny Kidd)
    span = (min((s["begin"] for c in chart for s in c["stints"]), default=None),
            max(((s["end"] or "9999") for c in chart for s in c["stints"]), default=None))
    for m in mine:
        if id(m) in used:
            continue
        within = m.get("begin") and span[0] and span[0][:4] <= m["begin"][:4] <= span[1][:4]
        eponymous = "eponymous" in [(a or "").lower() for a in m.get("attributes") or []]
        if not within or eponymous:
            out.append(m)
    return out + others


def _by_surname(by_name, name):
    """MusicBrainz's entry for a chart name that differs in a middle name or a
    short form of the first ('Joe Lynn Turner' / 'Joe Turner', 'Bobby' / 'Bob
    Rondinelli', 'Rich' / 'Richard Williams'): the same surname, and first
    names where one starts the other (or the first three letters agree)."""
    parts = re.sub(r'"[^"]*"', " ", name).split()  # 'Larry "Rhino" Reinhardt'
    if len(parts) < 2:
        return None
    first, last = name_key(parts[0]), name_key(parts[-1])

    def same_first(a):
        return a.startswith(first) or first.startswith(a) or (len(a) >= 3 and a[:3] == first[:3])

    hits = [ms for key, ms in by_name.items()
            if ms and len(ms[0]["person_name"].split()) >= 2
            and name_key(ms[0]["person_name"].split()[-1]) == last
            and same_first(name_key(ms[0]["person_name"].split()[0]))]
    return hits[0] if len(hits) == 1 else None
