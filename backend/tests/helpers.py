def band(mbid, name, begin, end, members, type_="Group"):
    """members: (person_id, name, begin, end, attributes)"""
    return {
        "mbid": mbid, "name": name, "type": type_, "disambiguation": "",
        "begin": begin, "end": end, "ended": end is not None,
        "memberships": [
            {"person_id": p, "person_name": n, "band_id": mbid, "band_name": name,
             "begin": b, "end": e, "ended": e is not None, "attributes": a}
            for p, n, b, e, a in members
        ],
    }


def person(mbid, name, bands, died=None):
    return {
        "mbid": mbid, "name": name, "type": "Person", "disambiguation": "",
        "begin": None, "end": died, "ended": died is not None,
        "memberships": [dict(m) for b in bands for m in b["memberships"] if m["person_id"] == mbid],
    }


JOY_DIVISION = band("jd", "Joy Division", "1976", "1980-05-18", [
    ("ian", "Ian Curtis", "1976", "1980-05-18", ["lead vocals", "original"]),
    ("bernard", "Bernard Sumner", "1976", "1980-05-18", ["guitar"]),
    ("hooky", "Peter Hook", "1976", "1980-05-18", ["bass guitar"]),
    ("steve", "Stephen Morris", "1977-08", "1980-05-18", ["drums (drum set)"]),
    ("terry", "Terry Mason", "1976", "1977-08", ["drums (drum set)"]),
])
NEW_ORDER = band("no", "New Order", "1980-07", None, [
    ("bernard", "Bernard Sumner", "1980-07", None, ["lead vocals", "guitar"]),
    ("hooky", "Peter Hook", "1980-07", "2007-05", ["bass guitar"]),
    ("steve", "Stephen Morris", "1980-07", None, ["drums (drum set)"]),
    ("gillian", "Gillian Gilbert", "1980-10", "2001", ["keyboard"]),
    ("gillian", "Gillian Gilbert", "2011-10", None, ["keyboard"]),
    ("phil", "Phil Cunningham", "2001", None, ["guitar"]),
    ("tom", "Tom Chapman", "2011-10", None, ["bass guitar"]),
])
ELECTRONIC = band("el", "Electronic", "1988", "2000", [
    ("bernard", "Bernard Sumner", "1988", "2000", ["lead vocals", "guitar"]),
    ("johnny", "Johnny Marr", "1988", "2000", ["guitar"]),
])
THE_SMITHS = band("smiths", "The Smiths", "1982-05", "1987-08", [
    ("johnny", "Johnny Marr", "1982-05", "1987-08", ["guitar"]),
    ("morrissey", "Morrissey", "1982-05", "1987-08", ["lead vocals"]),
])
BANDS = [JOY_DIVISION, NEW_ORDER, ELECTRONIC, THE_SMITHS]


def records():
    out = {b["mbid"]: b for b in BANDS}
    names = {m["person_id"]: m["person_name"] for b in BANDS for m in b["memberships"]}
    for pid, name in names.items():
        out[pid] = person(pid, name, BANDS, died="1980-05-18" if pid == "ian" else None)
    return out
