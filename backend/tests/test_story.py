import json
import re
from types import SimpleNamespace

import pytest

from app import story
from app.store import MemoryStore
from tests.test_events import ARTICLE as ALBUM, FIRE, INVENTED, STAGE, WORK
from tests.test_narrative import ARTICLE as BAND_ARTICLE, GOOD, band, verdicts_for


@pytest.fixture(autouse=True)
def store(monkeypatch):
    st = MemoryStore()
    monkeypatch.setattr("app.store.get_store", lambda: st)
    return st


class FakeModel:
    """One writing call (notes and events together) and one check; counts both."""
    def __init__(self, notes, evs, unsupported=()):
        self.writes = self.checks = 0
        outer = self

        class Messages:
            def create(self, **kw):
                if "verdicts" in kw["output_config"]["format"]["schema"]["properties"]:
                    outer.checks += 1
                    body = verdicts_for(kw["messages"][0]["content"], unsupported)
                else:
                    outer.writes += 1
                    outer.prompt = kw["messages"][0]["content"]
                    body = {"notes": notes, "events": evs}
                return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=json.dumps(body))])

        self.beta = SimpleNamespace(messages=Messages())


def ev(e, article="Mill Sessions"):
    return dict(e, article=article)


def test_a_band_is_read_in_one_call_and_checked_in_one(store):
    fake = FakeModel([GOOD], [ev(FIRE), ev(STAGE)])
    got = story.write_story(band(), BAND_ARTICLE, [(WORK, ALBUM)], client=fake)
    assert fake.writes == 1 and fake.checks == 1  # was 10-16 calls a band
    assert [n["text"] for n in got["notes"]] == [GOOD["text"]]
    assert {e["text"] for e in got["events"]} == {FIRE["text"], STAGE["text"]}
    assert all(e["subject"] == "Mill Sessions" for e in got["events"])
    assert "Band X" in fake.prompt and "Frank Zappa" in fake.prompt  # the band's article and its album's, together


def test_the_reading_is_recalled_and_the_band_notes_stay_its_own(store):
    fake = FakeModel([GOOD], [ev(FIRE)])
    story.write_story(band(), BAND_ARTICLE, [(WORK, ALBUM)], client=fake)
    again = story.write_story(band(), BAND_ARTICLE, [(WORK, ALBUM)], client=fake)
    assert fake.writes == 1 and again["events"][0]["text"] == FIRE["text"]  # stored, not asked again
    recalled = store.latest_notes("x")
    assert [n["text"] for n in recalled["notes"]] == [GOOD["text"]]  # its notes, not its events


def test_every_event_is_checked_against_its_own_article(store):
    stray = ev(INVENTED, article="Some Other Album")      # its source is in no article given
    reworded = ev(dict(STAGE, source="At the launch gig in Leeds the stage collapsed under the weight of the speakers."))
    got = story.write_story(band(), BAND_ARTICLE, [(WORK, ALBUM)], client=FakeModel([], [stray, reworded, ev(INVENTED)]))
    assert [e["text"] for e in got["events"]] == [STAGE["text"]]
    assert got["events"][0]["source"] == STAGE["source"]  # the misquote replaced by the article's sentence


def test_a_poster_reads_only_its_top_bands(monkeypatch, store):
    """The rest of the family recalls what's stored: no model."""
    from app import content
    from app.refiner import Band
    bands = [Band(id=f"b{i}", name=f"B{i}", start=1970, end=1980) for i in range(5)]
    monkeypatch.setattr(content, "Refiner", lambda **kw: SimpleNamespace(build=lambda h: SimpleNamespace(
        bands={b.id: b for b in bands})))
    monkeypatch.setattr(content, "NARRATIVE_BANDS", 2)
    read = []
    monkeypatch.setattr(story, "write_story", lambda b, *a, **k: read.append(b.id) or {"notes": [], "events": []})
    import app.wikipedia as W
    monkeypatch.setattr(W.WikipediaClient, "article", lambda self, t: {"title": t, "text": "x"})
    monkeypatch.setattr(W.WikipediaClient, "title_for", lambda self, q: "T")
    records = {b.id: {"mbid": b.id, "name": b.name, "wikidata": "Q", "works": [dict(WORK, length=1)],
                      "events": [{"text": "stored"}] if b.id == "b4" else None} for b in bands}
    stories, evs = content.gather_story(SimpleNamespace(store=store), {"root_id": "b0", "records": records},
                                        {"max_bands": 40}, lambda *a: None)
    assert read == ["b0", "b1"]                              # only the top two read now
    assert evs["b4"] == [{"text": "stored"}] and evs["b3"] == []  # the rest: what's stored, else nothing


def test_an_event_is_checked_against_the_article_that_holds_its_source(store):
    loose = ev(FIRE, article="Mill Sessions album")         # the model's loose name for "Mill Sessions"
    from_band = ev(dict(GOOD, significance=4), article="Band X history")  # from the band's own article
    got = story.write_story(band(), BAND_ARTICLE, [(WORK, ALBUM)], client=FakeModel([], [loose, from_band]))
    assert {e["text"] for e in got["events"]} == {FIRE["text"], GOOD["text"]}
    assert [e["subject"] for e in got["events"] if e["text"] == FIRE["text"]] == ["Mill Sessions"]
