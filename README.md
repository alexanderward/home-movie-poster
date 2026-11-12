# Home Movie Poster

Home Movie Poster turns a portrait-mounted television into a live cinema display. It discovers a
Kaleidescape system on the local network, shows active playback and progress, schedules movie
nights, and rotates through a small set of selected posters while the player is idle.

The application is a Django/Django Ninja API with a React/Vite client. SQLite stores presentation
settings and selections, TMDB supplies search metadata, and a dedicated read-only monitor follows
Strato playback. The application never imports or mirrors the Kaleidescape library.

```bash
make start
```

Open <http://localhost:8000/display> for the display and <http://localhost:8000/admin> for the
phone-friendly admin page. On Windows, run `make monitor` natively when Docker Desktop cannot expose
LAN multicast traffic to the monitor container.

Read the [documentation index](docs/README.md) for product behavior, architecture, deployment, and
validation. Run `make` to list public commands.

