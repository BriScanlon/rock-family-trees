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
import hashlib
import json
import os
import re

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

SYSTEM = """You write the handwritten notes on a rock family tree in the style of Pete Frame's Rock Family Trees.

The tree already shows each line-up of a band (who was in it, and when), and who went where. Your notes add what the lines can't: why someone left or was sacked, what a line-up recorded or is remembered for, how a band formed, split or re-formed, notable events.

You are given the band's line-ups and, as reference, its Wikipedia article. Work only from the article: every note must be a fact the article states. Don't add anything from memory, and leave out what the article doesn't support.

Write in your own words - never reuse a phrase of five or more consecutive words from the article (names and record titles excepted). Frame's voice: short, dry, factual, sometimes wry; past tense; sentence case; under 120 characters; no hype or speculation; nothing unkind about anyone, and nothing about private life unless it's central to the band's story (a death, for instance).

For each note give:
- date: when it happened, as "YYYY" or "YYYY-MM" (a date within the line-up it belongs to),
- text: the note,
- source: the passage of the article that supports it, copied exactly, character for character.

Aim for one or two notes for each line-up that the article says something interesting about, and none where it doesn't. Don't restate what the tree already shows (that someone joined or left, with the date) unless you add why."""

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
    """Whether the note shares a run of COPY_RUN words with the article."""
    words = _words(text)
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
        (dropped if reason else kept).append(dict(n, reason=reason) if reason else dict(n, year=_year(n["date"])))
    return kept, dropped


def _model_name(client=None):
    return OLLAMA_MODEL if BACKEND == "ollama" and client is None else MODEL


def _cache_path(band_id, revision, lineups, model):
    key = hashlib.sha1(f"{model}|{revision}|{lineups}".encode()).hexdigest()[:12]
    return os.path.join(CACHE_DIR, "narrative", f"{band_id.replace(':', '_')}-{key}.json")


def write_notes(band, article, client=None, use_cache=True):
    """Checked notes for a band: [{"date", "year", "text", "source"}], plus the
    article reference they came from. Nothing if the model declines.
    `client`: an Anthropic client (or a stand-in, in the tests)."""
    lineups = lineups_text(band)
    model = _model_name(client)
    path = _cache_path(band.id, article.get("revision"), lineups, model)
    if use_cache and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    reference = reference_text(article)
    prompt = (f"Band: {band.name}\n\nLine-ups:\n{lineups}\n\n"
              f"Reference - Wikipedia, \"{article['title']}\":\n<article>\n{reference}\n</article>")
    raw = _ask_ollama(prompt) if BACKEND == "ollama" and client is None else _ask_claude(prompt, client)
    if raw is None:  # declined
        return {"notes": [], "dropped": [], "source": None, "model": model}
    kept, dropped = check(json.loads(raw).get("notes", []), reference)
    result = {"notes": kept, "dropped": dropped, "model": model,
              "source": {"title": article["title"], "url": article.get("url"), "revision": article.get("revision")}}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
    return result


def _ask_ollama(prompt):
    """A local model through Ollama's chat API, held to the same JSON schema."""
    resp = requests.post(f"{OLLAMA_URL}/api/chat", timeout=1800, json={
        "model": OLLAMA_MODEL, "stream": False, "format": SCHEMA,
        "options": {"num_ctx": OLLAMA_CONTEXT, "temperature": 0.3},
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
    })
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def _ask_claude(prompt, client=None):
    import anthropic
    client = client or anthropic.Anthropic()
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=SYSTEM,
        # a model that declines on policy grounds hands over to the fallback
        betas=["server-side-fallback-2026-06-01"],
        fallbacks=[{"model": FALLBACK_MODEL}],
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
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


def main(argv=None):
    """Review a band's notes by hand before they go near a poster:
        python -m app.narrative <musicbrainz band id>
    Prints each line-up, the notes that landed on it with their source
    passages, and anything dropped with the reason."""
    import sys
    from app.pipeline import harvester_for
    from app.refiner import Refiner
    from app.wikipedia import WikipediaClient
    mbid = (argv or sys.argv[1:])[0]
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
