from apps.server.apps.posters.services import normalize_title


def test_title_normalization_ignores_punctuation_case_and_suffix():
    assert normalize_title("WALL·E (2008)") == "walle"
    assert normalize_title("Wall-E") == "walle"
