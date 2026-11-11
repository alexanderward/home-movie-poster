# System overview

The repository is a Python `uv` monorepo with a React client inside `apps/client`. Django owns persistence and the HTTP contracts; one separate asynchronous monitor owns discovery, the long-lived Kaleidescape connection, and library synchronization.

```text
LG / phone browser
        |
      nginx :8000
       /       \
 React bundle  Django Ninja + Channels
                    |             |
                 PgBouncer      Redis
                    |             |
                PostgreSQL   monitor heartbeat/state
                                  |
                  dedicated monitor process
                    /                    \
             SDDP / UDP 1443       pykaleidescape + /movies
```

## Runtime decisions

- Django 5.2 and Django Ninja provide same-origin HTTP APIs.
- Pydantic models own public contracts; `make client-contracts` generates TypeScript.
- Channels sends immediate display state and the client polls every five seconds when a socket is unavailable.
- PostgreSQL 18 stores configuration, library, schedule, sync history, and the last playback snapshot.
- PgBouncer uses transaction pooling. Django uses `CONN_MAX_AGE=0` and disables server-side cursors.
- Redis stores the monitor heartbeat and backs Channels. The Channels connection has no
  client-side read deadline because its queue receive is intentionally a blocking Redis
  operation; connection and process failures are still handled by Channels reconnection and
  the browser's HTTP polling fallback.
- nginx is the only LAN-facing process in production.

## Display resolution

`selectors.display_state()` is the single priority resolver. It chooses active playback observed within the 30-second grace window, then the nearest future movie night, then an eligible shuffled poster, then setup state. Both HTTP and WebSocket delivery serialize that same Pydantic model.

## Discovery and stable identity

The monitor performs active SDDP searches, accepts passive SDDP replies, and listens for older UDP heartbeats on port 1443. Candidates are probed with `pykaleidescape`; roles are stored by serial number, and a changed address updates the existing row. A manual hostname is a last-resort discovery seed.

Only the monitor container uses host networking. Django, nginx, PostgreSQL, PgBouncer, and Redis remain on the Compose network. On Windows, run `make monitor` natively because Docker Desktop may not deliver multicast reliably.

## Compatibility boundaries

### Kaleidescape `/movies`

The documented control protocol can resolve content details but cannot enumerate the complete library. `apps/common/kaleidescape/library.py` isolates parsing of the storage component's undocumented local `/movies` HTML. Sanitized fixtures lock expected behavior. A malformed or empty response fails the sync and retains the last successful library.

### LG webOS

The display uses conservative flex/grid CSS, JPEG posters, an uncropped `object-fit: contain` image, and Vite's legacy bundle with polyfills. Rotation occurs around a virtual canvas whose dimensions are swapped at 90° and 270°. Physical-device testing remains required because LG browser generations vary.

## Security and media

Mutations require same-origin CSRF tokens. Remote poster downloads are restricted to selected/discovered Kaleidescape addresses or approved TMDB image hosts, then decoded, resized, metadata-stripped, and re-encoded as JPEG. Credentials, bodies, cookies, poster bytes, and Kaleidescape artwork URLs are excluded from logs.
