"""The placement optimiser (issue #8, stage 2).

With all the content built first (app/content.py), choose what to show and
where, scoring page coverage, content and chronology together - the user's
three aims - rather than placing bands one at a time and never looking back.

The packer (app/grid.py) keeps every hard rule: text at least MIN_PRINT_PT,
every move down the page, time down every column, nothing overlapping. The
optimiser searches over what it's given:
- which bands are shown (the greedy choice's, which rank earned, and any
  more that fit), and at what level of detail,
- each band's preferred column (moving bands about the page),
- the placement pulls (era, top, near) and which side it fills from,
- the text size (fewer, larger rows can make a fuller page),
by simulated annealing from the greedy choice, and keeps the best layout.
"""
import math
import os
import random
import time

from app.content import LINEUP_CAPS
from app.cartographer import STYLES
from app.grid import GridLayout, coverage

OPTIMISE_SECONDS = float(os.getenv("OPTIMISE_SECONDS", "60"))
# weights of the score's parts: coverage (0-1), content (0-1), line-up detail
# (0-1), notes shown (0-1), chronology error (0-1, subtracted), text size above
# the smallest readable (subtracted as a bonus's negative)
W_COVERAGE, W_CONTENT, W_DETAIL, W_NOTES, W_CHRONOLOGY, W_TEXT = 1.0, 0.35, 0.15, 0.1, 0.5, 0.15
SCALES = (1.0, 1.1, 1.2, 1.3)
# placement pulls (era, top, near) to try; None is the grid's own defaults, which the
# band selection used, so the greedy choice always has a start that fits
PULLS = [None, (1.5, 0.3, 0.08), (3.0, 0.3, 0.08), (0.5, 0.3, 0.08), (1.5, 0.1, 0.3), (1.5, 0.6, 0.02)]


class Placement:
    """One candidate answer: what's shown and how it's arranged."""

    def __init__(self, caps, pulls=PULLS[0], mirror=False, hints=None, scale=1.0):
        self.caps, self.pulls, self.mirror = dict(caps), pulls, mirror
        self.hints, self.scale = dict(hints or {}), scale

    def copy(self):
        return Placement(self.caps, self.pulls, self.mirror, self.hints, self.scale)


