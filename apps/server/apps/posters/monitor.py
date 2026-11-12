from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import socket
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx
from asgiref.sync import sync_to_async
from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone
from kaleidescape import Device, const

from apps.common.kaleidescape.discovery import (
    DeviceCandidate,
    discover_sddp,
    listen_heartbeats,
    listen_sddp,
)
from apps.common.observability import event
from apps.common.posters import normalize_image

from .models import (
    ApplicationSettings,
    DiscoveredDevice,
    MonitorHeartbeat,
    Movie,
    PlaybackSnapshot,
)
from .services import complete_movie_night_after_playback, normalize_title

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


class PosterMonitor:
    """Read-only Strato monitor; persistent catalog data comes only from TMDB or uploads."""

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
            asyncio.create_task(self.database_heartbeat_loop(), name="health"),
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

    async def database_heartbeat_loop(self) -> None:
        while True:
            await sync_to_async(self.write_heartbeat)()
            await asyncio.sleep(10)

    @staticmethod
    def write_heartbeat() -> None:
        close_old_connections()
        MonitorHeartbeat.objects.update_or_create(
            pk=MonitorHeartbeat.SINGLETON_ID,
            defaults={"observed_at": timezone.now()},
        )

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
                    )
                except Exception as error:
                    event(
                        "discovery.device.failed",
                        level=logging.WARNING,
                        ip_address=candidate.ip_address,
                        error=error,
                    )
            await sync_to_async(self.auto_select_player)()
            await asyncio.sleep(60)

    async def probe(self, host: str) -> ProbeResult:
        device = Device(host, reconnect=False, timeout=5)
        try:
            await device.connect()
            return ProbeResult(
                serial_number=device.serial_number or host,
                ip_address=host,
                friendly_name=device.system.friendly_name or device.system.type or host,
                device_type=device.system.type,
                movie_zones=device.system.movie_zones,
                supports_playback=device.is_movie_player,
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
                "last_seen_at": timezone.now(),
            },
        )

    @staticmethod
    def auto_select_player() -> None:
        config = ApplicationSettings.load()
        if config.player_serial:
            return
        players = list(
            DiscoveredDevice.objects.filter(supports_playback=True).values_list(
                "serial_number", flat=True
            )
        )
        if len(players) == 1:
            config.player_serial = players[0]
            config.save(update_fields=["player_serial", "updated_at"])
            event("settings.player.auto_selected", player_serial=config.player_serial)

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
            poster_path = ""
            poster_source_hash = ""
            if movie_matches:
                cached = await self.cache_live_cover(device.movie.cover_hires or device.movie.cover)
                if cached:
                    poster_path, poster_source_hash = cached
            if not poster_path:
                poster_path = await sync_to_async(self.match_poster)(title or movie_title, year)
            await sync_to_async(self.write_snapshot)(
                connected=True,
                play_status=device.movie.play_status or const.PLAY_STATUS_NONE,
                title=title or movie_title,
                year=year,
                duration=device.movie.title_length or None,
                position=device.movie.title_location or None,
                poster_path=poster_path,
                poster_source_hash=poster_source_hash,
                observed=timezone.now(),
            )

    @staticmethod
    def match_poster(title: str, year: int | None) -> str:
        if not title:
            return ""
        query = Movie.objects.select_related("poster").filter(
            normalized_title=normalize_title(title), poster__isnull=False
        )
        if year:
            exact = query.filter(year=year).first()
            if exact and exact.poster:
                return exact.poster.path
        match = query.first()
        return match.poster.path if match and match.poster else ""

    async def cache_live_cover(self, url: str) -> tuple[str, str] | None:
        if not url:
            return None
        parsed = urlparse(url)
        allowed = await sync_to_async(
            lambda: set(DiscoveredDevice.objects.values_list("ip_address", flat=True))
        )()
        if not await self.is_allowed_device_url(parsed, allowed):
            return None
        source_hash = hashlib.sha256(url.encode()).hexdigest()
        prior = await sync_to_async(lambda: PlaybackSnapshot.objects.filter(pk=1).first())()
        if (
            prior
            and prior.poster_source_hash == source_hash
            and prior.poster_path
            and (Path(settings.MEDIA_ROOT) / prior.poster_path).is_file()
        ):
            return prior.poster_path, source_hash
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
                response = await client.get(url)
                response.raise_for_status()
            stored = await sync_to_async(normalize_image)(
                response.content, settings.MEDIA_ROOT, namespace="runtime"
            )
            return stored.relative_path, source_hash
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

    @staticmethod
    def delete_runtime_poster(relative_path: str) -> None:
        if not relative_path.startswith("runtime/"):
            return
        root = Path(settings.MEDIA_ROOT).resolve()
        target = (root / relative_path).resolve()
        if root in target.parents:
            target.unlink(missing_ok=True)

    def write_snapshot(
        self,
        *,
        connected: bool,
        play_status: str,
        title: str,
        year: int | None,
        duration: int | None,
        position: int | None,
        poster_path: str,
        poster_source_hash: str,
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
                "poster_path": poster_path,
                "poster_source_hash": poster_source_hash,
                "observed_at": observed,
            },
        )
        if prior and prior.poster_path != poster_path:
            self.delete_runtime_poster(prior.poster_path)
        if not prior or prior.play_status != play_status or prior.title != title:
            event(
                "playback.transition.observed",
                previous_status=prior.play_status if prior else "none",
                status=play_status,
                title=title,
            )
        if prior and prior.play_status in ACTIVE and play_status not in ACTIVE:
            complete_movie_night_after_playback(prior.title)
        event("playback.snapshot.updated", status=play_status, title=title)
