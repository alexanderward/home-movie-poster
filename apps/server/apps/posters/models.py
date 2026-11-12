from __future__ import annotations

from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class DiscoveredDevice(models.Model):
    serial_number = models.CharField(primary_key=True, max_length=64)
    friendly_name = models.CharField(max_length=200, blank=True)
    device_type = models.CharField(max_length=200, blank=True)
    ip_address = models.GenericIPAddressField(protocol="IPv4")
    movie_zones = models.PositiveSmallIntegerField(default=0)
    supports_playback = models.BooleanField(default=False)
    last_seen_at = models.DateTimeField()

    class Meta:
        ordering = ["friendly_name", "serial_number"]


class PosterAsset(models.Model):
    if TYPE_CHECKING:
        id: int

    path = models.CharField(max_length=500, unique=True)
    source_url_hash = models.CharField(max_length=64, blank=True, db_index=True)
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)


class Movie(models.Model):
    if TYPE_CHECKING:
        id: int
        poster_id: int | None

    class Source(models.TextChoices):
        TMDB = "tmdb", "TMDB"
        MANUAL = "manual", "Manual"

    source = models.CharField(max_length=20, choices=Source.choices)
    source_key = models.CharField(max_length=300)
    title = models.CharField(max_length=300)
    normalized_title = models.CharField(max_length=300, db_index=True)
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    poster = models.ForeignKey(
        PosterAsset, null=True, blank=True, on_delete=models.SET_NULL, related_name="movies"
    )
    include_in_rotation = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["source", "source_key"], name="movie_source_key_unique")
        ]
        ordering = ["title", "year"]


class MovieNight(models.Model):
    if TYPE_CHECKING:
        id: int
        movie_id: int

    movie = models.ForeignKey(Movie, on_delete=models.PROTECT, related_name="movie_nights")
    event_date = models.DateField(unique=True)
    showtime = models.TimeField(null=True, blank=True)
    archived = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["event_date"]


class PlaybackSnapshot(models.Model):
    SINGLETON_ID = 1

    id = models.PositiveSmallIntegerField(primary_key=True, default=SINGLETON_ID, editable=False)
    player_serial = models.CharField(max_length=64, blank=True)
    connected = models.BooleanField(default=False)
    play_status = models.CharField(max_length=20, default="none")
    title = models.CharField(max_length=300, blank=True)
    normalized_title = models.CharField(max_length=300, blank=True, db_index=True)
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    position_seconds = models.PositiveIntegerField(null=True, blank=True)
    poster_path = models.CharField(max_length=500, blank=True)
    poster_source_hash = models.CharField(max_length=64, blank=True)
    observed_at = models.DateTimeField()


class MonitorHeartbeat(models.Model):
    SINGLETON_ID = 1

    id = models.PositiveSmallIntegerField(primary_key=True, default=SINGLETON_ID, editable=False)
    observed_at = models.DateTimeField()


class ApplicationSettings(models.Model):
    SINGLETON_ID = 1

    id = models.PositiveSmallIntegerField(primary_key=True, default=SINGLETON_ID, editable=False)
    rotation = models.PositiveSmallIntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(270)]
    )
    slideshow_interval_seconds = models.PositiveSmallIntegerField(
        default=60, validators=[MinValueValidator(10), MaxValueValidator(300)]
    )
    timezone = models.CharField(max_length=64, default="America/Chicago")
    player_serial = models.CharField(max_length=64, blank=True)
    manual_host = models.CharField(max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self) -> None:
        if self.rotation not in (0, 90, 270):
            raise ValidationError({"rotation": "Rotation must be 0, 90, or 270 degrees."})

    @classmethod
    def load(cls) -> "ApplicationSettings":
        row, _ = cls.objects.get_or_create(pk=cls.SINGLETON_ID)
        return row
