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
import re
import unicodedata
from datetime import date

PARSER = "charts-2"  # stored with each chart: one read by an older parser is read again
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
    """'bar:Ian from:05/07/1969 till:end text:"Ian Gillan"' -> {bar, from, till, text}."""
    out = {}
    for key, quoted, plain in re.findall(r'(\w+):\s*(?:"([^"]*)"|(\S*))', line):
        out[key.lower()] = quoted if quoted else plain
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
            roles[f["id"]] = f["legend"].replace("_", " ").strip().lower()  # "bass, occasional vocals"
        elif section == "bardata" and "bar" in f:
            name = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", f.get("text") or f["bar"])
            bars[f["bar"]] = re.sub(r"<[^>]+>|'''?", "", name).strip()
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
        role = roles.get(col)
        if not role or role in ("studio album", "studio albums", "bars", "album"):
            continue
        s, e = _date(start, fmt, period, today), _date(end, fmt, period, today)
        if s is None or (e is not None and e <= s):
            continue
        principal = w is None or default_width is None or w >= default_width
        out.setdefault(bar, {"name": bars.get(bar, bar), "periods": []})["periods"].append((s, e, role, principal))
    return out


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
    out += [m for m in mine if id(m) not in used]  # MusicBrainz's word for anyone the chart doesn't name
    return out + others


def _by_surname(by_name, name):
    """MusicBrainz's entry for a chart name that differs only in a middle name
    or initial ('Joe Lynn Turner' / 'Joe Turner'): same first and last word."""
    words = name_key(" ".join(name.split()[:1])), name_key(" ".join(name.split()[-1:]))
    hits = [ms for key, ms in by_name.items()
            if ms and name_key(ms[0]["person_name"].split()[0]) == words[0]
            and name_key(ms[0]["person_name"].split()[-1]) == words[1]]
    return hits[0] if len(hits) == 1 else None
