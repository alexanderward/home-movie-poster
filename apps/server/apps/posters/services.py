from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Iterable, Mapping
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from django.conf import settings as django_settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.common.observability import event
from apps.common.posters import normalize_image

from .contracts import (
    ApplicationSettingsInput,
    DisplayOverrideInput,
    MovieNightInput,
    PlayerSettingsInput,
    PosterSearch,
    PosterSearchResult,
    TmdbSearchStatus,
)
from .models import (
    ApplicationSettings,
    Collection,
    CollectionItem,
    DiscoveredDevice,
    Movie,
    MovieNight,
    PosterAsset,
)
from .selectors import collection_ids, poster_url


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


def create_manual_movie(
    title: str, year: int | None, poster_contents: bytes, *, collection_id: int | None = None
) -> Movie:
    collection = Collection.objects.get(pk=collection_id) if collection_id is not None else None
    asset = store_poster(poster_contents)
    with transaction.atomic():
        movie = Movie.objects.create(
            source=Movie.Source.MANUAL,
            source_key=uuid4().hex,
            title=title.strip(),
            normalized_title=normalize_title(title),
            year=year,
            poster=asset,
        )
        if collection is not None:
            CollectionItem.objects.create(collection=collection, movie=movie)
    event("movie.manual.created", movie_id=movie.id, collection_id=collection_id)
    return movie


def replace_movie_poster(movie: Movie, poster_contents: bytes) -> Movie:
    movie.poster = store_poster(poster_contents)
    movie.save(update_fields=["poster", "updated_at"])
    event("movie.artwork.updated", movie_id=movie.id)
    return movie


def _unique_collection_name(name: str, *, exclude: int | None = None) -> str:
    name = name.strip()
    taken = Collection.objects.filter(name__iexact=name)
    if exclude is not None:
        taken = taken.exclude(pk=exclude)
    if taken.exists():
        raise ConflictError(f"A collection named “{name}” already exists.")
    return name


def create_collection(name: str) -> Collection:
    """Create a collection; the first one also becomes what the TV shows."""
    try:
        with transaction.atomic():
            collection = Collection.objects.create(name=_unique_collection_name(name))
            config = ApplicationSettings.load()
            if config.active_collection_id is None:
                config.active_collection = collection
                config.save(update_fields=["active_collection", "updated_at"])
    except IntegrityError as error:
        raise ConflictError("A collection with that name already exists.") from error
    event("collection.created", collection_id=collection.id)
    return collection


def update_collection(
    identifier: int,
    *,
    name: str | None = None,
    tv_headline: str | None = None,
    show_headline: bool | None = None,
) -> Collection:
    """Rename a collection and/or change its TV headline; ``None`` leaves a field unchanged."""
    collection = Collection.objects.get(pk=identifier)
    fields = ["updated_at"]
    if name is not None:
        collection.name = _unique_collection_name(name, exclude=identifier)
        fields.append("name")
    if tv_headline is not None:
        collection.tv_headline = tv_headline.strip()
        fields.append("tv_headline")
    if show_headline is not None:
        collection.show_headline = show_headline
        fields.append("show_headline")
    try:
        collection.save(update_fields=fields)
    except IntegrityError as error:
        raise ConflictError("A collection with that name already exists.") from error
    event("collection.updated", collection_id=identifier, fields=fields[1:])
    return collection


def rename_collection(identifier: int, name: str) -> Collection:
    return update_collection(identifier, name=name)


def delete_collection(identifier: int) -> None:
    """Delete a collection and its memberships; its items stay saved for other collections."""
    Collection.objects.get(pk=identifier).delete()
    event("collection.deleted", collection_id=identifier)


def set_active_collection(identifier: int | None) -> ApplicationSettings:
    config = ApplicationSettings.load()
    config.active_collection = (
        Collection.objects.get(pk=identifier) if identifier is not None else None
    )
    config.save(update_fields=["active_collection", "updated_at"])
    event("collection.activated", collection_id=identifier)
    return config


