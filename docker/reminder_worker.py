"""Проверка напоминаний раз в минуту; ошибки SMTP не останавливают сервис."""

import logging
import os
import signal
import sys
import threading
from pathlib import Path

# При запуске файла Python добавляет в путь docker/, а нужен корень приложения.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dnd_site.docker_settings")


def run_once():
    from django.conf import settings
    from django.db import close_old_connections
    from spells.reminders import send_due_reminders

    if not settings.SPELLBOOK_EMAIL_DELIVERY_ENABLED:
        return {"due": 0, "sent": 0, "failed": 0}
    try:
        return send_due_reminders()
    finally:
        close_old_connections()


def main():
    import django

    django.setup()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    logging.info("Проверка напоминаний запущена. Интервал: 60 секунд.")
    while not stop.is_set():
        try:
            result = run_once()
            if result["due"]:
                logging.info(
                    "Готово: %s. Отправлено: %s. Ошибок: %s.",
                    result["due"],
                    result["sent"],
                    result["failed"],
                )
        except Exception:
            logging.exception(
                "Не удалось проверить напоминания. Попытка повторится через минуту."
            )
        stop.wait(60)


if __name__ == "__main__":
    main()
