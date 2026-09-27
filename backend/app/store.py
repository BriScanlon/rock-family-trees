"""Record caches. `get_store()` picks Neo4j when configured and reachable,
otherwise falls back to JSON files so the app runs with no infrastructure."""
import json
import os
import threading
import time


class _Notes:
    """Notes written from Wikipedia (app/narrative.py), for stores without
    Neo4j: kept by key (model, article revision, line-ups), newest per band."""

    def put_notes(self, key, band_id, result):
        self._write_notes(key, dict(result, band_id=band_id, key=key, written_at=time.time()))

    def get_notes(self, key):
        return self._read_notes(key)

    def latest_notes(self, band_id, model=None):
        sets = [n for n in self._all_notes() if n.get("band_id") == band_id and n.get("model") != "curator"
                and not n.get("subject") and (not model or n.get("model") == model)]  # events aren't the band's notes
        return max(sets, key=lambda n: n.get("written_at", 0), default=None)


class MemoryStore(_Notes):
    name = "memory"

    def __init__(self, records=None):
        self.records = dict(records or {})
        self.notes = {}

    def get(self, mbid):
        return self.records.get(mbid)

    def put(self, record):
        self.records[record["mbid"]] = record

    def _write_notes(self, key, result):
        self.notes[key] = result

    def _read_notes(self, key):
        return self.notes.get(key)

    def _all_notes(self):
        return list(self.notes.values())


class FileStore(_Notes):
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

    def _notes_path(self, key):
        return os.path.join(self.root, "notes", f"{key}.json")

    def _write_notes(self, key, result):
        path = self._notes_path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with self._lock, open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=1)

    def _read_notes(self, key):
        try:
            with open(self._notes_path(key), encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def _all_notes(self):
        folder = os.path.join(self.root, "notes")
        if not os.path.isdir(folder):
            return []
        return [n for n in (self._read_notes(f[:-5]) for f in os.listdir(folder) if f.endswith(".json")) if n]


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
