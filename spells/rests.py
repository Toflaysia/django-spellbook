"""Короткий и длинный отдых по D&D 5e 2014; факт отдыха подтверждает игрок."""

from spells.abilities import resource_snapshot, refresh_ability_resources
from collections import Counter
import secrets
from django.utils import timezone
from spells.models import CharacterResource
from spells.rest_validation import DICE
from spells.combat import end_concentration


def hit_dice(person):
    # У каждого класса своя кость хитов. Одинаковые типы костей собираются в общий запас.
    pools = Counter()
    pools[
        (
            person.character_class.hit_die
            if person.character_class_id
            else person.fallback_hit_die
        )
    ] += person.primary_class_level
    if person.second_class_level:
        pools[
            (
                person.second_class.hit_die
                if person.second_class_id
                else person.fallback_hit_die
            )
        ] += person.second_class_level
    if person.warlock_level:
        pools[8] += person.warlock_level
    return {die: count for die, count in pools.items() if count > 0}


def spent_dice(person):
    # После изменения уровня отсекаем старый расход, который больше существующего запаса костей.
    return {
        str(die): min(total, max(0, person.spent_hit_dice.get(str(die), 0)))
        for die, total in hit_dice(person).items()
    }


def rest_state(person):
    # Готовим один ответ для здоровья и способностей; чтение состояния не применяет отдых.
    ability_resources, adopted = resource_snapshot(person)
    pools = hit_dice(person)
    spent = spent_dice(person)
    # За длинный отдых возвращается не больше половины общего числа костей, минимум одна.
    budget = max(1, sum(pools.values()) // 2)
    remaining = budget
    recovery = {}
    for die in sorted(pools, reverse=True):
        count = min(remaining, spent[str(die)])
        recovery[str(die)] = count
        remaining -= count
    return {
        "revision": person.rest_revision,
        "constitution_modifier": (person.constitution - 10) // 2,
        "recovery_budget": budget,
        "dice": [
            {
                "die": die,
                "maximum": total,
                "spent": spent[str(die)],
                "available": total - spent[str(die)],
                "recover": recovery[str(die)],
            }
            for die, total in sorted(pools.items())
        ],
        "ability_resources": ability_resources,
        "resources": [
            {
                "id": r.pk,
                "name": r.name,
                "current": r.current,
                "maximum": r.maximum,
                "refresh_on": r.refresh_on,
                "refresh_label": r.get_refresh_on_display(),
            }
            for r in person.rest_resources.filter(source_key__isnull=True).exclude(
                pk__in=adopted
            )
        ],
        "books": [
            {"id": b.pk, "name": b.name, "active": b.is_active}
            for b in person.spellbooks.order_by("name", "pk")
        ],
    }


def spend_hit_die(person, die):
    # Бросок кости и изменение хитов выполняются на сервере, а не принимаются из браузера.
    pools = hit_dice(person)
    spent = spent_dice(person)
    if die not in pools or spent[str(die)] >= pools[die]:
        raise ValueError("Нет доступной кости хитов этого типа.")
    if person.current_hit_points >= person.max_hit_points:
        raise ValueError("Хиты уже полные. Кость не потрачена.")
    roll = secrets.randbelow(die) + 1
    modifier = (person.constitution - 10) // 2
    healing = max(0, roll + modifier)
    before = person.current_hit_points
    person.current_hit_points = min(person.max_hit_points, before + healing)
    spent[str(die)] += 1
    person.spent_hit_dice = spent
    return f"1d{die}: {roll} {modifier:+d} = {healing}. Восстановлено хитов: {person.current_hit_points-before}. Кость потрачена."


def finish_rest(person, kind, books, recovery=None):
    # Сначала проверяем восстановление костей. При ошибке нельзя успеть выдать хиты и ячейки.
    now = timezone.now()
    if kind == "long":
        if person.current_hit_points < 1:
            raise ValueError("Для длинного отдыха нужен хотя бы 1 хит в начале отдыха.")
        spent = spent_dice(person)
        budget = max(1, sum(hit_dice(person).values()) // 2)
        recovery = recovery or {key: 0 for key in spent}
        if (
            set(recovery) != set(spent)
            or any(
                type(v) is not int or v < 0 or v > spent[k] for k, v in recovery.items()
            )
            or sum(recovery.values()) > budget
        ):
            raise ValueError("Проверь число восстанавливаемых костей хитов.")
        person.spent_hit_dice = {
            key: count - recovery[key] for key, count in spent.items()
        }
        person.current_hit_points = person.max_hit_points
        person.temporary_hit_points = 0
        person.last_long_rest_at = now
        if person.concentration_name or person.concentration_checks.exists():
            end_concentration(person)
            person.combat_revision += 1
    else:
        person.last_short_rest_at = now
    for book in books:
        fields = []
        if kind == "long":
            for level in range(1, 10):
                field = f"current_spell_slots_{level}"
                setattr(book, field, getattr(book, f"max_spell_slots_{level}"))
                fields.append(field)
        book.warlock_current_slots = book.warlock_max_slots
        fields.extend(["warlock_current_slots", "updated_at"])
        book.save(update_fields=fields)
    # Короткий отдых возвращает только короткие ресурсы; длинный — короткие и длинные.
    allowed = ["short", "long"] if kind == "long" else ["short"]
    _, adopted = resource_snapshot(person)
    resources = (
        person.rest_resources.select_for_update()
        .filter(source_key__isnull=True, refresh_on__in=allowed)
        .exclude(pk__in=adopted)
    )
    count = refresh_ability_resources(person, kind)
    for resource in resources:
        if resource.current != resource.maximum:
            resource.current = resource.maximum
            resource.save(update_fields=["current"])
            count += 1
    return f'{"Длинный" if kind=="long" else "Короткий"} отдых применён. Спеллбуков: {len(books)}. Восстановлено ресурсов: {count}.'
