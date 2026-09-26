# RFTG Backend & Worker

FastAPI app (`main.py`) plus an optional Celery worker (`app/worker.py`) that research band line-ups on MusicBrainz and render Pete Frame-style family tree posters as SVG. See the top-level README for the module overview and API options.

```bash
pip install -r requirements-dev.txt
uvicorn main:app --reload --port 8000   # TASK_MODE=inline, file cache: no other services needed
pytest
```

Environment variables (all optional):

| Variable | Default | |
| --- | --- | --- |
| `TASK_MODE` | `celery` if `RABBITMQ_URL` is set, else `inline` | where jobs run |
| `RABBITMQ_URL` | — | Celery broker |
| `GRAPH_STORE` | `neo4j` if `NEO4J_URI` is set, else `file` | record cache |
| `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` | | Neo4j connection |
| `CACHE_DIR` | `cache/artists` | file cache location |
| `ARTIFACT_DIR` | `artifacts` | generated SVGs and job status |
| `MB_USER_AGENT` | project URL | identify yourself to MusicBrainz |
| `FRONTEND_DIST` | `static` | serve a built frontend from this folder, if present |

Render the offline demo from the command line:

```bash
python -c "from app.pipeline import generate; print(generate('demo:yardbirds', 'demo', {'depth': 4}))"
# -> artifacts/demo.svg
```
