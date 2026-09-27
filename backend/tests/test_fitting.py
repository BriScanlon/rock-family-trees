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
    # both are direct lineage: Johnson from Geordie, the Young brothers from Marcus Hook Roll Band
    assert {"Geordie", "Marcus Hook Roll Band"} <= set(order[1:3])


def test_more_bands_come_before_more_line_ups():
    # A band left out must not fit even at its simplest, whatever detail the
    # bands on the sheet were given: detail never crowds out a band.
    from app.fitting import LINEUP_CAPS, _compose, _grid, select
    from app.refiner import Refiner
    yardbirds = harvester_for("demo:yardbirds").harvest("demo:yardbirds", depth=4)
    trees = {cap: Refiner(max_bands=24, max_lineups_per_band=cap).build(yardbirds) for cap in LINEUP_CAPS}
    chosen = select(trees, "A2")
    simplest = {k: LINEUP_CAPS[-1] for k in chosen} | {next(iter(chosen)): chosen[next(iter(chosen))]}
    full = trees[LINEUP_CAPS[0]]
    people = lambda b: {s.person_id for s in b.stints}
    drawn = set().union(*(people(full.bands[k]) for k in chosen))
    for k, b in full.bands.items():
        if k not in chosen and people(b) & drawn:
            assert not _grid(_compose(trees, {**simplest, k: LINEUP_CAPS[-1]}), "A2", "classic").fits(), b.name


def test_a_band_is_condensed_only_when_it_would_not_fit():
    # Frame numbered only the line-ups that mattered: a band's briefest
    # line-ups are folded together when that is what gets it on the sheet.
    from app.fitting import LINEUP_CAPS, ROOT_SHARE, _compose, _grid, select
    from app.grid import GridLayout
    from app.refiner import Refiner
    from app.fonts import STYLES
    acdc = harvester_for("demo:acdc").harvest("demo:acdc", depth=3)
    trees = {cap: Refiner(max_bands=24, max_lineups_per_band=cap).build(acdc) for cap in LINEUP_CAPS}
    chosen = select(trees, "A2")
    order = list(chosen)
    _, rows, _, _ = GridLayout.sheet("A2", dict(STYLES["classic"]))
    assert len(trees[chosen[order[0]]].bands[order[0]].lineups) <= max(3, int(rows * ROOT_SHARE))
    for k in order[1:]:
        n = len(trees[chosen[k]].bands[k].lineups)
        more = [c for c in LINEUP_CAPS if c > chosen[k] and len(trees[c].bands[k].lineups) > n]
        if more:  # with everything else as drawn, the next level of detail doesn't fit
            assert not _grid(_compose(trees, {**chosen, k: more[-1]}), "A2", "classic").fits(), k
    tree, layout, fit = fit_tree(acdc, paper="A3")
    # and the poster says so, under the members as Frame did
    marked = [r for b in layout["boxes"] for m in b["members"] for r in m["roles"][1:]
              if r.startswith(("joined", "left", "then", "after"))]
    assert fit["condensed_bands"] and marked


@pytest.mark.parametrize("paper", ["A3", "A2"])
def test_no_band_left_out_would_have_fitted(paper):
    # A band too big for the sheet is skipped, not the end of the search:
    # every connected band left out would not fit even at its simplest.
    from app.fitting import LINEUP_CAPS, _compose, _grid, select
    from app.refiner import Refiner
    acdc = harvester_for("demo:acdc").harvest("demo:acdc", depth=3)
    trees = {cap: Refiner(max_bands=24, max_lineups_per_band=cap).build(acdc) for cap in LINEUP_CAPS}
    chosen = select(trees, paper)
    full = trees[LINEUP_CAPS[0]]
    people = lambda b: {s.person_id for s in b.stints}
    drawn = set().union(*(people(full.bands[k]) for k in chosen))
    for k, b in full.bands.items():
        if k in chosen or not people(b) & drawn:
            continue
        for cap in LINEUP_CAPS:
            assert not _grid(_compose(trees, {**chosen, k: cap}), paper, "classic").fits(), (b.name, cap)


