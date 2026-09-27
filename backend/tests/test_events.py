import json
import re
from types import SimpleNamespace

import pytest

from app import events
from app.store import MemoryStore
from tests.test_narrative import band, verdicts_for


@pytest.fixture(autouse=True)
def store(monkeypatch):
    st = MemoryStore()
    monkeypatch.setattr("app.store.get_store", lambda: st)
    return st


WORK = {"wikidata": "Q1", "kind": "album", "title": "Mill Sessions", "date": "1972-05-01", "sitelinks": 30}
ARTICLE = {
    "title": "Mill Sessions", "revision": 7, "url": "https://en.wikipedia.org/wiki/Mill_Sessions",
    "text": "Mill Sessions is the second album by Band X, released in 1972.\n\n"
            "== Recording ==\n"
            "The album was recorded at a disused mill in Hebden Bridge after the band's studio burned down "
            "during a Frank Zappa concert next door. "
            "At the launch show in Leeds the stage collapsed under the weight of the speakers.\n",
}
FIRE = {"date": "1972-01", "significance": 5, "text": "Their studio burnt out mid-Zappa gig next door, so Mill Sessions was cut in a Pennine mill.",
        "source": "The album was recorded at a disused mill in Hebden Bridge after the band's studio burned down during a Frank Zappa concert next door."}
STAGE = {"date": "1972-06", "significance": 3, "text": "The Leeds launch gig ended when the stage gave way beneath the PA.",
         "source": "At the launch show in Leeds the stage collapsed under the weight of the speakers."}
INVENTED = {"date": "1972", "significance": 4, "text": "Mill Sessions went gold in a week.",
            "source": "Mill Sessions went gold within a week of release."}


class FakeModel:
    def __init__(self, found, unsupported=()):
        self.calls, outer = 0, self

        class Messages:
            def create(self, **kw):
                if "verdicts" in kw["output_config"]["format"]["schema"]["properties"]:
                    body = verdicts_for(kw["messages"][0]["content"], unsupported)
                else:
                    outer.calls += 1
                    outer.request = kw
                    body = {"events": found}
                return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=json.dumps(body))])

        self.beta = SimpleNamespace(messages=Messages())


def test_events_are_checked_like_notes_and_recalled(store):
    fake = FakeModel([FIRE, STAGE, INVENTED])
    got = events.write_events(band(), WORK, ARTICLE, client=fake)
    assert [e["text"] for e in got["notes"]] == [FIRE["text"], STAGE["text"]]  # the invented one had no source
    assert got["notes"][0]["significance"] == 5 and abs(got["notes"][0]["year"] - 1972.0) < 1e-9
    again = events.write_events(band(), WORK, ARTICLE, client=fake)
    assert fake.calls == 1 and again["notes"][0]["text"] == FIRE["text"]  # stored, not asked again
    assert store.latest_notes("x") is None  # an album's events aren't the band's own notes


def test_the_article_is_about_one_album_of_the_band(store):
    fake = FakeModel([])
    events.write_events(band(), WORK, ARTICLE, client=fake)
    prompt = fake.request["messages"][0]["content"]
    assert "Band: Band X" in prompt and "Album: Mill Sessions" in prompt and "Frank Zappa" in prompt


def test_the_longest_album_and_tour_articles_are_read():
    # Fireball is covered by as many Wikipedias as Machine Head, but Machine
    # Head's article (the Montreux fire) is twice as long
    works = [{"wikidata": f"Q{i}", "kind": k, "title": t, "date": None, "sitelinks": s, "length": n}
             for i, (k, t, s, n) in enumerate([
                 ("album", "Fireball", 30, 23531), ("album", "Machine Head", 30, 50390),
                 ("album", "Burn", 26, 56079), ("album", "Shades", 33, 49062), ("album", "Who Do We", 27, 9000),
                 ("tour", "Songs That Built Rock", 5, 24542), ("tour", "Secret USA", 3, 4000), ("tour", "Debut", 2, 6000)])]
    chosen = events.choose_works(works, albums=3, tours=2)
    assert [w["title"] for w in chosen] == ["Burn", "Machine Head", "Shades", "Songs That Built Rock", "Debut"]


def test_article_lengths_follow_redirects():
    from app.wikipedia import WikipediaClient

    class Session:
        headers = {}

        def get(self, url, params=None, timeout=None):
            body = {"query": {"redirects": [{"from": "Machine Head", "to": "Machine Head (album)"}],
                              "pages": [{"title": "Machine Head (album)", "length": 50390},
                                        {"title": "Fireball (album)", "length": 23531}]}}
            return SimpleNamespace(raise_for_status=lambda: None, json=lambda: body)

    got = WikipediaClient(min_interval=0, session=Session()).lengths(["Machine Head", "Fireball (album)"])
    assert got == {"Machine Head": 50390, "Fireball (album)": 23531}


def test_an_event_already_in_the_bands_notes_is_not_told_twice():
    story = "A fire at the Montreux casino during Zappa's show inspired Smoke on the Water."
    assert events.same_story("Montreux casino burnt down in Zappa's show; the fire became Smoke on the Water.", [story])
    assert not events.same_story("The California Jam drew 250,000 and Blackmore smashed a camera.", [story])


