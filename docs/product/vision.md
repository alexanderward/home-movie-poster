# Vision and scope

Home Movie Poster turns a vertically mounted television into a calm, accurate cinema marquee. It follows a Strato player in real time, advertises the next family movie night while the player is idle, and otherwise rotates through a deliberately small slideshow.

## Primary users

- A household member looking at the dedicated LG display.
- A trusted household administrator using a phone on the same LAN.

## Product rules

Playback always wins. Playing, paused, scan-forward, and scan-reverse states display `Now Playing`; a connection loss preserves that state for 30 seconds. The next unarchived movie night follows, then the no-repeat poster rotation, then setup guidance.

Movie-night dates are local calendar values in the configured timezone. Events may use any date, with a next-Friday shortcut. Today is `Tonight`, a future Friday is `Coming Friday`, and other dates use `Coming <weekday>`.

Posters are never cropped. The TV layout reserves remaining space for the headline, title, showtime, pause state, and a slim playback progress bar.

## Sources

- TMDB supplies movie search and presentation metadata and requires a read token in `.env`.
- Kaleidescape supplies read-only live playback state and current artwork; its library is never imported.
- Manual title, year, and poster upload is always available.

## Boundaries

The service is free, self-hosted, LAN-only, and intentionally unauthenticated. It does not stream video, control playback, enumerate or store a private Kaleidescape library, or expose itself safely to the internet.
