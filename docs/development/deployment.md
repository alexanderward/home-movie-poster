# Raspberry Pi and LG deployment

Use 64-bit Raspberry Pi OS on a Pi 4 or 5 with Docker Engine and Compose. Clone the repository, create `.env`, set a strong Django key, add a TMDB read token, set `DJANGO_ALLOWED_HOSTS` to the Pi address or hostname, then run:

```sh
docker compose --env-file .env \
  -f docker/compose.yaml \
  up --build -d
```

SQLite, selected posters, and the one transient live cover persist in the `poster-data` volume. Both application services restart automatically. Port 8000 is exposed to the LAN by default.

Open `http://PI_ADDRESS:8000/admin` on a phone. Open `http://PI_ADDRESS:8000/display` in the LG browser and enable its full-screen behavior if available. Use display settings to select 0°, 90°, or 270° based on the physical mount.

The monitor requires Linux host networking for SDDP multicast, passive advertisements, and UDP port 1443. Keep the Pi and Kaleidescape on the same broadcast domain. Use the manual hostname only when multicast cannot cross the network layout.

Back up the `poster-data` volume. Do not expose Django through router port forwarding.
