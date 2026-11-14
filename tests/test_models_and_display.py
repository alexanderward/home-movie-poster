import json
from datetime import date, timedelta

import pytest
from django.test import Client
from django.utils import timezone

from apps.server.apps.posters.contracts import DisplayOverrideInput, MovieNightInput
from apps.server.apps.posters.models import (
    ApplicationSettings,
    DiscoveredDevice,
    Movie,
    MovieNight,
    PlaybackSnapshot,
    PosterAsset,
)
from apps.server.apps.posters.monitor import PosterMonitor, ProbeResult
from apps.server.apps.posters.selectors import display_state, resolve_display
from apps.server.apps.posters.services import (
    ConflictError,
    add_to_collection,
    create_collection,
    save_movie_night,
    set_display_override,
)

pytestmark = pytest.mark.django_db(transaction=True)


def movie(title="Feature", source_key="movie-1", poster=True):
    asset = None
    if poster:
        asset = PosterAsset.objects.create(path=f"posters/{source_key}.jpg", width=100, height=150)
    return Movie.objects.create(
        source=Movie.Source.MANUAL,
        source_key=source_key,
        title=title,
        normalized_title=title.casefold(),
        poster=asset,
    )


def in_slideshow(*movies):
    """Put movies in the active collection, which the idle slideshow rotates through."""
    collection = create_collection("Slideshow")
    for row in movies:
        add_to_collection(collection.id, row.id)
    return collection


def test_display_priority_playback_schedule_rotation(monkeypatch):
    config = ApplicationSettings.load()
    config.slideshow_interval_seconds = 60
    config.save()
    scheduled = movie("Scheduled", "scheduled")
    in_slideshow(movie("Rotation", "rotation"))
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
    assert state.headline == "Paused"
    PlaybackSnapshot.objects.filter(pk=1).update(play_status="playing")
    assert display_state().headline == "Now Playing"

    PlaybackSnapshot.objects.all().delete()
    MovieNight.objects.all().delete()
    state = display_state()
    assert (state.mode, state.headline, state.title) == ("rotation", "Slideshow", "Rotation")


def test_playing_position_advances_on_the_server_clock():
    PlaybackSnapshot.objects.create(
        title="Playing",
        normalized_title="playing",
        play_status="playing",
        connected=True,
        position_seconds=600,
        duration_seconds=7200,
        observed_at=timezone.now() - timedelta(seconds=10),
    )
    assert 610 <= display_state().position_seconds <= 612

    PlaybackSnapshot.objects.filter(pk=1).update(play_status="paused")
    assert display_state().position_seconds == 600

    PlaybackSnapshot.objects.filter(pk=1).update(play_status="playing", position_seconds=7195)
    assert display_state().position_seconds == 7200


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


@pytest.mark.parametrize(
    ("days_away", "expected"),
    [(0, "Tonight"), (1, "Tomorrow Night"), (6, None), (7, "Coming Soon"), (21, "Coming Soon")],
)
def test_scheduled_headline_names_a_weekday_only_within_the_week(days_away, expected):
    event_date = timezone.localdate() + timedelta(days=days_away)
    MovieNight.objects.create(movie=movie(), event_date=event_date)
    assert display_state().headline == (expected or f"Coming {event_date.strftime('%A')}")


