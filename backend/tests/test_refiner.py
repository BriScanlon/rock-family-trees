from app.refiner import Refiner, default_title

from helpers import records


def build(**kw):
    harvest = {"root_id": "jd", "root_name": "Joy Division", "root_bands": ["jd"],
               "band_levels": {"jd": 0, "no": 1, "el": 1, "smiths": 2}, "records": records()}
    return Refiner(today=2026.5, **kw).build(harvest)


def names(lineup):
    return [m.name for m in lineup.members]


def test_joy_division_lineups():
    jd = build().bands["jd"]
    assert [lu.number for lu in jd.lineups] == [1, 2]
    assert "Terry Mason" in names(jd.lineups[0]) and "Stephen Morris" not in names(jd.lineups[0])
    assert "Stephen Morris" in names(jd.lineups[1])
    assert jd.lineups[1].end_label == "May 80"
    assert jd.lineups[0].members[0].roles == ["vocals"]


def test_rejoining_member_and_ongoing_band():
    no = build().bands["no"]
    with_gillian = [lu.number for lu in no.lineups if "Gillian Gilbert" in names(lu)]
    assert len(with_gillian) >= 2 and with_gillian != list(range(with_gillian[0], with_gillian[-1] + 1))
    assert no.lineups[-1].ongoing and no.lineups[-1].end_label == "present"


def test_selection_respects_max_bands_and_connectivity():
    tree = build(max_bands=3)
    assert list(tree.bands)[0] == "jd"
    assert len(tree.bands) == 3
    assert "smiths" not in tree.bands  # only reachable via Electronic, at a deeper level
    assert "smiths" in build().bands


def test_deaths_recorded():
    tree = build()
    assert tree.people["ian"].died_label == "May 80"


def test_titles():
    assert default_title("The Yardbirds") == "THE YARDBIRDS FAMILY TREE"
    assert default_title("Cream") == "THE CREAM FAMILY TREE"


def test_the_main_instrument_comes_first():
    from app.refiner import role_words
    assert role_words(["harmonica", "lead vocals", "percussion"])[0] == "vocals"  # Ian Gillan
    assert role_words(["percussion", "drums (drum set)"])[0] == "drums"
    assert role_words(["electric guitar", "background vocals"]) == ["guitar"]
    assert role_words(["bass guitar", "lead vocals"])[0] == "bass"  # Glenn Hughes: a bassist who sings


def _rainbow_like():
    from tests.helpers import band, person
    rb = band("rb", "Rainbow", "1975", None, [
        ("rb_g", "Ritchie Blackmore", "1975", "1984", ["guitar", "original"]),
        ("dio", "Ronnie James Dio", "1975", "1978", []),              # no instrument here...
        ("stone", "David Stone", None, None, []),                      # no dates at all
        ("dw", "Doogie White", "1994", None, ["lead vocals"])])
    sab = band("bs", "Black Sabbath", "1968", None, [
        ("dio", "Ronnie James Dio", "1979", "1982", ["lead vocals"]),  # ...but here
        ("ti", "Tony Iommi", "1968", None, ["guitar"])])
    mi5 = band("mi5", "M I 5", "1966", None, [                         # no end date, nothing open
        ("rod", "Rod Evans", "1966", "1967", ["lead vocals"]), ("ip", "Ian Paice", "1966", "1967", ["drums"])])
    maze = band("maze", "The Maze", "1967", "1968", [
        ("rod", "Rod Evans", "1967", "1968", ["lead vocals"]), ("ip", "Ian Paice", "1967", "1968", ["drums"])])
    gillan = band("gl", "Gillan", "1978", "1982", [
        ("ig", "Ian Gillan", None, None, ["lead vocals"]),              # undated, but it's his band
        ("jm", "John McCoy", "1978", "1982", ["bass"])])
    bands = [rb, sab, mi5, maze, gillan]
    names = {m["person_id"]: m["person_name"] for b in bands for m in b["memberships"]}
    records = {b["mbid"]: b for b in bands} | {p: person(p, n, bands) for p, n in names.items()}
    harvest = {"root_id": "rb", "root_name": "Rainbow", "root_bands": ["rb", "bs", "mi5", "maze", "gl"],
               "band_levels": {"rb": 0, "bs": 1, "mi5": 1, "maze": 1, "gl": 1}, "records": records}
    from app.refiner import Refiner
    return Refiner(today=2026.5, max_bands=10).build(harvest), records


def test_an_undated_member_does_not_fill_the_bands_life():
    # David Stone had no dates in MusicBrainz and turned up in every Rainbow
    # line-up from 1974 to now, hiding the 1984-94 break
    from app.refiner import Refiner
    tree, _ = _rainbow_like()
    rb = tree.bands["rb"]
    assert all("David Stone" not in [m.name for m in lu.members] for lu in rb.lineups)
    assert rb.undated == ["David Stone"]
    assert any(lu.after_gap for lu in rb.lineups)  # the break shows: split, then re-formed


def test_an_undated_member_the_band_is_named_after_stays():
    tree, _ = _rainbow_like()
    assert all("Ian Gillan" in [m.name for m in lu.members] for lu in tree.bands["gl"].lineups)


def test_a_missing_instrument_is_borrowed_from_another_membership():
    tree, _ = _rainbow_like()
    dio = next(s for s in tree.bands["rb"].stints if s.name == "Ronnie James Dio")
    assert dio.roles == ["vocals"]


def test_a_band_is_only_still_going_if_a_dated_membership_is_open():
    tree, _ = _rainbow_like()
    assert tree.bands["mi5"].ended and tree.bands["mi5"].end < 1970  # MI5, 1966-67, had no end date
    assert not tree.bands["rb"].ended  # Doogie White's membership is still open


