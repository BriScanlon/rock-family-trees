"""The short handwritten notes of Frame's trees ("Sacked after a punch-up in
Hamburg", "Recorded 'Machine Head' in Montreux"), written fresh by Claude with
the band's Wikipedia article as the reference.

Guardrails (issue #5): these go on posters people pay for, so nothing is
invented and nothing is copied.
- Every note names its source: the passage of the article that backs it.
  A note whose passage isn't in the article is dropped.
- Wikipedia's words stay Wikipedia's (CC BY-SA): a note sharing a run of
  COPY_RUN or more words with the article is dropped.
- Each note is dated, not tied to a line-up number, so it lands on whichever
  line-up covers that date however the band is condensed for the sheet.

Notes are cached per band, article revision and model: one call per band
until its article changes.

The model is a setting: NARRATIVE_BACKEND=ollama (a local model, e.g. Qwen
on the LAN: OLLAMA_URL, OLLAMA_MODEL) or anthropic (Claude, needs
ANTHROPIC_API_KEY). The prompt, schema and checks are the same for both.
"""
import contextlib
import hashlib
import json
import os
import re
import threading

import requests

BACKEND = os.getenv("NARRATIVE_BACKEND", "ollama" if os.getenv("OLLAMA_URL") else "anthropic")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
# rftg-qwen3 is qwen3:14b with its full native 40K context set in the model (ollama/Modelfile)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "rftg-qwen3")
OLLAMA_CONTEXT = int(os.getenv("OLLAMA_CONTEXT", "40960"))  # asked for too, in case a base model is used
MODEL = "claude-opus-5"
FALLBACK_MODEL = "claude-opus-4-8"
MAX_NOTE_CHARS = 120
COPY_RUN = 6            # this many words in a row, shared with the article, is copying
CACHE_DIR = os.getenv("CACHE_DIR", "./cache")
LOCK_DIR = os.getenv("LOCK_DIR", CACHE_DIR)  # shared by every worker process and container

SYSTEM = """You write the handwritten notes on a rock family tree, in the style of Pete Frame's Rock Family Trees.

The tree already draws every line-up of the band - who was in it and when - and a line for each musician who moved on. So never spend a note just saying who joined or left: the drawing shows that. Your notes tell what the lines can't:
- what a line-up recorded, and anything memorable about making it (where, how, what came of it),
- famous gigs, tours, incidents and turning points,
- why someone left, was sacked or came back,
- how the band formed, split, re-formed or ended.

You are given the band's line-ups and, as reference, its Wikipedia article. Work only from the article: each note must be something the article states. Nothing from memory, and nothing the article doesn't support.

Write in your own words: never reuse a run of five or more ordinary words from the article (names and titles of records and songs are fine to use). Frame's voice: short, dry, factual, sometimes wry; past tense; sentence case; under 120 characters; no hype, no speculation; nothing unkind about anyone; private life only where it's central to the story (a death, say).

For each note give:
- date: when it happened, "YYYY" or "YYYY-MM", within the line-up it belongs to,
- text: the note,
- source: the sentence of the article that supports it, copied exactly, character for character. If the note draws on two sentences, give both, joined by "...".

Be generous where the article is: two or three notes for a line-up with a rich story, one for most, none where the article says nothing of interest."""

SCHEMA = {
    "type": "object",
    "properties": {
        "notes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "date": {"type": "string"},
                    "text": {"type": "string"},
                    "source": {"type": "string"},
                },
                "required": ["date", "text", "source"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["notes"],
    "additionalProperties": False,
}


def reference_text(article):
    """The article's lead and History section: where line-up changes are told.
    (Discography, legacy and awards sections add cost, not notes.)"""
    text = article["text"]
    sections = re.split(r"\n(?===\s[^=].*?\s==\n)", "\n" + text)  # at each "== Section =="
    lead = sections[0].strip()
    history = [s.strip() for s in sections[1:] if re.match(r"==\s*(History|Career|Biography)\b", s.strip(), re.I)]
    return "\n\n".join([lead] + history) if history else text


def lineups_text(band):
    out = []
    for lu in band.lineups:
        members = ", ".join(f"{m.name} ({'/'.join(m.roles[:2]) or '?'})" for m in lu.members)
        out.append(f"{lu.start_label} to {lu.end_label}: {members}")
    return "\n".join(out)


def _norm(s):
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s).strip().lower()


