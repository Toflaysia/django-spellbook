"""Подготовка базы и статики перед запуском Gunicorn."""

import os
from pathlib import Path
import subprocess
import sys


def main():
    data = Path(os.environ.get("SPELLBOOK_DATA_DIR", "/data"))
    if not data.is_dir():
        raise RuntimeError("Не подключена папка данных.")
    (data / "media").mkdir(exist_ok=True)
    (data / ".docker-static").mkdir(exist_ok=True)
    # Напоминания запускаются только после успешной проверки готовности web.
    for arguments in [
        ("migrate", "--noinput"),
        ("collectstatic", "--noinput"),
        ("check",),
    ]:
        subprocess.run([sys.executable, "manage.py", *arguments], check=True)
    os.execvp(
        "gunicorn",
        [
            "gunicorn",
            "dnd_site.wsgi:application",
            "--bind",
            "0.0.0.0:8000",
            "--workers",
            "1",
            "--threads",
            "2",
            "--timeout",
            "60",
            "--access-logfile",
            "-",
            "--error-logfile",
            "-",
        ],
    )


if __name__ == "__main__":
    main()
