# Getting started

## Prerequisites

- Docker Engine with Compose v2
- Python 3.12.8 and `uv` 0.6.6 or newer
- Node 22.23.3 and pnpm 12.11.2 (the setup command can bootstrap pnpm through npm/npx)
- GNU Make

No development container is used.

## Setup

1. Copy `.env.example` to the ignored `.env` file.
2. Change `DJANGO_SECRET_KEY` and the database password before deploying.
3. Run `make setup`.
4. Run `make start` for the complete Docker stack.
5. Open `http://localhost:8000/admin` on a phone-sized browser and `http://localhost:8000/display` for the television.

For native Windows discovery, start the Docker stack without its monitor (`docker compose -f docker/compose.yaml up --scale monitor=0`) and run `make monitor` in a second terminal.

## Development split

Use `make web` for Django on port 8001 and `make client` for Vite on 5173. Vite proxies API and media paths to Django. PostgreSQL and Redis may still run through Compose.

## Verification

Run `make lint`, `make python-types`, `make client-build`, and `make test`. PostgreSQL integration and Playwright journeys are separate commands because they require services or a browser install.
