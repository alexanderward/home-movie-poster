"""Django setup is lazy so CLI diagnostics do not require a database."""

import os


def setup() -> None:
    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "apps.server.config.settings")
    django.setup()


def manage(arguments: list[str]) -> None:
    from django.core.management import execute_from_command_line

    setup()
    execute_from_command_line(["poster manage", *arguments])