def test_the_band_a_founder_came_from_is_kept_despite_bad_dates():
    # MusicBrainz has Dave Grohl's Foo Fighters membership as October 1994
    # only; as a founder he still counts as long-serving, and his move
    # straight from Nirvana makes it lineage, ahead of a side project and of a
    # band linked by a two-year drummer.
    from tests.helpers import band, person
    from app.refiner import Refiner
    ff = band("ff", "Foo Fighters", "1994-10", None, [
        ("dave", "Dave Grohl", "1994-10", "1994-10", ["lead vocals", "guitar", "original"]),
        ("taylor", "Taylor Hawkins", "1997-03", "2022-03", ["drums (drum set)"]),
        ("josh", "Josh Freese", "2023", "2025-05", ["drums (drum set)"])])
    nirvana = band("nv", "Nirvana", "1987", "1994-04-05", [
        ("kurt", "Kurt Cobain", "1987", "1994-04-05", ["guitar"]),
        ("dave", "Dave Grohl", "1990-09", "1994-04-05", ["drums (drum set)"])])
    chevy = band("cm", "Chevy Metal", "2012", None, [
        ("taylor", "Taylor Hawkins", "2012", "2022-03", ["lead vocals"])])
    vandals = band("vd", "The Vandals", "1980", None, [
        ("josh", "Josh Freese", "1989", None, ["drums (drum set)"])])
    bands = [ff, nirvana, chevy, vandals]
    people = {"dave": "Dave Grohl", "taylor": "Taylor Hawkins", "josh": "Josh Freese", "kurt": "Kurt Cobain"}
    records = {b["mbid"]: b for b in bands} | {p: person(p, n, bands) for p, n in people.items()}
    harvest = {"root_id": "ff", "root_name": "Foo Fighters", "root_bands": ["ff"],
               "band_levels": {"ff": 0, "nv": 1, "cm": 1, "vd": 1}, "records": records}
    order = [b.name for b in Refiner(today=2026.5).build(harvest).bands.values()]
    assert order[:2] == ["Foo Fighters", "Nirvana"], order


def test_standing_breaks_ties_but_lineage_beats_fame():
    # standing = how many Wikipedias cover a band (Wikidata sitelinks), damped
    from tests.helpers import band, person
    from app.refiner import Refiner
    root = band("r", "Root", "1990", None, [
        ("a", "Ann", "1990", None, ["lead vocals", "original"]),
        ("b", "Bob", "1990", None, ["guitar", "original"])])
    famous = band("f", "Zenith", "1985", "1989", [("a", "Ann", "1985", "1989", ["lead vocals"])])
    obscure = band("o", "Acorn", "1985", "1989", [("b", "Bob", "1985", "1989", ["guitar"])])
    fleeting = band("g", "Supergroup", "2010", "2011", [("a", "Ann", "2010", "2010-03", ["lead vocals"])])
    famous["sitelinks"], obscure["sitelinks"], fleeting["sitelinks"], root["sitelinks"] = 100, 10, 120, 30
    bands = [root, famous, obscure, fleeting]
    records = {b["mbid"]: b for b in bands} | {p: person(p, n, bands) for p, n in (("a", "Ann"), ("b", "Bob"))}
    harvest = {"root_id": "r", "root_name": "Root", "root_bands": ["r"],
               "band_levels": {"r": 0, "f": 1, "o": 1, "g": 1}, "records": records}
    order = [b.name for b in Refiner(today=2026.5).build(harvest).bands.values()]
    assert order.index("Zenith") < order.index("Acorn")        # same lineage, better known first (names say otherwise)
    assert order.index("Acorn") < order.index("Supergroup")    # lineage beats a famous side project
    for rec in bands:
        rec.pop("sitelinks")
    order = [b.name for b in Refiner(today=2026.5).build(harvest).bands.values()]
    assert set(order[1:3]) == {"Zenith", "Acorn"}              # unknown standing: neutral


def test_a_family_that_fits_whole_is_lettered_as_large_as_the_sheet_allows():
    """A small family doesn't leave half its sheet blank: it's lettered larger."""
    from app.fitting import fit_tree
    from app.pipeline import harvester_for
    harvest = harvester_for("demo:acdc").harvest("demo:acdc", depth=1)
    _, small, fit = fit_tree(harvest, paper="A0", max_bands=3)
    assert fit["bands_shown"] == fit["bands_available"]  # everything fits
    assert small["stats"]["smallest_text_pt"] > 6.5 * 1.3  # and prints well above the smallest readable size
