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
NARRATIVE_BANDS = int(os.getenv("NARRATIVE_BANDS", "0"))  # bands given notes; 0 = every candidate


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


def build_content(artist_id, opts, progress=None, harvester=None):
    """Harvest, refine, write notes, look up albums, trace links - all of it,
    before a single line-up is placed."""
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
    stories = gather_stories(harvester, harvest, opts, progress) if opts["notes"] else {}
    albums = gather_albums(harvester, harvest, opts, progress)
    events = gather_events(harvester, harvest, opts, progress) if opts["notes"] else {}
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


def gather_events(harvester, harvest, opts, progress):
    """Events from the top-ranked bands' most written-about albums and tours
    (app/events.py): {band id: [{"date", "year", "text", "significance",
    "subject"}]}. Each band's albums and tours are looked up once (Wikidata)
    and kept on its record; each article is read once per revision."""
    if harvest["root_id"].startswith("demo:"):
        return {}
    from app import events as ev
    from app.wikipedia import WikipediaClient
    ranked = list(Refiner(max_bands=opts["max_bands"]).build(harvest).bands.values())[:ev.EVENT_BANDS]
    wiki, out = WikipediaClient(), {}
    for i, band in enumerate(ranked):
        record = harvest["records"].get(band.id) or {}
        try:
            works = record.get("works")
            if works is None:
                works = wiki.works(record.get("wikidata"))
                record["works"] = works
                harvester.store.put(record)
            for work in ev.choose_works(works):
                progress(73, f"Reading about {band.name}'s {work['title']} ({i + 1} of {len(ranked)})")
                article = wiki.article(work["title"])
                if not article:
                    continue
                got = ev.write_events(band, work, article, store=harvester.store)
                out.setdefault(band.id, []).extend(
                    dict(n, subject=work["title"], kind=work["kind"], sitelinks=work["sitelinks"]) for n in got["notes"])
        except Exception as e:  # events are extra: the poster is drawn without them
            print(f"No events for {band.name}: {type(e).__name__}: {e}")
    return out


def gather_stories(harvester, harvest, opts, progress):
    """Notes from Wikipedia for the candidate bands: {band id: [notes]}.
    Written once per band, article revision and model, stored (Neo4j) and
    recalled after, so only a band's first poster waits for the model. If
    Wikipedia or the model can't be reached, the band's last stored notes are
    used; with none, the band has no notes and the poster is still drawn."""
    if harvest["root_id"].startswith("demo:"):
        return {}
    from app import narrative
    from app.wikipedia import WikipediaClient
    ranked = list(Refiner(max_bands=opts["max_bands"]).build(harvest).bands.values())
    ranked = ranked[:NARRATIVE_BANDS] if NARRATIVE_BANDS else ranked
    wiki, out = WikipediaClient(), {}
    for i, band in enumerate(ranked):
        progress(60 + int(12 * i / max(1, len(ranked))), f"Reading up on {band.name}")
        try:
            record = harvest["records"][band.id]
            if record.get("wikidata") is None:  # cached before Wikidata links were kept
                record = harvester._client().get_artist(band.id) or record
                harvester.store.put(record)
            article = wiki.article(wiki.title_for(record.get("wikidata")))
            if article:
                out[band.id] = narrative.write_notes(band, article, store=harvester.store)["notes"]
            else:
                out[band.id] = []
        except Exception as e:
            # Wikipedia or the model out of reach: recall the band's last notes, if any
            recalled = harvester.store.latest_notes(band.id)
            out[band.id] = recalled["notes"] if recalled else []
            if recalled and recalled.get("notes"):
                print(f"Recalled stored notes for {band.name} ({type(e).__name__}: {e})")
            else:
                print(f"No notes for {band.name}: {type(e).__name__}: {e}")
        # corrections by hand have the last word: added notes first, rejected ones never
        out[band.id] = narrative.final_notes(harvester.store, band.id, out.get(band.id, []))
    return out


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
