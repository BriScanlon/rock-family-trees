import musicbrainzngs
import os
from sqlitedict import SqliteDict
import time
import random

class Harvester:
    def __init__(self, cache_path="cache/mb_cache.sqlite"):
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        self.cache = SqliteDict(cache_path, autocommit=True)
        musicbrainzngs.set_useragent(
            os.getenv("MB_USER_AGENT", "RockFamilyTreeGen/1.2.1"),
            "1.2.1",
            "briscanlon@gmail.com"
        )
        # Strict rate limit (1 req/sec)
        self.last_call = 0

    def _wait_for_rate_limit(self):
        elapsed = time.time() - self.last_call
        if elapsed < 1.1:
            time.sleep(1.1 - elapsed)
        self.last_call = time.time()

    def _safe_call(self, func, *args, **kwargs):
        max_retries = 3
        for i in range(max_retries):
            try:
                self._wait_for_rate_limit()
                return func(*args, **kwargs)
            except Exception as e:
                if "503" in str(e) or "429" in str(e):
                    wait = (i + 1) * 2 + random.random()
                    print(f"Rate limited by MusicBrainz. Retrying in {wait:.1f}s...")
                    time.sleep(wait)
                    continue
                raise e
        return None

    def search_artists(self, query):
        cache_key = f"search:{query}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        try:
            result = self._safe_call(musicbrainzngs.search_artists, artist=query)
            if not result: return []
            
            artists = []
            for artist in result.get('artist-list', []):
                artists.append({
                    "id": artist['id'], "name": artist['name'],
                    "type": artist.get('type'), "disambiguation": artist.get('disambiguation')
                })
            self.cache[cache_key] = artists
            return artists
        except Exception as e:
            print(f"Search failed: {e}")
            return []

    def get_artist_details(self, mbid):
        if mbid in self.cache:
            return self.cache[mbid]
        
        try:
            print(f"--> Fetching MBID: {mbid}")
            artist = self._safe_call(
                musicbrainzngs.get_artist_by_id, mbid, 
                includes=["artist-rels", "label-rels", "release-groups"]
            )
            if artist:
                self.cache[mbid] = artist
            return artist
        except Exception as e:
            print(f"!!! Error details for {mbid}: {e}")
            return None

    def fetch_recursive(self, mbid, max_depth=2):
        visited = {}
        queue = [(mbid, 0)]
        
        while queue:
            current_mbid, depth = queue.pop(0)
            if current_mbid in visited: continue
                
            data = self.get_artist_details(current_mbid)
            if not data: continue
                
            visited[current_mbid] = data
            if depth < max_depth:
                artist_rels = data.get('artist', {}).get('artist-relation-list', [])
                for rel in artist_rels:
                    if 'artist' in rel and rel.get('type') == 'member of band':
                        target_id = rel['artist']['id']
                        if target_id not in visited:
                            queue.append((target_id, depth + 1))
                            
        return visited