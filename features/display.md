# TV display and rotation

The route `/display` renders a virtual canvas. At 90° and 270° the virtual width and height swap before the transform, so layout is calculated in the television's final orientation. Posters always use containment and remain fully visible.

The display polls the small state endpoint once per second. Playback position advances locally only during `playing` and corrects against each monitor observation.

Idle rotation defaults to 60 seconds and shows only the active [collection](collections.md); items without an image are skipped. The resolver uses a deterministic shuffle bag so images do not repeat before the collection is exhausted. With no active collection, or an empty one, the TV shows setup guidance.

## What the TV shows

Automatically, in priority order: what the player is playing (or paused on), then the next
movie night, then the active collection's slideshow, then setup guidance.

## Forcing the TV

"On the TV" at the top of the admin page overrides that order immediately (the TV picks it up
on its next one-second poll). An override stays on until someone chooses **Automatic** again.

- **Movie night** shows the next movie night even while something is playing.
- **Slideshow** shows a collection even during playback or before a movie night. It uses the
  active collection unless another one is picked, without changing which collection is active.
- **Poster** pins one image. Pin it with the pin button on any image in a collection; tapping
  the pin again returns the TV to automatic. A pinned poster has no headline.

When the forced source has nothing to show (no movie night scheduled, an empty collection, a
pinned image that was deleted), the TV follows the automatic order, and the admin says so. The
admin's slideshow **Preview** tab ignores overrides.

API: `GET /api/display/override` and `PUT /api/display/override` with
`{"mode": "auto" | "movie_night" | "slideshow" | "poster", "collection_id"?, "movie_id"?}`.
Both return the override and what the TV is showing now (`forced` is false when it fell back).
