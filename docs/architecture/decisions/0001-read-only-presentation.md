# Decision: read-only presentation architecture

## Status

Accepted on 2026-11-11.

## Context

Home Movie Poster is a household display controller, not a second movie catalog. The initial design
used PostgreSQL, PgBouncer, Redis, Channels, nginx, and an undocumented Kaleidescape `/movies`
adapter. Strato V does not expose that legacy page, and the product does not need to retain the
private Kaleidescape library.

## Decision

- Treat Strato as a read-only live playback source.
- Use TMDB as the searchable catalog.
- Save only selected presentation metadata, schedules, slideshow membership, settings, and poster
  assets in SQLite.
- Keep one transient playback snapshot and one replaceable Strato cover.
- Use one-second HTTP polling instead of WebSockets and Redis.
- Serve the built React client and media directly from Django.
- Deploy one shared image as `web` and host-networked `monitor` services.

## Consequences

The system is smaller, easier to back up, and independent of Kaleidescape library internals. TMDB is
required for catalog search, although saved selections and manual uploads continue to display when
TMDB is unavailable. One-second polling adds negligible LAN traffic and removes broker operations.
The SQLite file and media directory must live on the same host and be backed up together.