def _words(s):
    return re.findall(r"[a-z0-9']+", _norm(s))


def _copies(text, source_words):
    """Whether the note shares a run of COPY_RUN ordinary words with the
    article. Names and titles don't count: capitalised words and anything in
    quotes are masked (a run through "Perfect Strangers and The House of Blue
    Light" isn't copying)."""
    masked = re.sub(r'"[^"]*"|“[^”]*”', " # ", text)
    masked = re.sub(r"(?<![.!?]\s)(?<!^)\b[A-Z][\w'’-]*", " # ", masked)
    words = [w if w else "#" for w in re.findall(r"[a-z0-9']+|#", _norm(masked))]
    runs = {tuple(words[i:i + COPY_RUN]) for i in range(len(words) - COPY_RUN + 1)}
    return any(tuple(source_words[i:i + COPY_RUN]) in runs for i in range(len(source_words) - COPY_RUN + 1))


def _year(date):
    m = re.match(r"(\d{4})(?:-(\d{1,2}))?", date or "")
    if not m:
        return None
    return int(m.group(1)) + ((int(m.group(2)) - 1) / 12 if m.group(2) else 0.5)


def _backed(source, article_norm):
    """The source is in the article word for word: one passage, or several
    stitched together with "..." (each piece must be there, and substantial)."""
    pieces = [p for p in (_norm(x) for x in re.split(r"\.\.\.|…", source)) if p]
    return bool(pieces) and sum(len(p) for p in pieces) >= 20 and all(
        len(p) >= 12 and p.strip(" .,;") in article_norm for p in pieces)


def check(notes, article_text):
    """Keep only notes that are backed by the article, in our own words,
    short enough and dated. Returns (kept, dropped with reasons)."""
    article_norm = _norm(article_text)
    article_words = _words(article_text)
    kept, dropped = [], []
    for n in notes:
        reason = None
        if len(n.get("text", "")) > MAX_NOTE_CHARS:
            reason = "too long"
        elif _year(n.get("date")) is None:
            reason = "no date"
        elif not _backed(n.get("source", ""), article_norm):
            reason = "source not found in the article"
        elif _copies(n["text"], article_words):
            reason = f"shares {COPY_RUN}+ words with the article"
        if not reason and n["text"][:1].islower():  # sentence case, whatever the model did
            n = dict(n, text=n["text"][0].upper() + n["text"][1:])
        (dropped if reason else kept).append(dict(n, reason=reason) if reason else dict(n, year=_year(n["date"])))
    return kept, dropped


def _model_name(client=None):
    return OLLAMA_MODEL if BACKEND == "ollama" and client is None else MODEL


def prompt_id():
    """Fingerprint of the instructions notes are written and checked with:
    improving the prompts means writing afresh (older writings stay stored)."""
    return hashlib.sha1(f"{SYSTEM}|{VERIFY}".encode()).hexdigest()[:8]


def notes_key(band_id, revision, lineups, model):
    """One writing of a band's notes: the prompts, the model, the article
    revision and the line-ups it was written from. Any of them changing means
    writing afresh."""
    digest = hashlib.sha1(f"{prompt_id()}|{model}|{revision}|{lineups}".encode()).hexdigest()[:12]
    return f"{band_id}:{digest}"


def write_notes(band, article, client=None, use_cache=True, store=None):
    """Checked notes for a band: [{"date", "year", "text", "source"}], plus the
    article reference they came from. Nothing if the model declines.
    Every writing is kept in the store (Neo4j: Band -HAS_NOTES-> NoteSet
    -INCLUDES-> Note, dropped notes too, with the reason) and recalled rather
    than rewritten. `client`: an Anthropic client (or a stand-in, in the tests)."""
    if store is None:
        from app.store import get_store
        store = get_store()
    lineups = lineups_text(band)
    model = _model_name(client)
    key = notes_key(band.id, article.get("revision"), lineups, model)
    if use_cache:
        stored = store.get_notes(key)
        if stored is not None:
            return stored
    reference = reference_text(article)
    prompt = (f"Band: {band.name}\n\nLine-ups:\n{lineups}\n\n"
              f"Reference - Wikipedia, \"{article['title']}\":\n<article>\n{reference}\n</article>")
    raw = _ask_ollama(prompt) if BACKEND == "ollama" and client is None else _ask_claude(prompt, client)
    if raw is None:  # declined
        return {"notes": [], "dropped": [], "source": None, "model": model}
    kept, dropped = check(json.loads(raw).get("notes", []), reference)
    kept, unsupported = verify(kept, client)
    result = {"notes": kept, "dropped": dropped + unsupported, "model": model, "lineups": lineups,
              "prompt": prompt_id(),
              "source": {"title": article["title"], "url": article.get("url"), "revision": article.get("revision")}}
    store.put_notes(key, band.id, result)
    return result


