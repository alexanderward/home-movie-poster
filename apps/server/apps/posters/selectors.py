from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.db.models import Q
from django.utils import timezone

from .contracts import (
    CollectionDetail,
    CollectionList,
    CollectionSummary,
    DisplayOverrideView,
    DisplayState,
    MovieDetail,
    MovieNightView,
    MovieSummary,
)
from .models import (
    ApplicationSettings,
    Collection,
    CollectionItem,
    Movie,
    MovieNight,
    PlaybackSnapshot,
)

ACTIVE_PLAYBACK = {"playing", "paused", "forward", "reverse"}


def poster_url(movie: Movie | None) -> str | None:
    return f"/media/{movie.poster.path}" if movie and movie.poster_id else None


def summaries():
    """Movies with what a summary reads: the poster and collection memberships."""
    return Movie.objects.select_related("poster").prefetch_related("collection_entries")


def collection_ids(movie: Movie) -> list[int]:
    return sorted(entry.collection_id for entry in movie.collection_entries.all())


def movie_summary(movie: Movie) -> MovieSummary:
    return MovieSummary(
        id=movie.id,
        source=movie.source,
        source_key=movie.source_key,
        title=movie.title,
        year=movie.year,
        poster_url=poster_url(movie),
        collection_ids=collection_ids(movie),
    )


def movie_detail(movie: Movie) -> MovieDetail:
    return MovieDetail(**movie_summary(movie).model_dump())


def movies(
    *,
    query: str = "",
    source: str = "",
    collection_id: int | None = None,
    page: int = 1,
    page_size: int = 30,
):
    queryset = summaries().order_by("title", "year", "id")
    if query:
        queryset = queryset.filter(Q(title__icontains=query) | Q(normalized_title__contains=query))
    if source:
        queryset = queryset.filter(source=source)
    if collection_id is not None:
        queryset = queryset.filter(collection_entries__collection_id=collection_id)
    total = queryset.count()
    start = (page - 1) * page_size
    return [movie_summary(row) for row in queryset[start : start + page_size]], total


def movie_night(row: MovieNight) -> MovieNightView:
    return MovieNightView(
        id=row.id,
        movie=movie_summary(row.movie),
        event_date=row.event_date,
        showtime=row.showtime,
        archived=row.archived,
    )


def slideshow_headline(collection: Collection | None) -> str:
    """The TV's top band during a slideshow: the collection's headline or name, or empty when it's hidden."""
    if collection is None:
        return "Slideshow"
    if not collection.show_headline:
        return ""
    return collection.tv_headline or collection.name


def collection_summary(collection: Collection, *, active_id: int | None) -> CollectionSummary:
    entries = CollectionItem.objects.filter(collection=collection)
    cover = (
        entries.filter(movie__poster__isnull=False)
        .select_related("movie__poster")
        .order_by("-added_at", "-id")
        .first()
    )
    return CollectionSummary(
        id=collection.id,
        name=collection.name,
        tv_headline=collection.tv_headline,
        show_headline=collection.show_headline,
        item_count=entries.count(),
        cover_url=poster_url(cover.movie) if cover else None,
        active=collection.id == active_id,
    )


def collections() -> CollectionList:
    config = ApplicationSettings.load()
    active_id = config.active_collection_id
    return CollectionList(
        items=[collection_summary(row, active_id=active_id) for row in Collection.objects.all()],
        active_id=active_id,
        interval_seconds=config.slideshow_interval_seconds,
    )


def collection_detail(collection: Collection, *, limit: int = 24) -> CollectionDetail:
    summary = collection_summary(
        collection, active_id=ApplicationSettings.load().active_collection_id
    )
    entries = (
        CollectionItem.objects.filter(collection=collection)
        .select_related("movie__poster")
        .prefetch_related("movie__collection_entries")
        .order_by("-added_at", "-id")[:limit]
    )
    return CollectionDetail(
        **summary.model_dump(), items=[movie_summary(entry.movie) for entry in entries]
    )


def slideshow_movies(collection_id: int | None):
    """Images the idle slideshow rotates through: the active collection's items with art."""
    if collection_id is None:
        return Movie.objects.none()
    return Movie.objects.select_related("poster").filter(
        collection_entries__collection_id=collection_id, poster__isnull=False
    )


def _now_playing(config: ApplicationSettings, now: datetime) -> DisplayState | None:
    snapshot = PlaybackSnapshot.objects.filter(pk=1).first()
    if not snapshot or snapshot.play_status not in ACTIVE_PLAYBACK:
        return None
    if not (snapshot.connected or snapshot.observed_at >= now - timedelta(seconds=30)):
        return None
    return DisplayState(
        mode="now_playing",
        headline="Paused" if snapshot.play_status == "paused" else "Now Playing",
        title=snapshot.title,
        poster_url=f"/media/{snapshot.poster_path}" if snapshot.poster_path else None,
        playback_status=snapshot.play_status,
        position_seconds=snapshot.position_seconds,
        duration_seconds=snapshot.duration_seconds,
        observed_at=snapshot.observed_at,
        rotation=config.rotation,
        slideshow_interval_seconds=config.slideshow_interval_seconds,
    )


