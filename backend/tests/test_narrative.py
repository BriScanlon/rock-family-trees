import json
from types import SimpleNamespace

import pytest

from app import narrative
from app.refiner import Band, Lineup, LineupMember
from app.store import MemoryStore


@pytest.fixture(autouse=True)
def store(monkeypatch):
    """Each test gets its own note store (in memory, standing in for Neo4j)."""
    st = MemoryStore()
    monkeypatch.setattr("app.store.get_store", lambda: st)
    return st

ARTICLE = {
    "title": "Band X", "revision": 42, "url": "https://en.wikipedia.org/wiki/Band_X",
    "text": "Band X are a rock band formed in Leeds in 1970.\n\n"
            "== History ==\n"
            "In 1972 the band recorded their second album at a disused mill in Hebden Bridge, "
            "where the drummer broke both wrists falling off the loading bay. "
            "Singer Ann Able was sacked in 1974 after refusing to tour Japan.\n\n"
            "== Discography ==\nFirst (1971)\n",
}

GOOD = {"date": "1974", "text": "Able sacked for declining the Japanese tour.",
        "source": "Singer Ann Able was sacked in 1974 after refusing to tour Japan."}
COPIED = {"date": "1972", "text": "The drummer broke both wrists falling off the loading bay.",
          "source": "where the drummer broke both wrists falling off the loading bay"}
INVENTED = {"date": "1973", "text": "Headlined Reading, then fell out over the fee.",
            "source": "In 1973 the band headlined the Reading Festival."}
TOO_LONG = {"date": "1972", "text": "Made the second album in an old mill in the Pennines " * 3,
            "source": "In 1972 the band recorded their second album at a disused mill in Hebden Bridge"}
UNDATED = {"date": "the seventies", "text": "Cut record two in a Pennine mill.",
           "source": "In 1972 the band recorded their second album at a disused mill in Hebden Bridge"}


def verdicts_for(listing, unsupported=()):
    """The support check's answer: every note supported except those whose
    text contains one of `unsupported`."""
    import re as _re
    out = []
    for i, text in _re.findall(r"\[(\d+)\] Note: (.*)", listing):
        bad = any(u in text for u in unsupported)
        out.append({"index": int(i), "supported": not bad, "unsupported_claim": "the reason" if bad else ""})
    return {"verdicts": out}


class FakeClaude:
    """Stands in for anthropic.Anthropic(): answers the writing request with
    planted notes and the support check with verdicts, and counts the
    writing calls."""
    def __init__(self, notes, stop_reason="end_turn", unsupported=()):
        self.calls = 0
        outer = self

        class Messages:
            def create(self, **kw):
                if "verdicts" in kw["output_config"]["format"]["schema"]["properties"]:
                    body = verdicts_for(kw["messages"][0]["content"], unsupported)
                else:
                    outer.calls += 1
                    outer.request = kw
                    body = {"notes": notes}
                return SimpleNamespace(stop_reason=stop_reason,
                                       content=[SimpleNamespace(type="text", text=json.dumps(body))])

        self.beta = SimpleNamespace(messages=Messages())


def band():
    lu = lambda n, s, e, sl, el: Lineup(number=n, start=s, end=e, start_label=sl, end_label=el,
                                        members=[LineupMember(person_id="ann", name="Ann Able", roles=["vocals"])])
    return Band(id="x", name="Band X", start=1970, end=1980, lineups=[lu(1, 1970, 1974, "1970", "1974"),
                                                                        lu(2, 1974, 1980, "1974", "1980")])


def test_only_backed_notes_in_our_own_words_survive(tmp_path, monkeypatch):
    monkeypatch.setattr(narrative, "CACHE_DIR", str(tmp_path))
    fake = FakeClaude([GOOD, COPIED, INVENTED, TOO_LONG, UNDATED])
    result = narrative.write_notes(band(), ARTICLE, client=fake)
    assert [n["text"] for n in result["notes"]] == [GOOD["text"]]
    reasons = {d["text"][:20]: d["reason"] for d in result["dropped"]}
    assert "shares" in reasons[COPIED["text"][:20]]
    assert reasons[INVENTED["text"][:20]] == "source not found in the article"
    assert reasons[TOO_LONG["text"][:20]] == "too long"
    assert reasons[UNDATED["text"][:20]] == "no date"
    assert result["source"]["url"].endswith("Band_X")


def test_only_the_history_goes_to_claude_and_the_answer_is_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(narrative, "CACHE_DIR", str(tmp_path))
    fake = FakeClaude([GOOD])
    narrative.write_notes(band(), ARTICLE, client=fake)
    sent = fake.request["messages"][0]["content"]
    assert "Hebden Bridge" in sent and "First (1971)" not in sent  # the discography isn't sent
    assert "1970 to 1974: Ann Able (vocals)" in sent
    assert fake.request["output_config"]["format"]["type"] == "json_schema"
    again = narrative.write_notes(band(), ARTICLE, client=fake)
    assert fake.calls == 1 and again["notes"][0]["text"] == GOOD["text"]
    newer = dict(ARTICLE, revision=43)  # the article changed: write afresh
    narrative.write_notes(band(), newer, client=fake)
    assert fake.calls == 2


def test_a_declined_request_gives_no_notes(tmp_path, monkeypatch):
    monkeypatch.setattr(narrative, "CACHE_DIR", str(tmp_path))
    result = narrative.write_notes(band(), ARTICLE, client=FakeClaude([GOOD], stop_reason="refusal"))
    assert result["notes"] == []


