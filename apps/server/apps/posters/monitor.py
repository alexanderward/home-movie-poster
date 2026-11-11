from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import socket
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlparse

import httpx
from asgiref.sync import sync_to_async
from channels.layers import get_channel_layer
from django.core.cache import cache
from django.db import close_old_connections, transaction
from django.utils import timezone
from kaleidescape import Device, const

from apps.common.kaleidescape.discovery import (
    DeviceCandidate,
    discover_sddp,
    listen_heartbeats,
    listen_sddp,
)
from apps.common.kaleidescape.library import LibraryEntry, parse_movies_page
from apps.common.observability import event

from .models import (
    ApplicationSettings,
    DiscoveredDevice,
    LibrarySync,
    Movie,
    PlaybackSnapshot,
    PosterAsset,
)
from .services import normalize_title, store_poster

ACTIVE = {
    const.PLAY_STATUS_PLAYING,
    const.PLAY_STATUS_PAUSED,
    const.PLAY_STATUS_FORWARD,
    const.PLAY_STATUS_REVERSE,
}


@dataclass(frozen=True)
class ProbeResult:
    serial_number: str
    ip_address: str
    friendly_name: str
    device_type: str
    movie_zones: int
    supports_playback: bool
    supports_library: bool


@dataclass(frozen=True)
class ResolvedLibraryEntry:
    entry: LibraryEntry
    title: str
    year: int | None
    genre: str
    rating: str
    director: str
    synopsis: str
    poster_bytes: bytes | None
    poster_url: str


