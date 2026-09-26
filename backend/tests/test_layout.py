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
    return Cartographer(tree, paper="A1").layout()


def test_boxes_in_a_lane_never_overlap(layout):
    by_lane = {}
    for b in layout["boxes"]:
        by_lane.setdefault(b["lane"], []).append(b)
    for boxes in by_lane.values():
        boxes.sort(key=lambda b: b["y"])
        for a, b in zip(boxes, boxes[1:]):
            assert a["y"] + a["footprint"] <= b["y"], (a["id"], b["id"])


def test_time_flows_down_the_page(layout):
    boxes = sorted(layout["boxes"], key=lambda b: b["start"])
    for a, b in zip(boxes, boxes[1:]):
        if round(a["start"] * 12) < round(b["start"] * 12):
            assert a["y"] < b["y"]


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
    assert yb["members"][0]["roles"] == ["vocals", "harmonica"]
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
    assert root.tag.endswith("svg") and {root.get("width"), root.get("height")} == {"594mm", "841mm"}
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
