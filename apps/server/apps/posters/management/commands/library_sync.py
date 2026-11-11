from django.core.management.base import BaseCommand

from apps.server.apps.posters.services import request_library_sync


class Command(BaseCommand):
    help = "Queue an idempotent Kaleidescape library synchronization."

    def handle(self, *args, **options):
        del args, options
        sync = request_library_sync()
        self.stdout.write(self.style.SUCCESS(f"Queued library sync {sync.id}."))
