import pytest

from app.cartographer import MIN_PRINT_PT
from app.fitting import fit_tree
from app.pipeline import harvester_for


@pytest.fixture(scope="module")
def harvest():
    return harvester_for("demo:yardbirds").harvest("demo:yardbirds", depth=4)


@pytest.mark.parametrize("paper", ["A4", "A3", "A2", "A1", "A0"])
def test_every_sheet_prints_readably(harvest, paper):
    tree, layout, fit = fit_tree(harvest, paper=paper)
    assert layout["stats"]["paper"] == paper
    assert layout["stats"]["smallest_text_pt"] >= MIN_PRINT_PT
    assert fit["readable"]
    assert "demo:yardbirds" in tree.bands  # the root band is always kept


def test_bigger_sheets_hold_more(harvest):
    shown = [fit_tree(harvest, paper=p)[2]["bands_shown"] for p in ("A4", "A3", "A2", "A1", "A0")]
    assert shown == sorted(shown) and shown[0] < shown[-1]
    assert shown[-1] >= 10  # A0 holds the core family


def test_trimmed_tree_stays_connected_and_reports_omissions(harvest):
    tree, _, fit = fit_tree(harvest, paper="A2")
    people = lambda b: {s.person_id for s in b.stints}
    root = tree.bands["demo:yardbirds"]
    reached, frontier = {root.id}, [root]
    while frontier:
        b = frontier.pop()
        for other in tree.bands.values():
            if other.id not in reached and people(b) & people(other):
                reached.add(other.id)
                frontier.append(other)
    assert reached == set(tree.bands)
    assert len(fit["omitted_bands"]) == fit["bands_available"] - fit["bands_shown"] > 0


def test_auto_picks_the_smallest_sheet_that_holds_everything(harvest):
    small = harvester_for("demo:yardbirds").harvest("demo:yardbirds", depth=2)
    _, layout, fit = fit_tree(small, paper="auto")
    assert layout["stats"]["paper"] == "A1" and fit["omitted_bands"] == []


def test_bands_linked_by_long_serving_members_come_first():
    from app.refiner import Refiner
    acdc = harvester_for("demo:acdc").harvest("demo:acdc", depth=3)
    order = [b.name for b in Refiner().build(acdc).bands.values()]
    # Geordie (Brian Johnson, decades in AC/DC) outranks bands linked by early, brief members
    assert order.index("Geordie") < order.index("The Valentines")
    assert order.index("Geordie") < order.index("The Masters Apprentices")
    assert order[1] == "Marcus Hook Roll Band"  # both Young brothers


def test_line_ups_are_only_simplified_as_a_last_resort():
    acdc = harvester_for("demo:acdc").harvest("demo:acdc", depth=3)
    tree, layout, fit = fit_tree(acdc, paper="A2")
    assert fit["lineups_shown"] == sum(len(b.lineups) for b in tree.bands.values())
    assert all(lu.merged == 0 for b in tree.bands.values() for lu in b.lineups)
    tree, layout, fit = fit_tree(acdc, paper="A4")  # AC/DC alone is too big for A4
    merged = [lu for lu in tree.bands["demo:acdc"].lineups if lu.merged]
    assert merged and any("Simplified to fit" in " ".join(b["notes"]) for b in layout["boxes"])
