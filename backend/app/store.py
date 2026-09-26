"""Record caches. `get_store()` picks Neo4j when configured and reachable,
otherwise falls back to JSON files so the app runs with no infrastructure."""
import json
import os
import threading


class MemoryStore:
    name = "memory"

    def __init__(self, records=None):
        self.records = dict(records or {})

    def get(self, mbid):
        return self.records.get(mbid)

    def put(self, record):
        self.records[record["mbid"]] = record


class FileStore:
    name = "file"

    def __init__(self, root=None):
        self.root = root or os.getenv("CACHE_DIR", "cache/artists")
        os.makedirs(self.root, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, mbid):
        safe = "".join(c for c in mbid if c.isalnum() or c in "-_:")
        return os.path.join(self.root, f"{safe}.json")

    def get(self, mbid):
        try:
            with open(self._path(mbid)) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def put(self, record):
        path = self._path(record["mbid"])
        tmp = f"{path}.{threading.get_ident()}.tmp"
        with self._lock:
            with open(tmp, "w") as f:
                json.dump(record, f)
            os.replace(tmp, path)


_store = None
_store_lock = threading.Lock()


def get_store():
    global _store
    with _store_lock:
        if _store is not None:
            return _store
        kind = os.getenv("GRAPH_STORE", "neo4j" if os.getenv("NEO4J_URI") else "file")
        if kind == "neo4j":
            try:
                from app.graph_db import Neo4jStore
                _store = Neo4jStore()
                print("Using Neo4j record store")
                return _store
            except Exception as e:
                print(f"Neo4j unavailable ({e}); falling back to file store")
        _store = FileStore()
        return _store
