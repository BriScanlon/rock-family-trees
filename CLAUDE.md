# Rock Family Tree Generator — notes for Claude

Generates printable posters in the style of **Pete Frame's Rock Family Trees** from MusicBrainz data. The goal is output that genuinely looks like Frame's hand-drawn originals. Full history, research and measurements: `docs/PROGRESS.md`. Open work: GitHub issues #2 (shop), #3 (print-on-demand), #4 (routing / white space), #5 (anecdotes), #6 (choosing bands and line-up detail), #7 (Wikipedia and Wikidata as a source), #8 (content first, then a placement optimiser).

## Run and test

```bash
cd backend && pip install -r requirements-dev.txt && pytest          # ~90 tests, no network needed
uvicorn main:app --port 8000                                          # inline jobs + JSON file cache
cd frontend && npm install && npm run dev                              # http://localhost:3000, proxies /api
python backend/tests/live_smoke.py http://localhost:8000               # needs real MusicBrainz access
docker compose up --build                                              # full stack: RabbitMQ, Neo4j, worker
```

Offline demos (no network): artist ids `demo:yardbirds` and `demo:acdc` (search "yardbirds" / "ac/dc"). The data is approximate, written from general knowledge, in `backend/app/fixtures.py`. The two families connect via Jimmy Page and The Firm.

Render an SVG from the command line: `cd backend && python -c "from app.pipeline import generate; print(generate('demo:acdc','x',{'depth':3,'paper':'A1'}))"`, which writes `artifacts/x.svg`. To look at it, screenshot it with Playwright/Chromium. Always look at the output after layout or style changes.

## Pipeline (backend/app)

