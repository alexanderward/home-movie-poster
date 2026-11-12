# Environment

Copy `.env.example` to `.env`. The real file is ignored.

| Variable | Meaning |
| --- | --- |
| `DJANGO_SECRET_KEY` | Local Django signing key; replace before deployment. |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated LAN names or addresses. |
| `POSTER_DATABASE_PATH` | SQLite database path; `/data/poster.sqlite3` in containers. |
| `POSTER_TIME_ZONE` | IANA zone for movie-night calendar values. |
| `POSTER_MEDIA_ROOT` | Normalized poster directory; `/data/media` in containers. |
| `TMDB_READ_TOKEN` | TMDB API read token used for movie search. Never returned by the API. |
| `KALEIDESCAPE_MANUAL_HOST` | Optional direct Strato address when multicast discovery is unavailable. |
| `LOG_LEVEL` | Python log threshold. |
| `LOG_JSON` | Set to `1` for JSON logs. |
| `WEB_PORT` | LAN-facing Django port, default 8000. |

Do not commit `.env`, media, database data, Kaleidescape addresses, cached posters, or logs.
