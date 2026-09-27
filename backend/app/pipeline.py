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
NARRATIVE_BANDS = int(os.getenv("NARRATIVE_BANDS", "8"))  # the top-ranked bands given notes from Wikipedia


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


def gather_stories(harvester, harvest, opts, progress):
    """Notes from Wikipedia for the top-ranked bands: {band id: [notes]}.
    Written once per band, article revision and model, stored (Neo4j) and
    recalled after, so only a band's first poster waits for the model. If
    Wikipedia or the model can't be reached, the band's last stored notes are
    used; with none, the band has no notes and the poster is still drawn."""
    if harvest["root_id"].startswith("demo:"):
        return {}
    from app import narrative
    from app.refiner import Refiner
    from app.wikipedia import WikipediaClient
    ranked = list(Refiner(max_bands=opts["max_bands"]).build(harvest).bands.values())[:NARRATIVE_BANDS]
    wiki, out = WikipediaClient(), {}
    for i, band in enumerate(ranked):
        progress(70 + int(5 * i / max(1, len(ranked))), f"Reading up on {band.name}")
        try:
            record = harvest["records"][band.id]
            if record.get("wikidata") is None:  # cached before Wikidata links were kept
                record = harvester._client().get_artist(band.id) or record
                harvester.store.put(record)
            article = wiki.article(wiki.title_for(record.get("wikidata")))
            if article:
                out[band.id] = narrative.write_notes(band, article, store=harvester.store)["notes"]
        except Exception as e:
            # Wikipedia or the model out of reach: recall the band's last notes, if any
            recalled = harvester.store.latest_notes(band.id)
            if recalled and recalled.get("notes"):
                out[band.id] = recalled["notes"]
                print(f"Recalled stored notes for {band.name} ({type(e).__name__}: {e})")
            else:
                print(f"No notes for {band.name}: {type(e).__name__}: {e}")
    return out


def gather_albums(harvester, harvest, opts, progress):
    """Studio albums for the ranked bands ({band id: ["1972 Machine Head", ...]}),
    which fill the gaps on the poster as Frame's discographies did. Looked up
    once per band and kept on its record (Neo4j)."""
    from app.refiner import Refiner
    out = {}
    for band in Refiner(max_bands=opts["max_bands"]).build(harvest).bands.values():
        record = harvest["records"].get(band.id) or {}
        albums = record.get("albums")
        if albums is None and not band.id.startswith("demo:"):
            progress(74, f"Looking up {band.name}'s albums")
            try:
                albums = harvester._client().get_albums(band.id)
                harvester.store.put(dict(record, albums=albums))
            except Exception as e:
                print(f"No albums for {band.name}: {type(e).__name__}: {e}")
        out[band.id] = albums or []
    return out


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

    stories = gather_stories(harvester, harvest, opts, progress) if opts["notes"] else {}
    albums = gather_albums(harvester, harvest, opts, progress)

    progress(75, "Working out who played with whom, and how much fits on the paper")
    tree, layout, fit = fit_tree(harvest, paper=opts["paper"], max_bands=opts["max_bands"], title=opts["title"],
                                 timeline=opts["timeline"], lettering=lettering, stories=stories, albums=albums)
    if not tree.bands:
        raise ValueError(f"No dated band line-ups found for {harvest['root_name']} on MusicBrainz")

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
        "api_calls": harvest["api_calls"],
    }
