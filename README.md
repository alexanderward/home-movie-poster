# Home Movie Poster

Home Movie Poster turns a portrait-mounted television into a live cinema display. It discovers a
Kaleidescape system on the local network, shows active playback and progress, schedules movie
nights, and rotates through locally cached posters while the player is idle.

The application is a Django/Django Ninja API with a React/Vite client. PostgreSQL owns durable
state, Redis carries live display updates, and the dedicated monitor process owns all
Kaleidescape network activity.

```bash
make start
```

Open <http://localhost:8000/display> for the display and <http://localhost:8000/admin> for the
phone-friendly admin page. On Windows, run `make monitor` natively when Docker Desktop cannot expose
LAN multicast traffic to the monitor container.

Read the [documentation index](docs/README.md) for product behavior, architecture, deployment, and
validation. Run `make` to list public commands.

