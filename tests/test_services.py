from apps.server.apps.posters.services import merge_poster_results, normalize_title


def test_title_normalization_ignores_punctuation_case_and_suffix():
    assert normalize_title("WALL·E (2008)") == "walle"
    assert normalize_title("Wall-E") == "walle"


def local(movie_id, title, year, source="kaleidescape", source_key=None, rotation=True):
    from apps.server.apps.posters.models import Movie

    return Movie(
        id=movie_id,
        source=source,
        source_key=source_key or f"k{movie_id}",
        title=title,
        normalized_title=normalize_title(title),
        year=year,
        include_in_rotation=rotation,
    )


def tmdb(tmdb_id, title, year):
    return {"id": tmdb_id, "title": title, "year": year, "poster_url": f"https://t/{tmdb_id}.jpg"}


def test_merge_prefers_kaleidescape_copy_of_a_tmdb_hit():
    results = merge_poster_results(
        [local(1, "The Terminator", 1984)], [tmdb(218, "The Terminator", 1984)]
    )
    assert len(results) == 1
    assert results[0].movie_id == 1
    assert results[0].tmdb_id == 218
    assert results[0].sources == ["kaleidescape", "tmdb"]


def test_merge_matches_previously_imported_tmdb_movie_by_id():
    imported = local(2, "Terminator 2", 1991, source="tmdb", source_key="280")
    results = merge_poster_results([imported], [tmdb(280, "Terminator 2: Judgment Day", 1991)])
    assert [(row.movie_id, row.sources) for row in results] == [(2, ["tmdb"])]


def test_merge_collapses_kaleidescape_and_imported_copies():
    results = merge_poster_results(
        [local(3, "Heat", 1995, source="tmdb", source_key="949"), local(4, "Heat", 1995)],
        [tmdb(949, "Heat", 1995)],
    )
    assert len(results) == 1
    assert results[0].movie_id == 4
    assert results[0].sources == ["kaleidescape", "tmdb"]


def test_merge_keeps_remakes_with_different_years_apart():
    results = merge_poster_results([local(5, "Dune", 2021)], [tmdb(841, "Dune", 1984)])
    assert [(row.key, row.include_in_rotation) for row in results] == [
        ("movie:5", True),
        ("tmdb:841", False),
    ]
