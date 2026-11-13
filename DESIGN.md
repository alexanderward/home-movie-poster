# Design system

Frame uses a quiet theatrical visual language: black lacquer backgrounds, warm ivory
type, restrained gold accents, and generous negative space around unmodified poster art.

## Display

- Compose on a 9:16 virtual canvas and support 0°, 90°, and 270° rotation.
- The television is mounted vertically: lay it out like a modern marquee, with a headline band above
  the poster and a billing band beneath it. The two bands split the space the full-width poster
  leaves exactly in half, and everything sits on one centered axis, like the poster itself. Never use
  a side-by-side landscape layout; an unrotated landscape screen shows the portrait canvas
  pillarboxed as a preview.
- Never crop the primary poster, and show only the poster itself: no blurred copies or other
  background art behind it. The display hides the pointer.
- Keep it crisp: solid fills on black and hairlines, no glows, text shadows, blur, pills, or
  skeuomorphic props. Both bands use bundled Bebas Neue, uppercase and letter-spaced. Gold is the
  only accent, used sparingly (rules, the showtime, time left, progress); red is reserved for the
  live dot.
- Never repeat what the poster or the other band already says. The poster carries the title, so
  neither band shows it.
- The top band says *when*: the headline, widely letter-spaced between two gold hairlines, with a
  pulsing red dot while a movie is playing ("Paused" replaces "Now Playing" while paused). During a
  slideshow it shows the collection's TV headline (its name by default), or nothing if the
  collection hides it.
- The bottom band adds only what's missing. For a scheduled night it shows the date (none for
  Tonight, month and day when the headline names the day, the short weekday and date behind Coming
  Soon) and the gold showtime. While playing it shows time in, a thin gold progress rule with an
  ivory leading edge, and gold time left. The slideshow leaves it empty.
- Keep title, date, and showtime fully readable.

## Admin page

- Optimize for a 390-pixel phone viewport without sacrificing desktop use.
- Use large touch targets, visible labels, complete wrapping text, and reserved loading space.
- Use the same palette as the display, with bordered panels and clear success/error feedback.
- Forms use explicit labels, visible focus states, and keyboard-accessible controls.
- The admin is one view. "Up next" lists scheduled movie nights; "Find a movie" searches
  TMDB plus uploaded or previously selected posters (150 ms debounce, no submit button) and shows
  one poster card per film, merging a film found in several places. Each card has a round +/✓
  toggle on the poster that adds it to or removes it from the selected collection, and one quiet
  Schedule button (a date sheet that defaults to the next free Friday; on a scheduled film it becomes
  Reschedule and moves that night). Scheduling a TMDB film saves its presentation metadata without
  adding it to a collection.
- "Collections" sits between them: a row of pill tabs (a green dot marks the one on the TV, each
  shows its count, and a dashed "+ New" tab opens a name sheet). The selected collection shows
  whether it is on the TV, Show on TV / Take off TV, Edit (a sheet with the name and the TV headline:
  a "Show a headline above the poster" toggle and an optional headline that defaults to the name), and
  two-tap Delete; then its recently
  added thumbnails (each with × to remove, with Undo in the toast), an Add tile that jumps to search,
  Show all, and an "Upload images to <name>" panel that accepts several files at once (titles come
  from file names). A Preview link opens `/display?preview=slideshow`, which shows the active
  collection even while a movie night or playback would take over the TV. The hint says when a
  scheduled movie night is holding it.
- Settings (display, server address, Strato player, and TMDB status) is secondary, behind the
  header button (`/admin?view=settings`). It is a single column of grouped panels (label and hint
  on the left, control on the right; stacked on phones). There are no per-section save buttons: a
  floating "Unsaved changes · Discard · Save" bar appears only while a draft differs from what's saved.
- Each view loads only its own data. Search inputs are debounced, row toggles update in place, and
  unsaved form drafts are never overwritten by a background refresh.
- Success toasts dismiss themselves; errors stay until dismissed. Destructive actions take a
  second tap to confirm.