def write_playback(monitor, status, title):
    monitor.write_snapshot(
        connected=True,
        play_status=status,
        title=title,
        year=None,
        duration=7200,
        position=60,
        poster_path="",
        poster_source_hash="",
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
    scheduled = movie("Tonight")
    MovieNight.objects.create(movie=scheduled, event_date=tonight())
    in_slideshow(movie("Rotation", "rotation"))
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
    first = ProbeResult("SERIAL", "192.0.2.10", "Player", "Strato", 1, True)
    second = ProbeResult("SERIAL", "192.0.2.99", "Player", "Strato", 1, True)
    monitor.persist_probe(first)
    monitor.persist_probe(second)
    assert DiscoveredDevice.objects.get(pk="SERIAL").ip_address == "192.0.2.99"


def test_multiple_players_require_selection():
    now = timezone.now()
    DiscoveredDevice.objects.create(
        serial_number="PLAYER-1", ip_address="192.0.2.1", supports_playback=True, last_seen_at=now
    )
    DiscoveredDevice.objects.create(
        serial_number="PLAYER-2", ip_address="192.0.2.2", supports_playback=True, last_seen_at=now
    )
    PosterMonitor.auto_select_player()
    config = ApplicationSettings.load()
    assert config.player_serial == ""


def test_movie_matching_uses_saved_tmdb_presentation():
    tmdb = Movie.objects.create(
        source=Movie.Source.TMDB,
        source_key="55",
        title="Exact",
        normalized_title="exact",
        year=2025,
        poster=PosterAsset.objects.create(path="posters/tmdb.jpg", width=100, height=150),
    )
    assert PosterMonitor.match_poster("Exact", 2025) == tmdb.poster.path


def test_mutations_require_same_origin_csrf_token():
    client = Client(enforce_csrf_checks=True)
    session = client.get("/api/session")
    token = session.json()["csrf_token"]
    payload = json.dumps({"player_serial": "", "manual_host": "192.0.2.10"})
    assert client.put("/api/devices/player", payload, content_type="application/json").status_code == 403
    assert (
        client.put(
            "/api/devices/player",
            payload,
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        ).status_code
        == 200
    )


def test_slideshow_preview_ignores_scheduled_movie_night():
    scheduled = movie("Scheduled", "scheduled-preview")
    rotating = movie("Rotating", "rotating-preview")
    in_slideshow(rotating)
    save_movie_night(
        MovieNightInput(movie_id=scheduled.id, event_date=timezone.localdate() + timedelta(days=3))
    )
    assert display_state().mode == "scheduled"
    preview = display_state(slideshow_only=True)
    assert preview.mode == "rotation"
    assert preview.title == rotating.title


def test_forced_slideshow_beats_playback_and_movie_night():
    scheduled = movie("Scheduled", "forced-scheduled")
    in_slideshow(movie("Rotating", "forced-rotating"))
    save_movie_night(
        MovieNightInput(movie_id=scheduled.id, event_date=timezone.localdate() + timedelta(days=1))
    )
    PlaybackSnapshot.objects.create(
        title="Playing", play_status="playing", connected=True, observed_at=timezone.now()
    )
    assert display_state().mode == "now_playing"

    set_display_override(DisplayOverrideInput(mode="slideshow"))
    resolved, forced = resolve_display()
    assert (resolved.mode, resolved.title, forced) == ("rotation", "Rotating", True)

    set_display_override(DisplayOverrideInput(mode="movie_night"))
    assert (display_state().mode, display_state().title) == ("scheduled", "Scheduled")

    set_display_override(DisplayOverrideInput(mode="auto"))
    assert display_state().mode == "now_playing"


def test_forced_slideshow_can_show_a_collection_that_is_not_active():
    in_slideshow(movie("Default", "default-art"))
    other = create_collection("Holidays")
    add_to_collection(other.id, movie("Ornament", "ornament").id)
    set_display_override(DisplayOverrideInput(mode="slideshow", collection_id=other.id))
    state = display_state()
    assert (state.title, state.headline) == ("Ornament", "Holidays")
    assert ApplicationSettings.load().active_collection_id != other.id


def test_pinned_poster_stays_until_switched_back():
    pinned = movie("Pinned", "pinned")
    in_slideshow(movie("Rotating", "pinned-rotating"))
    set_display_override(DisplayOverrideInput(mode="poster", movie_id=pinned.id))
    state = display_state()
    assert (state.mode, state.title, state.headline) == ("pinned", "Pinned", "")
    # The admin's slideshow preview tab ignores the override.
    assert display_state(slideshow_only=True).title == "Rotating"
    with pytest.raises(ValueError):
        set_display_override(DisplayOverrideInput(mode="poster"))
    with pytest.raises(ValueError):
        set_display_override(
            DisplayOverrideInput(mode="poster", movie_id=movie("Bare", "bare", poster=False).id)
        )


def test_forced_source_with_nothing_to_show_falls_back_to_automatic():
    in_slideshow(movie("Rotating", "fallback-rotating"))
    set_display_override(DisplayOverrideInput(mode="movie_night"))
    state, forced = resolve_display()
    assert (state.mode, forced) == ("rotation", False)

    pinned = movie("Pinned", "fallback-pinned")
    set_display_override(DisplayOverrideInput(mode="poster", movie_id=pinned.id))
    pinned.delete()
    state, forced = resolve_display()
    assert (state.mode, forced) == ("rotation", False)


def test_override_endpoint_reports_what_the_tv_shows():
    client = Client(enforce_csrf_checks=True)
    token = client.get("/api/session").json()["csrf_token"]
    in_slideshow(movie("Rotating", "endpoint-rotating"))
    pinned = movie("Pinned", "endpoint-pinned")
    response = client.put(
        "/api/display/override",
        data=json.dumps({"mode": "poster", "movie_id": pinned.id}),
        content_type="application/json",
        headers={"X-CSRFToken": token},
    )
    assert response.status_code == 200
    body = response.json()
    assert (body["mode"], body["forced"], body["movie"]["id"]) == ("poster", True, pinned.id)
    assert body["now"]["mode"] == "pinned"
    assert client.get("/api/display").json()["title"] == "Pinned"
    assert client.get("/api/display/override").json()["mode"] == "poster"
