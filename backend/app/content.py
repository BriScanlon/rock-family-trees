"""Everything a poster could show, built and stored before any placement
(issue #8, stage 1: the user's instruction - "all content and links first,
then the placement being tried").

For a root band: the family harvested from MusicBrainz; every candidate
band's line-ups at each level of detail; notes written from Wikipedia for
every candidate with an article (stored in Neo4j, corrected by hand where a
person has); every candidate's albums; and every musician's moves between
line-ups (the links the lines draw). The placement (app/fitting.py, and the
optimiser to come) only reads this: it never fetches, writes or ranks.
"""
import os
import re
from dataclasses import dataclass, field

from app.fonts import STYLES, lettering_for
from app.musicbrainz import is_group
from app.refiner import Refiner

LINEUP_CAPS = (20, 12, 8, 5, 3)   # line-ups kept per band at each level of detail, fullest first
# A new family's first poster waits only for its top bands' notes and events;
# the rest of the family is read afterwards, in the background (enrich), and
# every poster after uses whatever is stored. (The user's Oasis poster waited
# hours reading all 40 bands before anything was drawn.)
NARRATIVE_BANDS = int(os.getenv("NARRATIVE_BANDS", "15"))  # bands whose notes a poster waits for


@dataclass
class Content:
    root_id: str
    root_name: str
    harvest: dict
    trees: dict                      # line-up cap -> FamilyTree (every candidate band)
    stories: dict = field(default_factory=dict)   # band id -> notes (from Wikipedia, and by hand)
    albums: dict = field(default_factory=dict)    # band id -> ["1972-03-25 Machine Head", ...]
    events: dict = field(default_factory=dict)    # band id -> events from its albums' and tours' articles
    links: list = field(default_factory=list)     # musicians' moves between line-ups
    lettering: str = "classic"

    @property
    def full(self):
        return self.trees[LINEUP_CAPS[0]]

    def summary(self):
        """What the placement has to work with."""
        bands = self.full.bands
        return {
            "bands": len(bands),
            "lineups": sum(len(b.lineups) for b in bands.values()),
            "bands_with_notes": sum(1 for k in bands if self.stories.get(k)),
            "notes": sum(len(self.stories.get(k, [])) for k in bands),
            "bands_with_albums": sum(1 for k in bands if self.albums.get(k)),
            "albums": sum(len(self.albums.get(k, [])) for k in bands),
            "events": sum(len(self.events.get(k, [])) for k in bands),
            "links": len(self.links),
        }


def build_content(artist_id, opts, progress=None, harvester=None, full=False):
    """Harvest, refine, write notes, look up albums, trace links - all of it,
    before a single line-up is placed. `full`: write notes and events for
    every candidate band (the background enrichment), not just the top ones."""
    from app.pipeline import harvester_for
    progress = progress or (lambda pct, msg: None)
    progress(5, "Checking the record collection")
    harvester = harvester or harvester_for(artist_id, opts["refresh"])
    harvest = harvester.harvest(
        artist_id, depth=opts["depth"], max_bands=opts["max_bands"],
        progress=lambda frac, msg: progress(5 + int(frac * 55), msg),
    )
    gather_standing(harvester, harvest, progress)  # before any ranking: it counts towards it
    gather_charts(harvester, harvest, progress)    # before any line-ups: it corrects them
    stories, events = gather_story(harvester, harvest, opts, progress, full) if opts["notes"] else ({}, {})
    albums = gather_albums(harvester, harvest, opts, progress)
    trees = build_trees(harvest, opts["max_bands"], opts.get("title"), stories, albums, events)
    lettering = opts["lettering"]
    if lettering not in STYLES:  # "auto": follow the root band's genres
        genres = [g for b in harvest["root_bands"] for g in harvest["records"].get(b, {}).get("genres", [])]
        lettering = lettering_for(genres)
    content = Content(root_id=artist_id, root_name=harvest["root_name"], harvest=harvest, trees=trees,
                      stories=stories, albums=albums, events=events, links=links_for(trees[LINEUP_CAPS[0]]), lettering=lettering)
    s = content.summary()
    progress(74, f"Ready: {s['bands']} bands, {s['lineups']} line-ups, {s['notes']} notes, "
                 f"{s['albums']} albums, {s['events']} events, {s['links']} links")
    return content


