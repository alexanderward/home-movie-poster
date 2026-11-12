from django.conf import settings


def test_sqlite_is_the_only_persistent_service() -> None:
    database = settings.DATABASES["default"]

    assert database["ENGINE"] == "django.db.backends.sqlite3"
    assert database["OPTIONS"]["transaction_mode"] == "IMMEDIATE"
    assert "CHANNEL_LAYERS" not in dir(settings)
