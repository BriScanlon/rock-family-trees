"""Events: the moments in a band's history worth a note of their own - the
fire at Montreux that gave Deep Purple "Smoke on the Water", Iron Maiden at
Rock in Rio - read from the Wikipedia articles on the band's albums and tours
(the user's idea: they tell the story and fill the page).

Each event is a dated note node on the album or tour it came from (Neo4j:
Band -RELEASED-> Album / -TOURED-> Tour -HAS_NOTES-> NoteSet -INCLUDES-> Note),
written in our own words from the article as a reference only, checked just
as the band's notes are (app/narrative.py: the source passage must be in the
article, nothing copied, nothing beyond the source), and recalled rather than
rewritten. The layout (app/grid.py) gives each its own small block beside the
line-up it happened to, where there's room, most significant first.
"""
import hashlib
import json
import os

from app import narrative

EVENT_BANDS = int(os.getenv("EVENT_BANDS", "12"))    # top bands whose albums and tours a poster waits for
EVENT_ALBUMS = int(os.getenv("EVENT_ALBUMS", "4"))   # a band's longest album articles read for a poster
EVENT_ALBUMS_FULL = int(os.getenv("EVENT_ALBUMS_FULL", "6"))  # and in the background, for every band
EVENT_TOURS = int(os.getenv("EVENT_TOURS", "2"))     # and tours
EVENT_CHARS = 160                                    # an event block holds a little more than a note
MIN_SIGNIFICANCE = int(os.getenv("EVENT_MIN_SIGNIFICANCE", "3"))  # placed on the poster from this up
ARTICLE_CHARS = 60000                                # tour articles run long (set lists): enough for the story

SYSTEM = """You pick out the moments worth telling from a Wikipedia article about one album or tour by a rock band, for a rock family tree in the style of Pete Frame's Rock Family Trees. Each becomes a small note beside the line-up it happened to.

Worth telling:
- how and where a record was made, when it's a story (a fire, a mobile studio, a famous building, a disaster, a feud),
- landmark performances: record crowds, famous festivals, legendary or disastrous shows,
- turning points: a breakthrough, a first number one, a ban, a controversy, a split on the road.

Never worth telling: sales figures and certifications, chart positions, reissues, bonus tracks and release formats, track listings, reviews, and who joined or left (the tree draws that). If the article's story is only those, give no events.

Work only from the article: each event must be something the article states. Nothing from memory.

Write in your own words: never reuse a run of five or more ordinary words from the article (names and titles of records, songs, places and events are fine). Frame's voice: short, dry, factual, sometimes wry; past tense; sentence case; under 160 characters; standing on its own (name the record or tour); nothing unkind about anyone.

For each event give:
- date: when it happened, "YYYY-MM" or "YYYY",
- text: the note,
- source: the sentence of the article that supports it, copied exactly, character for character; two sentences joined by "..." if needed,
- significance: 1 to 5. 5: a moment most rock fans know (the Montreux fire behind Smoke on the Water). 4: a story fans of the band retell. 3: a notable incident. 2 or 1: a detail. Be sparing with 4 and 5.

At most three events, the most memorable first. None if the article tells nothing memorable."""

SCHEMA = {
    "type": "object",
    "properties": {
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "date": {"type": "string"},
                    "text": {"type": "string"},
                    "source": {"type": "string"},
                    "significance": {"type": "integer"},
                },
                "required": ["date", "text", "source", "significance"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["events"],
    "additionalProperties": False,
}


CHECKS = "repair+context"  # how events are checked: a change here means reading afresh


def prompt_id():
    return hashlib.sha1(f"{SYSTEM}|{narrative.VERIFY}|{CHECKS}".encode()).hexdigest()[:8]


def events_key(work, revision, model):
    """One reading of an album's or tour's article: the prompts, the model and
    the article revision."""
    digest = hashlib.sha1(f"{prompt_id()}|{model}|{revision}".encode()).hexdigest()[:12]
    return f"event:{work['wikidata']}:{digest}"


def choose_works(works, albums=EVENT_ALBUMS, tours=EVENT_TOURS):
    """The band's most written-about albums and tours - the longest English
    articles, then the most Wikipedias covering them: where its famous
    moments are told."""
    ranked = sorted(works, key=lambda w: (-(w.get("length") or 0), -w["sitelinks"]))
    pick = [w for w in ranked if w["kind"] == "album"][:albums] + [w for w in ranked if w["kind"] == "tour"][:tours]
    return pick


def write_events(band, work, article, client=None, use_cache=True, store=None):
    """Checked events from one album's or tour's article:
    {"notes": [{"date", "year", "text", "source", "significance"}], "subject": work, ...}.
    Every reading is kept in the store and recalled rather than rewritten."""
    if store is None:
        from app.store import get_store
        store = get_store()
    model = narrative._model_name(client)
    key = events_key(work, article.get("revision"), model)
    if use_cache:
        stored = store.get_notes(key)
        if stored is not None:
            return dict(stored, subject=work)
    reference = article["text"][:ARTICLE_CHARS]
    prompt = (f"Band: {band.name}\n{work['kind'].title()}: {work['title']}\n\n"
              f"Reference - Wikipedia, \"{article['title']}\":\n<article>\n{reference}\n</article>")
    if narrative.BACKEND == "ollama" and client is None:
        raw = narrative._ask_ollama(prompt, SYSTEM, SCHEMA)
    else:
        raw = narrative._ask_claude(prompt, client, SYSTEM, SCHEMA)
    if raw is None:
        return {"notes": [], "dropped": [], "subject": work, "model": model}
    found = json.loads(raw).get("events", [])
    for e in found:
        e["significance"] = max(1, min(5, int(e.get("significance") or 1)))
    kept, dropped = narrative.check(found, reference, max_chars=EVENT_CHARS, repair=True)
    # checked against the source and the sentences either side of it
    widened = [dict(n, source=narrative.context(n["source"], reference)) for n in kept]
    ok, unsupported = narrative.verify(widened, client)
    ok_texts = {n["text"] for n in ok}
    kept = [n for n in kept if n["text"] in ok_texts]
    result = {"notes": kept, "dropped": dropped + unsupported, "model": model, "prompt": prompt_id(),
              "subject": work, "lineups": None,
              "source": {"title": article["title"], "url": article.get("url"), "revision": article.get("revision")}}
    store.put_notes(key, band.id, result)
    return result


def same_story(event_text, story_texts):
    """Whether an event is already told in the band's notes (the Montreux fire
    in both Machine Head's article and Deep Purple's): most of its telling
    words shared with one of them."""
    words = lambda t: {w for w in narrative._words(t) if len(w) >= 4}
    ew = words(event_text)
    for s in story_texts:
        sw = words(s)
        if ew and sw and len(ew & sw) / min(len(ew), len(sw)) >= 0.5:
            return True
    return False
