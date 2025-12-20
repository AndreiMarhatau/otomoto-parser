# otomoto-parser

Simple Playwright-based parser that paginates through results and appends items to a JSONL file.

## Usage

By default, each unique search URL gets its own output folder under `runs/`.

```
otomoto-parser "https://www.otomoto.pl/..."
```

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
