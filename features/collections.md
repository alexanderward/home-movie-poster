# Gallery collections

A collection is a named gallery: movie posters from TMDB, uploaded artwork, family photos, or any
mix. Items are saved once and may belong to any number of collections.

- **On the TV.** Exactly one collection, or none, is active. The idle slideshow rotates only through
  the active collection; playback and the next movie night still take priority
  unless the TV is [forced](display.md#forcing-the-tv) to a slideshow.
- **TV headline.** Each collection chooses what the TV's top band says during its slideshow: an
  optional headline of up to 40 characters ("Now Showing", "Coming Attractions"), falling back to
  the collection's name, or no headline at all so the poster stands alone. Edit it from the
  collection's Edit sheet.
- **Creating.** Names are unique regardless of case. The first collection created becomes active
  automatically so a fresh install shows something without a second step.
- **Adding.** In the admin page, the + on a search result adds it to the selected collection,
  importing a TMDB film first if needed. "Upload images to <name>" stores each file and adds it to
  that collection. A single upload may have a title and year; several at once are titled from their
  file names.
- **Removing.** × on a thumbnail removes the item from that collection only (with Undo). Deleting a
  collection keeps its items; if it was active, nothing is on the TV until another is chosen.
- **Migration.** Upgrading from the single slideshow moves every item that was in it into a
  collection named "Movies" and makes it active.

API: `GET/POST /api/collections`, `GET/PATCH/DELETE /api/collections/{id}` (`PATCH` takes any of
`name`, `tv_headline`, `show_headline`; omitted fields are unchanged),
`PUT/DELETE /api/collections/{id}/items/{movie_id}`, and `PUT /api/collections/active`
(`{"collection_id": id | null}`). `POST /api/movies/manual` accepts an optional `collection_id`.
