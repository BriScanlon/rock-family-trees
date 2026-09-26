"""Fit a family tree to a sheet of paper.

A poster is only worth printing if it can be read, so for a given sheet
(A4 up to A0) we trim the tree until its smallest text prints at
MIN_PRINT_PT or more. The least-connected bands are dropped first, keeping
the refiner's priority order (the root first, then the bands linked by the
longest-serving musicians) so whatever remains is one connected family.
Only if the root band alone still won't fit are its briefest line-ups
folded together - and the poster says so, since that loses detail.
"""
from app.cartographer import MIN_PRINT_PT, PAPER_MM, Cartographer
from app.refiner import Refiner

LINEUP_CAPS = (20, 12, 8, 5)   # most line-ups drawn per band, tried in turn
AUTO_PAPERS = ("A3", "A2", "A1", "A0")


def _layout(tree, paper, **kw):
    return Cartographer(tree, paper=paper, **kw).layout()


def _readable(layout):
    return layout["stats"].get("smallest_text_pt", 0) >= MIN_PRINT_PT


def _subset(tree, n):
    keep = list(tree.bands)[:n]
    return tree.model_copy(update={"bands": {k: tree.bands[k] for k in keep}})


def fit_tree(harvest, paper="auto", max_bands=24, title=None, **layout_kw):
    """Returns (tree, layout, fit) where fit describes anything left out."""
    trees = {cap: Refiner(max_bands=max_bands, max_lineups_per_band=cap).build(harvest, title=title)
             for cap in LINEUP_CAPS}
    full = trees[LINEUP_CAPS[0]]
    if not full.bands:
        return full, None, {}
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
        if paper != "auto":  # "none": no sheet, nothing to fit
            return result(full, _layout(full, None, **layout_kw))
        # smallest sheet that holds everything readably; else trim to A0
        for p in AUTO_PAPERS:
            layout = _layout(full, p, **layout_kw)
            if _readable(layout):
                return result(full, layout)
        paper = "A0"

    # Full detail with as many bands as fit; fewer line-ups only as a last resort.
    best = None
    for cap in LINEUP_CAPS:
        tree = trees[cap]
        lo, hi = 1, len(tree.bands)
        while lo <= hi:  # largest n that fits (fit shrinks as bands are added)
            mid = (lo + hi) // 2
            layout = _layout(_subset(tree, mid), paper, **layout_kw)
            if _readable(layout):
                if best is None or mid > best[0]:
                    best = (mid, cap, layout)
                lo = mid + 1
            else:
                hi = mid - 1
        if best:
            break  # something fits without simplifying line-ups any further
    if best is None:  # even the root band alone is too big: draw it anyway, as small as it must be
        tree = _subset(trees[LINEUP_CAPS[-1]], 1)
        return result(tree, _layout(tree, paper, **layout_kw))
    n, cap, layout = best
    return result(_subset(trees[cap], n), layout)
