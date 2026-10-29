"""Запуск Docker Compose из VS Code без команд в терминале."""

import os
from pathlib import Path
import shutil
import socket
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def docker_executable():
    executable = shutil.which("docker")
    if not executable and os.name == "nt":
        candidates = [
            Path(os.environ.get("ProgramFiles", "C:/Program Files"))
            / "Docker/Docker/resources/bin/docker.exe",
            Path(os.environ.get("LOCALAPPDATA", "."))
            / "Programs/DockerDesktop/resources/bin/docker.exe",
        ]
        executable = next((str(path) for path in candidates if path.is_file()), None)
    if not executable:
        raise RuntimeError(
            "Docker не найден. Установи Docker Desktop, открой его и перезапусти VS Code."
        )
    return executable


def environment():
    env = os.environ.copy()
    # На Linux используем владельца текущей папки, чтобы файлы базы оставались доступны.
    if hasattr(os, "getuid"):
        env["SPELLBOOK_UID"] = str(os.getuid())
        env["SPELLBOOK_GID"] = str(os.getgid())
    return env


def command(executable, *arguments, capture=False, timeout=None):
    return subprocess.run(
        [executable, *arguments],
        cwd=ROOT,
        env=environment(),
        check=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        timeout=timeout,
    )


def prepare():
    if not (ROOT / "manage.py").is_file() or not (ROOT / "compose.yaml").is_file():
        raise RuntimeError("Открой папку проекта с manage.py и compose.yaml.")
    executable = docker_executable()
    command(executable, "compose", "version", capture=True, timeout=20)
    try:
        engine = command(
            executable, "info", "--format", "{{.OSType}}", capture=True, timeout=20
        ).stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        raise RuntimeError(
            "Docker Engine недоступен. Открой Docker Desktop и дождись статуса Engine running."
        ) from None
    if engine != "linux":
        raise RuntimeError("В Docker Desktop переключись на Linux containers.")
    return executable


def start():
    executable = prepare()
    # Сначала собираем образ: ошибка сборки не должна остановить уже работающий сайт.
    command(executable, "compose", "config", "--quiet")
    print(
        "Собираю образ Spellbook. При первом запуске это может занять несколько минут.",
        flush=True,
    )
    command(executable, "compose", "build", "web")
    # Старый worker не должен обращаться к базе во время миграций новой версии.
    command(executable, "compose", "stop")
    try:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 8000))
    except OSError:
        raise RuntimeError(
            "Порт 8000 занят. Останови обычный сервер Spellbook и повтори запуск."
        ) from None
    try:
        command(executable, "compose", "up", "-d", "--wait", "--wait-timeout", "180")
    except subprocess.CalledProcessError:
        command(executable, "compose", "logs", "--tail", "60")
        raise RuntimeError(
            "Контейнеры не прошли проверку готовности. Смотри сообщения выше или Docker Desktop → Containers → spellbook."
        ) from None
    print("Готово: http://127.0.0.1:8000/", flush=True)
    print(
        "Контейнеры работают в фоне. Для остановки запусти stop_docker.py.", flush=True
    )
    return 0


def stop():
    executable = prepare()
    command(executable, "compose", "stop")
    print("Spellbook остановлен. База и изображения сохранены.", flush=True)
    return 0


def launch(action):
    try:
        return action()
    except KeyboardInterrupt:
        print(
            "Действие прервано. Состояние контейнеров можно проверить в Docker Desktop."
        )
        return 130
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"Не удалось выполнить действие: {error}")
        return 1
