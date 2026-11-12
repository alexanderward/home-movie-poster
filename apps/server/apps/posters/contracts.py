from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal

from pydantic import Field

from apps.common.contracts import ContractModel, RequiredName

MovieSource = Literal["tmdb", "manual"]
DisplayMode = Literal["now_playing", "scheduled", "rotation", "setup"]


class MovieSummary(ContractModel):
    id: int
    source: MovieSource
    source_key: str
    title: str
    year: int | None
    poster_url: str | None
    include_in_rotation: bool


class MovieDetail(MovieSummary):
    pass


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
