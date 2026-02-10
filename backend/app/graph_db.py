from neo4j import GraphDatabase
import os
from datetime import datetime

class Neo4jClient:
    def __init__(self):
        uri = os.getenv("NEO4J_URI", "bolt://rftg-neo4j:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password_placeholder")
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def upsert_band(self, mbid, name, start_year=None, end_year=None):
        with self.driver.session() as session:
            session.execute_write(self._upsert_band_tx, mbid, name, start_year, end_year)

    @staticmethod
    def _upsert_band_tx(tx, mbid, name, start_year, end_year):
        query = (
            "MERGE (b:Band {mbid: $mbid}) "
            "SET b.name = $name, b.start_year = $start_year, b.end_year = $end_year, b.last_updated = datetime() "
            "RETURN b"
        )
        tx.run(query, mbid=mbid, name=name, start_year=start_year, end_year=end_year)

    def upsert_membership(self, artist_mbid, artist_name, band_mbid, rel_data):
        with self.driver.session() as session:
            session.execute_write(self._upsert_membership_tx, artist_mbid, artist_name, band_mbid, rel_data)

    @staticmethod
    def _upsert_membership_tx(tx, artist_mbid, artist_name, band_mbid, rel_data):
        query = (
            "MERGE (a:Artist {mbid: $artist_mbid}) "
            "SET a.name = $artist_name "
            "WITH a "
            "MATCH (b:Band {mbid: $band_mbid}) "
            "MERGE (a)-[r:MEMBER_OF]->(b) "
            "SET r.role = $role, r.start_year = $start_year, r.end_year = $end_year, r.position = $position "
            "RETURN r"
        )
        tx.run(query, 
               artist_mbid=artist_mbid, artist_name=artist_name, 
               band_mbid=band_mbid, 
               role=rel_data.get('role'),
               start_year=rel_data.get('start_year'),
               end_year=rel_data.get('end_year'),
               position=rel_data.get('position'))

    def set_explored_depth(self, mbid, depth):
        with self.driver.session() as session:
            session.execute_write(self._set_depth_tx, mbid, depth)

    @staticmethod
    def _set_depth_tx(tx, mbid, depth):
        # Only update if the new depth is greater than existing
        query = (
            "MATCH (b:Band {mbid: $mbid}) "
            "SET b.explored_depth = CASE WHEN b.explored_depth IS NULL OR b.explored_depth < $depth THEN $depth ELSE b.explored_depth END "
            "RETURN b"
        )
        tx.run(query, mbid=mbid, depth=depth)

    def get_explored_depth(self, mbid):
        with self.driver.session() as session:
            result = session.execute_read(self._get_depth_tx, mbid)
            return result if result is not None else -1

    @staticmethod
    def _get_depth_tx(tx, mbid):
        query = "MATCH (b:Band {mbid: $mbid}) RETURN b.explored_depth AS depth"
        result = tx.run(query, mbid=mbid).single()
        return result["depth"] if result else None

    def get_subgraph(self, mbid, depth):
        """
        Returns a structured representation of the band and its members 
        up to a certain depth of relationships.
        """
        with self.driver.session() as session:
            return session.execute_read(self._get_subgraph_tx, mbid, depth)

    @staticmethod
    def _get_subgraph_tx(tx, mbid, depth):
        # Query to get bands and their members in the neighborhood
        # We use a variable length path to find all related bands and artists
        query = (
            "MATCH (root:Band {mbid: $mbid}) "
            "MATCH path = (root)-[:MEMBER_OF*0..$max_hops]-(target) "
            "WITH nodes(path) AS nodes, relationships(path) AS rels "
            "UNWIND nodes AS n "
            "UNWIND rels AS r "
            "RETURN DISTINCT n, r"
        )
        # depth * 2 because Band -> Artist -> Band is 2 hops
        result = tx.run(query, mbid=mbid, max_hops=depth * 2)
        
        bands = {}
        for record in result:
            node = record["n"]
            rel = record["r"]
            
            if "Band" in node.labels:
                b_id = node["mbid"]
                if b_id not in bands:
                    bands[b_id] = {
                        "id": b_id,
                        "name": node["name"],
                        "start_year": node["start_year"],
                        "end_year": node["end_year"],
                        "all_members": []
                    }
            
            if rel and rel.type == "MEMBER_OF":
                # Check if it's a relationship to one of our bands
                artist = rel.start_node
                band = rel.end_node
                b_id = band["mbid"]
                if b_id in bands:
                    member_data = {
                        "artist_id": artist["mbid"],
                        "artist_name": artist["name"],
                        "role": rel["role"],
                        "start_year": rel["start_year"],
                        "end_year": rel["end_year"],
                        "position": rel.get("position")
                    }
                    # Avoid duplicates
                    if not any(m["artist_id"] == member_data["artist_id"] and m["start_year"] == member_data["start_year"] for m in bands[b_id]["all_members"]):
                        bands[b_id]["all_members"].append(member_data)
        
        return {"bands": bands}
