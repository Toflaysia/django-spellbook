from pathlib import Path
import os
import subprocess


def main():
    project = Path(__file__).resolve().parent
    python = project / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not (project / 'manage.py').is_file():
        print('Помести run_server.py в папку проекта рядом с manage.py.')
        return 1
    if not python.is_file():
        print('Не найден Python в .venv. Проверь, что открыта папка проекта с существующим окружением .venv.')
        return 1
    print('Запускаю Spellbook: http://127.0.0.1:8000/', flush=True)
    print('Для остановки закрой терминал сервера кнопкой с корзиной.', flush=True)
    try:
        return subprocess.call([str(python), str(project / 'manage.py'), 'runserver'], cwd=project)
    except KeyboardInterrupt:
        return 130
    except OSError as error:
        print(f'Не удалось запустить Python: {error}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
