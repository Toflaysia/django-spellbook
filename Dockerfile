FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=dnd_site.docker_settings \
    SPELLBOOK_DATA_DIR=/data

WORKDIR /app
COPY requirements.docker.txt /app/requirements.docker.txt
RUN pip install --no-cache-dir -r requirements.docker.txt \
    && groupadd --gid 1000 spellbook \
    && useradd --uid 1000 --gid spellbook --no-create-home spellbook

# Код входит в образ, а база, изображения и настройки остаются снаружи.
COPY manage.py /app/manage.py
COPY dnd_site /app/dnd_site
COPY spells /app/spells
COPY docker /app/docker

USER spellbook
EXPOSE 8000
CMD ["python", "docker/entrypoint.py"]
