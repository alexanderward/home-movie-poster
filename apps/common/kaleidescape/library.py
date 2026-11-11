from __future__ import annotations

import html
from dataclasses import dataclass

from bs4 import BeautifulSoup


@dataclass(frozen=True)
class LibraryEntry:
    handle: str
    title: str
    year: int | None
    genre: str = ""
    rating: str = ""
    director: str = ""


def _text(row, selector: str) -> str:
    node = row.select_one(selector)
    return html.unescape(node.get_text(" ", strip=True)) if node else ""


def parse_movies_page(contents: str) -> list[LibraryEntry]:
    soup = BeautifulSoup(contents, "lxml")
    entries: list[LibraryEntry] = []
    seen: set[str] = set()
    for row in soup.select("tr.movie_container[selection_handle]"):
        raw_handle = row.get("selection_handle")
        handle = raw_handle.strip() if isinstance(raw_handle, str) else ""
        title = _text(row, ".movie_title a") or _text(row, ".movie_title")
        if not handle or not title or handle in seen:
            continue
        raw_year = _text(row, ".movie_year")
        entries.append(
            LibraryEntry(
                handle=handle,
                title=title,
                year=int(raw_year) if raw_year.isdigit() else None,
                genre=_text(row, ".movie_genre"),
                rating=_text(row, ".movie_rating"),
                director=_text(row, ".movie_director"),
            )
        )
        seen.add(handle)
    return entries
