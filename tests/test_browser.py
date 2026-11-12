from __future__ import annotations

import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest
from playwright.sync_api import Route, sync_playwright

pytestmark = pytest.mark.browser
ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:4173"
POSTER = "data:image/svg+xml," + (
    "%3Csvg xmlns='http://www.w3.org/2000/svg' width='600' height='900'%3E"
    "%3Crect width='600' height='900' fill='%23231e16'/%3E%3C/svg%3E"
)


@pytest.fixture(scope="module")
def preview_server():
    dist = ROOT / "apps" / "client" / "dist"
    if not dist.is_dir():
        pytest.skip("Run the client build before browser tests")

    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith("/static/assets/"):
                self.path = self.path.removeprefix("/static")
            elif self.path in {"/", "/display", "/admin"}:
                self.path = "/index.html"
            super().do_GET()

        def log_message(self, format, *args):
            del format, args

    server = ThreadingHTTPServer(("127.0.0.1", 4173), partial(Handler, directory=str(dist)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield
    server.shutdown()
    thread.join(timeout=10)


def display_state(rotation: int):
    return {
        "mode": "now_playing",
        "headline": "Now Playing",
        "title": "A Deliberately Long Feature Title for Layout Validation",
        "poster_url": POSTER,
        "event_date": None,
        "showtime": None,
        "playback_status": "playing",
        "position_seconds": 600,
        "duration_seconds": 7200,
        "observed_at": "2026-01-01T00:00:00Z",
        "rotation": rotation,
        "slideshow_interval_seconds": 60,
    }


@pytest.mark.parametrize(
    ("viewport", "rotation"),
    [
        ({"width": 1080, "height": 1920}, 0),
        ({"width": 1920, "height": 1080}, 90),
        ({"width": 1920, "height": 1080}, 270),
    ],
)
def test_display_viewports_and_poster_containment(preview_server, viewport, rotation):
    del preview_server
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport=viewport)

        def handler(route: Route):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(display_state(rotation)),
            )

        page.route("**/api/display", handler)
        page.goto(f"{BASE}/display")
        page.locator(".poster-frame img").wait_for()
        assert (
            page.locator(".display-canvas").get_attribute("class").find("is-rotated") >= 0
            if rotation
            else True
        )
        assert (
            page.locator(".poster-frame img").evaluate("node => getComputedStyle(node).objectFit")
            == "contain"
        )
        # The poster spans the full width of the portrait canvas.
        canvas = page.locator(".display-canvas").evaluate("node => node.clientWidth")
        poster = page.locator(".poster-frame img").evaluate("node => node.clientWidth")
        assert poster == canvas
        browser.close()


def test_phone_admin_is_usable_at_390_by_844(preview_server):
    del preview_server
    responses = {
        "/api/session": {
            "csrf_token": "test",
            "tmdb_enabled": False,
        },
        "/api/settings": {
            "rotation": 0,
            "slideshow_interval_seconds": 60,
            "timezone": "America/Chicago",
            "player_serial": "",
            "manual_host": "",
            "tmdb_enabled": False,
        },
        "/api/devices": [],
        "/api/movie-nights": [],
        "/api/slideshow": {"total": 0, "interval_seconds": 60, "items": []},
        "/api/health": {
            "status": "degraded",
            "database": True,
            "monitor": False,
            "player_connected": False,
            "tmdb_configured": False,
        },
    }
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 390, "height": 844})

        def handler(route: Route):
            path = route.request.url.split("?", 1)[0].replace(BASE, "")
            route.fulfill(
                status=200, content_type="application/json", body=json.dumps(responses[path])
            )

        page.route("**/api/**", handler)
        page.goto(f"{BASE}/admin")
        page.get_by_role("heading", name="Up next").wait_for()
        assert page.get_by_role("searchbox", name="Search TMDB").is_visible()
        assert page.get_by_text("Private by design.", exact=False).count() == 0
        assert page.locator("body").evaluate("node => node.scrollWidth <= window.innerWidth")
        page.get_by_role("button", name="Settings").click()
        page.get_by_role("heading", name="Settings").wait_for()
        assert page.get_by_role("heading", name="Server").is_visible()
        assert page.get_by_text("127.0.0.1", exact=True).is_visible()
        assert page.get_by_text(f"{BASE}/admin", exact=True).is_visible()
        assert page.locator("body").evaluate("node => node.scrollWidth <= window.innerWidth")
        page.get_by_role("button", name="Back to movie night").click()
        page.get_by_role("heading", name="Up next").wait_for()
        browser.close()
