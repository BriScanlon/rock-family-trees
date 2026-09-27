# Progress log

Where the project stands, what was learned, and what's next. Open work is tracked in GitHub issues: #2 shop, #3 print-on-demand fulfilment, #4 routing and white space, #5 anecdotes, #6 choosing bands and line-up detail.

## Status (end of first build session)

Working end to end: search → harvest → refine → fit to paper → layout → SVG → viewer, PNG and SVG download.
- 42 backend tests pass (`cd backend && pytest`), all offline.
- The UI was driven in headless Chromium: search, demo, draw, zoom, PNG export, paper badge.
- **Not yet tested** (the sandbox had no access): live MusicBrainz, Neo4j, and Docker Compose with RabbitMQ. Do this first on a normal machine:
  1. `docker compose up --build`, or run the backend and frontend directly (see `CLAUDE.md`).
  2. Search a real band, e.g. AC/DC, Deep Purple or Fleetwood Mac, at depth 2 then 3.
  3. Check instruments, dates, deaths and genres (for automatic lettering) come through from MusicBrainz, and that a second run is served from the cache (`api_calls` 0 in the job result).
  4. `python backend/tests/live_smoke.py`.

## Status (first run on a real machine, 2026-09-26)

All four checks above now pass on Windows 11 with Docker Desktop 29.8 and Python 3.11:
- `pytest`: 42 passed.
- `docker compose up --build`: backend in celery mode, worker connected to RabbitMQ, Neo4j healthy, frontend returns 200.
- Real AC/DC at depth 2: 9 of 24 bands, 68 line-ups, 83 people on A0. Smallest text 7.6pt, names 14.7pt. Lettering chose `heavy` from genres. The first run made 55 MusicBrainz calls in 61s; the second came from the Neo4j cache in 0.5s with 0 calls. Neo4j then held 37 bands and 318 artists.
- `live_smoke.py` (Iron Maiden, depth 2): completed with 10 bands, 52 line-ups, 60 people on A0, 58 API calls.
- The real early AC/DC line-ups check out, including Evans to Scott and Larry Van Kriedt's return in 1975.

Seen in the real posters, for issue #4: move lines take long detours round the outside, the right-centre of the sheet is largely empty, and bands with frequent side-player changes (Manfred Mann's Earth Band, Uriah Heep) take up about 40% of the AC/DC sheet. Some members have no instrument, apparently because MusicBrainz has none for them.

Local gotcha: if other stacks already publish 7474/7687/15672, add a git-excluded `docker-compose.override.yml` that remaps rftg-neo4j and rftg-rabbitmq with `ports: !override`. The app doesn't need those host ports.

## Frame's grid, and choosing what goes on it (2026-09-27)

A Foo Fighters poster on A3 came out as one band, with the page largely empty. This session rebuilt the layout on Frame's own grid and changed how bands and line-ups are chosen. Design discussion: issue #6.

**What the real posters show** (Faces 1979; Uriah Heep / Colosseum / Thin Lizzy 1979; Deep Purple; Black Sabbath / Ozzy):
- Every musician takes the same width, so a line-up is exactly as wide as its members.
- Line-ups of one era share a row, with names and bars level across the page.
- The notes sit inside the block, under the band name. Our notes column beside each block was a misreading, and it cost about 3 members' width per band.
- Each band keeps its columns, so lines drop straight.
- Only significant changes are numbered. Minor ones are written under the member ("replaced by…").
- Nothing is left blank: discographies and anecdotes fill the gaps.

**The layout** (`grid.py`): the sheet at 6.5pt *is* the grid. On A2 with heavy lettering that's 49 half-member columns × 11 rows. Runs of line-ups are placed whole, in date order: below everything earlier in their columns, below where their musicians came from, near their era's row and the bands they share musicians with. When a later band pushes a source below its target, the placement repairs and re-places.

**What goes on it** (`fitting.py`): more bands before more line-ups. Every band that fits at its simplest goes in, in ranking order; then detail is restored band by band. The root band takes at most 60% of the rows. Condensed line-ups say what they hide under the members ("then F. Stahl", "joined 1995") and in the notes ("Pat Smear rejoined in 2010.").

