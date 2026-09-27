"""Wikipedia articles, looked up on demand, as the reference for the notes.

MusicBrainz links an artist to its Wikidata item; Wikidata gives the English
Wikipedia article; Wikipedia gives the article as plain text with its revision
id (so anything written from it can be cached until the article changes).
Wikipedia's text is CC BY-SA: it is read as a *reference* only. The notes are
written fresh (app/narrative.py), never copied onto the poster.

Decision (issue #7): on demand for now; if the shop takes off, host a copy.
"""
import os
import threading
import time

import requests

WIKIDATA_API = os.getenv("WIKIDATA_API", "https://www.wikidata.org/w/api.php")
WIKIPEDIA_API = os.getenv("WIKIPEDIA_API", "https://en.wikipedia.org/w/api.php")
NOT_WIKIPEDIAS = {"commonswiki", "specieswiki", "metawiki", "wikidatawiki", "mediawikiwiki", "sourceswiki"}
DEFAULT_UA = "RockFamilyTreeGen/2.0 ( https://github.com/BriScanlon/rock-family-trees )"

_rate_lock = threading.Lock()
_last_call = [float("-inf")]


class WikipediaClient:
    def __init__(self, user_agent=None, min_interval=0.5, session=None):
        self.min_interval = min_interval
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": user_agent or os.getenv("MB_USER_AGENT") or DEFAULT_UA})

    def _get(self, url, params):
        # Wikimedia asks for gentle, identified clients; monotonic like the
        # MusicBrainz limiter, as Docker Desktop's wall clock steps backwards
        with _rate_lock:
            wait = self.min_interval - (time.monotonic() - _last_call[0])
            if wait > 0:
                time.sleep(wait)
            _last_call[0] = time.monotonic()
        resp = self.session.get(url, params=dict(params, format="json", formatversion=2), timeout=30)
        resp.raise_for_status()
        return resp.json()

    def sitelinks(self, wikidata_ids):
        """How many Wikipedias (language editions) have an article on each item:
        a band's standing in the world - Nirvana 106, No Use for a Name 22."""
        counts = {}
        ids = [q for q in dict.fromkeys(wikidata_ids) if q]
        for i in range(0, len(ids), 50):  # the API takes 50 at a time
            data = self._get(WIKIDATA_API, {"action": "wbgetentities", "ids": "|".join(ids[i:i + 50]),
                                            "props": "sitelinks"})
            for q, entity in (data.get("entities") or {}).items():
                links = entity.get("sitelinks") or {}
                counts[q] = sum(1 for site in links if site.endswith("wiki") and site not in NOT_WIKIPEDIAS)
        return counts

    def title_for(self, wikidata_id):
        """The English Wikipedia article for a Wikidata item, or None."""
        if not wikidata_id:
            return None
        data = self._get(WIKIDATA_API, {"action": "wbgetentities", "ids": wikidata_id,
                                        "props": "sitelinks", "sitefilter": "enwiki"})
        entity = (data.get("entities") or {}).get(wikidata_id) or {}
        return ((entity.get("sitelinks") or {}).get("enwiki") or {}).get("title")

    def article(self, title):
        """{"title", "text", "revision", "url"} for an article, or None."""
        if not title:
            return None
        data = self._get(WIKIPEDIA_API, {"action": "query", "prop": "extracts|info", "explaintext": 1,
                                         "exsectionformat": "wiki", "inprop": "url", "redirects": 1,
                                         "titles": title})
        pages = (data.get("query") or {}).get("pages") or []
        page = pages[0] if pages else {}
        if page.get("missing") or not page.get("extract"):
            return None
        return {"title": page.get("title", title), "text": page["extract"],
                "revision": page.get("lastrevid"), "url": page.get("fullurl")}

    def wikitext(self, title):
        """{"title", "text", "revision"}: an article's source (for its member
        chart), following redirects, or None."""
        if not title:
            return None
        try:
            data = self._get(WIKIPEDIA_API, {"action": "parse", "prop": "wikitext|revid", "redirects": 1,
                                             "page": title})
        except requests.HTTPError:
            return None
        parse = data.get("parse")
        if not parse or "error" in data:
            return None
        return {"title": parse.get("title", title), "text": parse.get("wikitext") or "", "revision": parse.get("revid")}
