# Frame

## Product purpose

Frame gives a household a portrait display that reacts to Kaleidescape playback, advertises the
next movie night, and otherwise rotates through one chosen gallery collection.

## Users and environment

- A household administrator uses a phone on the trusted LAN to choose movies and configure display behavior.
- A vertically mounted LG television keeps the display route open in its built-in browser.
- A Raspberry Pi 4 or 5 runs the two-service Docker stack and communicates with Strato over the LAN.

## Product rules

- Playback and pause always override scheduled and rotating posters.
- The app discovers players and retains the selection by serial number rather than fixed IP address.
- Posters remain uncropped. Status and showtime occupy the extra portrait space.
- Collections are named galleries of movie posters, uploaded artwork, and photos. An item may
  belong to several collections. Exactly one collection, or none, is on the TV at a time.
- TMDB is the searchable movie catalog; only scheduled movies and collection items are saved locally.
- Kaleidescape is read-only and supplies live playback state, progress, and current cover art only.
- The admin page is intentionally unauthenticated and must remain on a trusted LAN.
