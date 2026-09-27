"""Neo4j-backed cache of normalised MusicBrainz artist records.

Schema:
    (:Band   {mbid, name, type, disambiguation, begin, end, ended, fetched_at})
    (:Artist {mbid, name, type, disambiguation, begin, end, ended, fetched_at})
    (:Artist)-[:MEMBER_OF {key, begin, end, ended, attributes}]->(:Band)

A node with `fetched_at` set has had its full relation list stored, so it can be
served from the graph without calling MusicBrainz. MEMBER_OF is keyed on the
stint dates so people who leave and rejoin keep every stint.
"""
import json
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
            s.run("CREATE CONSTRAINT noteset_key IF NOT EXISTS FOR (n:NoteSet) REQUIRE n.key IS UNIQUE")

    def close(self):
        self.driver.close()

    # -- notes written from Wikipedia (app/narrative.py) -------------------
    #   (:Band)-[:HAS_NOTES]->(:NoteSet {key, model, prompt, revision, article_title,
    #       article_url, lineups, written_at})-[:INCLUDES]->(:Note {date, year,
    #       text, source, kept, reason, position})
    # A NoteSet is one writing: the key is the model, article revision and
    # line-ups it was written from. Dropped notes are kept too, with the reason.

    def put_notes(self, key, band_id, result):
        with self.driver.session() as s:
            s.execute_write(self._put_notes_tx, key, band_id, result)

    @staticmethod
    def _put_notes_tx(tx, key, band_id, result):
        source = result.get("source") or {}
        tx.run(
            "MERGE (b:Band {mbid: $band}) "
            "MERGE (ns:NoteSet {key: $key}) "
            "SET ns.model = $model, ns.revision = $revision, ns.article_title = $title, "
            "ns.article_url = $url, ns.lineups = $lineups, ns.prompt = $prompt, ns.written_at = datetime() "
            "WITH b, ns OPTIONAL MATCH (ns)-[:INCLUDES]->(old:Note) DETACH DELETE old "
            "WITH DISTINCT b, ns WHERE $subject IS NULL MERGE (b)-[:HAS_NOTES]->(ns)",
            band=band_id, key=key, model=result.get("model"), revision=source.get("revision"),
            title=source.get("title"), url=source.get("url"), lineups=result.get("lineups"),
            prompt=result.get("prompt"), subject=(result.get("subject") or {}).get("wikidata"),
        )
        subject = result.get("subject")
        if subject:  # an event reading: its notes hang off the album or tour they're about
            label, rel = ("Tour", "TOURED") if subject.get("kind") == "tour" else ("Album", "RELEASED")
            tx.run(
                f"MATCH (b:Band {{mbid: $band}}), (ns:NoteSet {{key: $key}}) "
                f"MERGE (s:{label} {{wikidata: $q}}) SET s.title = $title, s.date = $date, s.sitelinks = $links "
                f"MERGE (b)-[:{rel}]->(s) MERGE (s)-[:HAS_NOTES]->(ns)",
                band=band_id, key=key, q=subject["wikidata"], title=subject.get("title"),
                date=subject.get("date"), links=subject.get("sitelinks"),
            )
        notes = [dict(n, kept=True) for n in result.get("notes", [])] + \
                [dict(n, kept=False) for n in result.get("dropped", [])]
        for i, n in enumerate(notes):
            tx.run(
                "MATCH (ns:NoteSet {key: $key}) "
                "CREATE (ns)-[:INCLUDES]->(:Note {date: $date, year: $year, text: $text, source: $source, "
                "kept: $kept, reason: $reason, position: $i, significance: $significance})",
                key=key, date=n.get("date"), year=n.get("year"), text=n.get("text"), source=n.get("source"),
                kept=n["kept"], reason=n.get("reason"), i=i, significance=n.get("significance"),
            )

    def get_notes(self, key):
        with self.driver.session() as s:
            return s.execute_read(self._get_notes_tx, "ns.key = $key", key=key, match="MATCH (ns:NoteSet)")

    def latest_notes(self, band_id, model=None):
        """The band's most recently written notes (from any article revision),
        for when Wikipedia or the model can't be reached."""
        where = ("b.mbid = $band AND ns.model <> 'curator' AND NOT ns.key STARTS WITH 'rank:'"
                 + (" AND ns.model = $model" if model else ""))  # event ratings aren't the band's notes
        with self.driver.session() as s:
            return s.execute_read(self._get_notes_tx, where, band=band_id, model=model,
                                  match="MATCH (b:Band)-[:HAS_NOTES]->(ns:NoteSet)")

    @staticmethod
    def _get_notes_tx(tx, where, match, **params):
        row = tx.run(
            f"{match} WHERE {where} "
            "WITH ns ORDER BY ns.written_at DESC LIMIT 1 "
            "OPTIONAL MATCH (ns)-[:INCLUDES]->(n:Note) "
            "WITH ns, n ORDER BY n.position "
            "RETURN ns, collect(n) AS notes", **params,
        ).single()
        if not row or row["ns"] is None:
            return None
        ns = row["ns"]
        notes = [dict(n) for n in row["notes"]]
        strip = lambda n: {k: v for k, v in n.items() if k not in ("kept", "position") and v is not None}
        return {
            "notes": [strip(n) for n in notes if n.get("kept")],
            "dropped": [strip(n) for n in notes if not n.get("kept")],
            "model": ns.get("model"), "lineups": ns.get("lineups"), "prompt": ns.get("prompt"),
            "source": {"title": ns.get("article_title"), "url": ns.get("article_url"), "revision": ns.get("revision")},
        }

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
            "n.sitelinks = $sitelinks, n.chart = $chart, n.chart_source = $chart_source, n.works = $works, "
            "n.fetched_at = datetime()",
            mbid=record["mbid"], name=record["name"], type=record.get("type"),
            disambiguation=record.get("disambiguation"), begin=record.get("begin"),
            end=record.get("end"), ended=record.get("ended", False), genres=record.get("genres") or [],
            wikidata=record.get("wikidata"), sitelinks=record.get("sitelinks"),
            chart=None if record.get("chart") is None else json.dumps(record["chart"]),
            chart_source=record.get("chart_source"),
            works=None if record.get("works") is None else json.dumps(record["works"]),
        )
        if record.get("albums") is not None and label == "Band":
            # each album a node on the band, dated: a note in the band's history
            # (placed on the line-up together when it came out), not a list
            tx.run("MATCH (n:Band {mbid: $mbid}) SET n.albums_checked = true REMOVE n.albums "
                   "WITH n OPTIONAL MATCH (n)-[r:RELEASED]->(:Album) DELETE r", mbid=record["mbid"])
            for album in record["albums"]:
                when, _, title = album.partition(" ")
                tx.run("MATCH (n:Band {mbid: $mbid}) "
                       "MERGE (a:Album {key: $key}) SET a.title = $title, a.date = $date "
                       "MERGE (n)-[:RELEASED]->(a)",
                       mbid=record["mbid"], key=f"{record['mbid']}|{title}", title=title, date=when)
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
        albums = None  # not looked up yet (or only as the old undated list: look again)
        if n.get("albums_checked"):
            albums = sorted(f"{r['date']} {r['title']}" for r in tx.run(
                "MATCH (:Band {mbid: $mbid})-[:RELEASED]->(a:Album) RETURN a.date AS date, a.title AS title",
                mbid=mbid))
        return {
            "mbid": n["mbid"], "name": n.get("name"), "type": n.get("type"),
            "disambiguation": n.get("disambiguation") or "",
            "begin": n.get("begin"), "end": n.get("end"), "ended": bool(n.get("ended")),
            "genres": list(n.get("genres") or []),
            "wikidata": n.get("wikidata"),  # None: cached before Wikidata links were kept
            "albums": albums,
            "sitelinks": n.get("sitelinks"),  # Wikipedias with an article on the band; None: not looked up
            "chart": None if n.get("chart") is None else json.loads(n["chart"]),  # Wikipedia's member chart; [] none
            "chart_source": n.get("chart_source"),
            "works": None if n.get("works") is None else json.loads(n["works"]),  # its albums and tours (Wikidata)
            "memberships": [
                {"person_id": r["pid"], "person_name": r["pname"], "band_id": r["bid"],
                 "band_name": r["bname"], "begin": r["begin"], "end": r["end"],
                 "ended": bool(r["ended"]), "attributes": list(r["attributes"] or [])}
                for r in row["rels"] if r["pid"] and r["bid"]
            ],
        }