def build_trees(harvest, max_bands, title=None, stories=None, albums=None, events=None):
    """Every candidate band at each level of detail, with its notes and albums."""
    trees = {cap: Refiner(max_bands=max_bands, max_lineups_per_band=cap).build(harvest, title=title)
             for cap in LINEUP_CAPS}
    for tree in trees.values():
        for band in tree.bands.values():
            band.stories = (stories or {}).get(band.id, [])
            band.albums = (albums or {}).get(band.id, [])
            band.events = (events or {}).get(band.id, [])
    return trees


def links_for(tree):
    """Every musician's move from one line-up to the next, across the whole
    family: {person, name, from_band, from_lineup, to_band, to_lineup, year}.
    A musician carrying on in a band while playing in another (a side
    project) continues from their last line-up in that band."""
    appearances = {}
    for band in tree.bands.values():
        for lu in band.lineups:
            for m in lu.members:
                appearances.setdefault(m.person_id, []).append((band, lu, m.name))
    links = []
    for pid, apps in appearances.items():
        apps.sort(key=lambda a: (a[1].start, a[0].start, a[0].name))
        last, prev = {}, None
        for band, lu, name in apps:
            before = last.get(band.id)
            src = before if before is not None and before[1].number == lu.number - 1 else prev
            if src is not None and not (src[0].id == band.id and src[1].number == lu.number):
                links.append({"person": pid, "name": name, "from_band": src[0].id, "from_lineup": src[1].number,
                              "to_band": band.id, "to_lineup": lu.number, "year": round(lu.start, 2)})
            last[band.id], prev = (band, lu), (band, lu)
    return links


def enrich(artist_id, opts, progress=None):
    """Notes and events for the whole family, after its poster is drawn (a
    background job): the next poster of the family is fuller, and none waits."""
    from app import narrative
    with narrative.background():
        return build_content(artist_id, opts, progress, full=True).summary()


def gather_standing(harvester, harvest, progress):
    """Each harvested band's standing: how many Wikipedias have an article on it
    (Wikidata sitelinks), kept on its record (Neo4j) and counted in the ranking.
    Looked up once per band, 50 at a time."""
    if harvest["root_id"].startswith("demo:"):
        return
    from app.musicbrainz import is_group
    from app.wikipedia import WikipediaClient
    records = harvest["records"]
    todo = [r for r in records.values() if is_group(r) and r.get("sitelinks") is None]
    if not todo:
        return
    progress(58, f"Weighing up {len(todo)} bands")
    for i, record in enumerate(todo):
        if record.get("wikidata") is None:  # cached before Wikidata links were kept
            fresh = harvester._client().get_artist(record["mbid"])
            if fresh:
                record.update(wikidata=fresh.get("wikidata", ""))
    try:
        counts = WikipediaClient().sitelinks([r.get("wikidata") for r in todo])
    except Exception as e:  # standing is a refinement: rank without it this time
        print(f"No standing looked up: {type(e).__name__}: {e}")
        return
    for record in todo:
        record["sitelinks"] = counts.get(record.get("wikidata"), 0) if record.get("wikidata") else 0
        harvester.store.put(record)


def gather_charts(harvester, harvest, progress):
    """Each candidate band's Wikipedia member chart (app/charts.py), from its
    "List of ... members" page or its article, kept on its record (Neo4j)
    beside the MusicBrainz memberships: [] where there is none. Looked up once
    per band; the refiner applies it."""
    if harvest["root_id"].startswith("demo:"):
        return
    from app.charts import PARSER, chart_members, find_timeline
    from app.wikipedia import WikipediaClient
    records = harvest["records"]
    todo = [records[b] for b in harvest.get("band_levels", {})
            if b in records and is_group(records[b])
            and (records[b].get("chart") is None or not (records[b].get("chart_source") or "").startswith(PARSER))]
    if not todo:
        return
    wiki = WikipediaClient()
    for i, record in enumerate(todo):
        progress(59, f"Checking {record['name']}'s members against Wikipedia ({i + 1} of {len(todo)})")
        try:
            title = wiki.title_for(record.get("wikidata"))
            chart, source = [], PARSER
            if title:
                base = re.sub(r"\s*\([^)]*\)$", "", title)
                for page in dict.fromkeys([f"List of {title} members", f"List of {base} members", title]):
                    got = wiki.wikitext(page)
                    timeline = find_timeline(got["text"]) if got else None
                    if timeline:
                        chart = chart_members(timeline)
                        source = f"{PARSER} {got['title']}@{got['revision']}"
                        break
        except Exception as e:  # a correction: go without it this time, try again next time
            print(f"No member chart for {record['name']}: {type(e).__name__}: {e}")
            continue
        record["chart"], record["chart_source"] = chart, source
        harvester.store.put(record)


