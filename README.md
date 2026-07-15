# Pokemon Cube Finder

A local FastAPI web application for comparing a Pokemon TCG card collection
against Pokemon cube lists and ranking cubes by completion.

## Planned Scope

- Import a TCGplayer collection CSV with flexible column detection.
- Import CubeKoga cube lists through a dedicated source adapter.
- Compare owned cards against cube requirements with quantity-aware allocation.
- Rank cubes by copy completion, without using price data.
- Export missing-card lists as CSV.
- Keep pricing support as a future extension point.

## Development Setup

This project targets Python 3.12 on Linux.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
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

Repository initialized with the planned app structure. Implementation will
follow the architecture in `app/` and `tests/`.
