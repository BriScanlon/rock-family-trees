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
    assert shown[-1] == 12  # the whole family fits on A0


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
