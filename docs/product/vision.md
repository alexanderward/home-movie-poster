# Vision and scope

Home Movie Poster turns a vertically mounted television into a calm, accurate cinema marquee. It follows a Kaleidescape player in real time, advertises the next family movie night while the player is idle, and otherwise rotates through the local movie library.

## Primary users

- A household member looking at the dedicated LG display.
- A trusted household administrator using a phone on the same LAN.

## Product rules

Playback always wins. Playing, paused, scan-forward, and scan-reverse states display `Now Playing`; a connection loss preserves that state for 30 seconds. The next unarchived movie night follows, then the no-repeat poster rotation, then setup guidance.

Movie-night dates are local calendar values in the configured timezone. Events may use any date, with a next-Friday shortcut. Today is `Tonight`, a future Friday is `Coming Friday`, and other dates use `Coming <weekday>`.

Posters are never cropped. The TV layout reserves remaining space for the headline, title, showtime, pause state, and a slim playback progress bar.

## Sources

- Kaleidescape library metadata and artwork are the preferred source.
- TMDB is optional and requires a token in `.env`.
- Manual title, year, and poster upload is always available.

## Boundaries

The service is free, self-hosted, LAN-only, and intentionally unauthenticated. It does not stream video, control playback, expose itself safely to the internet, or upload a private movie library to a hosted service.