def set_display_override(payload: DisplayOverrideInput) -> ApplicationSettings:
    """Force what the TV shows until switched back to automatic."""
    config = ApplicationSettings.load()
    collection = movie = None
    if payload.mode == "slideshow" and payload.collection_id is not None:
        collection = Collection.objects.get(pk=payload.collection_id)
    if payload.mode == "poster":
        if payload.movie_id is None:
            raise ValueError("Choose a poster to pin to the TV.")
        movie = Movie.objects.get(pk=payload.movie_id)
        if not movie.poster_id:
            raise ValueError(f"{movie.title} has no image to show.")
    config.display_override = payload.mode
    config.override_collection = collection
    config.override_movie = movie
    config.save(
        update_fields=["display_override", "override_collection", "override_movie", "updated_at"]
    )
    event(
        "display.override",
        mode=payload.mode,
        collection_id=collection.id if collection else None,
        movie_id=movie.id if movie else None,
    )
    return config


def add_to_collection(collection_id: int, movie_id: int) -> Movie:
    collection = Collection.objects.get(pk=collection_id)
    movie = Movie.objects.get(pk=movie_id)
    _, created = CollectionItem.objects.get_or_create(collection=collection, movie=movie)
    if created:
        Collection.objects.filter(pk=collection_id).update(updated_at=timezone.now())
        event("collection.item.added", collection_id=collection_id, movie_id=movie_id)
    return movie


def remove_from_collection(collection_id: int, movie_id: int) -> None:
    deleted, _ = CollectionItem.objects.filter(
        collection_id=collection_id, movie_id=movie_id
    ).delete()
    if deleted:
        Collection.objects.filter(pk=collection_id).update(updated_at=timezone.now())
        event("collection.item.removed", collection_id=collection_id, movie_id=movie_id)


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
    return row


def delete_movie_night(identifier: int) -> None:
    row = MovieNight.objects.get(pk=identifier)
    row.delete()
    event("schedule.movie_night.deleted", movie_night_id=identifier)


def complete_movie_night_after_playback(title: str) -> MovieNight | None:
    """Archive tonight's movie night once its own title has played and stopped.

    The display then moves on to the next movie night or the slideshow instead of advertising a
    film the family just watched. Playing a different title leaves the movie night in place.
    """
    normalized = normalize_title(title)
    if not normalized:
        return None
    today = timezone.localdate(timezone.now(), ZoneInfo(ApplicationSettings.load().timezone))
    row = (
        MovieNight.objects.select_related("movie")
        .filter(event_date=today, archived=False, movie__normalized_title=normalized)
        .first()
    )
    if row is None:
        return None
    row.archived = True
    row.save(update_fields=["archived", "updated_at"])
    event("schedule.movie_night.watched", movie_night_id=row.id, event_date=today.isoformat())
    return row


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
    return row


def save_player_settings(payload: PlayerSettingsInput) -> ApplicationSettings:
    if payload.player_serial and not DiscoveredDevice.objects.filter(
        serial_number=payload.player_serial, supports_playback=True
    ).exists():
        raise ValidationError("Selected device does not support playback monitoring.")
    row = ApplicationSettings.load()
    row.player_serial = payload.player_serial
    row.manual_host = payload.manual_host.strip()
    row.save()
    event("settings.player.updated", player_serial=row.player_serial)
    return row


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
            "poster": poster,
        },
    )
    event("movie.tmdb.imported", movie_id=movie.id)
    return movie


TMDB_SEARCH_CACHE_SECONDS = 600
LOCAL_SEARCH_LIMIT = 24
# A manual presentation override wins when it matches a TMDB title.
SOURCE_PRIORITY = {Movie.Source.MANUAL: 0, Movie.Source.TMDB: 1}


def tmdb_search_cached(query: str) -> list[dict[str, object]]:
    """TMDB search with a short process-local cache for typing pauses."""
    key = "tmdb:search:" + hashlib.sha256(query.casefold().encode()).hexdigest()
    try:
        cached = cache.get(key)
    except Exception:
        cached = None
    if cached is not None:
        return cached
    results = tmdb_search(query)
    try:
        cache.set(key, results, TMDB_SEARCH_CACHE_SECONDS)
    except Exception:
        pass
    return results


