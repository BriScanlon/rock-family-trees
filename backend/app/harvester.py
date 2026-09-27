"""Collects the artist records needed to draw a family tree.

Depth is counted in *band generations*:
  depth 1  the root band(s) only (plus their members, for dates of death)
  depth 2  + every other band those members played in
  depth 3  + the members of those bands and *their* other bands, etc.

Every record is served from the store when cached; only misses hit
MusicBrainz. A fetch budget keeps deep trees from exploding.
"""
from collections import Counter
from datetime import date

from app.musicbrainz import MusicBrainzClient, is_group

FOUNDER_YEARS = 10  # a founder counts as this long-serving, whatever their dates say
MIN_WEIGHT = 0.5    # an undated or very brief member still links a little


def _year(s):
    try:
        parts = (s or "").split("-")
        return int(parts[0]) + (int(parts[1]) - 1) / 12 if len(parts) > 1 else int(parts[0])
    except ValueError:
        return None


def _tenure(m):
    """Years a membership lasted (undated ends: until now), with founders at
    least FOUNDER_YEARS: MusicBrainz sometimes closes a founder's membership
    by mistake (Dave Grohl, Foo Fighters, "1994-10 to 1994-10")."""
    start, end = _year(m.get("begin")), _year(m.get("end"))
    if end is None and not m.get("ended"):
        end = date.today().year
    years = (end - start) if start is not None and end is not None else 0.0
    if "original" in [(a or "").lower() for a in m.get("attributes") or []]:
        years = max(years, FOUNDER_YEARS)
    return max(years, 0.0)


class Harvester:
    def __init__(self, store=None, client=None, refresh=False):
        if store is None:
            from app.store import get_store
            store = get_store()
        self.store = store
        self.client = client
        self.refresh = refresh
        self.records = {}
        self.api_calls = 0

    def _client(self):
        if self.client is None:
            self.client = MusicBrainzClient()
        return self.client

    def search_artists(self, query):
        return self._client().search_artists(query)

    def fetch(self, mbid):
        if mbid in self.records:
            return self.records[mbid]
        record = None if self.refresh else self.store.get(mbid)
        if record is None:
            self.api_calls += 1
            record = self._client().get_artist(mbid)
            if record is None:
                return None
            self.store.put(record)
        self.records[mbid] = record
        return record

    def harvest(self, root_id, depth=2, max_bands=30, max_people=120, progress=None):
        progress = progress or (lambda frac, msg: None)
        depth = max(1, int(depth))
        band_budget = max(max_bands * 2, 8)

        root = self.fetch(root_id)
        if root is None:
            raise ValueError(f"Artist {root_id} not found on MusicBrainz")

        if is_group(root):
            root_bands = [root_id]
        else:
            # A person: their bands form the first generation.
            root_bands = list(dict.fromkeys(m["band_id"] for m in root["memberships"] if m["person_id"] == root_id))
            if not root_bands:
                raise ValueError(f"{root['name']} is not recorded as a member of any band")

        levels = {b: 0 for b in root_bands}
        frontier = root_bands[:band_budget]
        seen_people = {root_id} if not is_group(root) else set()
        bands_fetched = 0

        for level in range(depth):
            # 1. Fetch the bands in this generation (full lineups)
            fetched = []
            for i, band_id in enumerate(frontier):
                if bands_fetched >= band_budget:
                    break
                progress(0.1 + 0.8 * (level + i / max(len(frontier), 1)) / depth,
                         f"Reading band {bands_fetched + 1}: generation {level + 1}")
                rec = self.fetch(band_id)
                bands_fetched += 1
                if rec is not None:
                    fetched.append(rec)

            last_level = level == depth - 1
            if last_level and level > 0:
                break

            # 2. Fetch their members (death dates, and other bands for the next generation)
            people = []
            weight = Counter()  # how much each member mattered to this generation's bands
            for rec in fetched:
                for m in rec["memberships"]:
                    if m["band_id"] != rec["mbid"]:
                        continue
                    weight[m["person_id"]] += _tenure(m)
                    if m["person_id"] not in seen_people:
                        seen_people.add(m["person_id"])
                        people.append(m["person_id"])
            people = people[:max(0, max_people - len(seen_people) + len(people))]

            links = Counter()
            for i, pid in enumerate(people):
                progress(0.1 + 0.8 * (level + 0.5 + 0.5 * i / max(len(people), 1)) / depth,
                         f"Tracing member {i + 1} of {len(people)}")
                prec = self.fetch(pid)
                if prec is None:
                    continue
                for m in prec["memberships"]:
                    if m["person_id"] == pid and m["band_id"] not in levels:
                        # a band reached through a founder or a long-serving member
                        # matters more than one reached through a stand-in
                        links[m["band_id"]] += max(weight[pid], MIN_WEIGHT)

            if last_level:
                break
            # Most-connected bands first so the budget goes where it matters.
            frontier = [b for b, _ in links.most_common()]
            for b in frontier:
                levels[b] = level + 1

        return {
            "root_id": root_id,
            "root_name": root["name"],
            "root_bands": root_bands,
            "band_levels": levels,
            "records": self.records,
            "api_calls": self.api_calls,
        }
