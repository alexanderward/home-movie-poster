from __future__ import annotations

import hashlib
import os
import re
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings as django_settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.common.observability import event
from apps.common.posters import normalize_image

from .contracts import ApplicationSettingsInput, DeviceRolesInput, MovieNightInput
from .models import (
    ApplicationSettings,
    DiscoveredDevice,
    LibrarySync,
    Movie,
    MovieNight,
    PosterAsset,
)


class ConflictError(ValueError):
    """The requested state conflicts with an existing resource."""


class DependencyUnavailableError(RuntimeError):
    """An optional LAN or internet dependency could not serve the request."""


def normalize_title(value: str) -> str:
    value = re.sub(r"\([^)]*\)$", "", value).casefold()
    return re.sub(r"[^a-z0-9]+", "", value)


def store_poster(contents: bytes, *, source_url: str = "") -> PosterAsset:
    stored = normalize_image(contents, django_settings.MEDIA_ROOT)
    source_url_hash = hashlib.sha256(source_url.encode()).hexdigest() if source_url else ""
    asset, _ = PosterAsset.objects.get_or_create(
        path=stored.relative_path,
        defaults={
            "source_url_hash": source_url_hash,
            "width": stored.width,
            "height": stored.height,
        },
    )
    if source_url_hash and asset.source_url_hash != source_url_hash:
        asset.source_url_hash = source_url_hash
        asset.save(update_fields=["source_url_hash"])
    event("poster.cache.succeeded", asset_id=asset.id, width=asset.width, height=asset.height)
    return asset


def create_manual_movie(title: str, year: int | None, poster_contents: bytes) -> Movie:
    asset = store_poster(poster_contents)
    movie = Movie.objects.create(
        source=Movie.Source.MANUAL,
        source_key=uuid4().hex,
        title=title.strip(),
        normalized_title=normalize_title(title),
        year=year,
        poster=asset,
    )
    event("movie.manual.created", movie_id=movie.id)
    return movie


def update_movie(
    movie: Movie,
    *,
    include_in_rotation: bool | None = None,
    poster_contents: bytes | None = None,
) -> Movie:
    fields: list[str] = []
    if include_in_rotation is not None:
        movie.include_in_rotation = include_in_rotation
        fields.append("include_in_rotation")
        event("movie.rotation.updated", movie_id=movie.id, enabled=include_in_rotation)
    if poster_contents is not None:
        movie.poster = store_poster(poster_contents)
        fields.append("poster")
        event("movie.artwork.updated", movie_id=movie.id)
    if fields:
        movie.save(update_fields=[*fields, "updated_at"])
        broadcast_display_state()
    return movie


def save_movie_night(payload: MovieNightInput, *, identifier: int | None = None) -> MovieNight:
    configured_zone = ZoneInfo(ApplicationSettings.load().timezone)
    if payload.event_date < timezone.localdate(timezone.now(), configured_zone):
        raise ValidationError("Movie-night date cannot be in the past.")
    movie = Movie.objects.get(pk=payload.movie_id)
    try:
        with transaction.atomic():
            if identifier is None:
                row = MovieNight.objects.create(
                    movie=movie, event_date=payload.event_date, showtime=payload.showtime
                )
            else:
                row = MovieNight.objects.get(pk=identifier)
                row.movie = movie
                row.event_date = payload.event_date
                row.showtime = payload.showtime
                row.archived = False
                row.save()
    except IntegrityError as error:
        raise ConflictError("Another movie night already uses that date.") from error
    event(
        "schedule.movie_night.saved", movie_night_id=row.id, event_date=row.event_date.isoformat()
    )
    broadcast_display_state()
    return row


def delete_movie_night(identifier: int) -> None:
    row = MovieNight.objects.get(pk=identifier)
    row.delete()
    event("schedule.movie_night.deleted", movie_night_id=identifier)
    broadcast_display_state()