def merge_poster_results(
    local: Iterable[Movie],
    tmdb: Iterable[dict[str, Any]],
    memberships: Mapping[int, list[int]] | None = None,
) -> list[PosterSearchResult]:
    """Combine local movies and TMDB hits into one card per film.

    Films are the same when they share a TMDB id, or a normalized title and a year (a missing
    year on either side matches any year). Local copies come first, ordered by title, followed
    by TMDB-only films in TMDB relevance order. ``memberships`` maps a saved movie id to the
    ids of the collections it belongs to.
    """
    memberships = memberships or {}
    local_rows: list[dict[str, Any]] = []
    remote_rows: list[dict[str, Any]] = []
    by_tmdb: dict[int, dict[str, Any]] = {}
    by_title: dict[str, list[dict[str, Any]]] = {}

    def find(title: str, year: int | None, tmdb_id: int | None) -> dict[str, Any] | None:
        if tmdb_id is not None and tmdb_id in by_tmdb:
            return by_tmdb[tmdb_id]
        for row in by_title.get(normalize_title(title), []):
            if year is None or row["year"] is None or row["year"] == year:
                return row
        return None

    def remember(row: dict[str, Any]) -> None:
        by_title.setdefault(normalize_title(row["title"]), []).append(row)
        if row["tmdb_id"] is not None:
            by_tmdb[row["tmdb_id"]] = row

    def absorb(row: dict[str, Any], source: str, tmdb_id: int | None) -> None:
        if source not in row["sources"]:
            row["sources"].append(source)
        if tmdb_id is not None and row["tmdb_id"] is None:
            row["tmdb_id"] = tmdb_id
            by_tmdb[tmdb_id] = row

    for movie in sorted(local, key=lambda row: SOURCE_PRIORITY.get(row.source, 9)):
        tmdb_id = (
            int(movie.source_key)
            if movie.source == Movie.Source.TMDB and movie.source_key.isdigit()
            else None
        )
        existing = find(movie.title, movie.year, tmdb_id)
        if existing:
            absorb(existing, movie.source, tmdb_id)
            continue
        row = {
            "key": f"movie:{movie.id}",
            "title": movie.title,
            "year": movie.year,
            "poster_url": poster_url(movie),
            "sources": [movie.source],
            "movie_id": movie.id,
            "tmdb_id": tmdb_id,
            "collection_ids": memberships.get(movie.id, []),
        }
        local_rows.append(row)
        remember(row)

    for item in tmdb:
        tmdb_id = int(item["id"])
        existing = find(str(item["title"]), item.get("year"), tmdb_id)
        if existing:
            absorb(existing, Movie.Source.TMDB, tmdb_id)
            continue
        row = {
            "key": f"tmdb:{tmdb_id}",
            "title": str(item["title"]),
            "year": item.get("year"),
            "poster_url": item.get("poster_url"),
            "sources": [Movie.Source.TMDB],
            "movie_id": None,
            "tmdb_id": tmdb_id,
            "collection_ids": [],
        }
        remote_rows.append(row)
        remember(row)

    local_rows.sort(key=lambda row: (row["title"].casefold(), row["year"] or 0))
    return [PosterSearchResult(**row) for row in (*local_rows, *remote_rows)]


def search_posters(query: str) -> PosterSearch:
    query = query.strip()[:200]
    tmdb_status: TmdbSearchStatus = "ok" if os.environ.get("TMDB_READ_TOKEN") else "disabled"
    if not query:
        return PosterSearch(query=query, results=[], tmdb=tmdb_status)
    condition = Q(title__icontains=query)
    normalized = normalize_title(query)
    if normalized:
        condition |= Q(normalized_title__contains=normalized)
    local = list(
        Movie.objects.select_related("poster")
        .prefetch_related("collection_entries")
        .filter(condition)
        .order_by("title", "year", "id")[:LOCAL_SEARCH_LIMIT]
    )
    remote: list[dict[str, object]] = []
    if tmdb_status == "ok":
        try:
            remote = tmdb_search_cached(query)
        except DependencyUnavailableError:
            tmdb_status = "unavailable"
    memberships = {movie.id: collection_ids(movie) for movie in local}
    return PosterSearch(
        query=query, results=merge_poster_results(local, remote, memberships), tmdb=tmdb_status
    )
