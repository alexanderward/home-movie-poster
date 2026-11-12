from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal

from pydantic import Field

from apps.common.contracts import ContractModel, RequiredName

MovieSource = Literal["kaleidescape", "tmdb", "manual"]
DisplayMode = Literal["now_playing", "scheduled", "rotation", "setup"]


class MovieSummary(ContractModel):
    id: int
    source: MovieSource
    source_key: str
    title: str
    year: int | None
    poster_url: str | None
    include_in_rotation: bool
    available: bool


class MovieDetail(MovieSummary):
    genre: str
    rating: str
    director: str
    synopsis: str


class MoviePage(ContractModel):
    items: list[MovieSummary]
    page: int
    page_size: int
    total: int


class MovieUpdate(ContractModel):
    include_in_rotation: bool | None = None


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
    supports_library: bool
    selected_as_player: bool
    selected_as_library: bool
    last_seen_at: datetime


class DeviceRolesInput(ContractModel):
    player_serial: str = ""
    library_serial: str = ""
    manual_host: str = ""


class LibrarySyncStatus(ContractModel):
    id: int
    status: Literal["queued", "running", "succeeded", "failed"]
    requested_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    discovered_count: int
    updated_count: int
    error: str


class ApplicationSettingsInput(ContractModel):
    rotation: Literal[0, 90, 270]
    slideshow_interval_seconds: int = Field(ge=10, le=300)
    timezone: RequiredName


class ApplicationSettingsView(ApplicationSettingsInput):
    player_serial: str
    library_serial: str
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
    websocket_path: str = "/api/display/socket"


class HealthView(ContractModel):
    status: Literal["ok", "degraded"]
    database: bool
    redis: bool
    monitor: bool
    player_connected: bool
    last_library_sync: datetime | None


class TmdbMovie(ContractModel):
    id: int
    title: str
    year: int | None
    overview: str
    poster_url: str | None


TmdbSearchStatus = Literal["ok", "disabled", "unavailable"]


class PosterSearchResult(ContractModel):
    """One film found locally, on TMDB, or both, after duplicates are merged."""

    key: str
    title: str
    year: int | None
    poster_url: str | None
    sources: list[MovieSource]
    movie_id: int | None
    tmdb_id: int | None
    include_in_rotation: bool


class PosterSearch(ContractModel):
    query: str
    results: list[PosterSearchResult]
    tmdb: TmdbSearchStatus


class SlideshowView(ContractModel):
    """Posters the idle slideshow rotates through; ``items`` is the most recently changed few."""

    total: int
    interval_seconds: int
    items: list[MovieSummary]
