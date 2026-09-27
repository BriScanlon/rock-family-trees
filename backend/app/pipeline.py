"""Content first (harvest, line-ups, notes, albums, links: app/content.py), then
placement (app/fitting.py), then drawing - with progress reporting."""
import json
import os

from app.artist import Artist
from app.content import build_content
from app.fitting import fit_content
from app.fixtures import OfflineClient, build_records
from app.harvester import Harvester
from app.store import MemoryStore

ARTIFACT_DIR = os.getenv("ARTIFACT_DIR", "artifacts")


class Options(dict):
    DEFAULTS = {
        "depth": 2, "max_bands": 40, "title": None, "subtitle": None, "paper": "auto",
        "hand_drawn": False, "coloured_lines": False, "aged_paper": False, "timeline": False,
        "lettering": "auto",
        "notes": True,  # notes written from Wikipedia (app/narrative.py)
        "refresh": False,
    }

    def __init__(self, **kw):
        super().__init__(self.DEFAULTS)
        self.update({k: v for k, v in kw.items() if v is not None})


def harvester_for(artist_id, refresh=False):
    if artist_id.startswith("demo:"):
        return Harvester(store=MemoryStore(build_records()), client=OfflineClient())
    return Harvester(refresh=refresh)


def generate(artist_id, job_id, options=None, progress=None):
    opts = options if isinstance(options, Options) else Options(**(options or {}))
    progress = progress or (lambda pct, msg: None)
    os.makedirs(ARTIFACT_DIR, exist_ok=True)

    # 1. all the content, built and stored before any placement (issue #8); background
    #    reading of the family waits while a poster is being made
    from app import narrative
    with narrative.foreground():
        content = build_content(artist_id, opts, progress)
    lettering = content.lettering

    # 2. then the placement
    progress(75, "Working out who played with whom, and how much fits on the paper")
    tree, layout, fit = fit_content(content, paper=opts["paper"], timeline=opts["timeline"])
    if not tree.bands:
        raise ValueError(f"No dated band line-ups found for {content.root_name} on MusicBrainz")

    progress(88, "Drawing up the family tree")
    subtitle = opts["subtitle"]
    if subtitle is None:
        years = [b.start for b in tree.bands.values()] + [b.end for b in tree.bands.values()]
        n = len(tree.bands)
        subtitle = f"{n} band{'s' if n != 1 else ''} · {int(min(years))} – {int(max(years))}"
    layout["subtitle"] = subtitle
    layout["stats"].update(fit)

    progress(92, "Inking the lines")
    svg_path = os.path.join(ARTIFACT_DIR, f"{job_id}.svg")
    credit = ("RESEARCHED FROM MUSICBRAINZ AND WIKIPEDIA · DRAWN BY THE ROCK FAMILY TREE GENERATOR"
              if any(b.stories for b in tree.bands.values()) else None)
    Artist(layout, svg_path, hand_drawn=opts["hand_drawn"], coloured_lines=opts["coloured_lines"],
           aged_paper=opts["aged_paper"], credit=credit).save()
    with open(os.path.join(ARTIFACT_DIR, f"{job_id}.json"), "w") as f:
        json.dump({"tree": tree.model_dump(), "stats": layout["stats"]}, f)

    return {
        "result_url": f"/download/{job_id}",
        "title": tree.title,
        "stats": layout["stats"],
        "lettering": lettering,
        "api_calls": content.harvest["api_calls"],
        "content": content.summary(),
    }
