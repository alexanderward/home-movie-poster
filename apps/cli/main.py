from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
from pathlib import Path

from apps.common.observability import configure, event

ROOT = Path(__file__).resolve().parents[2]


def django_setup() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "apps.server.config.settings")
    import django

    django.setup()


def run_web(args: argparse.Namespace) -> int:
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "apps.server.config.asgi:application",
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--proxy-headers",
    ]
    if args.reload:
        command.extend(["--reload", "--reload-dir", "apps"])
    return subprocess.call(command, cwd=ROOT)


def run_client(args: argparse.Namespace) -> int:
    command = ["pnpm", "--dir", "apps/client", "dev", "--host", args.host]
    if args.port:
        command.extend(["--port", str(args.port)])
    return subprocess.call(command, cwd=ROOT)


def run_monitor(_: argparse.Namespace) -> int:
    django_setup()
    configure(service="monitor")
    from apps.server.apps.posters.monitor import PosterMonitor

    try:
        asyncio.run(PosterMonitor().run())
    except KeyboardInterrupt:
        event("monitor.stop.succeeded")
    return 0


def run_manage(args: argparse.Namespace) -> int:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "apps.server.config.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(["manage.py", *args.django_args])
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="poster")
    commands = root.add_subparsers(dest="command", required=True)

    web = commands.add_parser("web", help="Run the Django ASGI application")
    web.add_argument("--host", default="0.0.0.0")
    web.add_argument("--port", type=int, default=8001)
    web.add_argument("--reload", action=argparse.BooleanOptionalAction, default=True)
    web.set_defaults(handler=run_web)

    client = commands.add_parser("client", help="Run the Vite development server")
    client.add_argument("--host", default="0.0.0.0")
    client.add_argument("--port", type=int, default=5173)
    client.set_defaults(handler=run_client)

    monitor = commands.add_parser("monitor", help="Discover and monitor Kaleidescape devices")
    monitor.set_defaults(handler=run_monitor)

    manage = commands.add_parser("manage", help="Run a Django management command")
    manage.add_argument("django_args", nargs=argparse.REMAINDER)
    manage.set_defaults(handler=run_manage)
    return root


def main() -> int:
    args = parser().parse_args()
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
