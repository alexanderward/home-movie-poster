from datetime import date, timedelta

import pytest
from django.test import Client
from django.utils import timezone

from apps.server.apps.posters.contracts import MovieNightInput
from apps.server.apps.posters.models import (
    ApplicationSettings,
    DiscoveredDevice,
    Movie,
    MovieNight,
    PlaybackSnapshot,
    PosterAsset,
)
from apps.server.apps.posters.monitor import PosterMonitor, ProbeResult
from apps.server.apps.posters.selectors import display_state
from apps.server.apps.posters.services import ConflictError, save_movie_night

pytestmark = [pytest.mark.postgres, pytest.mark.django_db(transaction=True)]


def movie(title="Feature", source_key="movie-1", poster=True):
    asset = None
    if poster:
        asset = PosterAsset.objects.create(path=f"posters/{source_key}.jpg", width=100, height=150)
    return Movie.objects.create(
        source=Movie.Source.KALEIDESCAPE,
        source_key=source_key,
        title=title,
        normalized_title=title.casefold(),
        poster=asset,
    )


def test_display_priority_playback_schedule_rotation(monkeypatch):
    config = ApplicationSettings.load()
    config.slideshow_interval_seconds = 60
    config.save()
    scheduled = movie("Scheduled", "scheduled")
    rotating = movie("Rotation", "rotation")
    MovieNight.objects.create(movie=scheduled, event_date=timezone.localdate() + timedelta(days=1))
    assert display_state().title == "Scheduled"

    PlaybackSnapshot.objects.create(
        title="Playing",
        normalized_title="playing",
        play_status="paused",
        connected=True,
        observed_at=timezone.now(),
    )
    state = display_state()
    assert state.mode == "now_playing"
    assert state.playback_status == "paused"
    assert rotating.include_in_rotation


def test_stale_disconnected_playback_expires_to_schedule():
    scheduled = movie("Tonight")
    MovieNight.objects.create(movie=scheduled, event_date=timezone.localdate())
    PlaybackSnapshot.objects.create(
        title="Old state",
        normalized_title="oldstate",
        play_status="playing",
        connected=False,
        observed_at=timezone.now() - timedelta(seconds=31),
    )
    state = display_state()
    assert state.mode == "scheduled"
    assert state.headline == "Tonight"


def write_playback(monitor, status, title):
    monitor.write_snapshot(
        connected=True,
        play_status=status,
        title=title,
        year=None,
        duration=7200,
        position=60,
        poster_id=None,
        observed=timezone.now(),
    )


def tonight():
    config = ApplicationSettings.load()
    config.timezone = timezone.get_current_timezone_name()
    config.save()
    return timezone.localdate()


def test_other_title_stopping_reverts_to_scheduled_movie_night():
    MovieNight.objects.create(movie=movie("Tonight"), event_date=tonight())
    monitor = PosterMonitor()
    write_playback(monitor, "playing", "Something Else")
    assert display_state().mode == "now_playing"

    write_playback(monitor, "none", "")
    state = display_state()
    assert state.mode == "scheduled"
    assert state.title == "Tonight"


def test_watching_tonights_movie_retires_it_to_the_slideshow():
    MovieNight.objects.create(movie=movie("Tonight"), event_date=tonight())
    movie("Rotation", "rotation")
    monitor = PosterMonitor()
    write_playback(monitor, "playing", "Tonight")
    assert display_state().title == "Tonight"
    assert display_state().mode == "now_playing"

    write_playback(monitor, "none", "")
    assert MovieNight.objects.get().archived
    state = display_state()
    assert state.mode == "rotation"
    assert state.title == "Rotation"


def test_watching_a_future_movie_nights_title_keeps_it_scheduled():
    MovieNight.objects.create(movie=movie("Friday"), event_date=tonight() + timedelta(days=2))
    monitor = PosterMonitor()
    write_playback(monitor, "playing", "Friday")
    write_playback(monitor, "stopped", "Friday")
    assert not MovieNight.objects.get().archived
    assert display_state().mode == "scheduled"


def test_duplicate_movie_night_date_is_rejected():
    first = movie("First", "first")
    second = movie("Second", "second")
    event_date = date.today() + timedelta(days=3)
    save_movie_night(MovieNightInput(movie_id=first.id, event_date=event_date))
    with pytest.raises(ConflictError, match="already uses"):
        save_movie_night(MovieNightInput(movie_id=second.id, event_date=event_date))


def test_dhcp_address_change_updates_device_by_serial():
    monitor = PosterMonitor()
    first = ProbeResult("SERIAL", "192.0.2.10", "Player", "Strato", 1, True, True)
    second = ProbeResult("SERIAL", "192.0.2.99", "Player", "Strato", 1, True, True)
    monitor.persist_probe(first)
    monitor.persist_probe(second)
    assert DiscoveredDevice.objects.get(pk="SERIAL").ip_address == "192.0.2.99"


def test_multiple_players_require_selection_but_single_library_auto_selects():
    now = timezone.now()
    DiscoveredDevice.objects.create(
        serial_number="PLAYER-1", ip_address="192.0.2.1", supports_playback=True, last_seen_at=now
    )
    DiscoveredDevice.objects.create(
        serial_number="PLAYER-2", ip_address="192.0.2.2", supports_playback=True, last_seen_at=now
    )
    DiscoveredDevice.objects.create(
        serial_number="LIBRARY", ip_address="192.0.2.3", supports_library=True, last_seen_at=now
    )
    PosterMonitor.auto_select_roles()
    config = ApplicationSettings.load()
    assert config.player_serial == ""
    assert config.library_serial == "LIBRARY"


def test_movie_matching_prefers_kaleidescape_then_unique_tmdb(monkeypatch):
    kaleidescape = movie("Exact", "kscape")
    kaleidescape.year = 2025
    kaleidescape.save()
    tmdb = Movie.objects.create(
        source=Movie.Source.TMDB,
        source_key="55",
        title="Exact",
        normalized_title="exact",
        year=2025,
        poster=PosterAsset.objects.create(path="posters/tmdb.jpg", width=100, height=150),
    )
    monkeypatch.setenv("TMDB_READ_TOKEN", "configured")
    assert PosterMonitor.match_poster("Exact", 2025) == kaleidescape.poster_id
    kaleidescape.available = False
    kaleidescape.save()
    assert PosterMonitor.match_poster("Exact", 2025) == tmdb.poster_id


def test_mutations_require_same_origin_csrf_token():
    client = Client(enforce_csrf_checks=True)
    session = client.get("/api/session")
    token = session.json()["csrf_token"]
    assert client.post("/api/library-sync").status_code == 403
    assert client.post("/api/library-sync", HTTP_X_CSRFTOKEN=token).status_code == 202


def test_slideshow_preview_ignores_scheduled_movie_night():
    scheduled = movie("Scheduled", "scheduled-preview")
    rotating = movie("Rotating", "rotating-preview")
    scheduled.include_in_rotation = False
    scheduled.save()
    save_movie_night(
        MovieNightInput(movie_id=scheduled.id, event_date=timezone.localdate() + timedelta(days=3))
    )
    assert display_state().mode == "scheduled"
    preview = display_state(slideshow_only=True)
    assert preview.mode == "rotation"
    assert preview.title == rotating.title
