from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[3]
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "local-development-only-change-before-deployment")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]").split(",")

INSTALLED_APPS = ["apps.server.apps.posters.apps.PostersConfig"]
MIDDLEWARE = [
    "apps.server.request_logging.RequestLoggingMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "apps.server.config.urls"
ASGI_APPLICATION = "apps.server.config.asgi.application"
TEMPLATES: list[dict[str, object]] = []

DATABASE_PATH = Path(os.environ.get("POSTER_DATABASE_PATH", BASE_DIR / ".data" / "poster.sqlite3"))
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATABASE_PATH,
        "OPTIONS": {
            "timeout": 20,
            "transaction_mode": "IMMEDIATE",
            "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL",
        },
        "TEST": {"NAME": ":memory:"},
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "home-frame",
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("POSTER_TIME_ZONE", "America/Chicago")
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / ".static"
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.environ.get("POSTER_MEDIA_ROOT", BASE_DIR / ".media")).resolve()

LOGGING_CONFIG = "apps.common.observability.configure"
LOGGING = {"version": 1}
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_SAMESITE = "Strict"
DATA_UPLOAD_MAX_MEMORY_SIZE = 16 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 16 * 1024 * 1024
