import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-key-change-me")
DEBUG = True
ALLOWED_HOSTS = ["*"]

# daphne must be first so its runserver (ASGI + websockets + autoreload) wins.
INSTALLED_APPS = [
    "daphne",
    "channels",
    "django.contrib.staticfiles",
    "committee_web",
]

MIDDLEWARE = [
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": []},
}]

ASGI_APPLICATION = "config.asgi.application"
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

# sqlite is configured only to satisfy Django; no models/migrations are defined.
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3",
                         "NAME": BASE_DIR / "db.sqlite3"}}

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "web" / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