`musicbrainz.py` (JSON client, 1 req/s, `inc=artist-rels+genres`) → `store.py`/`graph_db.py` (cache: Neo4j or JSON files) → `harvester.py` (band → members → other bands, by generation, fetch budget spent on the bands reached through founders and long-serving members first) → `refiner.py` (dates, stints, line-ups, band ranking; Wikipedia member charts from `charts.py` applied here) → `wikipedia.py` + `narrative.py` (notes written from Wikipedia by a model, stored in Neo4j) → `fitting.py` (what goes on the sheet) → `grid.py` (Frame's grid layout; `cartographer.py` keeps the lane layout for timeline mode and shared helpers) → `artist.py` (SVG). `pipeline.py` wires them together; `jobs.py`/`worker.py`/`main.py` handle jobs and the API.

## Decisions already made (don't undo without asking)

- **Look** (checked against a photo of Frame's Black Sabbath / Ozzy Osbourne tree; the user said *not* to commit that photo):
  - Black ink on white, and line-ups are **not boxed**. The band name is large, with the dates stacked small beside it, then a ruled bar with members hanging from it **side by side**: first name over surname, one instrument beneath in lowercase full words.
  - One line per musician runs down to their place in the next line-up. A replacement takes the vacated column.
  - Notes are sentence-case paragraphs **inside the block, under the band name and above the bar**, wrapped to the line-up's width (as on Frame's Faces and Uriah Heep trees; the user confirmed the grid). A block may widen by up to two members to fit them.
  - A condensed line-up tells what it hides **under the members**, as Frame did: "then T. Hawkins", "after W. Goldsmith", "joined Mar 97", "left Sep 97"; anyone else goes in the notes ("Pat Smear rejoined in 2010.", "Briefly also: …"). Never "Simplified to fit".
  - No numbered circles, no parchment, no wobble by default (Frame used a ruler).
- **Lettering styles** (`fonts.STYLES`):
  - `classic`: Architects Daughter capitals and an outlined, shadowed title. The user said the Yardbirds poster in this style was "perfect".
  - `heavy`: Amatic SC, tall and narrow, for metal and hard rock (Sabbath / Ozzy).
  - `auto` chooses from MusicBrainz genres.
  - Styles need inline `style=` for font-family and fill, because the SVG stylesheet overrides presentation attributes.
- **Readability rules print size**: the smallest text must print at ≥ `MIN_PRINT_PT` (6.5pt) on the chosen sheet.
- **Layout is Frame's grid, flowing** (`grid.py`): one member-wide slot per musician (a block may stretch up to 1.8x into free columns beside it). Rows are split into quarter rows (`SUB`), so each column keeps its own pace; titles are *not* level across the page (the user chose a full page over that). A line-up takes only its own members' width and may drift up to `DRIFT` half-columns from the one before it. The packer fills holes, not just below what's drawn. **Time runs down each band and along every move** (a line-up starts below the bottom of the one its musicians left; a re-formed band goes below its earlier runs), but *not* down every column (`TIME_COLUMNS = False`, the user's choice: it let 5 more bands onto the Deep Purple A1). Moves are routed round the blocks themselves. Rows are not spread apart to reach the bottom (`MAX_SPREAD = 0`).
- **Fitting fills the grid breadth first** (`fitting.py`): more bands before more line-ups. Every band that fits at its simplest goes in, in ranking order; then detail is restored band by band while it fits. The root band takes at most 60% of the rows. `paper=auto` picks the smallest sheet that holds the whole family at full detail. Timeline mode keeps the older lane layout.
- **Ranking** (`refiner.Refiner._select`): a link is a shared musician, worth the geometric mean of their years in each band, ×2 for a direct move (left one, joined the other within 2 years), ×0.3 for a side project running alongside. Founders ("original") count as at least 10 years; undated memberships count as 0.25. Design and next steps (band significance via Wikidata, calibration families): GitHub issue #6.
- **Notes from Wikipedia** (`narrative.py`): Wikipedia is a *reference only*; the notes are written fresh and never copied (CC BY-SA). Every note must quote its source passage; code drops a note whose source isn't in the article, that shares 6 ordinary words with it (names and titles excepted), or that says more than its source (a second model pass). Stored in Neo4j (`Band-HAS_NOTES->NoteSet-INCLUDES->Note`, dropped ones too) and recalled, keyed on prompt fingerprint, model, article revision and line-ups. The user asked for all generated notes to be stored so they can be recalled.
- **The model is local by default:** Qwen3 14B through Ollama on the user's RX 7900 XT (20 GB). The model is `rftg-qwen3`, built from `ollama/Modelfile` with a 40,960-token context; the user wants a high context size. On Windows Ollama runs natively (Docker Desktop can't give a container an AMD GPU); containers reach it at `host.docker.internal:11434`. **One request at a time** (lock file on the data volume plus `OLLAMA_NUM_PARALLEL=1`). The LAN server at 192.168.4.118 has only 6 GB of VRAM, so it isn't used.
- **Wikipedia member charts correct MusicBrainz** (`charts.py`): stored beside MusicBrainz's memberships, never over them, and applied in the refiner for the members the chart lists; MusicBrainz's word stands for everyone else.
- **A poster waits only for its top bands** (`content.py`): notes for the top 15, events for the top 12 (4 albums, 2 tours each); every other band uses what's stored. After the poster, a background job (`enrich_family`) reads notes and events for the whole family (6 albums each), stepping aside whenever a poster is being made (`narrative.foreground/background`). Events are rated per band in one pass (`events.rank`), and the best (4+) get room kept beside their line-up while packing (root band 3, others 1). The user's first Oasis poster waited hours before this.
- **Events** (`events.py`, the user's idea): moments from each band's longest album and tour articles on Wikipedia (Wikidata finds them; ranked by article length), written by the model with the same source checks as the band notes (a misquoted source is replaced by the article sentence it came from), stored as NoteSets on Album/Tour nodes, significance 1-5; sales, charts and reissues are excluded.
- **Albums are notes in the band's history**: each is a dated `Album` node on its band in Neo4j (`Band-RELEASED->Album`, full release date), told in the block of the line-up together on its release date ("Recorded Burn (1974), ..."). **Never a list apart, and never in the side panels** (the user's instructions, twice). A block widens for its albums; if still short of room it says "and N more". Studio albums come from one MusicBrainz search per band.
- **Fill the page** as Frame did (his trees are 2-3% blank; the user wants no significant white space). **No side panels or lists apart** (the user's instruction): every piece of information is a note attached to the right band or musician at the right time. A block keeps whole sentences only; what it can't hold, and every event of significance 3+, becomes a *floating note* - its own small block near its line-up, tied to it with a dotted line (`GridLayout._place_notes`). A band's style goes on its first line-up. Where its longest-serving musicians played off the poster is told once each (`GridLayout._info_notes`): "also with" a band joined while a member, "went on to" one joined after leaving (on their last line-up), "previously with" one from before (on their first). The user allows rearranging bands and enlarging the text to fill space. Measure white space on the rendered PNG (share of empty tiles), not by eye.
- **Content first, then placement** (the user's instruction, issue #8): build every candidate band's line-ups, notes, albums and links before trying placements, then optimise placement for chronology, page coverage and content together. The optimiser (`optimise.py`, simulated annealing from the greedy fit, `OPTIMISE_SECONDS`) may add bands, change detail, move bands and enlarge text, but **never drops a band the greedy ranking chose**.
- Every generated SVG is self-contained: fonts are embedded as data URIs, and only the faces in use are included.
- Job status is shared through JSON files in `ARTIFACT_DIR`, not a Celery result backend.

## Conventions

- Match the existing code style; comments explain *why*.
- Keep tests offline, using the fixtures or `tests/helpers.py`. Add a test for each layout rule you rely on.
- Commit messages should explain the reason and include measurements when layout changes.
- Real MusicBrainz data, Neo4j and the Docker stack were first tested on 2026-09-26 (see `docs/PROGRESS.md`). MusicBrainz data can be wrong: Dave Grohl's Foo Fighters membership is recorded as October 1994 only.
- On Windows, Docker Desktop's VM clock drifts and steps backwards: the MusicBrainz rate limiter uses `time.monotonic()` for that reason.