def optimise(trees, paper, lettering, start_caps, seconds=None, seed=0, subtitle=None):
    """(tree, layout, score) for the best placement found within `seconds`,
    starting from `start_caps` ({band id: line-up cap}, root first; the
    greedy choice), or None if even that doesn't fit. Never worse than the
    start: every arrangement of it is scored first."""
    from app.fitting import _compose
    seconds = OPTIMISE_SECONDS if seconds is None else seconds
    rng = random.Random(seed)
    full = trees[LINEUP_CAPS[0]]
    order = list(full.bands)  # the refiner's ranking, root first
    people = {k: {s.person_id for s in b.stints} for k, b in full.bands.items()}
    worth = {k: 1 / (1 + 0.1 * i) for i, k in enumerate(order)}
    style = dict(STYLES.get(lettering, STYLES["classic"]))
    sheets = {s: GridLayout.sheet(paper, style, s) for s in SCALES}
    root = order[0]
    # the greedy choice's bands won their places by ranking, so they stay: the
    # optimiser may add bands and drop those it added, never trade a ranked
    # band (Gillan) for a fuller page of minor ones (the user's ranking, #6)
    kept = set(start_caps)

    def evaluate(p):
        cols, rows, _, _ = sheets[p.scale]
        tree = _compose(trees, p.caps)
        grid = GridLayout(tree, paper=paper, subtitle=subtitle, lettering=lettering, cols=cols, rows=rows,
                          weights=p.pulls, mirror=p.mirror, hints=p.hints, scale=p.scale)
        if not kept <= set(p.caps) or not grid.fits():
            return None
        layout = grid.layout()
        return tree, layout, _score(layout, tree, p, worth, full)

    def neighbour(p):
        q = p.copy()
        move = rng.choice(["add", "add", "drop", "detail", "detail", "hint", "hint", "pulls", "scale"])
        shown = list(q.caps)
        if move == "add":
            linked = set().union(*(people[k] for k in shown))
            out = [k for k in order if k not in q.caps and people[k] & linked]
            if out:  # better-ranked bands more often
                k = rng.choices(out, weights=[worth[k] for k in out])[0]
                q.caps[k] = LINEUP_CAPS[-1]
        elif move == "drop" and set(shown) - kept:
            k = rng.choice(sorted(set(shown) - kept))
            del q.caps[k]
            q.hints.pop(k, None)
            for other in set(q.caps) - _connected(q.caps, people, root):  # and whatever hung off it
                del q.caps[other]
                q.hints.pop(other, None)
        elif move == "detail" and len(shown) > 1:  # the root keeps its detail (ROOT_SHARE)
            k = rng.choice(shown[1:])
            i = LINEUP_CAPS.index(q.caps[k]) + rng.choice([-1, 1])
            if 0 <= i < len(LINEUP_CAPS):
                q.caps[k] = LINEUP_CAPS[i]
        elif move == "hint":
            k = rng.choice(shown)
            cols = sheets[q.scale][0]
            if k in q.hints and rng.random() < 0.3:
                del q.hints[k]
            else:
                q.hints[k] = rng.randrange(cols)
        elif move == "pulls":
            q.pulls = rng.choice(PULLS)
            q.mirror = rng.random() < 0.5
        else:
            q.scale = rng.choice(SCALES)
        q.caps = {k: q.caps[k] for k in order if k in q.caps}  # root first, ranking order
        return q

    starts = [(Placement(start_caps, pulls, mirror)) for pulls in PULLS for mirror in (False, True)]
    scored = [(p, got) for p in starts for got in [evaluate(p)] if got is not None]
    if not scored:
        return None
    current, cur_eval = max(scored, key=lambda pg: pg[1][2]["total"])
    best, best_p = cur_eval, current
    deadline = time.time() + seconds
    t0, t1 = 0.03, 0.002
    tried = accepted = 0
    while time.time() < deadline:
        progress = 1 - (deadline - time.time()) / max(seconds, 1e-9)
        temperature = t0 * (t1 / t0) ** progress
        candidate = neighbour(current)
        got = evaluate(candidate)
        tried += 1
        if got is None:
            continue
        delta = got[2]["total"] - cur_eval[2]["total"]
        if delta >= 0 or rng.random() < math.exp(delta / temperature):
            current, cur_eval = candidate, got
            accepted += 1
            if got[2]["total"] > best[2]["total"]:
                best, best_p = got, candidate
    tree, layout, score = best
    score = dict(score, tried=tried, accepted=accepted, scale=best_p.scale)
    return tree, layout, score


def _connected(caps, people, root):
    """The bands reachable from the root through shared musicians: the family
    must stay in one piece."""
    seen, todo = {root}, [root]
    while todo:
        k = todo.pop()
        for other in caps:
            if other not in seen and people[other] & people[k]:
                seen.add(other)
                todo.append(other)
    return seen


def _score(layout, tree, p, worth, full):
    """Higher is better: coverage + content + detail + notes shown - chronology
    error + larger text."""
    cov = coverage(layout)
    content = sum(worth[k] for k in tree.bands) / sum(worth.values())
    detail = (sum(len(b.lineups) for b in tree.bands.values())
              / max(1, sum(len(full.bands[k].lineups) for k in tree.bands)))
    said = " ".join(" ".join(b["notes"]) for b in layout["boxes"])
    notes = [s["text"].rstrip(".")[:30] for b in tree.bands.values() for s in b.stories]
    notes_shown = sum(1 for n in notes if n in said) / len(notes) if notes else 1.0
    chron = _chronology_error(layout)
    total = (W_COVERAGE * cov + W_CONTENT * content + W_DETAIL * detail + W_NOTES * notes_shown
             - W_CHRONOLOGY * chron + W_TEXT * (p.scale - 1))
    return {"total": total, "coverage": cov, "content": content, "detail": detail,
            "notes_shown": notes_shown, "chronology_error": chron}


def _chronology_error(layout):
    """How far rows stray from reading as time down the page: the mean distance
    (in rows) of each line-up from a straight time-to-row line fitted through
    them all, as a share of the rows used."""
    pts = [(b["start"], b["row"]) for b in layout["boxes"]]
    if len(pts) < 3:
        return 0.0
    n = len(pts)
    mt = sum(t for t, _ in pts) / n
    mr = sum(r for _, r in pts) / n
    var = sum((t - mt) ** 2 for t, _ in pts) or 1e-9
    slope = sum((t - mt) * (r - mr) for t, r in pts) / var
    err = sum(abs(r - (mr + slope * (t - mt))) for t, r in pts) / n
    rows = max(r for _, r in pts) + 1
    return err / rows