def _movie_night(config: ApplicationSettings, local_date: date) -> DisplayState | None:
    upcoming = (
        MovieNight.objects.select_related("movie__poster")
        .filter(event_date__gte=local_date, archived=False)
        .order_by("event_date")
        .first()
    )
    if not upcoming:
        return None
    days_away = (upcoming.event_date - local_date).days
    if days_away == 0:
        headline = "Tonight"
    elif days_away == 1:
        headline = "Tomorrow Night"
    elif days_away < 7:
        # A bare weekday is only unambiguous within the coming week.
        headline = f"Coming {upcoming.event_date.strftime('%A')}"
    else:
        headline = "Coming Soon"
    return DisplayState(
        mode="scheduled",
        headline=headline,
        title=upcoming.movie.title,
        poster_url=poster_url(upcoming.movie),
        event_date=upcoming.event_date,
        showtime=upcoming.showtime,
        rotation=config.rotation,
        slideshow_interval_seconds=config.slideshow_interval_seconds,
    )


def _slideshow(
    config: ApplicationSettings, now: datetime, collection: Collection | None
) -> DisplayState | None:
    eligible = list(slideshow_movies(collection.id if collection else None).order_by("id"))
    if not eligible:
        return None
    bucket = int(now.timestamp()) // config.slideshow_interval_seconds
    cycle, index = divmod(bucket, len(eligible))
    random.Random(cycle).shuffle(eligible)
    selected = eligible[index]
    return DisplayState(
        mode="rotation",
        headline=slideshow_headline(collection),
        title=selected.title,
        poster_url=poster_url(selected),
        rotation=config.rotation,
        slideshow_interval_seconds=config.slideshow_interval_seconds,
    )


def _pinned(config: ApplicationSettings) -> DisplayState | None:
    movie = config.override_movie
    if movie is None or not movie.poster_id:
        return None
    return DisplayState(
        mode="pinned",
        headline="",
        title=movie.title,
        poster_url=poster_url(movie),
        rotation=config.rotation,
        slideshow_interval_seconds=config.slideshow_interval_seconds,
    )


def resolve_display(*, slideshow_only: bool = False) -> tuple[DisplayState, bool]:
    """What the television shows now, and whether a forced override is what put it there.

    Automatic order is playback, then the next movie night, then the active collection's
    slideshow. A forced override shows only its own source; when that source has nothing to show,
    the TV falls back to the automatic order. ``slideshow_only`` is the admin's preview tab: the
    active collection's slideshow regardless of overrides, playback, and movie nights.
    """
    config = ApplicationSettings.load()
    now = timezone.now()
    local_date = timezone.localdate(now, ZoneInfo(config.timezone))
    MovieNight.objects.filter(event_date__lt=local_date, archived=False).update(archived=True)
    override = ApplicationSettings.Override

    state: DisplayState | None
    forced = False
    if slideshow_only:
        state = _slideshow(config, now, config.active_collection)
    else:
        mode = config.display_override
        if mode == override.MOVIE_NIGHT:
            state = _movie_night(config, local_date)
        elif mode == override.SLIDESHOW:
            state = _slideshow(config, now, config.override_collection or config.active_collection)
        elif mode == override.POSTER:
            state = _pinned(config)
        else:
            state = None
        forced = state is not None
        state = (
            state
            or _now_playing(config, now)
            or _movie_night(config, local_date)
            or _slideshow(config, now, config.active_collection)
        )

    if state is None:
        state = DisplayState(
            mode="setup",
            headline="Frame",
            title="Open the admin page to connect Strato or fill a collection.",
            poster_url=None,
            rotation=config.rotation,
            slideshow_interval_seconds=config.slideshow_interval_seconds,
        )
    return state, forced


def display_state(*, slideshow_only: bool = False) -> DisplayState:
    """What the television shows now; see ``resolve_display``."""
    return resolve_display(slideshow_only=slideshow_only)[0]


def display_override() -> DisplayOverrideView:
    config = ApplicationSettings.load()
    state, forced = resolve_display()
    movie = config.override_movie
    return DisplayOverrideView(
        mode=config.display_override,  # type: ignore[arg-type]
        collection_id=config.override_collection_id,
        movie=movie_summary(movie) if movie else None,
        forced=forced,
        now=state,
    )
