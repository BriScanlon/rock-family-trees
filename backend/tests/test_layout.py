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
    assert abs(H / W - 2 ** 0.5) < 0.01
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
    assert any("ERIC CLAPTON LEFT TO JOIN JOHN MAYALL'S BLUESBREAKERS" in n for n in notes)
    assert any("KEITH RELF DIED MAY 76" in n for n in notes)
    assert any(n.startswith("SPLIT") for n in notes)
    assert all(b["date_label"].startswith("(") for b in layout["boxes"])


def test_svg_is_valid_and_self_contained(layout, tmp_path):
    svg = Artist(layout, str(tmp_path / "t.svg")).render()
    root = ET.fromstring(svg)
    assert root.tag.endswith("svg") and root.get("width") == "594mm"
    assert "@font-face" in svg and "http" not in svg.replace("http://www.w3.org/2000/svg", "")
    assert "THE YARDBIRDS FAMILY TREE" in svg


def test_default_style_is_ink_on_white(layout):
    svg = Artist(layout).render()
    assert 'fill="#ffffff"' in svg
    assert 'filter="url(#rough)"' not in svg and 'url(#paper)' not in svg
    assert "font-family:'Architects Daughter'" in svg
    assert "PAUL SAMWELL-SMITH" in svg  # architect's capitals throughout


def test_optional_extras(layout):
    svg = Artist(dict(layout, timeline=True), hand_drawn=True, aged_paper=True).render()
    assert 'filter="url(#rough)"' in svg and 'url(#paper)' in svg and ">1965<" in svg
