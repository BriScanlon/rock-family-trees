"""Fit a family tree to a sheet of paper.

A poster is only worth printing if it can be read, so the sheet is taken at
the smallest readable print size (MIN_PRINT_PT) and treated as Frame's grid:
so many member-wide columns across, so many rows of line-ups down
(app/grid.py). The fitting fills it. Bands go in the refiner's priority order
(the root first, then the most strongly linked), first each at its simplest,
so that as many bands as possible go in, then with detail restored band by
band while it still fits: as Frame numbered only the line-ups that mattered,
a band with more changes than there is room for has its briefest line-ups
folded together (told under the members) rather than crowding out a band. The
root band takes at most ROOT_SHARE of the rows, so the family around it has
room too. Every band added shares a musician with one already drawn, so the
result is one connected family.

With a year scale (timeline) the old lane layout is used instead, trimmed
band by band until it reads.
"""
from app.cartographer import MIN_PRINT_PT, PAPER_MM, STYLES, Cartographer
from app.grid import GridLayout
from app.refiner import Refiner

LINEUP_CAPS = (20, 12, 8, 5, 3)   # most line-ups drawn per band, tried in turn
AUTO_PAPERS = ("A3", "A2", "A1", "A0")
ROOT_SHARE = 0.6                  # most of the sheet's rows the root band may take


def _layout(tree, paper, **kw):
    return Cartographer(tree, paper=paper, **kw).layout()


def _readable(layout):
    return layout["stats"].get("smallest_text_pt", 0) >= MIN_PRINT_PT


def _subset(tree, n):
    return _only(tree, list(tree.bands)[:n])


def _only(tree, keep):
    return tree.model_copy(update={"bands": {k: tree.bands[k] for k in keep}})


def _compose(trees, chosen):
    """One tree from each chosen band at its chosen line-up cap (root first)."""
    full = trees[LINEUP_CAPS[0]]
    return full.model_copy(update={"bands": {k: trees[cap].bands[k] for k, cap in chosen.items()}})


# placement pulls (era, top, near) tried for the final layout, each from the left and the right
ARRANGEMENTS = [(1.5, 0.3, 0.08), (3.0, 0.3, 0.08), (0.5, 0.3, 0.08), (1.5, 0.1, 0.3), (1.5, 0.6, 0.02)]


def _fullest(tree, paper, lettering, subtitle=None):
    """The same bands, arranged several ways: keep the layout that covers the
    most of the page (Frame's trees are all but solid ink)."""
    from app.grid import coverage
    cols, rows, _, _ = GridLayout.sheet(paper, dict(STYLES.get(lettering, STYLES["classic"])))
    best = None
    for weights in ARRANGEMENTS:
        for mirror in (False, True):
            grid = GridLayout(tree, paper=paper, subtitle=subtitle, lettering=lettering, cols=cols, rows=rows,
                              weights=weights, mirror=mirror)
            if not grid.fits():
                continue
            layout = grid.layout()
            score = coverage(layout)
            if best is None or score > best[0]:
                best = (score, layout)
    return best[1] if best else _grid(tree, paper, lettering, subtitle).layout()


def _grid(tree, paper, lettering, subtitle=None):
    cols, rows, _, _ = GridLayout.sheet(paper, dict(STYLES.get(lettering, STYLES["classic"])))
    return GridLayout(tree, paper=paper, subtitle=subtitle, lettering=lettering, cols=cols, rows=rows)


def select(trees, paper, lettering="classic"):
    """{band id: line-up cap} for the sheet, or None if not even the root
    band fits at its simplest."""
    full = trees[LINEUP_CAPS[0]]
    order = list(full.bands)
    _, rows, _, _ = GridLayout.sheet(paper, dict(STYLES.get(lettering, STYLES["classic"])))
    root = order[0]
    caps = [c for c in LINEUP_CAPS if len(trees[c].bands[root].lineups) <= max(3, int(rows * ROOT_SHARE))]
    chosen = None
    for cap in caps or LINEUP_CAPS[-1:]:
        if _grid(_compose(trees, {root: cap}), paper, lettering).fits():
            chosen = {root: cap}
            break
    if chosen is None:
        return None
    people = {k: {s.person_id for s in b.stints} for k, b in full.bands.items()}
    fits = lambda caps: _grid(_compose(trees, caps), paper, lettering).fits()
    simplest = LINEUP_CAPS[-1]

    def add_bands():
        """Every band that fits at its simplest, in priority order. A band
        skipped earlier may fit once others have moved things about (the
        placement isn't monotonic), so go round until nothing more fits."""
        added = True
        while added:
            added = False
            linked = set().union(*(people[k] for k in chosen))
            for k in order[1:]:
                if k not in chosen and people[k] & linked and fits({**chosen, k: simplest}):
                    chosen[k] = simplest
                    linked |= people[k]
                    added = True

    # More bands before more line-ups: the tree is about how bands lead to one
    # another, so a minor personnel change mustn't take the place of a band.
    add_bands()
    upgraded = True
    while upgraded:  # then detail back, band by band in priority order
        upgraded = False
        for k in order[1:]:
            if k not in chosen:
                continue
            for cap in (c for c in LINEUP_CAPS if c > chosen[k]):
                if len(trees[cap].bands[k].lineups) <= len(trees[chosen[k]].bands[k].lineups):
                    continue
                if fits({**chosen, k: cap}):
                    chosen[k] = cap
                    upgraded = True
                    break
    add_bands()
    return chosen


