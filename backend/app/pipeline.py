"""Search -> harvest -> refine -> lay out -> render, with progress reporting."""
import json
import os

from app.artist import Artist
from app.fitting import fit_tree
from app.fonts import STYLES, lettering_for
from app.fixtures import OfflineClient, build_records
from app.harvester import Harvester
from app.store import MemoryStore

ARTIFACT_DIR = os.getenv("ARTIFACT_DIR", "artifacts")


class Options(dict):
    DEFAULTS = {
        "depth": 2, "max_bands": 24, "title": None, "subtitle": None, "paper": "auto",
        "hand_drawn": False, "coloured_lines": False, "aged_paper": False, "timeline": False,
        "lettering": "auto",
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

    progress(5, "Checking the record collection")
    harvester = harvester_for(artist_id, opts["refresh"])
    harvest = harvester.harvest(
        artist_id, depth=opts["depth"], max_bands=opts["max_bands"],
        progress=lambda frac, msg: progress(5 + int(frac * 65), msg),
    )

    lettering = opts["lettering"]
    if lettering not in STYLES:  # "auto": follow the root band's genres
        genres = [g for b in harvest["root_bands"] for g in harvest["records"].get(b, {}).get("genres", [])]
        lettering = lettering_for(genres)

    progress(75, "Working out who played with whom, and how much fits on the paper")
    tree, layout, fit = fit_tree(harvest, paper=opts["paper"], max_bands=opts["max_bands"], title=opts["title"],
                                 timeline=opts["timeline"], lettering=lettering)
    if not tree.bands:
        raise ValueError(f"No dated band line-ups found for {harvest['root_name']} on MusicBrainz")

    progress(88, "Drawing up the family tree")
    subtitle = opts["subtitle"]
    if subtitle is None:
        years = [b.start for b in tree.bands.values()] + [b.end for b in tree.bands.values()]
        subtitle = f"{len(tree.bands)} bands · {int(min(years))} – {int(max(years))}"
    layout["subtitle"] = subtitle
    layout["stats"].update(fit)

    progress(92, "Inking the lines")
    svg_path = os.path.join(ARTIFACT_DIR, f"{job_id}.svg")
    Artist(layout, svg_path, hand_drawn=opts["hand_drawn"], coloured_lines=opts["coloured_lines"],
           aged_paper=opts["aged_paper"]).save()
    with open(os.path.join(ARTIFACT_DIR, f"{job_id}.json"), "w") as f:
        json.dump({"tree": tree.model_dump(), "stats": layout["stats"]}, f)

    return {
        "result_url": f"/download/{job_id}",
        "title": tree.title,
        "stats": layout["stats"],
        "lettering": lettering,
        "api_calls": harvest["api_calls"],
    }
