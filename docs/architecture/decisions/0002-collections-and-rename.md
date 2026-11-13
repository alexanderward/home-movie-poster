# Decision: gallery collections and the Frame name

## Status

Accepted on 2026-11-11.

## Context

The idle slideshow was one global set of movie posters, chosen with a per-movie flag. The household
also wants to show uploaded artwork and photos, grouped into themed sets that can be switched, so
"Home Movie Poster" no longer described the product.

## Decision

- Rename the product to **Frame** (package and image `home-frame`, CLI `frame`).
- Replace the per-movie `include_in_rotation` flag with named collections joined to saved items
  many-to-many, and one nullable `active_collection` setting that feeds the idle slideshow.
- Keep Kaleidescape now-playing and movie nights unchanged; collections replace only the slideshow.
- Keep internal identifiers that would force data moves: the Django app label `posters` (its table
  names), the `Movie` model for every saved item, the `POSTER_*` environment variables, and the
  Docker volume name `home-movie-poster_poster-data`.

## Consequences

Switching what the TV shows is one tap, and an image can appear in several themes without being
stored twice. Migration 0003 moves the old slideshow into an active "Movies" collection and is
reversible. Code reads "movie" where it now means any saved image; a rename of that model can follow
separately if it starts to cause confusion.