def test_works_come_from_wikidata_most_written_about_first():
    from app.wikipedia import WikipediaClient
    rows = [
        {"item": {"value": "http://www.wikidata.org/entity/Q2"}, "t": {"value": "http://www.wikidata.org/entity/Q482994"},
         "date": {"value": "1972-03-25T00:00:00Z"}, "links": {"value": "30"},
         "article": {"value": "https://en.wikipedia.org/wiki/Machine_Head_(album)"}},
        {"item": {"value": "http://www.wikidata.org/entity/Q2"}, "t": {"value": "http://www.wikidata.org/entity/Q208569"},
         "date": {"value": "1972-03-01T00:00:00Z"}, "links": {"value": "30"},
         "article": {"value": "https://en.wikipedia.org/wiki/Machine_Head_(album)"}},
        {"item": {"value": "http://www.wikidata.org/entity/Q9"}, "t": {"value": "http://www.wikidata.org/entity/Q1573906"},
         "start": {"value": "1984-08-09T00:00:00Z"}, "links": {"value": "9"},
         "article": {"value": "https://en.wikipedia.org/wiki/World_Slavery_Tour"}},
    ]

    class Session:
        headers = {}

        def get(self, url, params=None, timeout=None):
            assert "wd:Q101505" in params["query"]
            return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"results": {"bindings": rows}})

    got = WikipediaClient(min_interval=0, session=Session()).works("Q101505")
    assert got == [
        {"wikidata": "Q2", "kind": "album", "title": "Machine Head (album)", "date": "1972-03-01", "sitelinks": 30},
        {"wikidata": "Q9", "kind": "tour", "title": "World Slavery Tour", "date": "1984-08-09", "sitelinks": 9},
    ]


def _layout_with_events(evs, paper="A1", max_bands=6):
    from app.fitting import fit_tree
    from app.pipeline import harvester_for
    harvest = harvester_for("demo:yardbirds").harvest("demo:yardbirds", depth=4)
    tree, _, _ = fit_tree(harvest, paper=paper, max_bands=max_bands)  # a small family: room to spare
    tree.bands["demo:yardbirds"].events = evs
    from app.grid import GridLayout
    from app.cartographer import STYLES
    cols, rows, _, _ = GridLayout.sheet(paper, dict(STYLES["classic"]))
    return tree, GridLayout(tree, paper=paper, cols=cols, rows=rows).layout()


def test_events_sit_in_free_space_beside_their_line_up():
    from app.narrative import lineup_for
    evs = [dict(e, year=float(e["year"]), subject="Mill Sessions") for e in [
        {"date": "1966-06", "year": 1966.4, "significance": 5, "text": "Played the Marquee so loud the ceiling came down on the front row."},
        {"date": "1967-02", "year": 1967.1, "significance": 3, "text": "Toured Australia with Roy Orbison and the Walker Brothers in a single week."},
    ]]
    tree, L = _layout_with_events(evs)
    placed = L["events"]
    assert placed, "room was found for at least the most significant event"
    assert placed[0]["significance"] == 5
    yb = tree.bands["demo:yardbirds"]
    for e in placed:
        target = lineup_for(yb.lineups, e["year"])
        assert e["lineup"] == f"demo:yardbirds#{target.number}"  # beside the line-up it happened to
        for b in L["boxes"]:  # never over a line-up
            assert not (e["x"] < b["x"] + b["w"] and b["x"] < e["x"] + e["w"] and
                        e["y"] < b["y"] + b["h"] and b["y"] < e["y"] + e["h"]), b["id"]
        for line in L["trunks"] + L["edges"]:  # nor over a musician's line, bar a long drop (it passes behind the text)
            for (ax, ay), (bx, by) in zip(line["points"], line["points"][1:]):
                if ax == bx and abs(by - ay) > L["grid"]["row_h"]:
                    continue
                assert not (min(ax, bx) < e["x"] + e["w"] and e["x"] < max(ax, bx) and
                            min(ay, by) < e["y"] + e["h"] and e["y"] < max(ay, by))
        box = next(b for b in L["boxes"] if b["id"] == e["lineup"])
        if e["tie"]:  # tied along its line-up's row
            assert box["y"] <= e["tie"][0][1] <= box["y"] + box["h"]


def test_an_event_the_notes_already_tell_is_left_out():
    story_like = {"date": "1966-06", "year": 1966.4, "significance": 5, "subject": "X",
                  "text": "Clapton quit for John Mayall's Bluesbreakers over the pop singles."}
    tree, L = _layout_with_events([story_like])
    yb = tree.bands["demo:yardbirds"]
    told = " ".join(s["text"] for s in yb.stories) + " ".join(b["notes_text"] for b in L["boxes"])
    if "Clapton" in told and "Mayall" in told:
        assert L["events"] == []


def test_a_minor_detail_is_not_placed():
    minor = {"date": "1966-06", "year": 1966.4, "significance": 2, "subject": "X",
             "text": "Reissued on coloured vinyl with two bonus tracks for the anniversary."}
    tree, L = _layout_with_events([minor])
    assert L["events"] == []


def test_a_misquoted_source_is_found_in_the_article(store):
    reworded = dict(FIRE, source="The album was recorded at an old mill in Hebden Bridge after the band's studio burned down during a Frank Zappa concert next door.")
    got = events.write_events(band(), WORK, ARTICLE, client=FakeModel([reworded]))
    assert [e["text"] for e in got["notes"]] == [FIRE["text"]]
    assert got["notes"][0]["source"] == FIRE["source"]  # the article's own sentence, not the misquote


def test_a_fact_from_the_next_sentence_still_counts():
    from app import narrative
    text = ARTICLE["text"]
    ctx = narrative.context(FIRE["source"], text)
    assert "stage collapsed" in ctx and "Frank Zappa" in ctx


def test_a_made_up_source_is_not_repaired(store):
    got = events.write_events(band(), WORK, ARTICLE, client=FakeModel([INVENTED]))
    assert got["notes"] == []


def test_an_event_dated_to_month_zero_still_draws():
    odd = {"date": "1966-00", "year": 1966.4, "significance": 5, "subject": "X",
           "text": "Played a club so small the drummer set up in the car park outside."}
    tree, L = _layout_with_events([odd])
    assert all("1966" in e["heading"] for e in L["events"])
