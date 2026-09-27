import re
import xml.etree.ElementTree as ET

import pytest

from app.artist import Artist
from app.cartographer import Cartographer
from app.pipeline import harvester_for
from app.refiner import Refiner


@pytest.fixture(scope="module")
def layout():
    harvest = harvester_for("demo:yardbirds").harvest("demo:yardbirds", depth=4)
    tree = Refiner(today=2026.5).build(harvest)
    return Cartographer(tree, paper="auto").layout()


def test_boxes_in_a_lane_never_overlap(layout):
    by_lane = {}
    for b in layout["boxes"]:
        by_lane.setdefault(b["lane"], []).append(b)
    for boxes in by_lane.values():
        boxes.sort(key=lambda b: b["y"])
        for a, b in zip(boxes, boxes[1:]):
            assert a["y"] + a["footprint"] <= b["y"], (a["id"], b["id"])


def test_every_move_goes_down_the_page(layout):
    # (time down each band: test_time_runs_down_every_band; the user dropped time down every column)
    by_id = {b["id"]: b for b in layout["boxes"]}
    for e in layout["edges"]:
        a, b = by_id[e["from"]], by_id[e["to"]]
        if a["lane"] != b["lane"]:
            assert b["y"] > a["y"] + a["footprint"], (e["from"], e["to"])


def test_timeline_mode_keeps_a_strict_time_grid():
    harvest = harvester_for("demo:yardbirds").harvest("demo:yardbirds", depth=4)
    L = Cartographer(Refiner(today=2026.5).build(harvest), timeline=True).layout()
    boxes = sorted(L["boxes"], key=lambda b: b["start"])
    for a, b in zip(boxes, boxes[1:]):
        if round(a["start"] * 12) < round(b["start"] * 12):
            assert a["y"] < b["y"]


def test_text_is_readable_in_print(layout):
    # The Cartographer draws everything it is given (fitting.py does the trimming),
    # so check the paper choice on a family that fits, and a single band.
    family = Cartographer(Refiner(today=2026.5).build(
        harvester_for("demo:yardbirds").harvest("demo:yardbirds", depth=2)), paper="auto").layout()
    assert family["stats"]["paper"] == "A1" and family["stats"]["smallest_text_pt"] >= 6.5
    small = Cartographer(Refiner(today=2026.5).build(
        harvester_for("demo:yardbirds").harvest("demo:yardbirds", depth=1)), paper="auto").layout()
    assert small["stats"]["paper"] in ("A3", "A2") and small["stats"]["smallest_text_pt"] >= 6.5


def test_everything_fits_on_the_paper(layout):
    W, H = layout["width"], layout["height"]
    assert abs(max(W, H) / min(W, H) - 2 ** 0.5) < 0.01
    for b in layout["boxes"]:
        assert 0 < b["x"] and b["x"] + b["w"] < W
        assert 0 < b["y"] and b["y"] + b["footprint"] < layout["footer_y"]


def test_member_moves_are_routed(layout):
    moves = {(e["person_id"].split(":")[-1], e["from"].split("#")[0].split(":")[-1], e["to"].split("#")[0].split(":")[-1])
             for e in layout["edges"]}
    assert ("jimmy-page", "yardbirds", "led-zeppelin") in moves
    assert ("eric-clapton", "cream", "blind-faith") in moves
    for e in layout["edges"]:
        assert len(e["points"]) >= 4


def test_frame_style_notes(layout):
    notes = [" ".join(b["notes"]) for b in layout["boxes"]]
    assert any("Eric Clapton left to join John Mayall's Bluesbreakers." in n for n in notes)
    assert any("Keith Relf died in May 1976." in n for n in notes)
    assert any(n.startswith("Split in") for n in notes)
    assert all(len(b["dates"]) == 2 for b in layout["boxes"])  # stacked beside the band name


def test_members_hang_side_by_side(layout):
    yb = next(b for b in layout["boxes"] if b["band_name"] == "The Yardbirds" and b["number"] == 1)
    assert [m["lines"] for m in yb["members"]][:2] == [["KEITH", "RELF"], ["CHRIS", "DREJA"]]
    assert yb["members"][0]["roles"] == ["vocals"]  # one instrument each, as Frame writes them
    xs = [m["cx"] for m in yb["members"]]
    assert xs == sorted(xs) and len(set(xs)) == len(xs)


