import musicbrainzngs
import os
import time
import random
from app.graph_db import Neo4jClient

class Harvester:
    def __init__(self):
        musicbrainzngs.set_useragent(
            os.getenv("MB_USER_AGENT", "RockFamilyTreeGen/1.2.1"),
            "1.2.1",
            "briscanlon@gmail.com"
        )
        self.last_call = 0
        self.db = Neo4jClient()

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
        try:
            result = self._safe_call(musicbrainzngs.search_artists, artist=query)
            if not result: return []
            
            artists = []
            for artist in result.get('artist-list', []):
                artists.append({
                    "id": artist['id'], "name": artist['name'],
                    "type": artist.get('type'), "disambiguation": artist.get('disambiguation')
                })
            return artists
        except Exception as e:
            print(f"Search failed: {e}")
            return []

    def sync_artist_to_neo4j(self, mbid):
        """Fetches data from MB and writes it to Neo4j"""
        try:
            print(f"--> Syncing MBID to Neo4j: {mbid}")
            result = self._safe_call(
                musicbrainzngs.get_artist_by_id, mbid, 
                includes=["artist-rels"]
            )
            if not result: return
            
            artist_data = result.get('artist', {})
            name = artist_data.get('name')
            is_group = artist_data.get('type') == 'Group'
            
            if is_group:
                ls = artist_data.get('life-span', {})
                start = self._parse_year(ls.get('begin'))
                end = self._parse_year(ls.get('end'))
                self.db.upsert_band(mbid, name, start, end)
                
                # Members
                rels = artist_data.get('artist-relation-list', [])
                for idx, rel in enumerate(rels):
                    if rel.get('type') == 'member of band':
                        target = rel.get('artist', {})
                        m_id, m_name = target.get('id'), target.get('name')
                        
                        membership = {
                            "role": self._parse_role(rel.get('attributes', [])),
                            "start_year": self._parse_year(rel.get('begin')),
                            "end_year": self._parse_year(rel.get('end')),
                            "position": idx
                        }
                        self.db.upsert_membership(m_id, m_name, mbid, membership)
            else:
                # Individual artist - we just upsert them (memberships will link them to bands)
                # Note: In a real recursion, we might want to find bands this artist is in.
                # But here we focus on Group-down recursion.
                pass
                
        except Exception as e:
            print(f"!!! Error syncing {mbid}: {e}")

    def fetch_recursive(self, mbid, max_depth=2):
        """
        Depth-aware recursive harvest.
        1. Check Neo4j for explored_depth.
        2. If too shallow, expand.
        """
        current_explored = self.db.get_explored_depth(mbid)
        
        if current_explored < max_depth:
            print(f"Cache miss or shallow (depth {current_explored} < {max_depth}). Expanding...")
            self._expand_recursive(mbid, max_depth)
            self.db.set_explored_depth(mbid, max_depth)
        else:
            print(f"Cache hit (depth {current_explored} >= {max_depth}).")

        # Always return the subgraph from Neo4j
        return self.db.get_subgraph(mbid, max_depth)

    def _expand_recursive(self, mbid, max_depth):
        visited = set()
        queue = [(mbid, 0)]
        
        while queue:
            curr_mbid, depth = queue.pop(0)
            if curr_mbid in visited: continue
            visited.add(curr_mbid)
            
            # Sync this node to Neo4j
            self.sync_artist_to_neo4j(curr_mbid)
            
            if depth < max_depth:
                # To find neighbors, we look at what we just put in Neo4j 
                # or we can extract them from the MB response.
                # Let's use the MB response for simplicity during sync.
                result = self._safe_call(musicbrainzngs.get_artist_by_id, curr_mbid, includes=["artist-rels"])
                if not result: continue
                
                rels = result.get('artist', {}).get('artist-relation-list', [])
                for rel in rels:
                    if rel.get('type') == 'member of band':
                        target_id = rel.get('artist', {}).get('id')
                        if target_id and target_id not in visited:
                            queue.append((target_id, depth + 1))

    def _parse_year(self, date_str):
        if not date_str or len(date_str) < 4: return None
        try: return int(date_str[:4])
        except: return None

    def _parse_role(self, attributes):
        parts = [a if isinstance(a, str) else a.get('attribute', '') for a in attributes]
        return ", ".join(filter(None, parts)) if parts else None
