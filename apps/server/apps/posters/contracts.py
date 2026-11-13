from __future__ import annotations

from datetime import date, datetime, time
from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from apps.common.contracts import ContractModel, RequiredName

MovieSource = Literal["tmdb", "manual"]
DisplayMode = Literal["now_playing", "scheduled", "rotation", "pinned", "setup"]
DisplayOverrideMode = Literal["auto", "movie_night", "slideshow", "poster"]


class MovieSummary(ContractModel):
    id: int
    source: MovieSource
    source_key: str
    title: str
    year: int | None
    poster_url: str | None
    collection_ids: list[int]


class MovieDetail(MovieSummary):
    pass


class MoviePage(ContractModel):
    items: list[MovieSummary]
    page: int
    page_size: int
    total: int


class MovieNightInput(ContractModel):
    movie_id: int
    event_date: date
    showtime: time | None = None


class MovieNightView(ContractModel):
    id: int
    movie: MovieSummary
    event_date: date
    showtime: time | None
    archived: bool


class DiscoveredDeviceView(ContractModel):
    serial_number: str
    friendly_name: str
    device_type: str
    ip_address: str
    supports_playback: bool
    selected_as_player: bool
    last_seen_at: datetime


class PlayerSettingsInput(ContractModel):
    player_serial: str = ""
    manual_host: str = ""


class ApplicationSettingsInput(ContractModel):
    rotation: Literal[0, 90, 270]
    slideshow_interval_seconds: int = Field(ge=10, le=300)
    timezone: RequiredName


class ApplicationSettingsView(ApplicationSettingsInput):
    player_serial: str
    manual_host: str
    tmdb_enabled: bool


class DisplayState(ContractModel):
    mode: DisplayMode
    headline: str
    title: str
    poster_url: str | None
    event_date: date | None = None
    showtime: time | None = None
    playback_status: str | None = None
    position_seconds: int | None = None
    duration_seconds: int | None = None
    observed_at: datetime | None = None
    rotation: Literal[0, 90, 270]
    slideshow_interval_seconds: int


class SessionView(ContractModel):
    csrf_token: str
    tmdb_enabled: bool


class HealthView(ContractModel):
    status: Literal["ok", "degraded"]
    database: bool
    monitor: bool
    player_connected: bool
    tmdb_configured: bool


TmdbSearchStatus = Literal["ok", "disabled", "unavailable"]


class PosterSearchResult(ContractModel):
    """One film found in TMDB or the small set of saved presentation records."""

    key: str
    title: str
    year: int | None
    poster_url: str | None
    sources: list[MovieSource]
    movie_id: int | None
    tmdb_id: int | None
    collection_ids: list[int]


class PosterSearch(ContractModel):
    query: str
    results: list[PosterSearchResult]
    tmdb: TmdbSearchStatus


CollectionName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
]


class CollectionInput(ContractModel):
    name: CollectionName


TvHeadline = Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)]


class CollectionUpdateInput(ContractModel):
    """Edit a collection; omitted fields stay as they are."""

    name: CollectionName | None = None
    tv_headline: TvHeadline | None = None
    show_headline: bool | None = None


class CollectionSummary(ContractModel):
    """A named gallery; ``cover_url`` is its most recently added item's image.

    ``tv_headline`` is what the TV's top band says during its slideshow (blank uses ``name``), and
    ``show_headline`` false leaves that band empty.
    """

    id: int
    name: str
    tv_headline: str
    show_headline: bool
    item_count: int
    cover_url: str | None
    active: bool


class CollectionList(ContractModel):
    """Every collection, which one the idle slideshow shows, and how long each image stays."""

    items: list[CollectionSummary]
    active_id: int | None
    interval_seconds: int


class CollectionDetail(CollectionSummary):
    """One collection; ``items`` is its most recently added few (``item_count`` is the total)."""

    items: list[MovieSummary]


class ActiveCollectionInput(ContractModel):
    collection_id: int | None


class DisplayOverrideInput(ContractModel):
    """Force what the TV shows until switched back to ``auto``.

    ``slideshow`` takes an optional ``collection_id`` (omitted uses the active collection) and
    ``poster`` requires ``movie_id``. Other ids are ignored.
    """

    mode: DisplayOverrideMode
    collection_id: int | None = None
    movie_id: int | None = None


class DisplayOverrideView(ContractModel):
    """The configured override and what the TV is showing because of it right now.

    ``forced`` is false when the forced source has nothing to show and the TV fell back to the
    normal order.
    """

    mode: DisplayOverrideMode
    collection_id: int | None
    movie: MovieSummary | None
    forced: bool
    now: DisplayState
