# Environment

Copy `.env.example` to `.env`. The real file is ignored.

| Variable | Meaning |
| --- | --- |
| `DJANGO_SECRET_KEY` | Local Django signing key; replace before deployment. |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated LAN names or addresses. |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Database credentials. |
| `POSTER_TIME_ZONE` | IANA zone for movie-night calendar values. |
| `POSTER_MEDIA_ROOT` | Normalized poster directory; `/data/media` in containers. |
| `POSTER_REDIS_URL` | Redis database used by Channels and monitor health. |
| `TMDB_READ_TOKEN` | Optional TMDB API read token. Never returned by the API. |
| `LOG_LEVEL` | Python log threshold. |
| `LOG_JSON` | Set to `1` for JSON logs. |
| `WEB_PORT` | LAN-facing nginx port, default 8000. |
| `POSTGRES_PORT`, `REDIS_PORT` | Loopback ports used by native tooling and host-networked monitor. |

Do not commit `.env`, media, database data, Kaleidescape addresses, cached posters, or logs.
