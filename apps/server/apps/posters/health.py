from __future__ import annotations

from datetime import timedelta

from django.core.cache import cache
from django.db import connection
from django.utils import timezone

from .contracts import HealthView
from .models import LibrarySync, PlaybackSnapshot


def health() -> HealthView:
    database = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        database = False

    redis = True
    try:
        cache.set("health:probe", "ok", 10)
        redis = cache.get("health:probe") == "ok"
    except Exception:
        redis = False

    heartbeat = cache.get("monitor:heartbeat") if redis else None
    monitor = bool(heartbeat and heartbeat >= timezone.now() - timedelta(seconds=30))
    snapshot = PlaybackSnapshot.objects.filter(pk=1).first() if database else None
    completed = (
        LibrarySync.objects.filter(status=LibrarySync.Status.SUCCEEDED).first()
        if database
        else None
    )
    ok = database and redis and monitor
    return HealthView(
        status="ok" if ok else "degraded",
        database=database,
        redis=redis,
        monitor=monitor,
        player_connected=bool(snapshot and snapshot.connected),
        last_library_sync=completed.finished_at if completed else None,
    )
