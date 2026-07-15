# Pokemon Cube Finder

A local FastAPI web application for comparing a Pokemon TCG card collection
against Pokemon cube lists and ranking cubes by completion.

## Current Features

- Upload and preview a TCGplayer-style collection CSV.
- Detect likely columns for card name, set, set code, collector number, quantity,
  printing, and condition.
- Manually correct the column mapping before replacing the stored collection.
- Import manual cube lists from pasted text or CSV.
- Probe CubeKoga URLs through a dedicated adapter and fail back to manual import
  when CubeKoga does not expose readable structured data.
- Compare cubes against your collection with deterministic quantity allocation.
- Show exact-printing matches separately from name-only matches.
- Rank cubes by copy completion, missing copies, unique completion, or cube name.
- Export each cube's missing cards as CSV.
- Keep pricing isolated behind a future `PriceProvider` interface.

## Development Setup

This project targets Python 3.12 on Linux.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

## Database

The SQLite database is created automatically on app startup. To initialize it
without starting the server:

```bash
python -c "from app.database import init_db; init_db()"
```

## Run Locally

```bash
uvicorn app.main:app --reload
```

The application will be available at <http://127.0.0.1:8000>.

## Tests

```bash
pytest
```

## Status

Version 1 is functional for local collection upload, manual cube import,
completion ranking, cube details, and missing-card export. CubeKoga support is
isolated in `app/adapters/cube_sources/cubekoga.py`; it validates CubeKoga URLs
and probes likely structured endpoints, but may need a real public cube URL to
harden against CubeKoga's current frontend data flow.
