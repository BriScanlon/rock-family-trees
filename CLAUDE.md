# Rock Family Tree Generator — notes for Claude

Generates printable posters in the style of **Pete Frame's Rock Family Trees** from MusicBrainz data. The goal is output that genuinely looks like Frame's hand-drawn originals. Full history, research and measurements: `docs/PROGRESS.md`. Open work: GitHub issues #2 (shop), #3 (print-on-demand), #4 (routing / white space), #5 (anecdotes).

## Run and test

```bash
cd backend && pip install -r requirements-dev.txt && pytest          # ~40 tests, no network needed
uvicorn main:app --port 8000                                          # inline jobs + JSON file cache
cd frontend && npm install && npm run dev                              # http://localhost:3000, proxies /api
python backend/tests/live_smoke.py http://localhost:8000               # needs real MusicBrainz access
docker compose up --build                                              # full stack: RabbitMQ, Neo4j, worker
```

Offline demos (no network): artist ids `demo:yardbirds` and `demo:acdc` (search "yardbirds" / "ac/dc"). The data is approximate, written from general knowledge, in `backend/app/fixtures.py`. The two families connect via Jimmy Page and The Firm.

Render an SVG from the command line: `cd backend && python -c "from app.pipeline import generate; print(generate('demo:acdc','x',{'depth':3,'paper':'A1'}))"`, which writes `artifacts/x.svg`. To look at it, screenshot it with Playwright/Chromium. Always look at the output after layout or style changes.

## Pipeline (backend/app)

`musicbrainz.py` (JSON client, 1 req/s, `inc=artist-rels+genres`) → `store.py`/`graph_db.py` (cache: Neo4j or JSON files) → `harvester.py` (band → members → other bands, by generation, fetch budget) → `refiner.py` (dates, stints, line-ups, band priority) → `fitting.py` (trim to paper) → `cartographer.py` (layout) → `artist.py` (SVG). `pipeline.py` wires them together; `jobs.py`/`worker.py`/`main.py` handle jobs and the API.

## Decisions already made (don't undo without asking)

- **Look** (checked against a photo of Frame's Black Sabbath / Ozzy Osbourne tree; the user said *not* to commit that photo):
  - Black ink on white, and line-ups are **not boxed**. The band name is large, with the dates stacked small beside it, then a ruled bar with members hanging from it **side by side**: first name over surname, one instrument beneath in lowercase full words.
  - One line per musician runs down to their place in the next line-up. A replacement takes the vacated column.
  - Notes are sentence-case paragraphs beside the line-up.
  - No numbered circles, no parchment, no wobble by default (Frame used a ruler).
- **Lettering styles** (`fonts.STYLES`):
  - `classic`: Architects Daughter capitals and an outlined, shadowed title. The user said the Yardbirds poster in this style was "perfect".
  - `heavy`: Amatic SC, tall and narrow, for metal and hard rock (Sabbath / Ozzy).
  - `auto` chooses from MusicBrainz genres.
  - Styles need inline `style=` for font-family and fill, because the SVG stylesheet overrides presentation attributes.
- **Readability rules print size**: the smallest text must print at ≥ `MIN_PRINT_PT` (6.5pt) on the chosen sheet.
  - `fitting.py` drops the least-connected bands first. Bands are ranked by the years their shared musicians served in bands already chosen.
  - Only if the root band alone won't fit does it fold line-ups together, and each folded line-up gets a "Simplified to fit" note. Never silently invent line-ups.
  - `paper=auto` picks the smallest sheet that holds the whole family.
- **Layout**: compact packing by default. Each lane packs tightly, keeping time order within lanes and along musicians' moves. A strict time grid is used only when `timeline=True` (year scale).
- Every generated SVG is self-contained: fonts are embedded as data URIs, and only the faces in use are included.
- Job status is shared through JSON files in `ARTIFACT_DIR`, not a Celery result backend.

## Conventions

- Match the existing code style; comments explain *why*.
- Keep tests offline, using the fixtures or `tests/helpers.py`. Add a test for each layout rule you rely on.
- Commit messages should explain the reason and include measurements when layout changes.
- The development sandbox that built this could not reach MusicBrainz, Neo4j or most websites, so real-data behaviour is still untested. Test it first when running somewhere with network access.
