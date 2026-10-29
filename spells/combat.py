"""Состояния персонажа и проверки концентрации по D&D 5e 2014."""

import secrets
from django.urls import reverse
from spells.models import ConcentrationCheck
from spells.spell_access import visible_spells
from spells.templatetags.description_tags import description_text


def constitution_save(person):
    # Берём тот же спасбросок Телосложения, который показан в листе, включая владение и бонусы.
    return next(
        row for row in person.computed_checks["saves"] if row["key"] == "constitution"
    )


def combat_state(person, user):
    spell = (
        visible_spells(user).filter(pk=person.concentration_spell_id).first()
        if person.concentration_spell_id
        else None
    )
    save = constitution_save(person)
    return {
        "revision": person.combat_revision,
        "concentration": {
            "name": person.concentration_name,
            "url": reverse("spell_detail_page", args=[spell.pk]) if spell else None,
        },
        "save_bonus": save["total"],
        "save_formula": save["formula"],
        "conditions": [
            {
                "id": row.pk,
                "condition_id": row.condition_id,
                "name": row.condition.name,
                "note": row.note,
                "incapacitates": row.incapacitates,
                "description": description_text(row.condition.description),
                "url": reverse(
                    "catalog_detail_page",
                    kwargs={"slug": "conditions", "pk": row.condition_id},
                ),
            }
            for row in person.active_conditions.select_related("condition").filter(
                condition__category="COND"
            )
        ],
        "checks": [
            {"id": row.pk, "damage": row.damage, "dc": row.dc}
            for row in person.concentration_checks.all()
        ],
    }


def end_concentration(person):
    # Одновременно убираем название, ссылку и отложенные проверки прежней концентрации.
    person.concentration_spell = None
    person.concentration_name = ""
    person.concentration_checks.all().delete()


def concentration_damage(person, damage):
    # Проверка нужна только при положительном уроне и действующей концентрации.
    if not person.concentration_name or damage <= 0:
        return ""
    person.combat_revision += 1
    if person.current_hit_points == 0:
        end_concentration(person)
        return " Концентрация прекращена: хиты опустились до 0."
    # Сложность концентрации равна половине полученного урона, округлённой вниз, но не меньше 10.
    dc = max(10, damage // 2)
    ConcentrationCheck.objects.create(person=person, damage=damage, dc=dc)
    return f" Нужен спасбросок Телосложения для концентрации: СЛ {dc}."


def roll_concentration(person, check, mode):
    # При преимуществе берём больший из двух d20, при помехе — меньший.
    if mode not in ("normal", "advantage", "disadvantage"):
        raise ValueError("Выбери обычный бросок, преимущество или помеху.")
    rolls = [secrets.randbelow(20) + 1 for _ in range(1 if mode == "normal" else 2)]
    chosen = min(rolls) if mode == "disadvantage" else max(rolls)
    bonus = constitution_save(person)["total"]
    total = chosen + bonus
    success = total >= check.dc
    message = f'Концентрация: {", ".join(map(str, rolls))}; выбрано {chosen} {bonus:+d} = {total}, СЛ {check.dc}. '
    if success:
        check.delete()
        message += "Концентрация сохранена."
    else:
        end_concentration(person)
        message += "Концентрация прекращена."
    return message
