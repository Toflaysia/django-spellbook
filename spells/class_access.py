"""Shared class visibility and editing rules for pages, forms and API."""
from django.db.models import Q
from django.core.exceptions import PermissionDenied
from spells.models import CharacterClass


def visible_classes(user=None):
    objects = CharacterClass.objects.all()
    if user is not None and user.is_authenticated and user.is_staff:
        return objects
    query = Q(created_by__isnull=True) | Q(is_public=True)
    if user is not None and user.is_authenticated:
        query |= Q(created_by__user=user)
    return objects.filter(query)


def can_edit_class(user, item):
    return bool(user.is_authenticated and (user.is_staff or (item.created_by_id and item.created_by.user_id == user.pk)))


def require_class_editor(user, item):
    if not can_edit_class(user, item):
        raise PermissionDenied


def class_emblem(name):
    names = {'варвар':'barbarian','бард':'bard','воин':'fighter','волшебник':'wizard','друид':'druid','жрец':'cleric','изобретатель':'artificer','колдун':'warlock','монах':'monk','паладин':'paladin','плут':'rogue','следопыт':'ranger','чародей':'sorcerer'}
    value = name.strip().casefold()
    return names.get(value, value if value in names.values() else 'custom')


def scope_spell_classes(spell, user):
    from django.db.models import prefetch_related_objects, Prefetch
    from spells.models import Subclass
    classes = visible_classes(user)
    # Replace the unscoped cache if a caller prefetched relations earlier.
    cache = getattr(spell, '_prefetched_objects_cache', {})
    cache.pop('aviable_classes', None)
    cache.pop('aviable_subclasses', None)
    prefetch_related_objects([spell],
        Prefetch('aviable_classes', queryset=classes),
        Prefetch('aviable_subclasses', queryset=Subclass.objects.filter(character_class__in=classes)))
    return spell
