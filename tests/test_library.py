from pathlib import Path

from apps.common.kaleidescape.library import parse_movies_page


def test_movies_adapter_handles_entities_duplicates_and_missing_fields():
    html = (Path(__file__).parent / "fixtures" / "movies.html").read_text(encoding="utf-8")
    entries = parse_movies_page(html)
    assert [(entry.handle, entry.title, entry.year) for entry in entries] == [
        ("h-1", "Wall-E & Friends", 2008),
        ("h-2", "Unknown Year", None),
    ]
    assert entries[0].genre == "Animation"


def test_malformed_or_unrecognized_movies_page_is_empty():
    assert parse_movies_page("<html><tr selection_handle='x'>broken") == []