def save_settings(payload: ApplicationSettingsInput) -> ApplicationSettings:
    try:
        ZoneInfo(payload.timezone)
    except ZoneInfoNotFoundError as error:
        raise ValidationError("Timezone must be a valid IANA timezone name.") from error
    row = ApplicationSettings.load()
    row.rotation = payload.rotation
    row.slideshow_interval_seconds = payload.slideshow_interval_seconds
    row.timezone = payload.timezone
    row.full_clean()
    row.save()
    event(
        "settings.display.updated", rotation=row.rotation, interval=row.slideshow_interval_seconds
    )
    broadcast_display_state()
    return row


def save_roles(payload: DeviceRolesInput) -> ApplicationSettings:
    for serial, capability in (
        (payload.player_serial, "supports_playback"),
        (payload.library_serial, "supports_library"),
    ):
        if (
            serial
            and not DiscoveredDevice.objects.filter(
                serial_number=serial, **{capability: True}
            ).exists()
        ):
            raise ValidationError(
                f"Selected device does not have the required {capability} capability."
            )
    row = ApplicationSettings.load()
    row.player_serial = payload.player_serial
    row.library_serial = payload.library_serial
    row.manual_host = payload.manual_host.strip()
    row.save()
    event(
        "settings.devices.updated",
        player_serial=row.player_serial,
        library_serial=row.library_serial,
    )
    return row


def request_library_sync() -> LibrarySync:
    existing = LibrarySync.objects.filter(
        status__in=[LibrarySync.Status.QUEUED, LibrarySync.Status.RUNNING]
    ).first()
    if existing:
        return existing
    row = LibrarySync.objects.create()
    event("library.sync.queued", sync_id=row.id)
    return row


def broadcast_display_state() -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)("display", {"type": "display.refresh"})


def tmdb_search(query: str) -> list[dict[str, object]]:
    token = os.environ.get("TMDB_READ_TOKEN", "")
    if not token:
        raise ValidationError("TMDB is not configured.")
    try:
        response = httpx.get(
            "https://api.themoviedb.org/3/search/movie",
            params={"query": query, "include_adult": "false", "language": "en-US"},
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=10,
        )
        response.raise_for_status()
    except httpx.HTTPError as error:
        raise DependencyUnavailableError("TMDB is temporarily unavailable.") from error
    results = []
    for item in response.json().get("results", [])[:12]:
        release_date = item.get("release_date") or ""
        results.append(
            {
                "id": int(item["id"]),
                "title": item.get("title") or item.get("original_title") or "Untitled",
                "year": int(release_date[:4]) if release_date[:4].isdigit() else None,
                "overview": item.get("overview") or "",
                "poster_url": (
                    f"https://image.tmdb.org/t/p/w780{item['poster_path']}"
                    if item.get("poster_path")
                    else None
                ),
            }
        )
    return results


def import_tmdb_movie(tmdb_id: int) -> Movie:
    token = os.environ.get("TMDB_READ_TOKEN", "")
    if not token:
        raise ValidationError("TMDB is not configured.")
    try:
        response = httpx.get(
            f"https://api.themoviedb.org/3/movie/{tmdb_id}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=10,
        )
        response.raise_for_status()
    except httpx.HTTPError as error:
        raise DependencyUnavailableError("TMDB is temporarily unavailable.") from error
    item = response.json()
    poster = None
    if item.get("poster_path"):
        url = f"https://image.tmdb.org/t/p/w1280{item['poster_path']}"
        try:
            image = httpx.get(url, timeout=15, follow_redirects=False)
            image.raise_for_status()
        except httpx.HTTPError as error:
            raise DependencyUnavailableError("TMDB artwork is temporarily unavailable.") from error
        poster = store_poster(image.content, source_url=url)
    release_date = item.get("release_date") or ""
    movie, _ = Movie.objects.update_or_create(
        source=Movie.Source.TMDB,
        source_key=str(tmdb_id),
        defaults={
            "title": item.get("title") or item.get("original_title") or "Untitled",
            "normalized_title": normalize_title(item.get("title") or ""),
            "year": int(release_date[:4]) if release_date[:4].isdigit() else None,
            "genre": ", ".join(genre["name"] for genre in item.get("genres", [])),
            "synopsis": item.get("overview") or "",
            "poster": poster,
            "available": True,
        },
    )
    event("movie.tmdb.imported", movie_id=movie.id)
    return movie
