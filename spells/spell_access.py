from django.db.models import Q
from spells.models import Spell


def visible_spells(user):
    query = Q(is_official=True) | Q(is_official=False, is_public=True)
    if user is not None and user.is_authenticated:
        query |= Q(is_official=False, created_by__user=user)
    return Spell.objects.filter(query)


def collected_spells(user):
    if user is None or not user.is_authenticated:
        return Spell.objects.none()
    return visible_spells(user).filter(
        Q(created_by__user=user, is_official=False) | Q(saved_by_players__user=user)
    ).distinct()


def can_edit_spell(user, spell):
    return bool(user is not None and user.is_authenticated and (
        (spell.is_official and user.is_staff) or
        (not spell.is_official and spell.created_by_id and spell.created_by.user_id == user.pk)
    ))