class PosterMonitor:
    def __init__(self) -> None:
        self.candidates: asyncio.Queue[DeviceCandidate] = asyncio.Queue()
        self.device: Device | None = None
        self.player_serial = ""
        self.player_host = ""
        self.snapshot_lock = asyncio.Lock()

    async def run(self) -> None:
        event("monitor.start.succeeded")
        tasks = [
            asyncio.create_task(self.discovery_loop(), name="discovery"),
            asyncio.create_task(self.passive_sddp_loop(), name="passive-sddp"),
            asyncio.create_task(self.heartbeat_loop(), name="heartbeats"),
            asyncio.create_task(self.connection_loop(), name="connection"),
            asyncio.create_task(self.library_loop(), name="library"),
            asyncio.create_task(self.heartbeat_cache_loop(), name="health"),
        ]
        try:
            await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            if self.device:
                await self.mark_disconnected()
                await self.disconnect_player()
            event("monitor.stop.succeeded")

    async def heartbeat_cache_loop(self) -> None:
        while True:
            await sync_to_async(cache.set)("monitor:heartbeat", timezone.now(), 45)
            await asyncio.sleep(10)

    async def heartbeat_loop(self) -> None:
        while True:
            try:
                await listen_heartbeats(self.candidates)
            except (OSError, RuntimeError) as error:
                event("discovery.heartbeat.degraded", level=logging.WARNING, error=error)
                await asyncio.sleep(300)

    async def passive_sddp_loop(self) -> None:
        while True:
            try:
                await listen_sddp(self.candidates)
            except (OSError, RuntimeError) as error:
                event("discovery.passive_sddp.degraded", level=logging.WARNING, error=error)
                await asyncio.sleep(300)

    async def discovery_loop(self) -> None:
        while True:
            config = await sync_to_async(ApplicationSettings.load)()
            manual = config.manual_host or os.environ.get("KALEIDESCAPE_MANUAL_HOST", "")
            if manual:
                try:
                    address = await asyncio.get_running_loop().run_in_executor(
                        None, lambda: socket.gethostbyname(manual)
                    )
                    await self.candidates.put(DeviceCandidate(address, {}, "manual"))
                except OSError as error:
                    event("discovery.manual.failed", level=logging.WARNING, error=error)
            try:
                for candidate in await discover_sddp():
                    await self.candidates.put(candidate)
            except OSError as error:
                event("discovery.sddp.degraded", level=logging.WARNING, error=error)

            pending: dict[str, DeviceCandidate] = {}
            while not self.candidates.empty():
                candidate = await self.candidates.get()
                pending[candidate.ip_address] = candidate
            for candidate in pending.values():
                try:
                    result = await self.probe(candidate.ip_address)
                    await sync_to_async(self.persist_probe)(result)
                    event(
                        "discovery.device.succeeded",
                        serial_number=result.serial_number,
                        source=candidate.source,
                        playback=result.supports_playback,
                        library=result.supports_library,
                    )
                except Exception as error:
                    event(
                        "discovery.device.failed",
                        level=logging.WARNING,
                        ip_address=candidate.ip_address,
                        error=error,
                    )
            await sync_to_async(self.auto_select_roles)()
            await asyncio.sleep(60)

    async def probe(self, host: str) -> ProbeResult:
        device = Device(host, reconnect=False, timeout=5)
        try:
            await device.connect()
            supports_library = False
            try:
                async with httpx.AsyncClient(timeout=5, follow_redirects=False) as client:
                    response = await client.get(f"http://{host}/movies")
                    supports_library = response.status_code == 200
            except httpx.HTTPError:
                pass
            return ProbeResult(
                serial_number=device.serial_number or host,
                ip_address=host,
                friendly_name=device.system.friendly_name or device.system.type or host,
                device_type=device.system.type,
                movie_zones=device.system.movie_zones,
                supports_playback=device.is_movie_player,
                supports_library=supports_library,
            )
        finally:
            await device.disconnect()

    @staticmethod
    def persist_probe(result: ProbeResult) -> None:
        close_old_connections()
        DiscoveredDevice.objects.update_or_create(
            serial_number=result.serial_number,
            defaults={
                "friendly_name": result.friendly_name,
                "device_type": result.device_type,
                "ip_address": result.ip_address,
                "movie_zones": result.movie_zones,
                "supports_playback": result.supports_playback,
                "supports_library": result.supports_library,
                "last_seen_at": timezone.now(),
            },
        )

    @staticmethod
    def auto_select_roles() -> None:
        config = ApplicationSettings.load()
        changed = False
        if not config.player_serial:
            players = list(
                DiscoveredDevice.objects.filter(supports_playback=True).values_list(
                    "serial_number", flat=True
                )
            )
            if len(players) == 1:
                config.player_serial = players[0]
                changed = True
        if not config.library_serial:
            libraries = list(
                DiscoveredDevice.objects.filter(supports_library=True).values_list(
                    "serial_number", flat=True
                )
            )
            if len(libraries) == 1:
                config.library_serial = libraries[0]
                changed = True
        if changed:
            config.save()
            event(
                "settings.devices.auto_selected",
                player_serial=config.player_serial,
                library_serial=config.library_serial,
            )

    async def connection_loop(self) -> None:
        while True:
            selected = await sync_to_async(self.selected_player)()
            if selected is None:
                if self.device or self.player_serial:
                    await self.mark_disconnected()
                await self.disconnect_player()
                await asyncio.sleep(3)
                continue
            serial, host = selected
            if serial != self.player_serial or host != self.player_host or not self.device:
                if self.device:
                    await self.mark_disconnected()
                await self.disconnect_player()
                self.device = Device(host, reconnect=True, reconnect_delay=5, timeout=8)
                self.player_serial = serial
                self.player_host = host

                async def handle_event(name: str, *args) -> None:
                    del name, args
                    await self.publish_snapshot()

                self.device.dispatcher.connect(handle_event)
                try:
                    await self.device.connect()
                    await self.device.refresh()
                    event("playback.connection.succeeded", player_serial=serial)
                    await self.publish_snapshot()
                except Exception as error:
                    event(
                        "playback.connection.failed",
                        level=logging.WARNING,
                        player_serial=serial,
                        error=error,
                    )
                    await self.mark_disconnected()
                    await self.disconnect_player()
                    await asyncio.sleep(5)
                    continue
            try:
                assert self.device
                if not self.device.is_connected:
                    await self.mark_disconnected()
                else:
                    await self.device.refresh()
                    await self.publish_snapshot()
            except Exception as error:
                event("playback.refresh.failed", level=logging.WARNING, error=error)
                await self.mark_disconnected()
            await asyncio.sleep(15)

    @staticmethod
    def selected_player() -> tuple[str, str] | None:
        config = ApplicationSettings.load()
        if not config.player_serial:
            return None
        row = DiscoveredDevice.objects.filter(serial_number=config.player_serial).first()
        return (row.serial_number, row.ip_address) if row else None

    async def disconnect_player(self) -> None:
        if self.device:
            await self.device.disconnect()
        self.device = None
        self.player_serial = ""
        self.player_host = ""

    async def mark_disconnected(self) -> None:
        changed = await sync_to_async(
            lambda: PlaybackSnapshot.objects.filter(pk=1, connected=True).update(connected=False)
        )()
        if changed:
            event(
                "playback.connection.lost", level=logging.WARNING, player_serial=self.player_serial
            )
        await self.broadcast()

    async def publish_snapshot(self) -> None:
        if not self.device or not self.device.is_connected or self.snapshot_lock.locked():
            return
        async with self.snapshot_lock:
            device = self.device
            title = device.osd.title_name or device.movie.title
            movie_title = device.movie.title
            movie_matches = (
                not title
                or not movie_title
                or normalize_title(title) == normalize_title(movie_title)
            )
            year = int(device.movie.year) if str(device.movie.year).isdigit() else None
            poster_id = None
            if movie_matches:
                poster_id = await self.cache_live_cover(
                    device.movie.cover_hires or device.movie.cover
                )
            if not poster_id:
                poster_id = await sync_to_async(self.match_poster)(title or movie_title, year)
            observed = timezone.now()
            await sync_to_async(self.write_snapshot)(
                connected=True,
                play_status=device.movie.play_status or const.PLAY_STATUS_NONE,
                title=title or movie_title,
                year=year,
                duration=device.movie.title_length or None,
                position=device.movie.title_location or None,
                poster_id=poster_id,
                observed=observed,
            )
            await self.broadcast()

    @staticmethod
    def match_poster(title: str, year: int | None) -> int | None:
        if not title:
            return None
        query = Movie.objects.filter(
            normalized_title=normalize_title(title), poster__isnull=False, available=True
        )
        kaleidescape = query.filter(source=Movie.Source.KALEIDESCAPE)
        if year:
            kaleidescape = kaleidescape.filter(year=year)
        exact = kaleidescape.first()
        if exact:
            return exact.poster_id
        if not os.environ.get("TMDB_READ_TOKEN"):
            return None
        tmdb = query.filter(source=Movie.Source.TMDB)
        if year:
            tmdb = tmdb.filter(year=year)
        matches = list(tmdb[:2])
        return matches[0].poster_id if len(matches) == 1 else None

    async def cache_live_cover(self, url: str) -> int | None:
        if not url:
            return None
        parsed = urlparse(url)
        allowed = await sync_to_async(
            lambda: set(DiscoveredDevice.objects.values_list("ip_address", flat=True))
        )()
        if not await self.is_allowed_device_url(parsed, allowed):
            return None
        digest = hashlib.sha256(url.encode()).hexdigest()
        cached = await sync_to_async(
            lambda: PosterAsset.objects.filter(source_url_hash=digest).first()
        )()
        if cached:
            return cached.id
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
                response = await client.get(url)
                response.raise_for_status()
            asset = await sync_to_async(store_poster)(response.content, source_url=url)
            return asset.id
        except Exception as error:
            event("poster.live.failed", level=logging.WARNING, error=error)
            return None

    @staticmethod
    async def is_allowed_device_url(parsed, allowed: set[str]) -> bool:
        if parsed.scheme != "http" or not parsed.hostname or parsed.username or parsed.password:
            return False
        if parsed.hostname in allowed:
            return True
        try:
            resolved = await asyncio.get_running_loop().run_in_executor(
                None, lambda: socket.gethostbyname(parsed.hostname or "")
            )
        except OSError:
            return False
        return resolved in allowed

    def write_snapshot(
        self,
        *,
        connected: bool,
        play_status: str,
        title: str,
        year: int | None,
        duration: int | None,
        position: int | None,
        poster_id: int | None,
        observed,
    ) -> None:
        prior = PlaybackSnapshot.objects.filter(pk=1).first()
        PlaybackSnapshot.objects.update_or_create(
            pk=1,
            defaults={
                "player_serial": self.player_serial,
                "connected": connected,
                "play_status": play_status,
                "title": title,
                "normalized_title": normalize_title(title),
                "year": year,
                "duration_seconds": duration,
                "position_seconds": position,
                "poster_id": poster_id,
                "observed_at": observed,
            },
        )
        if not prior or prior.play_status != play_status or prior.title != title:
            event(
                "playback.transition.observed",
                previous_status=prior.play_status if prior else "none",
                status=play_status,
                title=title,
            )
        event("playback.snapshot.updated", status=play_status, title=title)

    async def broadcast(self) -> None:
        layer = get_channel_layer()
        if layer:
            await layer.group_send("display", {"type": "display.refresh"})

    async def library_loop(self) -> None:
        # Give discovery and automatic role selection a chance to complete at startup.
        await asyncio.sleep(10)
        while True:
            sync = await sync_to_async(self.next_sync)()
            if sync:
                await self.perform_library_sync(sync)
            await asyncio.sleep(5)

    @staticmethod
    def next_sync() -> LibrarySync | None:
        queued = LibrarySync.objects.filter(status=LibrarySync.Status.QUEUED).first()
        if queued:
            return queued
        now = timezone.now()
        running = LibrarySync.objects.filter(status=LibrarySync.Status.RUNNING).first()
        if running:
            if running.started_at and running.started_at < now - timedelta(minutes=5):
                running.status = LibrarySync.Status.QUEUED
                running.error = "Recovered after monitor restart."
                running.save(update_fields=["status", "error"])
                event("library.sync.recovered", sync_id=running.id)
                return running
            return None
        latest_attempt = LibrarySync.objects.first()
        if (
            latest_attempt
            and latest_attempt.status == LibrarySync.Status.FAILED
            and latest_attempt.finished_at
            and latest_attempt.finished_at >= now - timedelta(minutes=10)
        ):
            return None
        latest = LibrarySync.objects.filter(status=LibrarySync.Status.SUCCEEDED).first()
        if (
            not latest
            or not latest.finished_at
            or latest.finished_at < now - timedelta(hours=6)
        ):
            return LibrarySync.objects.create()
        return None

    async def perform_library_sync(self, sync: LibrarySync) -> None:
        host = await sync_to_async(self.library_host)()
        if not host:
            await sync_to_async(self.fail_sync)(sync.id, "No library-capable device is selected.")
            return
        await sync_to_async(self.start_sync)(sync.id)
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
                response = await client.get(f"http://{host}/movies")
                response.raise_for_status()
            entries = parse_movies_page(response.text)
            if not entries:
                raise ValueError("The Kaleidescape movies page contained no recognized titles.")
            device = Device(host, reconnect=False, timeout=10)
            await device.connect()
            try:
                allowed = await sync_to_async(
                    lambda: set(DiscoveredDevice.objects.values_list("ip_address", flat=True))
                )()
                semaphore = asyncio.Semaphore(4)
                async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
                    resolved = await asyncio.gather(
                        *(
                            self.resolve_library_entry(device, client, semaphore, entry, allowed)
                            for entry in entries
                        )
                    )
            finally:
                await device.disconnect()
            updated = await sync_to_async(self.persist_library)(resolved)
            await sync_to_async(self.complete_sync)(sync.id, len(entries), updated)
            await self.broadcast()
        except Exception as error:
            await sync_to_async(self.fail_sync)(sync.id, str(error))
            event("library.sync.failed", level=logging.ERROR, sync_id=sync.id, error=error)

    @staticmethod
    def library_host() -> str | None:
        config = ApplicationSettings.load()
        row = DiscoveredDevice.objects.filter(serial_number=config.library_serial).first()
        return row.ip_address if row else None

    async def resolve_library_entry(
        self,
        device: Device,
        client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        entry: LibraryEntry,
        allowed: set[str],
    ) -> ResolvedLibraryEntry:
        async with semaphore:
            details = await device.get_content_details(entry.handle)
            url = details.field_hires_cover_url or details.field_cover_url
            poster_bytes = None
            parsed = urlparse(url) if url else None
            if parsed and await self.is_allowed_device_url(parsed, allowed):
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                    poster_bytes = response.content
                except httpx.HTTPError:
                    poster_bytes = None
            year = int(details.field_year) if str(details.field_year).isdigit() else entry.year
            return ResolvedLibraryEntry(
                entry=entry,
                title=details.field_title or entry.title,
                year=year,
                genre=details.field_genre or entry.genre,
                rating=details.field_rating or entry.rating,
                director=details.field_director or entry.director,
                synopsis=details.field_synopsis,
                poster_bytes=poster_bytes,
                poster_url=url,
            )

    @staticmethod
    @transaction.atomic
    def persist_library(entries: list[ResolvedLibraryEntry]) -> int:
        handles = [item.entry.handle for item in entries]
        Movie.objects.filter(source=Movie.Source.KALEIDESCAPE).exclude(
            source_key__in=handles
        ).update(available=False)
        updated = 0
        for item in entries:
            poster = (
                store_poster(item.poster_bytes, source_url=item.poster_url)
                if item.poster_bytes
                else None
            )
            defaults = {
                "title": item.title,
                "normalized_title": normalize_title(item.title),
                "year": item.year,
                "genre": item.genre,
                "rating": item.rating,
                "director": item.director,
                "synopsis": item.synopsis,
                "available": True,
            }
            if poster:
                defaults["poster"] = poster
            _, created = Movie.objects.update_or_create(
                source=Movie.Source.KALEIDESCAPE,
                source_key=item.entry.handle,
                defaults=defaults,
            )
            updated += int(created or bool(defaults))
        return updated

    @staticmethod
    def start_sync(identifier: int) -> None:
        LibrarySync.objects.filter(pk=identifier).update(
            status=LibrarySync.Status.RUNNING, started_at=timezone.now(), error=""
        )
        event("library.sync.started", sync_id=identifier)

    @staticmethod
    def complete_sync(identifier: int, discovered: int, updated: int) -> None:
        LibrarySync.objects.filter(pk=identifier).update(
            status=LibrarySync.Status.SUCCEEDED,
            finished_at=timezone.now(),
            discovered_count=discovered,
            updated_count=updated,
        )
        event("library.sync.succeeded", sync_id=identifier, discovered=discovered, updated=updated)

    @staticmethod
    def fail_sync(identifier: int, message: str) -> None:
        LibrarySync.objects.filter(pk=identifier).update(
            status=LibrarySync.Status.FAILED,
            finished_at=timezone.now(),
            error=message[:500],
        )
