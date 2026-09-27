import time

from app import musicbrainz
from app.musicbrainz import MusicBrainzClient


def test_rate_limit_ignores_wall_clock_steps(monkeypatch):
    # Docker Desktop's VM clock steps backwards; a wall-clock limiter then
    # slept for the size of the step and hung the harvest.
    sleeps = []
    monkeypatch.setattr(musicbrainz.time, "sleep", sleeps.append)
    monkeypatch.setattr(musicbrainz, "_last_call", [float("-inf")])
    client = MusicBrainzClient(min_interval=1.1)

    client._wait()
    real_time = time.time
    monkeypatch.setattr(musicbrainz.time, "time", lambda: real_time() - 3600)
    client._wait()

    assert len(sleeps) == 1 and sleeps[0] <= 1.1
