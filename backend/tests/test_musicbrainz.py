from app.musicbrainz import is_group, normalize_artist
from app.refiner import parse_date, role_words

BAND_JSON = {
    "id": "jd", "name": "Joy Division", "type": "Group", "disambiguation": "",
    "life-span": {"begin": "1976", "end": "1980-05-18", "ended": True},
    "genres": [{"name": "post-punk", "count": 9}, {"name": "gothic rock", "count": 3}],
    "relations": [
        {"type": "member of band", "direction": "backward", "begin": "1976", "end": "1980-05-18",
         "ended": True, "attributes": ["original", "lead vocals"],
         "artist": {"id": "ian", "name": "Ian Curtis", "type": "Person"}},
        {"type": "producer", "direction": "backward", "artist": {"id": "x", "name": "Martin Hannett"}},
        {"type": "wikidata", "direction": "forward", "url": {"resource": "https://www.wikidata.org/wiki/Q101505"}},
    ],
}
PERSON_JSON = {
    "id": "bernard", "name": "Bernard Sumner", "type": "Person",
    "life-span": {"begin": "1956-01-04", "ended": False},
    "relations": [
        {"type": "member of band", "direction": "forward", "begin": "1980", "end": None, "ended": False,
         "attributes": ["guitar"], "artist": {"id": "no", "name": "New Order", "type": "Group"}},
    ],
}


def test_normalize_band_keeps_only_memberships():
    rec = normalize_artist(BAND_JSON)
    assert rec["ended"] and rec["end"] == "1980-05-18"
    assert len(rec["memberships"]) == 1
    m = rec["memberships"][0]
    assert (m["person_id"], m["band_id"], m["attributes"]) == ("ian", "jd", ["original", "lead vocals"])
    assert is_group(rec)
    assert rec["genres"] == ["post-punk", "gothic rock"]


def test_normalize_keeps_the_wikidata_link():
    # the way into Wikipedia for the notes; "" means MusicBrainz has none
    assert normalize_artist(BAND_JSON)["wikidata"] == "Q101505"
    assert normalize_artist(PERSON_JSON)["wikidata"] == ""


def test_normalize_person_direction():
    rec = normalize_artist(PERSON_JSON)
    m = rec["memberships"][0]
    assert (m["person_id"], m["band_id"], m["band_name"]) == ("bernard", "no", "New Order")
    assert not is_group(rec)


def test_roles_are_plain_words():
    assert role_words(["original", "lead vocals", "harmonica"]) == ["vocals", "harmonica"]
    assert role_words(["bass guitar", "background vocals"]) == ["bass"]
    assert role_words(["drums (drum set)"]) == ["drums"]
    assert role_words(["theremin"]) == ["theremin"]


def test_parse_date_precision():
    assert parse_date("1966-03-12") == (1966 + 2 / 12, "Mar 66")
    assert parse_date("1966") == (1966.0, "1966")
    assert parse_date(None) == (None, None)


class FakeResponse:
    def __init__(self, status, payload=None):
        self.status_code, self.payload = status, payload

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, responses):
        self.responses, self.headers, self.requests = list(responses), {}, []

    def get(self, url, params=None, timeout=None):
        self.requests.append((url, params))
        return self.responses.pop(0)


def test_client_search_and_retry(monkeypatch):
    from app import musicbrainz
    monkeypatch.setattr(musicbrainz.time, "sleep", lambda s: None)
    session = FakeSession([
        FakeResponse(503),
        FakeResponse(200, {"artists": [{"id": "jd", "name": "Joy Division", "type": "Group", "country": "GB",
                                        "life-span": {"begin": "1976", "end": "1980-05-18"}}]}),
        FakeResponse(200, BAND_JSON),
        FakeResponse(404),
    ])
    client = musicbrainz.MusicBrainzClient(session=session, min_interval=0)
    results = client.search_artists("joy division")
    assert results[0]["years"] == "1976–1980" and results[0]["country"] == "GB"
    assert client.get_artist("jd")["memberships"][0]["person_name"] == "Ian Curtis"
    assert client.get_artist("missing") is None
    assert session.requests[2][1] == {"inc": "artist-rels+genres+url-rels", "fmt": "json"}
    assert "User-Agent" in session.headers
