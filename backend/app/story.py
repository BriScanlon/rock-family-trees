"""A band's story in one reading: the notes for its line-ups and the events
from its albums and tours, in one call to the model, then one check.

Asked one article at a time (app/narrative.py, app/events.py) a band took
10-16 calls - notes, then each album and tour, each written then checked,
then a pass to rate the events against each other - and a family's first
poster 150+. Given the band's article with its most written-about albums and
tours together (they fit the 40K context), the model writes the notes and
the events at once and rates the events on one scale for the whole band (the
user's suggestion). Two calls a band: one to write, one to check.

The rules are the notes' rules: Wikipedia is a reference only; every note and
event quotes the passage it came from, which must be in that article (a
misquote is replaced by the article's own sentence), nothing copied, nothing
beyond its source. Stored in Neo4j as two note sets on the band - its notes
(recalled by poster after poster) and its events - keyed on the prompt, the
model, the line-ups and every article's revision.
"""
import hashlib
import json
import os
import re

from app import narrative
from app.events import EVENT_CHARS

CONTEXT_CHARS = int(os.getenv("STORY_CONTEXT_CHARS", "90000"))  # ~25K tokens in, room left to answer
BAND_SHARE = 0.4  # of the context for the band's own article; the rest shared by its albums and tours

SYSTEM = """You write the handwritten notes on a rock family tree, in the style of Pete Frame's Rock Family Trees.

You are given one band's line-ups and, as reference, Wikipedia articles: the band's own article, and articles on some of its albums and tours, each marked with its title. Work only from these articles: each thing you write must be something an article states. Nothing from memory.

Write two kinds of thing.

NOTES, from the band's article: what the line-ups can't show. The tree already draws every line-up and a line for each musician who moved on, so never spend a note saying who joined or left. Tell: what a line-up recorded and anything memorable about making it; famous gigs, tours, incidents, turning points; why someone left, was sacked or came back; how the band formed, split, re-formed or ended. Two or three notes for a line-up with a rich story, one for most, none where the article says nothing of interest. Each under 120 characters.

EVENTS, from the album and tour articles: the moments worth a note of their own. How and where a record was made when it's a story (a fire, a mobile studio, a disaster, a feud); landmark performances (record crowds, famous festivals, legendary or disastrous shows); turning points (a breakthrough, a ban, a controversy, a split on the road). Never: sales figures, certifications, chart positions, reissues, bonus tracks, release formats, track listings, reviews, who joined or left. At most three per article, none if it tells nothing memorable. Each under 160 characters, standing on its own (name the record or tour).

Rate every event against the others, one scale for the whole band:
5: a moment most rock fans know (the Montreux casino fire that gave Deep Purple "Smoke on the Water"). At most one or two, if any.
4: a story the band's fans retell. 3: a notable incident. 2: a detail. 1: trivia. A first show at a venue, a live release or a chart place is 1 or 2.

Write in your own words: never reuse a run of five or more ordinary words from an article (names and titles of records, songs, places and events are fine). Frame's voice: short, dry, factual, sometimes wry; past tense; sentence case; no hype, no speculation; nothing unkind about anyone.

For every note and event give:
- date: when it happened, "YYYY-MM" or "YYYY",
- text,
- source: the sentence of the article that supports it, copied exactly, character for character; two sentences joined by "..." if needed.
For an event, also give article: the title of the article it came from, and significance."""

SCHEMA = {
    "type": "object",
    "properties": {
        "notes": {"type": "array", "items": {
            "type": "object",
            "properties": {"date": {"type": "string"}, "text": {"type": "string"}, "source": {"type": "string"}},
            "required": ["date", "text", "source"], "additionalProperties": False}},
        "events": {"type": "array", "items": {
            "type": "object",
            "properties": {"article": {"type": "string"}, "date": {"type": "string"}, "text": {"type": "string"},
                           "source": {"type": "string"}, "significance": {"type": "integer"}},
            "required": ["article", "date", "text", "source", "significance"], "additionalProperties": False}},
    },
    "required": ["notes", "events"],
    "additionalProperties": False,
}


def prompt_id():
    return hashlib.sha1(f"{SYSTEM}|{narrative.VERIFY}|repair+context|any-article|source-year".encode()).hexdigest()[:8]


def story_key(band_id, articles, lineups, model):
    revisions = "|".join(f"{a['title']}@{a.get('revision')}" for a in articles)
    digest = hashlib.sha1(f"{prompt_id()}|{model}|{revisions}|{lineups}".encode()).hexdigest()[:12]
    return f"{band_id}:story:{digest}"