def gather_story(harvester, harvest, opts, progress, full=False):
    """Each band's notes and events in one reading (app/story.py): the band's
    article with its most written-about albums and tours, one call to write
    and one to check. A poster reads its top NARRATIVE_BANDS bands (4 albums,
    2 tours each); every other band recalls what's stored; `full` (the
    background enrichment) reads them all, 6 albums each. Returns
    ({band id: notes}, {band id: events})."""
    if harvest["root_id"].startswith("demo:"):
        return {}, {}
    from app import events as ev
    from app import narrative
    from app.story import write_story
    from app.wikipedia import WikipediaClient
    everyone = list(Refiner(max_bands=opts["max_bands"]).build(harvest).bands.values())
    ranked = everyone if full or not NARRATIVE_BANDS else everyone[:NARRATIVE_BANDS]
    albums = ev.EVENT_ALBUMS_FULL if full else ev.EVENT_ALBUMS
    wiki, stories, events = WikipediaClient(), {}, {}

    def recall(band):
        record = harvest["records"].get(band.id) or {}
        got = harvester.store.latest_notes(band.id)
        stories[band.id] = got["notes"] if got else []
        events[band.id] = list(record.get("events") or [])

    for band in everyone[len(ranked):]:  # beyond the poster's top bands: what's stored, no model
        recall(band)
    for i, band in enumerate(ranked):
        progress(60 + int(13 * i / max(1, len(ranked))), f"Reading up on {band.name} ({i + 1} of {len(ranked)})")
        record = harvest["records"].get(band.id) or {}
        try:
            if record.get("wikidata") is None:  # cached before Wikidata links were kept
                record = harvester._client().get_artist(band.id) or record
                harvester.store.put(record)
            works = record.get("works")
            if works is None or any("length" not in w for w in works):
                works = works if works is not None else wiki.works(record.get("wikidata"))
                lengths = wiki.lengths([w["title"] for w in works])
                works = [dict(w, length=lengths.get(w["title"], 0)) for w in works]
                record["works"] = works
                harvester.store.put(record)
            band_article = wiki.article(wiki.title_for(record.get("wikidata")))
            work_articles = [(w, a) for w in ev.choose_works(works, albums=albums)
                             for a in [wiki.article(w["title"])] if a]
            if band_article or work_articles:
                got = write_story(band, band_article, work_articles, store=harvester.store)
                stories[band.id], events[band.id] = got["notes"], got["events"]
                # kept on the band's record: later posters recall them without the model
                record["events"], record["events_depth"] = got["events"], albums
                harvester.store.put(record)
            else:
                stories[band.id], events[band.id] = [], []
        except Exception as e:  # Wikipedia or the model out of reach: what's stored, if anything
            print(f"Recalled what's stored for {band.name} ({type(e).__name__}: {e})")
            recall(band)
    for band in everyone:  # corrections by hand have the last word
        stories[band.id] = narrative.final_notes(harvester.store, band.id, stories.get(band.id, []))
    return stories, events


def gather_albums(harvester, harvest, opts, progress):
    """Studio albums for the ranked bands ({band id: ["1972-03-25 Machine Head", ...]}),
    each told on the line-up together when it came out. Looked up once per
    band and kept as Album nodes on the band (Neo4j)."""
    out = {}
    for band in Refiner(max_bands=opts["max_bands"]).build(harvest).bands.values():
        record = harvest["records"].get(band.id) or {}
        albums = record.get("albums")
        if albums is None and not band.id.startswith("demo:"):
            progress(72, f"Looking up {band.name}'s albums")
            try:
                albums = harvester._client().get_albums(band.id)
                harvester.store.put(dict(record, albums=albums))
            except Exception as e:
                print(f"No albums for {band.name}: {type(e).__name__}: {e}")
        out[band.id] = albums or []
    return out
