from django.conf import settings


def test_channel_layer_allows_blocking_redis_reads() -> None:
    hosts = settings.CHANNEL_LAYERS["default"]["CONFIG"]["hosts"]

    assert hosts == [{"address": settings.REDIS_URL, "socket_timeout": None}]
