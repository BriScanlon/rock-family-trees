import pytest

from app.harvester import Harvester
from app.store import FileStore, MemoryStore

from helpers import records


class FakeClient:
    def __init__(self):
        self.data = records()
        self.calls = []

    def get_artist(self, mbid):
        self.calls.append(mbid)
        return self.data.get(mbid)


def test_depth_one_fetches_band_and_members_only():
    client = FakeClient()
    result = Harvester(store=MemoryStore(), client=client).harvest("jd", depth=1)
    assert result["band_levels"] == {"jd": 0}
    assert "no" not in client.calls
    assert set(client.calls) == {"jd", "ian", "bernard", "hooky", "steve", "terry"}


def test_depth_levels():
    client = FakeClient()
    result = Harvester(store=MemoryStore(), client=client).harvest("jd", depth=3)
    assert result["band_levels"]["no"] == 1
    assert result["band_levels"]["el"] == 1
    assert result["band_levels"]["smiths"] == 2
    assert len(client.calls) == len(set(client.calls))


def test_cache_prevents_refetch(tmp_path):
    store = FileStore(str(tmp_path))
    first = FakeClient()
    Harvester(store=store, client=first).harvest("jd", depth=2)
    second = FakeClient()
    Harvester(store=store, client=second).harvest("jd", depth=2)
    assert first.calls and second.calls == []


def test_person_as_root_uses_their_bands():
    result = Harvester(store=MemoryStore(), client=FakeClient()).harvest("johnny", depth=1)
    assert set(result["root_bands"]) == {"el", "smiths"}


def test_unknown_artist():
    with pytest.raises(ValueError):
        Harvester(store=MemoryStore(), client=FakeClient()).harvest("nope")
