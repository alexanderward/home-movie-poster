from __future__ import annotations

import os

from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.middleware.csrf import CsrfViewMiddleware, get_token
from ninja import File, Form, Router, Schema, Status
from ninja.files import UploadedFile

from apps.server.apps.posters import selectors, services

from .contracts import (
    ApplicationSettingsInput,
    ApplicationSettingsView,
    DeviceRolesInput,
    DiscoveredDeviceView,
    DisplayState,
    HealthView,
    LibrarySyncStatus,
    MovieDetail,
    MovieNightInput,
    MovieNightView,
    MoviePage,
    MovieUpdate,
    SessionView,
    TmdbMovie,
)
from .health import health
from .models import ApplicationSettings, DiscoveredDevice, LibrarySync, Movie, MovieNight

router = Router(tags=["home-movie-poster"])


def require_csrf(request: HttpRequest) -> None:
    middleware = CsrfViewMiddleware(lambda _: HttpResponse())
    rejection = middleware.process_view(request, lambda _: HttpResponse(), (), {})
    if rejection is not None:
        raise PermissionDenied("CSRF validation failed.")


@router.get("/session", response=SessionView)
def session(request: HttpRequest):
    return SessionView(
        csrf_token=get_token(request), tmdb_enabled=bool(os.environ.get("TMDB_READ_TOKEN"))
    )


@router.get("/display", response=DisplayState)
def display(request: HttpRequest):
    del request
    return selectors.display_state()


@router.get("/movies", response=MoviePage)
def list_movies(
    request: HttpRequest,
    query: str = "",
    source: str = "",
    rotation: str = "",
    page: int = 1,
    page_size: int = 30,
):
    del request
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    rotation_filter = {"included": True, "excluded": False}.get(rotation)
    items, total = selectors.movies(
        query=query,
        source=source,
        include_in_rotation=rotation_filter,
        page=page,
        page_size=page_size,
    )
    return MoviePage(items=items, page=page, page_size=page_size, total=total)


@router.get("/movies/{movie_id}", response=MovieDetail)
def get_movie(request: HttpRequest, movie_id: int):
    del request
    return selectors.movie_detail(Movie.objects.select_related("poster").get(pk=movie_id))


@router.post("/movies/manual", response={201: MovieDetail})
def manual_movie(
    request: HttpRequest,
    title: Form[str],
    year: Form[int | None] = None,
    poster: File[UploadedFile] = None,  # type: ignore[assignment]
):
    require_csrf(request)
    if poster is None:
        raise ValueError("Choose a poster image.")
    movie = services.create_manual_movie(title, year, poster.read())
    return Status(201, selectors.movie_detail(movie))


@router.patch("/movies/{movie_id}", response=MovieDetail)
def patch_movie(request: HttpRequest, movie_id: int, payload: MovieUpdate):
    require_csrf(request)
    movie = Movie.objects.select_related("poster").get(pk=movie_id)
    return selectors.movie_detail(
        services.update_movie(movie, include_in_rotation=payload.include_in_rotation)
    )


@router.post("/movies/{movie_id}/poster", response=MovieDetail)
def replace_movie_poster(request: HttpRequest, movie_id: int, poster: File[UploadedFile]):
    require_csrf(request)
    movie = Movie.objects.select_related("poster").get(pk=movie_id)
    return selectors.movie_detail(services.update_movie(movie, poster_contents=poster.read()))


@router.get("/movie-nights", response=list[MovieNightView])
def list_movie_nights(request: HttpRequest):
    del request
    return [
        selectors.movie_night(row)
        for row in MovieNight.objects.select_related("movie__poster").order_by("event_date")
    ]


@router.post("/movie-nights", response={201: MovieNightView})
def create_movie_night(request: HttpRequest, payload: MovieNightInput):
    require_csrf(request)
    return Status(201, selectors.movie_night(services.save_movie_night(payload)))


@router.patch("/movie-nights/{movie_night_id}", response=MovieNightView)
def patch_movie_night(request: HttpRequest, movie_night_id: int, payload: MovieNightInput):
    require_csrf(request)
    return selectors.movie_night(services.save_movie_night(payload, identifier=movie_night_id))


@router.delete("/movie-nights/{movie_night_id}", response={204: None})
def remove_movie_night(request: HttpRequest, movie_night_id: int):
    require_csrf(request)
    services.delete_movie_night(movie_night_id)
    return Status(204, None)


@router.get("/devices", response=list[DiscoveredDeviceView])
def devices(request: HttpRequest):
    del request
    config = ApplicationSettings.load()
    return [
        DiscoveredDeviceView(
            serial_number=row.serial_number,
            friendly_name=row.friendly_name,
            device_type=row.device_type,
            ip_address=row.ip_address,
            supports_playback=row.supports_playback,
            supports_library=row.supports_library,
            selected_as_player=row.serial_number == config.player_serial,
            selected_as_library=row.serial_number == config.library_serial,
            last_seen_at=row.last_seen_at,
        )
        for row in DiscoveredDevice.objects.all()
    ]


@router.put("/devices/roles", response=ApplicationSettingsView)
def device_roles(request: HttpRequest, payload: DeviceRolesInput):
    require_csrf(request)
    return settings_view(services.save_roles(payload))


@router.get("/library-sync", response=LibrarySyncStatus | None)
def library_sync_status(request: HttpRequest):
    del request
    row = LibrarySync.objects.first()
    return LibrarySyncStatus.model_validate(row) if row else None


@router.post("/library-sync", response={202: LibrarySyncStatus})
def library_sync(request: HttpRequest):
    require_csrf(request)
    return Status(202, LibrarySyncStatus.model_validate(services.request_library_sync()))


def settings_view(row: ApplicationSettings) -> ApplicationSettingsView:
    return ApplicationSettingsView(
        rotation=row.rotation,
        slideshow_interval_seconds=row.slideshow_interval_seconds,
        timezone=row.timezone,
        player_serial=row.player_serial,
        library_serial=row.library_serial,
        manual_host=row.manual_host,
        tmdb_enabled=bool(os.environ.get("TMDB_READ_TOKEN")),
    )


@router.get("/settings", response=ApplicationSettingsView)
def get_settings(request: HttpRequest):
    del request
    return settings_view(ApplicationSettings.load())


@router.put("/settings", response=ApplicationSettingsView)
def update_settings(request: HttpRequest, payload: ApplicationSettingsInput):
    require_csrf(request)
    return settings_view(services.save_settings(payload))


@router.get("/tmdb/search", response=list[TmdbMovie])
def search_tmdb(request: HttpRequest, query: str):
    del request
    return [TmdbMovie.model_validate(item) for item in services.tmdb_search(query)]


class TmdbImport(Schema):
    tmdb_id: int


@router.post("/tmdb/import", response={201: MovieDetail})
def import_tmdb(request: HttpRequest, payload: TmdbImport):
    require_csrf(request)
    return Status(201, selectors.movie_detail(services.import_tmdb_movie(payload.tmdb_id)))


@router.get("/health", response=HealthView)
def get_health(request: HttpRequest):
    del request
    return health()
