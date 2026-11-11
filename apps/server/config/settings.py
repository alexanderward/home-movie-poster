from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[3]
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "local-development-only-change-before-deployment")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]").split(",")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "channels",
    "apps.server.apps.posters.apps.PostersConfig",
]
MIDDLEWARE = [
    "apps.server.request_logging.RequestLoggingMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "apps.server.config.urls"
ASGI_APPLICATION = "apps.server.config.asgi.application"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "APP_DIRS": True}]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "home_movie_poster"),
        "USER": os.environ.get("POSTGRES_USER", "movie_poster"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "movie-poster-local-development"),
        "HOST": os.environ.get("DATABASE_HOST", "127.0.0.1"),
        "PORT": os.environ.get("POSTGRES_PORT", "5433"),
        "CONN_MAX_AGE": 0,
        "DISABLE_SERVER_SIDE_CURSORS": True,
    }
}

REDIS_URL = os.environ.get("POSTER_REDIS_URL", "redis://127.0.0.1:6379/0")
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            # Channel receives use a five-second blocking Redis command. redis-py 8
            # also defaults socket reads to five seconds, which makes an idle socket
            # race the command timeout and disconnect. Blocking channel reads must not
            # have a client-side read deadline.
            "hosts": [{"address": REDIS_URL, "socket_timeout": None}],
            "capacity": 100,
            "expiry": 60,
            "group_expiry": 90,
        },
    }
}
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
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
