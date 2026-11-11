# Home Movie Poster

## Product purpose

Home Movie Poster gives a household a portrait cinema display that reacts to Kaleidescape playback,
advertises the next movie night, and otherwise celebrates the local movie library.

## Users and environment

- A household administrator uses a phone on the trusted LAN to choose movies and configure display behavior.
- A vertically mounted LG television keeps the display route open in its built-in browser.
- A Raspberry Pi 4 or 5 runs the Docker stack and communicates with Kaleidescape components over the LAN.

## Product rules

- Playback and pause always override scheduled and rotating posters.
- The app discovers devices and retains selections by serial number rather than fixed IP address.
- Posters remain uncropped. Status and showtime occupy the extra portrait space.
- TMDB is optional; Kaleidescape and manual posters keep the application fully usable without it.
- The admin page is intentionally unauthenticated and must remain on a trusted LAN.