def test_undated_members_stay_when_most_of_the_band_is_undated():
    # MI5: only Ian Paice has dates; dropping the other four left a one-man band
    from tests.helpers import band, person
    from app.refiner import Refiner
    mi5 = band("mi5", "M I 5", "1966", "1967", [("ip", "Ian Paice", "1966", "1967", ["drums"])] +
               [(p, n, None, None, []) for p, n in (("rod", "Rod Evans"), ("rl", "Roger Lewis"),
                                                     ("jk", "Jack Keene"), ("cb", "Chris Banham"))])
    records = {"mi5": mi5, **{m["person_id"]: person(m["person_id"], m["person_name"], [mi5]) for m in mi5["memberships"]}}
    tree = Refiner(today=2026.5).build({"root_id": "mi5", "root_name": "M I 5", "root_bands": ["mi5"],
                                        "band_levels": {"mi5": 0}, "records": records})
    assert len(tree.bands["mi5"].lineups[0].members) == 5 and tree.bands["mi5"].undated == []


def test_a_secondary_role_alone_takes_the_musicians_principal_instrument():
    from app.refiner import Refiner
    band = lambda mbid, name: {"mbid": mbid, "name": name, "type": "Group", "begin": "1991", "end": None, "ended": False}
    m = lambda pid, name, bid, bname, attrs, begin="1991", end=None: {
        "person_id": pid, "person_name": name, "band_id": bid, "band_name": bname,
        "begin": begin, "end": end, "ended": end is not None, "attributes": attrs}
    oasis = dict(band("o", "Oasis"), memberships=[
        m("liam", "Liam Gallagher", "o", "Oasis", ["original", "tambourine"], "1991", "2009"),
        m("noel", "Noel Gallagher", "o", "Oasis", ["background vocals"], "1991", "2009"),
        m("noel", "Noel Gallagher", "o", "Oasis", ["guitar"], "2025"),
        m("joey", "Joey Waronker", "o", "Oasis", ["drums", "touring"], "2025")])
    beady = dict(band("b", "Beady Eye"), memberships=[m("liam", "Liam Gallagher", "b", "Beady Eye", ["lead vocals"], "2009", "2014")])
    harvest = {"root_id": "o", "root_name": "Oasis", "root_bands": ["o"], "band_levels": {"o": 0, "b": 1},
               "records": {"o": oasis, "b": beady}}
    tree = Refiner(today=2026.7).build(harvest)
    roles = {s.name: s.roles[0] for s in tree.bands["o"].stints if s.start < 2000}
    assert roles == {"Liam Gallagher": "vocals", "Noel Gallagher": "guitar"}
    assert "Joey Waronker" not in {s.name for s in tree.bands["o"].stints}  # touring: not a member


def test_a_brief_absence_does_not_draw_the_line_up_twice():
    from app.refiner import Refiner
    m = lambda pid, name, attrs, begin, end=None: {
        "person_id": pid, "person_name": name, "band_id": "o", "band_name": "Oasis",
        "begin": begin, "end": end, "ended": end is not None, "attributes": attrs}
    oasis = {"mbid": "o", "name": "Oasis", "type": "Group", "begin": "1991", "end": "2009", "ended": True,
             "memberships": [m("liam", "Liam Gallagher", ["lead vocals"], "1991-06", "2009-08"),
                             m("guigsy", "Paul McGuigan", ["bass"], "1991-06", "1995-09"),
                             m("guigsy", "Paul McGuigan", ["bass"], "1995-11", "1999-08"),
                             m("gem", "Gem Archer", ["guitar"], "1999-11", "2009-08")]}
    harvest = {"root_id": "o", "root_name": "Oasis", "root_bands": ["o"], "band_levels": {"o": 0}, "records": {"o": oasis}}
    lineups = Refiner(today=2026.7).build(harvest).bands["o"].lineups
    sets = [tuple(m.person_id for m in lu.members) for lu in lineups]
    assert all(a != b for a, b in zip(sets, sets[1:])), sets  # never the same line-up twice in a row


def test_a_one_off_concert_leads_nowhere():
    """Noel Gallagher played one night with Mick Fleetwood and Friends: that
    gig can be on the Oasis tree, but Fleetwood Mac and The Who can't come
    in through it."""
    from app.refiner import Refiner, one_off
    rec = lambda mbid, name, begin, end, ms: {"mbid": mbid, "name": name, "type": "Group", "begin": begin,
                                              "end": end, "ended": end is not None, "memberships": ms}
    m = lambda pid, name, bid, bname, begin, end: {"person_id": pid, "person_name": name, "band_id": bid,
                                                   "band_name": bname, "begin": begin, "end": end,
                                                   "ended": end is not None, "attributes": ["guitar"]}
    oasis = rec("o", "Oasis", "1991", "2009", [m("noel", "Noel Gallagher", "o", "Oasis", "1991", "2009")])
    gig = rec("g", "Mick Fleetwood and Friends", "2020-02-25", "2020-02-25",
              [m("noel", "Noel Gallagher", "g", "MFaF", "2020-02-25", "2020-02-25"),
               m("mick", "Mick Fleetwood", "g", "MFaF", "2020-02-25", "2020-02-25")])
    fmac = rec("f", "Fleetwood Mac", "1967", None, [m("mick", "Mick Fleetwood", "f", "Fleetwood Mac", "1967", None)])
    assert one_off(gig) and not one_off(oasis) and not one_off(fmac)
    harvest = {"root_id": "o", "root_name": "Oasis", "root_bands": ["o"], "band_levels": {"o": 0, "g": 1, "f": 2},
               "records": {"o": oasis, "g": gig, "f": fmac}}
    chosen = set(Refiner(today=2026.7).build(harvest).bands)
    assert "g" in chosen and "f" not in chosen
