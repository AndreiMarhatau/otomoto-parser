# otomoto-parser

This repository now contains two tracks:

- `v1`: the original CLI parser and Excel aggregation flow.
- `v2`: a Python backend + React UI for request history, progress tracking, and categorized listing review.

## Setup

I use `uv`:

```
uv sync
uv run otomoto-parser "https://www.otomoto.pl/..."
```

To run the new app:

```
uv run parser-app
```

That starts the Python backend and serves the built React UI from the same process.

The app stores request history, parser progress, categorized results, and Excel exports under `.parser-app-data/` by default.

## Docker

Build and run with Docker Compose:

```
docker compose up --build
```

The app will be available at `http://127.0.0.1:8000`.

Persistent app data is stored in the named Docker volume `parser_app_data`, mounted inside the container at `/data`.

## Usage

## v1 CLI usage

By default, each unique search URL gets its own output folder under `runs/`.

```
otomoto-parser "https://www.otomoto.pl/..."
```

You can also run it interactively; omit the URL and/or mode and it will prompt you.

The parser supports three run modes:

- `resume` (default): continue from the last processed page for this URL.
- `append-newer`: start from page 1 and stop once an existing listing is encountered.
- `full`: start from scratch and overwrite existing output/state.

Example:

```
otomoto-parser "https://www.otomoto.pl/..." --mode append-newer
```

To override output paths manually:

```
otomoto-parser "https://www.otomoto.pl/..." --output /tmp/results.jsonl --state /tmp/state.json
```

Each JSONL record includes the full GraphQL node/edge data so you get all available fields, including image URLs (e.g. thumbnail sizes).

## v2 categorization rules

Listings are categorized in this order:

1. No `priceEvaluation` data: `Price evaluation out of range`
2. `cepikVerified` is false: `Data not verified`
3. `country_origin` is `us`: `Imported from US`
4. Everything else: `To be checked`

## How it works (short)

- Retries GraphQL requests with exponential backoff (default 4 attempts, base 1s; configurable).
- Adds a random delay between pages (default 10–20s; configurable).
- Recommended: sort results by “Najnowsze” so you can keep iterating and append newer listings as they appear.
