import musicbrainzngs
import os
from sqlitedict import SqliteDict
import time

class Harvester:
    def __init__(self, cache_path="cache/mb_cache.sqlite"):
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        self.cache = SqliteDict(cache_path, autocommit=True)
        musicbrainzngs.set_useragent(
            os.getenv("MB_USER_AGENT", "RockFamilyTreeGen/1.2.0"),
            "1.2.0",
            "contact@example.com"
        )

    def search_artists(self, query):
        cache_key = f"search:{query}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        try:
            result = musicbrainzngs.search_artists(artist=query)
            artists = []
            for artist in result.get('artist-list', []):
                artists.append({
                    "id": artist['id'],
                    "name": artist['name'],
                    "type": artist.get('type'),
                    "disambiguation": artist.get('disambiguation')
                })
            self.cache[cache_key] = artists
            return artists
        except Exception as e:
            print(f"Error searching artists: {e}")
            return []

    def get_artist_details(self, mbid):
        if mbid in self.cache:
            return self.cache[mbid]
        
        try:
            # Fetch artist with artist-rels and band-rels
            artist = musicbrainzngs.get_artist_by_id(
                mbid, 
                includes=["artist-rels", "label-rels", "release-groups"]
            )
            self.cache[mbid] = artist
            # Respect rate limits
            time.sleep(1)
            return artist
        except Exception as e:
            print(f"Error fetching artist {mbid}: {e}")
            return None

    def fetch_recursive(self, mbid, max_depth=2):
        # Implementation of recursive crawling
        pass
