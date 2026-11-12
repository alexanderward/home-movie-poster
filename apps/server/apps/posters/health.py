from __future__ import annotations

import os
from datetime import timedelta

from django.db import connection
from django.utils import timezone

from .contracts import HealthView
from .models import MonitorHeartbeat, PlaybackSnapshot


def health() -> HealthView:
    database = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        database = False

    heartbeat = MonitorHeartbeat.objects.filter(pk=1).first() if database else None
    monitor = bool(
        heartbeat and heartbeat.observed_at >= timezone.now() - timedelta(seconds=30)
    )
    snapshot = PlaybackSnapshot.objects.filter(pk=1).first() if database else None
    tmdb_configured = bool(os.environ.get("TMDB_READ_TOKEN"))
    ok = database and monitor and tmdb_configured
    return HealthView(
        status="ok" if ok else "degraded",
        database=database,
        monitor=monitor,
        player_connected=bool(snapshot and snapshot.connected),
        tmdb_configured=tmdb_configured,
    )
