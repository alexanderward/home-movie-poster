# System overview

The repository is a Python `uv` monorepo with a React client inside `apps/client`. Django owns the
HTTP contracts and the small durable presentation state. A separate asynchronous monitor owns
read-only Strato discovery and playback observation.

```text
LG / phone browser
        |
    Django :8000  -------- TMDB search and selected metadata
     /        \
React bundle  SQLite + selected poster files
                   ^
                   |
        read-only monitor process
            /             \
     SDDP / UDP 1443   pykaleidescape playback
```

## Runtime decisions

- Django 5.2 and Django Ninja provide same-origin HTTP APIs and serve the built React bundle.
- Pydantic models own public contracts; `make client-contracts` generates TypeScript.
- The display polls its small state endpoint once per second. No WebSocket broker is required.
- SQLite in WAL mode stores settings, saved TMDB/manual presentations, schedules, slideshow flags,
  discovery state, one monitor heartbeat, and one playback snapshot.
- Selected TMDB and uploaded posters are normalized into a local media directory. Strato live art
  uses one replaceable runtime file and is never added to the saved catalog.
- Production consists of two containers from one image: `web` and the host-networked `monitor`.

## Display resolution

`selectors.display_state()` is the single priority resolver. It chooses active playback observed
within the 30-second grace window, then the nearest future movie night, then an eligible shuffled
poster, then setup state. HTTP polling serializes that Pydantic model.

## Search and saved presentation state

TMDB is the searchable catalog. Search results remain remote until a user schedules a movie or adds
it to the slideshow. At that point the server saves only the TMDB identifier, title, year, slideshow
flag, and a normalized poster. Manual uploads use the same compact presentation model.

The application never enumerates or mirrors the Kaleidescape library. A live title may reuse a
previously selected poster by normalized title and year when Strato does not provide current art.

## Discovery and stable identity

The monitor performs active SDDP searches, accepts passive SDDP replies, and listens for older UDP
heartbeats on port 1443. Candidates are probed with `pykaleidescape`; the selected player is stored
by serial number, and a changed address updates the existing row. A manual address is a last-resort
discovery seed.

Only the monitor container uses host networking. On Windows, run `make monitor` natively when Docker
Desktop does not deliver multicast reliably.

## LG webOS

The display uses conservative flex/grid CSS, JPEG posters, an uncropped `object-fit: contain` image,
and Vite's legacy bundle with polyfills. Rotation occurs around a virtual canvas whose dimensions are
swapped at 90 degrees and 270 degrees. Physical-device testing remains required because LG browser
generations vary.

## Security and media

Mutations require same-origin CSRF tokens. Remote poster downloads are restricted to discovered
Strato addresses or approved TMDB image hosts, then decoded, resized, metadata-stripped, and
re-encoded as JPEG. Credentials, bodies, cookies, poster bytes, and artwork URLs are excluded from
logs. The service remains LAN-only and intentionally unauthenticated.
