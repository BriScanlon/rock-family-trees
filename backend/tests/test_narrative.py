import json
from types import SimpleNamespace

from app import narrative
from app.refiner import Band, Lineup, LineupMember

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


class FakeClaude:
    """Stands in for anthropic.Anthropic(): returns planted notes as the
    structured-output JSON and counts the calls."""
    def __init__(self, notes, stop_reason="end_turn"):
        self.calls = 0
        outer = self

        class Messages:
            def create(self, **kw):
                outer.calls += 1
                outer.request = kw
                return SimpleNamespace(stop_reason=stop_reason,
                                       content=[SimpleNamespace(type="text", text=json.dumps({"notes": notes}))])

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
        sent.update(url=url, body=json)
        return SimpleNamespace(raise_for_status=lambda: None,
                               json=lambda: {"message": {"content": __import__("json").dumps({"notes": [GOOD, COPIED]})}})

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