def _references(band_article, work_articles):
    """The band's lead and history, then each album and tour article, cut to
    share the context (an article's opening - background, recording - is
    where its story is)."""
    band_ref = narrative.reference_text(band_article)[:int(CONTEXT_CHARS * BAND_SHARE)] if band_article else ""
    room = CONTEXT_CHARS - len(band_ref)
    each = room // max(1, len(work_articles))
    works = [(w, a["text"][:each]) for w, a in work_articles]
    return band_ref, works


def write_story(band, band_article, work_articles, client=None, use_cache=True, store=None):
    """{"notes": [...], "events": [...]} for a band, checked. `work_articles`:
    [(work, article)] - its albums and tours with their Wikipedia articles.
    Recalled from the store while nothing it was written from has changed."""
    if store is None:
        from app.store import get_store
        store = get_store()
    model = narrative._model_name(client)
    lineups = narrative.lineups_text(band)
    articles = ([band_article] if band_article else []) + [a for _, a in work_articles]
    key = story_key(band.id, articles, lineups, model)
    if use_cache:
        notes, evs = store.get_notes(f"{key}:notes"), store.get_notes(f"{key}:events")
        if notes is not None and evs is not None:
            return {"notes": notes["notes"], "events": evs["notes"]}
    band_ref, works = _references(band_article, work_articles)
    parts = [f"Band: {band.name}\n\nLine-ups:\n{lineups}"]
    if band_ref:
        parts.append(f"Reference - Wikipedia, \"{band_article['title']}\" (the band):\n<article>\n{band_ref}\n</article>")
    for w, text in works:
        parts.append(f"Reference - Wikipedia, \"{w['title']}\" ({w['kind']}):\n<article>\n{text}\n</article>")
    prompt = "\n\n".join(parts)
    if narrative.BACKEND == "ollama" and client is None:
        raw = narrative._ask_ollama(prompt, SYSTEM, SCHEMA)
    else:
        raw = narrative._ask_claude(prompt, client, SYSTEM, SCHEMA)
    answer = json.loads(raw or "{}")

    # each checked against its own article; a misquoted source replaced by the article's sentence
    notes, dropped = narrative.check(answer.get("notes", []), band_ref, repair=True) if band_ref else ([], [])
    # an event is checked against whichever article holds its source - the model names
    # its article loosely ("Definitely Maybe" for "Definitely Maybe (album)"), or takes
    # it from the band's own; its label only breaks a tie
    band_work = {"title": band_article["title"], "kind": "band", "sitelinks": 0} if band_article else None
    sources = [(w, text) for w, text in works] + ([(band_work, band_ref)] if band_ref else [])
    label = lambda t: re.sub(r"\s*\([^)]*\)|[^a-z0-9]", "", (t or "").lower())
    evs = []
    for e in answer.get("events", []):
        e = dict(e, significance=max(1, min(5, int(e.get("significance") or 1))))
        ordered = sorted(sources, key=lambda wt: label(wt[0]["title"]) != label(e.get("article")))
        for w, text in ordered:
            kept, bad = narrative.check([e], text, max_chars=EVENT_CHARS, repair=True)
            if kept:
                subject = w["title"] if w["kind"] != "band" else None
                evs += [dict(k, subject=subject, kind=w["kind"], sitelinks=w["sitelinks"],
                             context=narrative.context(k["source"], text)) for k in kept]
                break
        else:
            dropped.append(dict(bad[0] if bad else e, article=e.get("article")))

    # one check for the lot: nothing beyond its source (an event with the sentences either side)
    listing = notes + [dict(e, source=e["context"]) for e in evs]
    ok, unsupported = narrative.verify(listing, client)
    ok_texts = {n["text"] for n in ok}
    notes = [n for n in notes if n["text"] in ok_texts]
    evs = [{k: v for k, v in e.items() if k != "context"} for e in evs if e["text"] in ok_texts]
    dropped += unsupported

    meta = {"model": model, "lineups": lineups, "prompt": prompt_id(),
            "source": {"title": band_article["title"] if band_article else None,
                       "url": band_article.get("url") if band_article else None,
                       "revision": band_article.get("revision") if band_article else None}}
    store.put_notes(f"{key}:notes", band.id, dict(meta, notes=notes, dropped=[d for d in dropped if "article" not in d]))
    store.put_notes(f"{key}:events", band.id, dict(meta, notes=evs, dropped=[d for d in dropped if "article" in d]))
    return {"notes": notes, "events": evs}
