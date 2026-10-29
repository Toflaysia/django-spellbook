"""Остановка контейнеров Spellbook кнопкой ▶ в VS Code."""

from dnd_site.docker_launcher import launch, stop

if __name__ == "__main__":
    raise SystemExit(launch(stop))