VERIFY = """You check the notes written for a rock family tree against their sources.

For each note you get its text and the source passage it was written from. Decide whether the source states everything the note claims - every fact, reason and detail. A note is supported only if nothing in it goes beyond its source: an added reason, event, number, place or judgement makes it unsupported, even if it happens to be true. Rewording is fine; so is leaving things out.

For each note, give its index, whether it is supported, and if not, the claim the source doesn't support."""

VERIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "supported": {"type": "boolean"},
                    "unsupported_claim": {"type": "string"},
                },
                "required": ["index", "supported", "unsupported_claim"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["verdicts"],
    "additionalProperties": False,
}


def verify(notes, client=None):
    """Second look: keep a note only if its source states everything it
    claims (the source was checked to be in the article; this checks the note
    doesn't go beyond it). Returns (kept, dropped with reasons)."""
    if not notes:
        return [], []
    listing = "\n\n".join(f"[{i}] Note: {n['text']}\n    Source: {n['source']}" for i, n in enumerate(notes))
    ask = _ask_ollama if BACKEND == "ollama" and client is None else (lambda p, s, f: _ask_claude(p, client, s, f))
    raw = ask(listing, VERIFY, VERIFY_SCHEMA)
    verdicts = {v["index"]: v for v in json.loads(raw or "{}").get("verdicts", [])}
    kept, dropped = [], []
    for i, n in enumerate(notes):
        v = verdicts.get(i)
        if v and v["supported"]:
            kept.append(n)
        else:  # unsupported, or not judged at all: leave it out
            claim = (v or {}).get("unsupported_claim") or "not confirmed by the check"
            dropped.append(dict(n, reason=f"goes beyond its source: {claim}"))
    return kept, dropped


_local_lock = threading.Lock()


@contextlib.contextmanager
def one_at_a_time():
    """The local model serves one request at a time: two at once would need
    twice the memory for the 40K context, more than the GPU has. Poster jobs
    run in parallel (worker processes, and the API in inline mode), so the
    queue is a lock file on the shared data volume, held for each request."""
    with _local_lock:
        try:
            import fcntl
        except ImportError:  # Windows (tests, local runs): the thread lock is the queue
            yield
            return
        os.makedirs(LOCK_DIR, exist_ok=True)
        with open(os.path.join(LOCK_DIR, "ollama.lock"), "w") as f:
            fcntl.flock(f, fcntl.LOCK_EX)  # waits for the request in progress
            try:
                yield
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)


def _ask_ollama(prompt, system=SYSTEM, schema=SCHEMA):
    """A local model through Ollama's chat API, held to the JSON schema,
    one request at a time."""
    with one_at_a_time():
        resp = requests.post(f"{OLLAMA_URL}/api/chat", timeout=1800, json={
            "model": OLLAMA_MODEL, "stream": False, "format": schema,
            "options": {"num_ctx": OLLAMA_CONTEXT, "temperature": 0.3},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        })
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def _ask_claude(prompt, client=None, system=SYSTEM, schema=SCHEMA):
    import anthropic
    client = client or anthropic.Anthropic()
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=system,
        # a model that declines on policy grounds hands over to the fallback
        betas=["server-side-fallback-2026-06-01"],
        fallbacks=[{"model": FALLBACK_MODEL}],
        output_config={"format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": prompt}],
    )
    if response.stop_reason == "refusal":
        return None
    return next((b.text for b in response.content if b.type == "text"), "{}")


def lineup_for(lineups, year):
    """The one line-up a note dated `year` belongs on: the one running then,
    else the nearest (a year-only date sits mid-year)."""
    running = [lu for lu in lineups if lu.start <= year < lu.end]
    if running:
        return running[-1]
    return min(lineups, key=lambda lu: min(abs(year - lu.start), abs(year - lu.end)), default=None)