def test_replacement_takes_the_vacated_column(layout):
    yb = {b["number"]: b for b in layout["boxes"] if b["band_name"] == "The Yardbirds"}
    col = lambda n, who: next(m["col"] for m in yb[n]["members"] if who in m["person_id"])
    assert col(1, "top-topham") == col(2, "eric-clapton") == col(3, "jeff-beck")
    assert col(1, "keith-relf") == col(5, "keith-relf")


def test_each_musician_line_runs_down_to_the_next_lineup(layout):
    boxes = {b["id"]: b for b in layout["boxes"]}
    yb1, yb2 = boxes["demo:yardbirds#1"], boxes["demo:yardbirds#2"]
    relf = [t for t in layout["trunks"] if t["person_id"].endswith("keith-relf")
            and t["points"][0][1] < yb2["y"] and t["points"][-1][1] == yb2["bar_y"]]
    assert relf and relf[0]["points"][0][1] >= yb1["bar_y"]


def test_svg_is_valid_and_self_contained(layout, tmp_path):
    svg = Artist(layout, str(tmp_path / "t.svg")).render()
    root = ET.fromstring(svg)
    assert root.tag.endswith("svg") and {root.get("width"), root.get("height")} == {"841mm", "1189mm"}  # A0
    assert "@font-face" in svg and "http" not in svg.replace("http://www.w3.org/2000/svg", "")
    assert "THE YARDBIRDS FAMILY TREE" in svg


def test_default_style_is_ink_on_white(layout):
    svg = Artist(layout).render()
    assert 'fill="#ffffff"' in svg
    assert 'filter="url(#rough)"' not in svg and 'url(#paper)' not in svg
    assert "font-family:'Architects Daughter'" in svg
    assert ">SAMWELL-SMITH<" in svg  # surname lettered under the first name
    assert svg.count("<rect") == 2  # background and border only: line-ups are not boxed


def test_optional_extras(layout):
    svg = Artist(dict(layout, timeline=True), hand_drawn=True, aged_paper=True).render()
    assert 'filter="url(#rough)"' in svg and 'url(#paper)' in svg and ">1965<" in svg


def test_lettering_styles():
    from app.fonts import lettering_for
    assert lettering_for(["heavy metal", "hard rock"]) == "heavy"
    assert lettering_for(["blues rock", "british rhythm & blues"]) == "classic"
    assert lettering_for([]) == "classic"
    harvest = harvester_for("demo:yardbirds").harvest("demo:yardbirds", depth=2)
    tree = Refiner(today=2026.5).build(harvest)
    heavy = Artist(Cartographer(tree, lettering="heavy").layout()).render()
    classic = Artist(Cartographer(tree, lettering="classic").layout()).render()
    assert "font-family:'Amatic SC'" in heavy and "font-family:'Amatic SC'" not in classic


