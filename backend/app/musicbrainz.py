"""Thin MusicBrainz JSON web-service client.

Everything the rest of the app needs about an artist is normalised into a
plain "record" dict so it can be cached (Neo4j or JSON files) and replayed
without touching the network again:

    {
      "mbid": str, "name": str, "type": "Group" | "Person" | ...,
      "disambiguation": str, "begin": "1976-05" | None, "end": ... | None,
      "ended": bool, "genres": ["hard rock", ...],
      "memberships": [   # "member of band" relations, always person -> band
        {"person_id", "person_name", "band_id", "band_name",
         "begin", "end", "ended", "attributes": [..]}
      ]
    }
"""
import os
import random
import threading
import time

import requests

MB_ROOT = os.getenv("MB_API_ROOT", "https://musicbrainz.org/ws/2")
DEFAULT_UA = "RockFamilyTreeGen/2.0 ( https://github.com/BriScanlon/rock-family-trees )"

GROUP_TYPES = {"Group", "Orchestra", "Choir"}

# MusicBrainz allows one request per second per client, shared across threads.
_rate_lock = threading.Lock()
_last_call = [float("-inf")]


class MusicBrainzError(Exception):
    pass


class MusicBrainzClient:
    def __init__(self, user_agent=None, min_interval=1.1, session=None):
        self.user_agent = user_agent or os.getenv("MB_USER_AGENT") or DEFAULT_UA
        self.min_interval = min_interval
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent, "Accept": "application/json"})

    def _wait(self):
        with _rate_lock:
            # Monotonic, not wall-clock: if the clock steps backwards (Docker
            # Desktop's VM clock does) the last call looks like it's in the
            # future and the sleep below would last as long as the step.
            elapsed = time.monotonic() - _last_call[0]
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            _last_call[0] = time.monotonic()

    def _get(self, path, params):
        params = dict(params, fmt="json")
        last_error = None
        for attempt in range(4):
            self._wait()
            try:
                resp = self.session.get(f"{MB_ROOT}/{path}", params=params, timeout=20)
            except requests.RequestException as e:
                last_error = e
                time.sleep((attempt + 1) * 1.5)
                continue
            if resp.status_code in (429, 502, 503):
                last_error = MusicBrainzError(f"HTTP {resp.status_code}")
                wait = (attempt + 1) * 2 + random.random()
                print(f"MusicBrainz throttled ({resp.status_code}); retrying in {wait:.1f}s")
                time.sleep(wait)
                continue
            if resp.status_code == 404:
                return None
            if resp.status_code >= 400:
                raise MusicBrainzError(f"HTTP {resp.status_code} for {path}")
            return resp.json()
        raise MusicBrainzError(f"MusicBrainz unavailable: {last_error}")

    def search_artists(self, query, limit=15):
        data = self._get("artist", {"query": query, "limit": limit}) or {}
        results = []
        for a in data.get("artists", []):
            ls = a.get("life-span") or {}
            years = "–".join(filter(None, [(ls.get("begin") or "")[:4], (ls.get("end") or "")[:4]]))
            results.append({
                "id": a["id"],
                "name": a.get("name"),
                "type": a.get("type"),
                "disambiguation": a.get("disambiguation") or None,
                "country": a.get("country"),
                "years": years or None,
                "score": a.get("score"),
            })
        return results

    def get_artist(self, mbid):
        data = self._get(f"artist/{mbid}", {"inc": "artist-rels+genres+url-rels"})
        if data is None:
            return None
        return normalize_artist(data)

    def get_albums(self, mbid):
        """A band's studio albums, oldest first: ["1972 Machine Head", ...].
        One search rather than paging through every release group (Deep
        Purple has 412, mostly compilations)."""
        query = f"arid:{mbid} AND primarytype:album AND NOT secondarytype:*"
        data = self._get("release-group", {"query": query, "limit": 100}) or {}
        albums = sorted({(rg.get("first-release-date") or "")[:4] + " " + rg["title"]
                         for rg in data.get("release-groups", [])
                         if rg.get("primary-type") == "Album" and not rg.get("secondary-types")
                         and (rg.get("first-release-date") or "")[:4].isdigit()})
        return albums


def normalize_artist(data):
    """Convert a /ws/2/artist/{id}?inc=artist-rels JSON payload into a record."""
    ls = data.get("life-span") or {}
    record = {
        "mbid": data["id"],
        "name": data.get("name") or "Unknown",
        "type": data.get("type"),
        "disambiguation": data.get("disambiguation") or "",
        "begin": ls.get("begin"),
        "end": ls.get("end"),
        "ended": bool(ls.get("ended")),
        "genres": [g["name"] for g in sorted(data.get("genres") or [], key=lambda g: -(g.get("count") or 0))],
        "memberships": [],
        # the artist's Wikidata item, if MusicBrainz links one ("" = looked, none);
        # the way into Wikipedia for the notes (app/wikipedia.py)
        "wikidata": next((rel["url"]["resource"].rstrip("/").rsplit("/", 1)[-1]
                          for rel in data.get("relations", [])
                          if rel.get("type") == "wikidata" and rel.get("url", {}).get("resource")), ""),
    }
    for rel in data.get("relations", []):
        if rel.get("type") != "member of band" or "artist" not in rel:
            continue
        other = rel["artist"]
        # direction "backward": the other artist is the member (we are the band)
        if rel.get("direction") == "backward":
            person_id, person_name = other["id"], other.get("name")
            band_id, band_name = record["mbid"], record["name"]
        else:
            person_id, person_name = record["mbid"], record["name"]
            band_id, band_name = other["id"], other.get("name")
        record["memberships"].append({
            "person_id": person_id,
            "person_name": person_name,
            "band_id": band_id,
            "band_name": band_name,
            "begin": rel.get("begin"),
            "end": rel.get("end"),
            "ended": bool(rel.get("ended")),
            "attributes": list(rel.get("attributes") or []),
        })
    return record


def is_group(record):
    if record.get("type") in GROUP_TYPES:
        return True
    if record.get("type") is None:
        # Untyped artists that have members are treated as bands.
        return any(m["band_id"] == record["mbid"] for m in record.get("memberships", []))
    return False