# -- corrections by hand --------------------------------------------------
# A person has the last word: notes added by hand always show (first), and a
# generated note rejected by hand never shows again, however often the notes
# are rewritten. Kept in the store as the band's "curator" note set.
CURATOR = "curator"


def _curated_key(band_id):
    return f"{band_id}:{CURATOR}"


def curated(store, band_id):
    return store.get_notes(_curated_key(band_id)) or {"notes": [], "dropped": [], "model": CURATOR}


def add_note(store, band_id, date, text):
    """Add a note by hand: shown on the line-up covering `date`, before any other."""
    if _year(date) is None:
        raise ValueError(f"Date must be YYYY or YYYY-MM, not {date!r}")
    cur = curated(store, band_id)
    cur["notes"] = [n for n in cur["notes"] if n["text"] != text] + [
        {"date": date, "year": _year(date), "text": text, "source": "added by hand"}]
    store.put_notes(_curated_key(band_id), band_id, dict(cur, model=CURATOR))
    return cur


def reject_note(store, band_id, start_of_text, reason="rejected by hand"):
    """Reject every generated note starting with `start_of_text`, for good."""
    cur = curated(store, band_id)
    cur["dropped"] = [d for d in cur["dropped"] if d["text"] != start_of_text] + [
        {"text": start_of_text, "reason": reason}]
    store.put_notes(_curated_key(band_id), band_id, dict(cur, model=CURATOR))
    return cur


def final_notes(store, band_id, generated):
    """What a poster shows: notes added by hand, then the generated ones not
    rejected by hand."""
    cur = curated(store, band_id)
    rejected = [d["text"] for d in cur["dropped"]]
    return list(cur["notes"]) + [n for n in generated if not any(n["text"].startswith(r) for r in rejected)]


def main(argv=None):
    """Review a band's notes, and correct them by hand:
        python -m app.narrative <band id>                        write (or recall) and review
        python -m app.narrative show <band id>                   what a poster would show, with status
        python -m app.narrative add <band id> <YYYY[-MM]> <text>  add a note by hand
        python -m app.narrative reject <band id> <start of note>  never show that generated note
    The review prints each line-up, the notes that landed on it with their
    source passages, and anything dropped with the reason."""
    import sys
    from app.pipeline import harvester_for
    from app.refiner import Refiner
    from app.wikipedia import WikipediaClient
    args = list(argv or sys.argv[1:])
    if args and args[0] in ("add", "reject", "show"):
        from app.store import get_store
        store = get_store()
        command, band_id = args[0], args[1]
        if command == "add":
            add_note(store, band_id, args[2], " ".join(args[3:]))
        elif command == "reject":
            reject_note(store, band_id, " ".join(args[2:]))
        latest = store.latest_notes(band_id) or {"notes": []}
        rejected = [d["text"] for d in curated(store, band_id)["dropped"]]
        for n in curated(store, band_id)["notes"]:
            print(f"  by hand   {n['date']:>7}  {n['text']}")
        for n in latest["notes"]:
            status = "REJECTED " if any(n["text"].startswith(r) for r in rejected) else "generated"
            print(f"  {status} {n['date']:>7}  {n['text']}")
        return
    mbid = args[0]
    harvester = harvester_for(mbid)
    record = harvester.fetch(mbid)
    if record.get("wikidata") is None:  # cached before Wikidata links were kept
        record = harvester._client().get_artist(mbid)
    tree = Refiner().build(harvester.harvest(mbid, depth=1))
    band = tree.bands[mbid]
    wiki = WikipediaClient()
    article = wiki.article(wiki.title_for(record.get("wikidata")))
    if not article:
        print(f"No English Wikipedia article linked for {band.name}")
        return
    result = write_notes(band, article)
    print(f"{band.name}: {len(result['notes'])} notes kept, {len(result['dropped'])} dropped  "
          f"(from {article['url']}, revision {article['revision']})\n")
    placed = {id(n): lineup_for(band.lineups, n["year"]) for n in result["notes"]}
    for lu in band.lineups:
        print(f"{lu.start_label} to {lu.end_label}: {', '.join(m.name for m in lu.members)}")
        for n in result["notes"]:
            if placed[id(n)] is lu:
                print(f"    {n['date']:>7}  {n['text']}\n             source: \"{n['source'][:160]}\"")
    for d in result["dropped"]:
        print(f"  DROPPED ({d['reason']}): {d['text']}")


if __name__ == "__main__":
    main()
