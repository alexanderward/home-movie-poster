from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Discover Kaleidescape devices and publish live display state."

    def handle(self, *args, **options):
        del args, options
        import asyncio

        from apps.common.observability import configure
        from apps.server.apps.posters.monitor import PosterMonitor

        configure(service="monitor")
        asyncio.run(PosterMonitor().run())