def test_a_local_model_through_ollama_gets_the_same_schema_and_checks(tmp_path, monkeypatch):
    monkeypatch.setattr(narrative, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(narrative, "BACKEND", "ollama")
    sent = {}

    def post(url, json=None, timeout=None):
        if "verdicts" in json["format"]["properties"]:
            body = verdicts_for(json["messages"][1]["content"])
        else:
            sent.update(url=url, body=json)
            body = {"notes": [GOOD, COPIED]}
        return SimpleNamespace(raise_for_status=lambda: None,
                               json=lambda: {"message": {"content": __import__("json").dumps(body)}})

    monkeypatch.setattr(narrative.requests, "post", post)
    result = narrative.write_notes(band(), ARTICLE)
    assert sent["url"].endswith("/api/chat") and sent["body"]["format"] == narrative.SCHEMA
    assert sent["body"]["options"]["num_ctx"] >= 32768  # the whole article must fit
    assert [n["text"] for n in result["notes"]] == [GOOD["text"]]  # the copied note is still caught
    assert result["model"] == narrative.OLLAMA_MODEL


def test_a_source_stitched_from_passages_counts_if_every_piece_is_there(tmp_path, monkeypatch):
    # models quote "A... B" from two places: true notes were being dropped
    monkeypatch.setattr(narrative, "CACHE_DIR", str(tmp_path))
    stitched = dict(GOOD, source="In 1972 the band recorded their second album... "
                                 "Singer Ann Able was sacked in 1974 after refusing to tour Japan.")
    forged = dict(GOOD, text="Able quit to go solo.", source="In 1972 the band recorded their second album... "
                                                              "Singer Ann Able left in 1974 to go solo.")
    result = narrative.write_notes(band(), ARTICLE, client=FakeClaude([stitched, forged]))
    assert [n["source"] for n in result["notes"]] == [stitched["source"]]
    assert result["dropped"][0]["reason"] == "source not found in the article"


def test_a_note_going_beyond_its_source_is_dropped(tmp_path, monkeypatch):
    # "Evans and Simper dismissed for not fitting the new direction": the
    # source only says they were dismissed - the reason came from nowhere
    monkeypatch.setattr(narrative, "CACHE_DIR", str(tmp_path))
    embellished = dict(GOOD, date="1974", text="Able sacked for declining Japan, having lost her voice.")
    result = narrative.write_notes(band(), ARTICLE, client=FakeClaude([GOOD, embellished], unsupported=("voice",)))
    assert [n["text"] for n in result["notes"]] == [GOOD["text"]]
    assert result["dropped"][0]["reason"].startswith("goes beyond its source")


def test_names_and_titles_are_not_copying():
    words = narrative._words("The album Perfect Strangers and The House of Blue Light were released, "
                             "after the drummer broke both wrists falling off the loading bay")
    assert not narrative._copies("Back as Mark II: Perfect Strangers and The House of Blue Light.", words)
    assert narrative._copies("The drummer broke both wrists falling off the loading bay.", words)


def test_notes_are_stored_and_recalled_not_rewritten(store):
    # written once and kept (dropped ones too, with the reason); a later poster
    # recalls them - and if Wikipedia or the model is out of reach, the band's
    # latest notes can still be recalled
    fake = FakeClaude([GOOD, COPIED])
    first = narrative.write_notes(band(), ARTICLE, client=fake)
    again = narrative.write_notes(band(), ARTICLE, client=fake)
    assert fake.calls == 1 and again["notes"] == first["notes"]
    key = narrative.notes_key("x", 42, narrative.lineups_text(band()), narrative.MODEL)
    kept = store.get_notes(key)
    assert [n["text"] for n in kept["notes"]] == [GOOD["text"]]
    assert kept["dropped"][0]["reason"].startswith("shares")
    assert store.latest_notes("x")["notes"][0]["text"] == GOOD["text"]


def test_new_prompts_write_afresh_and_the_old_notes_stay(store, monkeypatch):
    fake = FakeClaude([GOOD])
    narrative.write_notes(band(), ARTICLE, client=fake)
    monkeypatch.setattr(narrative, "SYSTEM", narrative.SYSTEM + " Be wry.")
    narrative.write_notes(band(), ARTICLE, client=fake)
    assert fake.calls == 2 and len(store.notes) == 2  # both writings kept, recallable


def test_notes_start_with_a_capital():
    kept, _ = narrative.check([dict(GOOD, text="able sacked for declining the Japanese tour.")], ARTICLE["text"])
    assert kept[0]["text"].startswith("Able")


def test_corrections_by_hand_have_the_last_word(store):
    # a person can add a note (shown first) and reject a generated one for good,
    # even after the notes are rewritten
    fake = FakeClaude([GOOD])
    generated = narrative.write_notes(band(), ARTICLE, client=fake)["notes"]
    narrative.add_note(store, "x", "1971", "Played the Leeds Poly union bar every Friday.")
    narrative.reject_note(store, "x", "Able sacked")
    shown = narrative.final_notes(store, "x", generated)
    assert [n["text"] for n in shown] == ["Played the Leeds Poly union bar every Friday."]
    assert shown[0]["year"] == 1971.5 and shown[0]["source"] == "added by hand"
    assert store.latest_notes("x")["model"] != narrative.CURATOR  # recall never picks the hand-made set
    import pytest as _pytest
    with _pytest.raises(ValueError):
        narrative.add_note(store, "x", "the seventies", "Undated.")


def test_the_sources_year_wins_over_the_models():
    article = "In August 1996 the band played two nights at Knebworth to 125,000 people each night."
    note = {"date": "1997-08", "text": "Two nights at Knebworth drew 125,000 apiece.",
            "source": "In August 1996 the band played two nights at Knebworth to 125,000 people each night."}
    kept, _ = narrative.check([note], article)
    assert kept[0]["date"] == "1996" and int(kept[0]["year"]) == 1996
