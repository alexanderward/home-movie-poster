# Design system

Home Movie Poster uses a quiet theatrical visual language: black lacquer backgrounds, warm ivory
type, restrained gold accents, and generous negative space around unmodified poster art.

## Display

- Compose on a 9:16 virtual canvas and support 0°, 90°, and 270° rotation.
- The television is mounted vertically: lay it out like a theater marquee, with the poster at full
  canvas width and a single title band beneath. Never use a side-by-side landscape layout; an
  unrotated landscape screen shows the portrait canvas pillarboxed as a preview.
- Never crop the primary poster. Decorative background treatments may blur the same image.
- Keep status labels uppercase and letter-spaced. Keep title, date, and showtime fully readable.
- Progress is a thin gold rule with an ivory leading edge.

## Admin page

- Optimize for a 390-pixel phone viewport without sacrificing desktop use.
- Use large touch targets, visible labels, complete wrapping text, and reserved loading space.
- Use the same palette as the display, with bordered panels and clear success/error feedback.
- Forms use explicit labels, visible focus states, and keyboard-accessible controls.
- The admin is one view. "Up next" lists scheduled movie nights; "Find a movie" searches
  TMDB plus uploaded or previously selected posters (150 ms debounce, no submit button) and shows
  one poster card per film, merging a film found in several places. Each card has a round +/✓
  slideshow toggle on the poster and one quiet Schedule button (a date sheet that defaults to the
  next free Friday; on a scheduled film it becomes Reschedule and moves that night). Scheduling a TMDB
  film saves its presentation metadata without adding it to the slideshow.
- "Slideshow" sits between them: the count, interval, recently added thumbnails (each with ×
  to remove, with Undo in the toast), an Add tile that jumps to search, Show all, and a Preview
  link to `/display?preview=slideshow`, which shows the slideshow even while a movie night or
  playback would take over the TV. It says when a scheduled movie night is holding it.
- Settings (display, server address, Strato player, and TMDB status) is secondary, behind the
  header button (`/admin?view=settings`). It is a single column of grouped panels (label and hint
  on the left, control on the right; stacked on phones). There are no per-section save buttons: a
  floating "Unsaved changes · Discard · Save" bar appears only while a draft differs from what's saved.
- Each view loads only its own data. Search inputs are debounced, row toggles update in place, and
  unsaved form drafts are never overwritten by a background refresh.
- Success toasts dismiss themselves; errors stay until dismissed. Destructive actions take a
  second tap to confirm.
