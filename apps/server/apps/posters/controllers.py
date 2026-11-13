from __future__ import annotations

import os

from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.middleware.csrf import CsrfViewMiddleware, get_token
from ninja import File, Form, Router, Schema, Status
from ninja.files import UploadedFile

from apps.server.apps.posters import selectors, services

from .contracts import (
    ActiveCollectionInput,
    ApplicationSettingsInput,
    ApplicationSettingsView,
    CollectionDetail,
    CollectionInput,
    CollectionList,
    CollectionUpdateInput,
    DiscoveredDeviceView,
    DisplayOverrideInput,
    DisplayOverrideView,
    DisplayState,
    HealthView,
    MovieDetail,
    MovieNightInput,
    MovieNightView,
    MoviePage,
    PlayerSettingsInput,
    PosterSearch,
    SessionView,
)
from .health import health
from .models import ApplicationSettings, Collection, DiscoveredDevice, MovieNight

router = Router(tags=["frame"])


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
def display(request: HttpRequest, preview: str = ""):
    """Current television state; ``preview=slideshow`` ignores playback and movie nights."""
    del request
    return selectors.display_state(slideshow_only=preview == "slideshow")


@router.get("/display/override", response=DisplayOverrideView)
def get_display_override(request: HttpRequest):
    del request
    return selectors.display_override()


@router.put("/display/override", response=DisplayOverrideView)
def put_display_override(request: HttpRequest, payload: DisplayOverrideInput):
    """Force the TV to a movie night, a slideshow, or one poster; ``auto`` restores the order."""
    require_csrf(request)
    services.set_display_override(payload)
    return selectors.display_override()


@router.get("/movies", response=MoviePage)
def list_movies(
    request: HttpRequest,
    query: str = "",
    source: str = "",
    collection: int | None = None,
    page: int = 1,
    page_size: int = 30,
):
    del request
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    items, total = selectors.movies(
        query=query,
        source=source,
        collection_id=collection,
        page=page,
        page_size=page_size,
    )
    return MoviePage(items=items, page=page, page_size=page_size, total=total)


# Declared before /movies/{movie_id} so "manual" is not routed as a movie id.
@router.post("/movies/manual", response={201: MovieDetail})
def manual_movie(
    request: HttpRequest,
    title: Form[str],
    year: Form[int | None] = None,
    collection_id: Form[int | None] = None,
    poster: File[UploadedFile] = None,  # type: ignore[assignment]
):
    """Upload an image (a poster, artwork, a photo) and optionally add it to a collection."""
    require_csrf(request)
    if poster is None:
        raise ValueError("Choose an image.")
    movie = services.create_manual_movie(title, year, poster.read(), collection_id=collection_id)
    return Status(201, selectors.movie_detail(movie))


@router.get("/movies/{movie_id}", response=MovieDetail)
def get_movie(request: HttpRequest, movie_id: int):
    del request
    return selectors.movie_detail(selectors.summaries().get(pk=movie_id))


@router.post("/movies/{movie_id}/poster", response=MovieDetail)
def replace_movie_poster(request: HttpRequest, movie_id: int, poster: File[UploadedFile]):
    require_csrf(request)
    movie = selectors.summaries().get(pk=movie_id)
    return selectors.movie_detail(services.replace_movie_poster(movie, poster.read()))


@router.get("/collections", response=CollectionList)
def list_collections(request: HttpRequest):
    del request
    return selectors.collections()


@router.post("/collections", response={201: CollectionDetail})
def create_collection(request: HttpRequest, payload: CollectionInput):
    require_csrf(request)
    return Status(201, selectors.collection_detail(services.create_collection(payload.name)))


@router.put("/collections/active", response=CollectionList)
def activate_collection(request: HttpRequest, payload: ActiveCollectionInput):
    """Choose which collection the idle slideshow shows; ``null`` shows none."""
    require_csrf(request)
    services.set_active_collection(payload.collection_id)
    return selectors.collections()


@router.get("/collections/{collection_id}", response=CollectionDetail)
def get_collection(request: HttpRequest, collection_id: int, limit: int = 24):
    del request
    return selectors.collection_detail(
        Collection.objects.get(pk=collection_id), limit=min(max(limit, 1), 1000)
    )


@router.patch("/collections/{collection_id}", response=CollectionDetail)
def update_collection(request: HttpRequest, collection_id: int, payload: CollectionUpdateInput):
    require_csrf(request)
    """Rename a collection or change its TV headline; omitted fields are left unchanged."""
    return selectors.collection_detail(
        services.update_collection(
            collection_id,
            name=payload.name,
            tv_headline=payload.tv_headline,
            show_headline=payload.show_headline,
        )
    )


@router.delete("/collections/{collection_id}", response={204: None})
def delete_collection(request: HttpRequest, collection_id: int):
    require_csrf(request)
    services.delete_collection(collection_id)
    return Status(204, None)


@router.put("/collections/{collection_id}/items/{movie_id}", response=MovieDetail)
def add_collection_item(request: HttpRequest, collection_id: int, movie_id: int):
    require_csrf(request)
    services.add_to_collection(collection_id, movie_id)
    return selectors.movie_detail(selectors.summaries().get(pk=movie_id))


@router.delete("/collections/{collection_id}/items/{movie_id}", response={204: None})
def remove_collection_item(request: HttpRequest, collection_id: int, movie_id: int):
    require_csrf(request)
    services.remove_from_collection(collection_id, movie_id)
    return Status(204, None)


@router.get("/movie-nights", response=list[MovieNightView])
def list_movie_nights(request: HttpRequest):
    del request
    return [
        selectors.movie_night(row)
        for row in MovieNight.objects.select_related("movie__poster")
        .prefetch_related("movie__collection_entries")
        .order_by("event_date")
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
            selected_as_player=row.serial_number == config.player_serial,
            last_seen_at=row.last_seen_at,
        )
        for row in DiscoveredDevice.objects.all()
    ]


@router.put("/devices/player", response=ApplicationSettingsView)
def player_settings(request: HttpRequest, payload: PlayerSettingsInput):
    require_csrf(request)
    return settings_view(services.save_player_settings(payload))


def settings_view(row: ApplicationSettings) -> ApplicationSettingsView:
    return ApplicationSettingsView(
        rotation=row.rotation,
        slideshow_interval_seconds=row.slideshow_interval_seconds,
        timezone=row.timezone,
        player_serial=row.player_serial,
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


@router.get("/posters/search", response=PosterSearch)
def search_posters(request: HttpRequest, query: str = ""):
    """Search TMDB and the small set of saved presentation records."""
    del request
    return services.search_posters(query)


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
