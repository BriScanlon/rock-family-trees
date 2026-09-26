# Progress log

Where the project stands, what was learned, and what's next. Open work is tracked in GitHub issues: #2 shop, #3 print-on-demand fulfilment, #4 routing and white space, #5 anecdotes.

## Status (end of first build session)

Working end to end: search → harvest → refine → fit to paper → layout → SVG → viewer, PNG and SVG download.
- 42 backend tests pass (`cd backend && pytest`), all offline.
- The UI was driven in headless Chromium: search, demo, draw, zoom, PNG export, paper badge.
- **Not yet tested** (the sandbox had no access): live MusicBrainz, Neo4j, and Docker Compose with RabbitMQ. Do this first on a normal machine:
  1. `docker compose up --build`, or run the backend and frontend directly (see `CLAUDE.md`).
  2. Search a real band, e.g. AC/DC, Deep Purple or Fleetwood Mac, at depth 2 then 3.
  3. Check instruments, dates, deaths and genres (for automatic lettering) come through from MusicBrainz, and that a second run is served from the cache (`api_calls` 0 in the job result).
  4. `python backend/tests/live_smoke.py`.

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
