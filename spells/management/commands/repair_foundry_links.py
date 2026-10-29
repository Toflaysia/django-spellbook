"""Repair old spell descriptions without importing them again."""
from django.contrib.auth.models import AnonymousUser
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from spells.import_links import ImportLinker
from spells.models import Spell


class Command(BaseCommand):
    help = 'Преобразовать старые ссылки Foundry в описаниях заклинаний.'

    def handle(self, *args, **options):
        lookup = Q()
        for field in ('description', 'higher_level'):
            for marker in ('@Compendium[', '@UUID['):
                lookup |= Q(**{field+'__contains': marker})
        changed = 0
        warnings = 0
        linkers = {}
        try:
            with transaction.atomic():
                for spell in Spell.objects.filter(lookup).select_related('created_by__user').iterator():
                    # Public descriptions must never acquire links to private works.
                    user = spell.created_by.user if not spell.is_official and not spell.is_public and spell.created_by_id else AnonymousUser()
                    identity = user.pk if user.is_authenticated else None
                    if identity not in linkers:
                        linkers[identity] = ImportLinker(user)
                    linker = linkers[identity]
                    linker.warnings.clear()
                    fields = []
                    for field in ('description', 'higher_level'):
                        old = getattr(spell, field)
                        new = linker.description(old, references_only=True)
                        if old != new:
                            setattr(spell, field, new)
                            fields.append(field)
                    if fields:
                        spell.save(update_fields=fields)
                        changed += 1
                    warnings += len(linker.warnings)
        except (ValueError, TypeError, RecursionError) as error:
            raise CommandError('Очистка описаний отменена: обнаружен неверный формат. Изменения базы не сохранены.') from error
        self.stdout.write(f'Исправлено заклинаний: {changed}. Ссылок без подходящей записи или названия: {warnings}.')