**Ranking** (`refiner.py`, and the harvester's fetch budget): two-sided tenure, doubled for direct moves, reduced for side projects, founders as long-serving, undated memberships as nominal. Why Nirvana was missing: after a database wipe, the harvester's raw link count never fetched it (it tied with dozens of Grohl's minor projects). And once fetched, Grohl's broken MusicBrainz dates (Foo Fighters "1994-10 to 1994-10") made the link worth half a year.

Bands shown at 6.5pt:

| | A3 | A2 | A1 |
|---|---|---|---|
| Foo Fighters (real data), before | 1 | 1 | 5 |
| Foo Fighters, now | 9 (incl. Nirvana) | 12 | 19 |
| Yardbirds demo, before → now | 3 → 7 | 9 → 16 | 10 → 21 |
| AC/DC demo, before → now | 1 → 11 | 11 → 14 | 9 → 17 (all) |

Line-up blocks now use 55–82% of the grid on A3/A2/A1, against 14–23% of the drawing area before (not quite the same measure, but the same idea).

Also fixed: the MusicBrainz rate limiter uses a monotonic clock, because Docker Desktop's VM clock drifted an hour and stepped backwards, and a job slept for the size of the step. And job status writes retry on Windows, where replacing a file another thread is reading fails with `WinError 5`.

## Data quality, notes from Wikipedia, and filling the page (2026-09-27, later)

**Data fixes found on real posters** (Deep Purple A1):
- An undated MusicBrainz membership was stretched over the band's whole life. David Stone (Rainbow keyboards, 1977–78) appeared in every Rainbow line-up and hid the 1984–93 break. Undated members are now left out, and noted as "dates unknown", when at least half the band is dated. Founders and eponymous members keep the full span.
- A band only counts as "still going" if a dated membership is still open.
- Missing instruments are borrowed from the musician's other memberships.
- Renamings are noted ("Renamed The Maze").
- The instrument shown is the principal one (Gillan: vocals, not harmonica).

**Notes from Wikipedia** (issues #5, #7; `app/wikipedia.py`, `app/narrative.py`):
- MusicBrainz url-rels give the Wikidata item, which gives the article; the lead plus History section goes to a model with the band's line-ups.
- It returns short dated notes, each with its source passage. Code checks the source is in the article, the note doesn't share 6 ordinary words with it (names and titles excepted), and a second pass confirms the source supports every claim.
- **Model:** local Qwen3 14B through Ollama by default (`rftg-qwen3` in `ollama/Modelfile`: 40,960-token context, 15.7 GB, all in the RX 7900 XT's memory). On Windows Ollama runs natively, because Docker Desktop can't give a container an AMD GPU. Requests queue one at a time (a lock file on the shared data volume, plus `OLLAMA_NUM_PARALLEL=1`). Claude is the alternative (`NARRATIVE_BACKEND=anthropic`).
- **Stored in Neo4j:** `(:Band)-[:HAS_NOTES]->(:NoteSet)-[:INCLUDES]->(:Note)`, dropped notes included with the reason. Keyed on prompt fingerprint, model, article revision and line-ups, so improving the prompt writes afresh while older writings stay. If Wikipedia or the model is unreachable, the latest stored notes are used.
- Example: Mark II reads "Montreux fire inspires 'Smoke on the Water'; album recorded in hotel corridor".

**Filling the page.** Measured as the share of the drawing area with no ink (tiles about 1/48 of the width). Frame's Faces and Uriah Heep trees score 2–3%.

| Deep Purple A1 | Empty |
|---|---|
| Grid layout, notes for 8 bands | 58% |
| + text panels (albums only) | 54% |
| + 40 candidate bands, panels filled from several bands | 37–42% |
| + albums placed with the line-up that recorded them, columns spread to the sheet's edges | 39% |

The remaining gap is structural. The greedy placement can't revisit a choice, and the panels run out of material.

**Next** (agreed with the user):
1. **Content first:** build every candidate band's line-ups, notes, albums and links, stored in Neo4j, before any placement.
2. **Then a placement optimiser** scoring coverage, content and chronology (issue #8).
- Also: #6 band significance (Wikidata); Wikipedia member timelines (#7 stage 2) for Rainbow's missing 1990s line-ups; correct Grohl's Foo Fighters membership on MusicBrainz (needs the user's account).

## The placement optimiser (issue #8 stage 2, 2026-09-27)

`app/optimise.py` starts from the greedy fitting and runs simulated annealing for `OPTIMISE_SECONDS` (default 60). It varies:
- bands added beyond greedy's,
- each band's level of detail,
- a preferred column per band (`GridLayout(hints=...)`),
- the placement pulls and mirroring,
- the text scale, from 1.0 to 1.3× the smallest readable size.

The score is coverage + 0.35 content (rank-weighted bands) + 0.15 line-up detail + 0.1 notes shown − 0.5 chronology error (the distance from a straight time-to-row fit) + 0.15 × the text scale above 1.0.

The packer still enforces every hard rule. The **greedy choice's bands are always kept**: the first run swapped Gillan and The Artwoods for Hollywood Monsters and The Javelins because that filled the page better, which overturns the ranking.

Deep Purple A1 (40 candidate bands, 240 line-ups, 162 notes):
- greedy: 22 bands, 59 line-ups, 40% empty tiles;
- optimised for 60s: 22 bands, 61 line-ups, 38% empty (about 1,000 layouts tried);
- with swaps allowed: 25 bands, 34% empty, but ranked bands lost.

Most of the remaining white space is beside blocks within a row. Next steps are to widen blocks sideways into free columns, which is issue #4 territory, and to speed up the packer so more layouts can be tried.

## Line tracks (issue #4) and Wikipedia member charts (issue #7 stage 2), 2026-09-27

**Line tracks.** Parallel lines were offset by a counter cycling through five positions, so the sixth line in a gap lay on the first. `grid._Tracks` now gives each run the nearest track that is free along its whole length:
- channels have tracks 4px apart (seven in a 30px channel); gaps have tracks 5px apart;
- a departure's track sits above any arrival's in the same column, so their drops never merge.

On Deep Purple A1, overlapping runs between different musicians went from 6 to 1; the one left is in a channel full across its width. The old #4 ideas for the lane layout (lane ordering, 2D packing) are superseded by the grid. Rejoin stubs and bundles are not done: Frame drew those lines.

**Member charts.** `app/charts.py` reads a band's EasyTimeline chart from the wikitext of "List of X members", or else the article:
- it works out stints to the day, with the principal instrument taken from the full-width bar;
- it drops blips under 45 days and merges breaks under a month;
- the chart is stored on the band record (`chart`, `chart_source` = page@revision) beside MusicBrainz's memberships, never over them;
- the refiner applies it for the members it lists.

Deep Purple family: 13 of 80 candidate bands have a chart. Deep Purple now matches it exactly (Bolin on guitar, Satriani, the 1989 gap). Rainbow has none, and its MusicBrainz data is poor (Blackmore missing after 1993, roles blank): that is the case for the line-up confirmation graph, which is deferred.

## How the look was arrived at

1. First pass: boxed line-ups on aged paper with a Western title font. Research found Frame's trees are black ink on white, in precise architectural hand lettering (he trained as a surveyor/architect), with many handwritten notes. Sources: Eye Magazine "Branches and roots" (issue 78, 2010), Wikipedia, and interviews. Most pages couldn't be fetched from the sandbox, only searched.
2. The user supplied a photo of Frame's Black Sabbath / Ozzy Osbourne tree. That drove the current structure: unboxed line-ups, a bar with members hanging side by side, first name over surname with the instrument beneath, one line per musician, and prose notes beside each line-up. The photo is **not** to be committed.
3. The user noted Frame's lettering varies with the music. The classic architect hand (their favourite, on the Yardbirds poster) and the tall narrow "heavy" hand are both kept, with automatic choice by genre.

## Readability and white space (measured)

Method: rasterise the SVG, count 1/40-width tiles with no ink, and compute printed point sizes from px × (sheet mm / canvas px).

| | smallest text | names | empty sheet |
|---|---|---|---|
| Before (Yardbirds, 12 bands, A1, boxed grid rows) | 4.0pt | 4.7pt | 75% |
| Compact packing + inline notes + larger base sizes (same tree on A0) | 6.9pt | 9.1pt | 69% |
| 9-band tree on A1 | 7.1pt | 9.3pt | 58% |

Causes found:
- A global row per line-up (44 rows for 50 line-ups).
- A notes column reserved in every lane (about 25% of the width).
- The height is set by the longest chain of line-ups (e.g. Bluesbreakers into Fleetwood Mac).

The remaining white space and long lines are issue #4.

Fitting per sheet (AC/DC demo, 17 bands, 62 line-ups):
- A4: AC/DC only, simplified to 8 line-ups
- A3: AC/DC, 12 of 13 line-ups
- A2: 4 bands
- A1: 9 bands
- A0: all 17

Smallest text is 6.6–7.2pt throughout.

## Print-on-demand research (issue #3)

- **Prodigi** (UK): API v4 with a free sandbox. Global SKUs route orders to the nearest lab. It takes JPG/PNG/PDF at 300 dpi and can add bleed itself. Recommended first.
- **Gelato**: order API with webhooks. It takes PDF/X-4 in CMYK with 4mm bleed, and also SVG. Good second provider for worldwide delivery.
- **Printful**: API available, but it uses its own paper sizes rather than A-sizes.
- Payments: Stripe Checkout, fulfilling orders from the `checkout.session.completed` webhook.
- Still to do: server-side PDF export via headless Chromium, which renders the embedded fonts correctly.

## Ideas parked

- Anecdotes: see issue #5 for sources and the guardrails on generated text.
- Framed prints, accounts and order history: open questions in issue #2.
- A test print of A3 at 6.5pt to confirm the readability threshold on paper.
