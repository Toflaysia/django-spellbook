from django.apps import AppConfig


class SpellsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "spells"

    def ready(self):
        from spells.search import register_unicode_search

        register_unicode_search()
