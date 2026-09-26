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
