from __future__ import annotations

import random
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.db.models import Q
from django.utils import timezone

from .contracts import DisplayState, MovieDetail, MovieNightView, MovieSummary, SlideshowView
from .models import ApplicationSettings, Movie, MovieNight, PlaybackSnapshot

ACTIVE_PLAYBACK = {"playing", "paused", "forward", "reverse"}


def poster_url(movie: Movie | None) -> str | None:
    return f"/media/{movie.poster.path}" if movie and movie.poster_id else None


def movie_summary(movie: Movie) -> MovieSummary:
    return MovieSummary(
        id=movie.id,
        source=movie.source,
        source_key=movie.source_key,
        title=movie.title,
        year=movie.year,
        poster_url=poster_url(movie),
        include_in_rotation=movie.include_in_rotation,
    )


def movie_detail(movie: Movie) -> MovieDetail:
    return MovieDetail(**movie_summary(movie).model_dump())


def movies(
    *,
    query: str = "",
    source: str = "",
    include_in_rotation: bool | None = None,
    page: int = 1,
    page_size: int = 30,
):
    queryset = Movie.objects.select_related("poster").order_by("title", "year", "id")
    if query:
        queryset = queryset.filter(Q(title__icontains=query) | Q(normalized_title__contains=query))
    if source:
        queryset = queryset.filter(source=source)
    if include_in_rotation is not None:
        queryset = queryset.filter(include_in_rotation=include_in_rotation)
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


def slideshow_movies():
    """Movies the idle slideshow rotates through."""
    return Movie.objects.select_related("poster").filter(
        include_in_rotation=True, poster__isnull=False
    )


def slideshow(limit: int = 24) -> SlideshowView:
    rows = slideshow_movies()
    return SlideshowView(
        total=rows.count(),
        interval_seconds=ApplicationSettings.load().slideshow_interval_seconds,
        items=[movie_summary(row) for row in rows.order_by("-updated_at", "id")[:limit]],
    )


def display_state(*, slideshow_only: bool = False) -> DisplayState:
    """What the television shows now: playback, then the next movie night, then the slideshow.

    ``slideshow_only`` skips playback and movie nights so the admin can preview the slideshow.
    """
    config = ApplicationSettings.load()
    now = timezone.now()
    local_date = timezone.localdate(now, ZoneInfo(config.timezone))
    snapshot = (
        None
        if slideshow_only
        else PlaybackSnapshot.objects.filter(pk=1).first()
    )
    if snapshot and snapshot.play_status in ACTIVE_PLAYBACK:
        fresh = snapshot.connected or snapshot.observed_at >= now - timedelta(seconds=30)
        if fresh:
            return DisplayState(
                mode="now_playing",
                headline="Now Playing",
                title=snapshot.title,
                poster_url=f"/media/{snapshot.poster_path}" if snapshot.poster_path else None,
                playback_status=snapshot.play_status,
                position_seconds=snapshot.position_seconds,
                duration_seconds=snapshot.duration_seconds,
                observed_at=snapshot.observed_at,
                rotation=config.rotation,
                slideshow_interval_seconds=config.slideshow_interval_seconds,
            )

    MovieNight.objects.filter(event_date__lt=local_date, archived=False).update(archived=True)
    upcoming = (
        None
        if slideshow_only
        else MovieNight.objects.select_related("movie__poster")
        .filter(event_date__gte=local_date, archived=False)
        .order_by("event_date")
        .first()
    )
    if upcoming:
        if upcoming.event_date == local_date:
            headline = "Tonight"
        elif upcoming.event_date.weekday() == 4:
            headline = "Coming Friday"
        else:
            headline = f"Coming {upcoming.event_date.strftime('%A')}"
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

    eligible = list(slideshow_movies().order_by("id"))
    if eligible:
        bucket = int(now.timestamp()) // config.slideshow_interval_seconds
        cycle, index = divmod(bucket, len(eligible))
        random.Random(cycle).shuffle(eligible)
        selected = eligible[index]
        return DisplayState(
            mode="rotation",
            headline="From Your Slideshow",
            title=selected.title,
            poster_url=poster_url(selected),
            rotation=config.rotation,
            slideshow_interval_seconds=config.slideshow_interval_seconds,
        )

    return DisplayState(
        mode="setup",
        headline="Home Movie Poster",
        title="Open the admin page to connect Strato or choose a poster.",
        poster_url=None,
        rotation=config.rotation,
        slideshow_interval_seconds=config.slideshow_interval_seconds,
    )
