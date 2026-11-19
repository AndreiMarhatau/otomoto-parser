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

The app will be available on port `8000` on the Docker host.
For example: `http://127.0.0.1:8000`.
By default, Docker Compose publishes it on all interfaces.

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

### Optional access code

Open **Settings → Access code** (or `/access` to sign in). With no code,
existing behavior is unchanged. Set an 8–128 character code **on your trusted local
network before publishing the app**. Anyone with access while protection is off
can set it. The browser remembers a 365-day HttpOnly, host-only session, not the code.
Active sessions renew in their last 30 days; there is no fixed lifetime while used.
Logout persistently revokes that session, including earlier renewed tokens.
Existing valid cookies upgrade without requiring the code; clearing browser cookies
or 365 days without renewal requires signing in again.
All API routes and API documentation require authentication while enabled.
Initial setup asks for the new code twice; changes ask for current, new and repeat.
Changing/disabling the code requires the current code and invalidates old sessions.
Codes are salted/scrypt-hashed; configuration persists in `access.json` in the
application data directory (the existing `/data` Docker volume). No `.env` needed.
Login/configuration attempts are limited globally to 10 per minute per process.
Run a single application worker; this lightweight file-backed gate is not a
multi-worker identity service. Use HTTPS at your reverse proxy, forward the original
Host, and configure Uvicorn to trust forwarded scheme headers only from that proxy.
Do not publish port 8000 directly. Never publish an instance with protection off.
The previous wildcard CORS policy is removed; serve UI/API from the same origin.
To recover a forgotten code, stop the app and remove only `access.json` locally,
then restart and configure a replacement before exposing it again.
