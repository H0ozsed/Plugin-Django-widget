"""Settings of the migrated dashboard backend, reduced to what the proof needs.

Compared with the original ``config/settings.py``, the migration only adds ``"widget_hub"`` to
``INSTALLED_APPS`` and the ``WIDGET_HUB`` dict below. PostgreSQL, allauth, e-mail and CORS
settings are unchanged and omitted here; the proof runs on SQLite.
"""

import os

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "proof-only-not-secret")
DEBUG = False
ALLOWED_HOSTS = ["*"]
USE_TZ = True
ROOT_URLCONF = "epitech_after.urls"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "widget_hub",
    "services",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
STATIC_URL = "static/"

WIDGET_HUB = {
    # The dashboard runs behind nginx, which overwrites X-Forwarded-For (see docker-compose.yml).
    "ABOUT_TRUST_X_FORWARDED_FOR": True,
    # The React front places widgets freely in pixels, not on the built-in front's grid.
    "POSITION_VALIDATOR": "services.legacy.pixel_position",
    "CREDENTIALS_KEY": os.environ.get("WIDGET_HUB_CREDENTIALS_KEY", "proof-only-credentials-key"),
}