def fit_tree(harvest, paper="auto", max_bands=24, title=None, timeline=False, lettering="classic",
             stories=None, albums=None, **layout_kw):
    """Returns (tree, layout, fit) where fit describes anything left out.
    `stories`: {band id: dated notes from app/narrative.py}, drawn with the line-ups."""
    from app.content import build_trees
    trees = build_trees(harvest, max_bands, title, stories, albums)
    return _fit_trees(trees, paper, timeline, lettering, **layout_kw)


def fit_content(content, paper="auto", timeline=False, optimise_seconds=None, **layout_kw):
    """The placement, from finished content (app/content.py): it only reads.
    On a sheet too small for everything, the greedy choice is then improved
    by the placement optimiser (app/optimise.py) for `optimise_seconds`."""
    from app.optimise import OPTIMISE_SECONDS
    seconds = OPTIMISE_SECONDS if optimise_seconds is None else optimise_seconds
    return _fit_trees(content.trees, paper, timeline, content.lettering, optimise_seconds=seconds, **layout_kw)


def _fit_trees(trees, paper, timeline, lettering, optimise_seconds=0, **layout_kw):
    full = trees[LINEUP_CAPS[0]]
    if not full.bands:
        return full, None, {}
    if timeline:
        return _fit_lanes(trees, paper, timeline=True, lettering=lettering, **layout_kw)
    total_bands = len(full.bands)
    total_lineups = sum(len(b.lineups) for b in full.bands.values())

    def result(tree, layout):
        shown = sum(len(b.lineups) for b in tree.bands.values())
        return tree, layout, {
            "bands_shown": len(tree.bands), "bands_available": total_bands,
            "lineups_shown": shown, "lineups_available": total_lineups,
            "omitted_bands": [b.name for k, b in full.bands.items() if k not in tree.bands],
            "condensed_bands": {b.name: [len(b.lineups), len(full.bands[k].lineups)]
                                for k, b in tree.bands.items() if len(b.lineups) < len(full.bands[k].lineups)},
            "readable": _readable(layout),
        }

    if paper not in PAPER_MM:
        if paper != "auto":  # "none": no sheet, nothing to fit
            return result(full, GridLayout(full, paper=None, lettering=lettering, **layout_kw).layout())
        # the smallest sheet that holds the whole family at full detail; else fill A0
        for p in AUTO_PAPERS:
            grid = _grid(full, p, lettering, **layout_kw)
            if grid.fits():
                return result(full, grid.layout())
        paper = "A0"

    chosen = select(trees, paper, lettering)
    if chosen is None:  # even the root band alone is too big: draw it anyway, as small as it must be
        tree = _subset(trees[LINEUP_CAPS[-1]], 1)
        return result(tree, GridLayout(tree, paper=paper, lettering=lettering, **layout_kw).layout())
    if optimise_seconds > 0:
        from app.optimise import optimise
        tree, layout, score = optimise(trees, paper, lettering, chosen, optimise_seconds, **layout_kw)
        tree, layout, fit = result(tree, layout)
        return tree, layout, dict(fit, placement=score)
    tree = _compose(trees, chosen)
    return result(tree, _fullest(tree, paper, lettering, **layout_kw))


def _fit_lanes(trees, paper, **layout_kw):
    """The lane layout (with a year scale): add bands in priority order,
    skipping any that won't fit readably."""
    full = trees[LINEUP_CAPS[0]]
    total_bands = len(full.bands)
    total_lineups = sum(len(b.lineups) for b in full.bands.values())

    def result(tree, layout):
        shown = sum(len(b.lineups) for b in tree.bands.values())
        return tree, layout, {
            "bands_shown": len(tree.bands), "bands_available": total_bands,
            "lineups_shown": shown, "lineups_available": total_lineups,
            "omitted_bands": [b.name for k, b in full.bands.items() if k not in tree.bands],
            "readable": _readable(layout),
        }

    if paper not in PAPER_MM:
        if paper != "auto":
            return result(full, _layout(full, None, **layout_kw))
        for p in AUTO_PAPERS:
            layout = _layout(full, p, **layout_kw)
            if _readable(layout):
                return result(full, layout)
        paper = "A0"
    for cap in LINEUP_CAPS:
        tree = trees[cap]
        order = list(tree.bands)
        layout = _layout(_only(tree, order[:1]), paper, **layout_kw)
        if not _readable(layout):
            continue
        people = {k: {s.person_id for s in b.stints} for k, b in tree.bands.items()}
        keep, linked = order[:1], set(people[order[0]])
        for k in order[1:]:
            if not people[k] & linked:
                continue
            trial = _layout(_only(tree, keep + [k]), paper, **layout_kw)
            if _readable(trial):
                keep, layout = keep + [k], trial
                linked |= people[k]
        return result(_only(tree, keep), layout)
    tree = _subset(trees[LINEUP_CAPS[-1]], 1)
    return result(tree, _layout(tree, paper, **layout_kw))
