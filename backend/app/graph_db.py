"""Neo4j-backed cache of normalised MusicBrainz artist records.

Schema:
    (:Band   {mbid, name, type, disambiguation, begin, end, ended, fetched_at})
    (:Artist {mbid, name, type, disambiguation, begin, end, ended, fetched_at})
    (:Artist)-[:MEMBER_OF {key, begin, end, ended, attributes}]->(:Band)

A node with `fetched_at` set has had its full relation list stored, so it can be
served from the graph without calling MusicBrainz. MEMBER_OF is keyed on the
stint dates so people who leave and rejoin keep every stint.
"""
import os
import time

from neo4j import GraphDatabase

from app.musicbrainz import is_group


class Neo4jStore:
    name = "neo4j"

    def __init__(self, uri=None, user=None, password=None, connect_timeout=30):
        uri = uri or os.getenv("NEO4J_URI", "bolt://rftg-neo4j:7687")
        user = user or os.getenv("NEO4J_USER", "neo4j")
        password = password or os.getenv("NEO4J_PASSWORD", "password_placeholder")
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        deadline = time.time() + connect_timeout
        while True:
            try:
                self.driver.verify_connectivity()
                break
            except Exception:
                if time.time() > deadline:
                    self.driver.close()
                    raise
                time.sleep(2)
        with self.driver.session() as s:
            s.run("CREATE CONSTRAINT band_mbid IF NOT EXISTS FOR (b:Band) REQUIRE b.mbid IS UNIQUE")
            s.run("CREATE CONSTRAINT artist_mbid IF NOT EXISTS FOR (a:Artist) REQUIRE a.mbid IS UNIQUE")

    def close(self):
        self.driver.close()

    def put(self, record):
        with self.driver.session() as s:
            s.execute_write(self._put_tx, record)

    @staticmethod
    def _put_tx(tx, record):
        label = "Band" if is_group(record) else "Artist"
        tx.run(
            f"MERGE (n:{label} {{mbid: $mbid}}) "
            "SET n.name = $name, n.type = $type, n.disambiguation = $disambiguation, "
            "n.begin = $begin, n.end = $end, n.ended = $ended, n.genres = $genres, n.wikidata = $wikidata, "
            "n.fetched_at = datetime()",
            mbid=record["mbid"], name=record["name"], type=record.get("type"),
            disambiguation=record.get("disambiguation"), begin=record.get("begin"),
            end=record.get("end"), ended=record.get("ended", False), genres=record.get("genres") or [],
            wikidata=record.get("wikidata"),
        )
        for m in record.get("memberships", []):
            tx.run(
                "MERGE (a:Artist {mbid: $pid}) ON CREATE SET a.name = $pname "
                "MERGE (b:Band {mbid: $bid}) ON CREATE SET b.name = $bname "
                "MERGE (a)-[r:MEMBER_OF {key: $key}]->(b) "
                "SET r.begin = $begin, r.end = $end, r.ended = $ended, r.attributes = $attrs",
                pid=m["person_id"], pname=m["person_name"], bid=m["band_id"], bname=m["band_name"],
                key=f"{m.get('begin') or ''}|{m.get('end') or ''}",
                begin=m.get("begin"), end=m.get("end"), ended=m.get("ended", False),
                attrs=m.get("attributes") or [],
            )

    def get(self, mbid):
        with self.driver.session() as s:
            return s.execute_read(self._get_tx, mbid)

    @staticmethod
    def _get_tx(tx, mbid):
        row = tx.run(
            "CALL { MATCH (n:Band {mbid: $mbid}) RETURN n UNION MATCH (n:Artist {mbid: $mbid}) RETURN n } "
            "WITH n WHERE n.fetched_at IS NOT NULL "
            "OPTIONAL MATCH (n)-[r:MEMBER_OF]-() "
            "WITH n, r, startNode(r) AS a, endNode(r) AS b "
            "RETURN n, collect(CASE WHEN r IS NULL THEN null ELSE {pid: a.mbid, pname: a.name, "
            "bid: b.mbid, bname: b.name, begin: r.begin, end: r.end, ended: r.ended, "
            "attributes: r.attributes} END) AS rels LIMIT 1",
            mbid=mbid,
        ).single()
        if not row:
            return None
        n = row["n"]
        return {
            "mbid": n["mbid"], "name": n.get("name"), "type": n.get("type"),
            "disambiguation": n.get("disambiguation") or "",
            "begin": n.get("begin"), "end": n.get("end"), "ended": bool(n.get("ended")),
            "genres": list(n.get("genres") or []),
            "wikidata": n.get("wikidata"),  # None: cached before Wikidata links were kept
            "memberships": [
                {"person_id": r["pid"], "person_name": r["pname"], "band_id": r["bid"],
                 "band_name": r["bname"], "begin": r["begin"], "end": r["end"],
                 "ended": bool(r["ended"]), "attributes": list(r["attributes"] or [])}
                for r in row["rels"] if r["pid"] and r["bid"]
            ],
        }
