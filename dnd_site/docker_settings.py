"""Отдельные настройки контейнера; обычный запуск использует прежний settings.py."""

import os
from pathlib import Path
from .email_config import configure_email, project_secret_key

# Ключ читается до импорта основных настроек и сохраняется между пересозданиями образа.
DATA_DIR = Path(os.environ.get("SPELLBOOK_DATA_DIR", "/data")).resolve()
if not DATA_DIR.is_dir():
    raise RuntimeError("Не подключён каталог данных Spellbook.")
os.environ.setdefault("SPELLBOOK_SECRET_KEY", project_secret_key(DATA_DIR))

from .settings import *  # noqa: F403,E402

DEBUG = False
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get(
        "SPELLBOOK_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]"
    ).split(",")
    if host.strip()
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "db.sqlite3",
        "OPTIONS": {"timeout": 20, "transaction_mode": "IMMEDIATE"},
    }
}
MEDIA_ROOT = DATA_DIR / "media"
STATIC_URL = "/static/"
STATIC_ROOT = DATA_DIR / ".docker-static"

# Используются уже заполненные настройки почты из папки проекта.
globals().update(configure_email(DATA_DIR))
SESSION_COOKIE_HTTPONLY = True
SECURE_CONTENT_TYPE_NOSNIFF = True
# Доступ по HTTP ограничен localhost в compose.yaml; HTTPS нужен для размещения в сети.
