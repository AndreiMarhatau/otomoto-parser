# otomoto-parser

GraphQL-based parser that paginates through results and appends items to a JSONL file.

## Setup

I use `uv`:

```
uv sync
uv run otomoto-parser "https://www.otomoto.pl/..."
```

## Usage

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

## How it works (short)

- Retries GraphQL requests with exponential backoff (default 4 attempts, base 1s; configurable).
- Adds a random delay between pages (default 10–20s; configurable).
- Recommended: sort results by “Najnowsze” so you can keep iterating and append newer listings as they appear.