def test_line_ups_never_overlap(layout):
    # each column keeps its own pace (the user chose that over rows level
    # across the page), but no two blocks may share any of the page
    boxes = layout["boxes"]
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            assert not (a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"] and
                        a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"]), (a["id"], b["id"])


def test_every_member_takes_one_slot(layout):
    # one equal slot each; a block stretched into free space beside it
    # spreads them evenly, never narrower than a slot
    for b in layout["boxes"]:
        slot = b["w"] / b["span"]
        assert slot >= layout["lettering"]["col_w"] - 1e-6
        xs = sorted(m["cx"] for m in b["members"])
        assert all(abs((x - b["x"] - slot / 2) / slot - round((x - b["x"] - slot / 2) / slot)) < 1e-6 for x in xs)
        assert len(set(xs)) == len(xs) and xs[-1] < b["x"] + b["w"]


def test_notes_sit_under_the_band_name(layout):
    from app.grid import NOTE_LINES
    for b in layout["boxes"]:
        assert b["y"] < b["notes_y"] < b["bar_y"] and len(b["notes"]) <= NOTE_LINES


def test_time_runs_down_every_band(layout):
    # the user chose a fuller page over time down every column: each band's
    # line-ups still run down in order (and every move goes down, below)
    by_band = {}
    for b in layout["boxes"]:
        by_band.setdefault(b["band_id"], []).append(b)
    for boxes in by_band.values():
        boxes.sort(key=lambda b: b["start"])
        for a, b in zip(boxes, boxes[1:]):
            assert a["y"] + a["h"] <= b["y"], (a["id"], b["id"])


def test_every_move_goes_down(layout):
    by_id = {b["id"]: b for b in layout["boxes"]}
    for e in layout["edges"]:
        assert by_id[e["to"]]["y"] >= by_id[e["from"]]["y"] + by_id[e["from"]]["h"], (e["from"], e["to"])


@pytest.mark.parametrize("root,depth", [("demo:yardbirds", 4), ("demo:acdc", 3)])
def test_musicians_lines_never_run_through_another_lineup(root, depth):
    tree = Refiner(today=2026.5).build(harvester_for(root).harvest(root, depth=depth))
    L = Cartographer(tree, paper="auto").layout()
    for t in L["trunks"]:
        for (x1, y1), (x2, y2) in zip(t["points"], t["points"][1:]):
            if x1 != x2:
                continue  # only the long vertical runs can cross a line-up
            lo, hi = sorted((y1, y2))
            for b in L["boxes"]:
                inside_x = b["x"] < x1 < b["x"] + b["w"]
                inside_y = lo < b["y"] + 4 and b["y"] + b["footprint"] - 4 < hi
                assert not (inside_x and inside_y), (t["person_id"], b["id"])


def test_a_reformed_band_is_not_joined_through_the_band_below_it():
    # Split-and-re-formed band X, with Y (sharing a member) between its two
    # runs; the line from X's first run to its second must be routed round
    # Y, not drawn straight down through it.
    from tests.helpers import band, person
    x = band("x", "Band X", "1970", "1982", [
        ("ann", "Ann", "1970", "1972", ["lead vocals"]), ("bob", "Bob", "1970", "1972", ["guitar"]),
        ("ann", "Ann", "1980", "1982", ["lead vocals"]), ("bob", "Bob", "1980", "1982", ["guitar"])])
    y = band("y", "Band Y", "1974", "1976", [
        ("ann", "Ann", "1974", "1976", ["lead vocals"]), ("cy", "Cy", "1974", "1976", ["drums"])])
    records = {"x": x, "y": y, **{p: person(p, n, [x, y]) for p, n in (("ann", "Ann"), ("bob", "Bob"), ("cy", "Cy"))}}
    harvest = {"root_id": "x", "root_name": "Band X", "root_bands": ["x"],
               "band_levels": {"x": 0, "y": 1}, "records": records}
    L = Cartographer(Refiner(today=2026.5).build(harvest), paper="auto").layout()
    ys = {b["id"]: b for b in L["boxes"]}
    between = ys["y#1"]
    for t in L["trunks"]:
        lo, hi = sorted(p[1] for p in t["points"][:2])
        assert not (lo < between["y"] and between["y"] + between["footprint"] < hi), t["person_id"]
    assert any(e["from"].startswith("x#") and e["to"].startswith("x#") for e in L["edges"])


def test_folded_line_ups_are_told_under_the_members():
    # A band condensed to one line-up still names everyone who played in it:
    # "joined"/"left" under members, "then"/"after" for whoever held the same
    # place, anything else in the notes - never "Simplified to fit".
    from tests.helpers import band, person
    x = band("x", "Band X", "1990", "2000", [
        ("ann", "Ann Able", "1990", "2000", ["lead vocals"]),
        ("bob", "Bob Baker", "1990", "1995", ["drums (drum set)"]),
        ("cy", "Cy Cole", "1995", "1996", ["drums (drum set)"]),
        ("dee", "Dee Dunn", "1996", "2000", ["drums (drum set)"]),
        ("eve", "Eve East", "1997", "1998", ["trumpet"])])
    records = {"x": x, **{p: person(p, n, [x]) for p, n in (("ann", "Ann Able"), ("bob", "Bob Baker"),
                                                         ("cy", "Cy Cole"), ("dee", "Dee Dunn"), ("eve", "Eve East"))}}
    harvest = {"root_id": "x", "root_name": "Band X", "root_bands": ["x"], "band_levels": {"x": 0}, "records": records}
    tree = Refiner(today=2026.5, max_lineups_per_band=1).build(harvest)
    L = Cartographer(tree, paper="auto").layout()
    (b,) = L["boxes"]
    text = " ".join(r for m in b["members"] for r in m["roles"]) + " " + " ".join(b["notes"])
    names = " ".join(" ".join(m["lines"]) for m in b["members"]).upper()
    for who in ("Bob Baker", "Cy Cole", "Dee Dunn", "Eve East"):
        surname = who.split()[1]
        assert surname.upper() in names or surname in text, who
    assert "Simplified to fit" not in " ".join(b["notes"])


def test_a_year_only_date_still_finds_who_was_replaced():
    # MusicBrainz often knows only the year someone joined: "1997" must still
    # read as following a member who left in September 1997.
    from tests.helpers import band, person
    x = band("x", "Band X", "1995", "2000", [
        ("ann", "Ann Able", "1995", "2000", ["lead vocals"]),
        ("pat", "Pat Smear", "1995", "1997-09", ["guitar"]),
        ("fra", "Franz Stahl", "1997", "1999", ["guitar"])])
    records = {"x": x, **{p: person(p, n, [x]) for p, n in (("ann", "Ann Able"), ("pat", "Pat Smear"),
                                                         ("fra", "Franz Stahl"))}}
    harvest = {"root_id": "x", "root_name": "Band X", "root_bands": ["x"], "band_levels": {"x": 0}, "records": records}
    L = Cartographer(Refiner(today=2026.5, max_lineups_per_band=1).build(harvest), paper="auto").layout()
    marks = [r for b in L["boxes"] for m in b["members"] for r in m["roles"]]
    assert "then F. Stahl" in marks or "after P. Smear" in marks, marks


def test_someone_who_stays_on_is_not_listed_as_brief():
    # Pat Smear rejoined the Foo Fighters in 2010 and stayed: in a line-up
    # condensed over 1999-2017 that doesn't show him, he rejoined; he wasn't
    # there "briefly".
    from tests.helpers import band, person
    from app.grid import GridLayout
    from app.refiner import Lineup, LineupMember
    x = band("x", "Band X", "1995", None, [
        ("ann", "Ann Able", "1995", None, ["lead vocals"]),
        ("pat", "Pat Smear", "1995", "1997", ["guitar"]),
        ("pat", "Pat Smear", "2010", None, ["guitar"]),
        ("cy", "Cy Cole", "2001", "2003", ["keyboard"])])
    records = {"x": x, **{p: person(p, n, [x]) for p, n in (("ann", "Ann Able"), ("pat", "Pat Smear"),
                                                         ("cy", "Cy Cole"))}}
    harvest = {"root_id": "x", "root_name": "Band X", "root_bands": ["x"], "band_levels": {"x": 0}, "records": records}
    tree = Refiner(today=2026.5).build(harvest)
    folded = Lineup(number=2, start=1999.0, end=2017.0, start_label="1999", end_label="2017",
                    members=[LineupMember(person_id="ann", name="Ann Able", roles=["vocals"])], merged=3)
    _, notes = GridLayout(tree)._annotations(tree.bands["x"], folded)
    assert "Pat Smear rejoined in 2010." in notes, notes
    assert notes[-1] == "Briefly also: Cy Cole (keyboards).", notes


def test_renamings_and_unknown_dates_are_told():
    from tests.test_refiner import _rainbow_like
    tree, _ = _rainbow_like()
    L = Cartographer(tree, paper="auto").layout()
    notes = {b["id"]: " ".join(b["notes"]) for b in L["boxes"]}
    assert "Renamed The Maze in 1967." in " ".join(v for k, v in notes.items() if k.startswith("mi5#"))
    assert "Also, dates unknown: David Stone." in notes["rb#1"]


def test_a_briefly_also_list_is_kept_short():
    from tests.helpers import band, person
    from app.grid import BRIEF_NAMES, GridLayout
    from app.refiner import Lineup, LineupMember
    x = band("x", "Band X", "1980", None, [("a", "Ann Able", "1980", None, ["lead vocals"])] +
             [(f"p{i}", f"Player {i}", "1984", "1985", ["guitar"]) for i in range(9)])
    records = {"x": x, **{m["person_id"]: person(m["person_id"], m["person_name"], [x]) for m in x["memberships"]}}
    tree = Refiner(today=2026.5).build({"root_id": "x", "root_name": "Band X", "root_bands": ["x"],
                                        "band_levels": {"x": 0}, "records": records})
    folded = Lineup(number=1, start=1980.0, end=1990.0, start_label="1980", end_label="1990",
                    members=[LineupMember(person_id="a", name="Ann Able", roles=["vocals"])])
    _, notes = GridLayout(tree)._annotations(tree.bands["x"], folded)
    assert notes[-1].count("Player") == BRIEF_NAMES and notes[-1].endswith(f"and {9 - BRIEF_NAMES} others.")


def test_notes_from_wikipedia_land_on_their_line_up_first():
    harvest = harvester_for("demo:yardbirds").harvest("demo:yardbirds", depth=2)
    from app.fitting import fit_tree
    stories = {"demo:yardbirds": [{"date": "1965-03", "year": 1965.2,
                                   "text": "Clapton quit over the pop direction of their single"}]}
    tree, L, fit = fit_tree(harvest, paper="A1", stories=stories)
    yb = tree.bands["demo:yardbirds"]
    from app.narrative import lineup_for
    target = lineup_for(yb.lineups, 1965.2)
    box = next(b for b in L["boxes"] if b["id"] == f"demo:yardbirds#{target.number}")
    assert " ".join(box["notes"]).startswith("Clapton quit over the pop direction")
    others = [b for b in L["boxes"] if b["band_id"] == "demo:yardbirds" and b is not box]
    assert not any("Clapton quit" in " ".join(b["notes"]) for b in others)


def test_albums_go_with_the_line_up_that_made_them():
    harvest = harvester_for("demo:yardbirds").harvest("demo:yardbirds", depth=2)
    from app.fitting import fit_tree
    from app.grid import album_time
    from app.narrative import lineup_for
    albums = {"demo:yardbirds": ["1966-07-15 Roger the Engineer", "1967-07-24 Little Games"]}
    tree, L, fit = fit_tree(harvest, paper="A1", albums=albums)
    yb = tree.bands["demo:yardbirds"]
    for album in albums["demo:yardbirds"]:
        title = album.split(" ", 1)[1]
        target = lineup_for(yb.lineups, album_time(album))
        box = next(b for b in L["boxes"] if b["id"] == f"demo:yardbirds#{target.number}")
        assert title in " ".join(box["notes"]), title  # in the block of the line-up that made it
        others = [b for b in L["boxes"] if b["band_id"] == "demo:yardbirds" and b is not box]
        assert not any(title in " ".join(b["notes"]) for b in others)


def test_the_release_date_decides_the_line_up():
    from app.grid import album_time
    assert abs(album_time("1972-03-25 Machine Head") - 1972.23) < 0.01
    assert album_time("1966 Roger the Engineer") == 1966.5


def test_a_block_short_of_room_says_how_many_more_albums():
    from app.grid import _recorded
    many = [f"19{70 + i}-01-01 Album {i}" for i in range(6)]
    assert _recorded(many, 2) == "Recorded Album 0 (1970), Album 1 (1971) and 4 more."
    assert _recorded(many).count("(") == 6


def _overlaps(L):
    """Pairs of different musicians' lines lying on one another for more than a pixel."""
    segs = [(l["person_id"], (x1, y1), (x2, y2)) for l in L["edges"] + L["trunks"]
            for (x1, y1), (x2, y2) in zip(l["points"], l["points"][1:])]
    found = []
    for i, (p, a, b) in enumerate(segs):
        for q, c, d in segs[i + 1:]:
            if p == q:
                continue  # one musician's line forking to two line-ups
            for axis in (0, 1):  # vertical runs share x, horizontal runs share y
                o = 1 - axis
                if a[axis] == b[axis] == c[axis] == d[axis] and a[o] != b[o] and c[o] != d[o]:
                    if min(max(a[o], b[o]), max(c[o], d[o])) - max(min(a[o], b[o]), min(c[o], d[o])) > 1:
                        found.append((p, q))
    return found


@pytest.mark.parametrize("root,depth,paper", [("demo:yardbirds", 4, "A2"), ("demo:acdc", 3, "A2")])
def test_lines_never_lie_on_one_another(root, depth, paper):
    from app.fitting import fit_tree
    _, L, _ = fit_tree(harvester_for(root).harvest(root, depth=depth), paper=paper, max_bands=24)
    assert _overlaps(L) == []


def test_a_departure_track_sits_above_an_arrival_in_the_same_column():
    from app.grid import _Tracks
    t = _Tracks(13, 4)
    arrive = t.take("row", 0, 100, side=1, arrives=100)       # from the left, down into column 100
    leave = t.take("row", 100, 200, side=-1, leaves=100)      # from column 100, off to the right
    assert leave < arrive  # the leaving line's drop ends above where the arriving one's begins
    crowded = [t.take("row", 300, 400) for _ in range(len(t.offsets))]
    assert len(set(crowded)) == len(t.offsets)  # each run its own track while there are tracks


def test_info_notes_attach_to_the_band_and_time_they_belong_to():
    """Where a musician played off the poster, and a band's style, are notes
    in the line-ups (the user's instruction), not a panel of lists."""
    from app.fitting import fit_tree
    from app.grid import GridLayout
    from app.narrative import lineup_for
    harvest = harvester_for("demo:yardbirds").harvest("demo:yardbirds", depth=4)
    tree, L, _ = fit_tree(harvest, paper="A2", max_bands=24)
    assert "panels" not in L
    grid = GridLayout(tree, paper="A2")
    grid._prepare()
    on_poster = {b.name for b in tree.bands.values()}
    seen = set()
    for band_id, notes in grid.info.items():
        band = tree.bands[band_id]
        for n in notes:
            if n["text"].startswith("Style:"):
                assert lineup_for(band.lineups, n["year"]) is band.lineups[0]
                continue
            named = re.findall(r"(?:with|to) (.+)\.$", n["text"])
            for name in re.split(r", | and ", named[0]) if named else []:
                assert re.sub(r" \(\d{4}\)$", "", name) not in on_poster  # a move on the poster is a line, not words
            assert n["text"] not in seen  # each told once
            seen.add(n["text"])
            who = next(p for p in tree.people.values() if n["text"].startswith(p.name + " "))
            stints = [s for s in band.stints if s.person_id == who.id]
            if " went on to " in n["text"]:  # on their last line-up in the band
                assert abs(n["year"] - (max(s.end for s in stints) - 0.01)) < 1e-6
            elif " previously with " in n["text"]:
                assert n["year"] == min(s.start for s in stints)
            else:  # joined while a member
                assert any(s.start <= n["year"] < s.end for s in stints)


def test_a_musicians_other_bands_are_one_sentence_per_line_up():
    from app.grid import GridLayout
    from app.refiner import Band, FamilyTree, Lineup, LineupMember, Person, Stint
    stint = Stint(person_id="p", name="Dave LaRue", start=1990, end=2020, roles=["bass"])
    lu = Lineup(number=1, start=1990, end=2020, start_label="1990", end_label="2020", members=[LineupMember(person_id="p", name="Dave LaRue", roles=["bass"])])
    band = Band(id="b", name="Dregs", level=0, start=1990, end=2020, stints=[stint], lineups=[lu])
    person = Person(id="p", name="Dave LaRue", joined={"Dregs": 1990, "Trio": 2003, "Colours": 2011})
    tree = FamilyTree(root_id="b", root_name="Dregs", title="T", bands={"b": band}, people={"p": person})
    grid = GridLayout(tree, paper=None)
    notes = [n["text"] for n in grid._info_notes().get("b", [])]
    assert notes == ["Dave LaRue also with Trio (2003), Colours (2011)."]


@pytest.mark.parametrize("root,depth,paper", [("demo:yardbirds", 4, "A2"), ("demo:acdc", 3, "A2")])
def test_moves_go_round_other_line_ups(root, depth, paper):
    """With each column at its own pace the channels don't run level across
    the page: a move's line must still never cross a line-up it doesn't
    join (the margin is the last resort)."""
    from app.fitting import fit_tree
    _, L, _ = fit_tree(harvester_for(root).harvest(root, depth=depth), paper=paper, max_bands=24)
    for e in L["edges"]:
        for (x1, y1), (x2, y2) in zip(e["points"], e["points"][1:]):
            lx, hx, ly, hy = min(x1, x2), max(x1, x2), min(y1, y2), max(y1, y2)
            for b in L["boxes"]:
                if b["id"] in (e["from"], e["to"]):
                    continue
                assert not (b["x"] < hx and lx < b["x"] + b["w"] and b["y"] < hy and ly < b["y"] + b["h"]), (e["from"], e["to"], b["id"])
