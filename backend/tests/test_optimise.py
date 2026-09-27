from app.content import build_content
from app.fitting import select
from app.optimise import _chronology_error, _connected, optimise
from app.pipeline import Options

PAPER = "A3"  # too small for the whole Yardbirds family, so there's a choice to make


def _content():
    return build_content("demo:yardbirds", Options(depth=4, max_bands=24))


def test_the_optimiser_never_does_worse_than_greedy():
    content = _content()
    chosen = select(content.trees, PAPER, content.lettering)
    tree, layout, score = optimise(content.trees, PAPER, content.lettering, chosen, seconds=2)
    assert set(chosen) <= set(tree.bands)  # the bands rank earned stay
    start = optimise(content.trees, PAPER, content.lettering, chosen, seconds=0)[2]
    assert score["total"] >= start["total"]


def test_the_optimiser_keeps_the_hard_rules():
    content = _content()
    chosen = select(content.trees, PAPER, content.lettering)
    tree, layout, _ = optimise(content.trees, PAPER, content.lettering, chosen, seconds=2)
    root = list(content.full.bands)[0]
    assert list(tree.bands)[0] == root and len(tree.bands[root].lineups) == len(
        content.trees[chosen[root]].bands[root].lineups)
    people = {k: {s.person_id for s in b.stints} for k, b in tree.bands.items()}
    assert _connected(tree.bands, people, root) == set(tree.bands)  # one family
    assert layout["stats"]["smallest_text_pt"] >= 6.5
    for b in layout["boxes"]:  # time runs down every column
        for other in layout["boxes"]:
            overlap = b["x"] < other["x"] + other["w"] and other["x"] < b["x"] + b["w"]
            if overlap and other["row"] > b["row"]:
                assert other["start"] >= b["start"] - 1


def test_the_optimiser_is_repeatable_with_a_seed():
    content = _content()
    chosen = select(content.trees, PAPER, content.lettering)
    a = optimise(content.trees, PAPER, content.lettering, chosen, seconds=0, seed=3)
    b = optimise(content.trees, PAPER, content.lettering, chosen, seconds=0, seed=3)
    assert list(a[0].bands) == list(b[0].bands) and a[2]["total"] == b[2]["total"]


def test_chronology_error_counts_rows_out_of_time_order():
    in_order = {"boxes": [{"start": 1960 + i, "row": i} for i in range(6)]}
    muddled = {"boxes": [{"start": 1960 + i, "row": r} for i, r in enumerate([0, 5, 1, 4, 2, 3])]}
    assert _chronology_error(in_order) < 1e-9 < _chronology_error(muddled)
