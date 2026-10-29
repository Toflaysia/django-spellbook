"""Подготовка умений и учёт их расхода. Чтение страницы не меняет базу."""

import secrets
from spells.ability_rules import REFRESH, builtin_resources, builtin_features
from spells.models import ClassFeature, CharacterResource


def class_slots(person):
    # Уровни основного и второго класса считаются отдельно: Ци не должно расти от уровня воина.
    slots = [(person.character_class, person.primary_class_level, person.subclass)]
    if person.second_class_id and person.second_class_level:
        slots.append(
            (person.second_class, person.second_class_level, person.second_subclass)
        )
    result = [(cls, level, sub) for cls, level, sub in slots if cls and level > 0]
    return result


def ability_sheet(person):
    # Здесь только подготовка карточек. Открытие страницы не должно тратить ресурсы или создавать записи.
    classes, subclasses, resources = [], [], {}
    # Опциональные умения не включаются автоматически: у каждого персонажа свой выбор.
    selected = set(person.selected_optional_features.values_list("pk", flat=True))
    for cls, level, sub in class_slots(person):
        group = dict(name=cls.name, level=level, features=[])
        sub_active = (
            sub and sub.character_class_id == cls.pk and level >= sub.level_gained
        )
        sub_group = (
            dict(name=sub.name, level=level, features=[]) if sub_active else None
        )
        builtins = builtin_resources(cls.ability_rules, level, person)
        for item in builtins:
            # По правилам мультикласса жрец и паладин делят один запас канала.
            key = (
                "shared:channel_divinity"
                if item["code"] == "channel_divinity"
                else f'class:{cls.pk}:{item["code"]}'
            )
            item = dict(item, key=key, class_level=level, rule=cls.ability_rules)
            previous = resources.get(key)
            if not previous or item["maximum"] > previous["maximum"]:
                resources[key] = item
            group["features"].append(
                dict(
                    name=item["name"],
                    description="",
                    level=item["level"],
                    note=item["note"],
                    resource_key=key,
                )
            )
        group["features"].extend(builtin_features(cls.ability_rules, level, person))
        features = cls.features.select_related("subclass").order_by(
            "level", "name", "pk"
        )
        for feature in features:
            levels = [n for n in feature.acquisition_levels if n <= level]
            if not levels or (
                feature.subclass_id
                and (not sub_active or feature.subclass_id != sub.pk)
            ):
                continue
            target = sub_group if feature.subclass_id else group
            row = dict(
                id=feature.pk,
                name=feature.name,
                level=min(levels),
                levels=levels,
                description=feature.description,
                optional=feature.is_optional,
                selected=feature.pk in selected,
                resource_key="",
            )
            active = not feature.is_optional or row["selected"]
            # Формула справочника использует уровень этого класса, а мастерство — суммарный уровень персонажа.
            if active and feature.resource_formula:
                formula = feature.resource_formula
                base = feature.resource_amount
                if formula == "class_level":
                    base *= level
                elif formula == "proficiency":
                    base *= person.effective_proficiency_bonus
                elif formula != "fixed":
                    base *= max(1, (getattr(person, formula) - 10) // 2)
                key = f"feature:{feature.pk}"
                resources[key] = dict(
                    key=key,
                    name=feature.name,
                    level=min(levels),
                    maximum=base,
                    refresh_on=feature.resource_refresh_on,
                    note="",
                    code="catalog",
                    rule="",
                    class_level=level,
                )
                row["resource_key"] = key
            # Убираем дубликат встроенной карточки, оставляя её счётчик и пояснение.
            duplicate = (
                next(
                    (
                        r
                        for r in group["features"]
                        if not r.get("id")
                        and r["name"].casefold() == feature.name.casefold()
                    ),
                    None,
                )
                if not feature.subclass_id
                else None
            )
            if duplicate and not feature.is_optional:
                if row["resource_key"]:
                    old_key = duplicate["resource_key"]
                    replacement = resources.pop(row["resource_key"])
                    replacement["key"] = old_key or row["resource_key"]
                    if old_key == "shared:channel_divinity":
                        replacement["maximum"] = max(
                            replacement["maximum"], resources[old_key]["maximum"]
                        )
                    resources[replacement["key"]] = replacement
                    row["resource_key"] = replacement["key"]
                else:
                    row["resource_key"] = duplicate["resource_key"]
                row["note"] = duplicate.get("note", "")
                group["features"].remove(duplicate)
            target["features"].append(row)
        group["features"].sort(key=lambda row: (row["level"], row["name"].casefold()))
        classes.append(group)
        if sub_group:
            sub_group["features"].sort(
                key=lambda row: (row["level"], row["name"].casefold())
            )
            subclasses.append(sub_group)
    return dict(classes=classes, subclasses=subclasses, resources=resources)


def resource_snapshot(person, sheet=None):
    # Максимум пересчитывается по актуальным данным, а уже потраченные использования сохраняются.
    sheet = sheet or ability_sheet(person)
    stored = list(person.rest_resources.all())
    keyed = {row.source_key: row for row in stored if row.source_key}
    adopted = set()
    result = []
    for key, spec in sheet["resources"].items():
        row = keyed.get(key)
        if row is None:
            # Старый ручной счётчик с тем же названием сохраняет уже потраченные применения.
            row = next(
                (
                    r
                    for r in stored
                    if not r.source_key
                    and r.pk not in adopted
                    and r.name.casefold() == spec["name"].casefold()
                ),
                None,
            )
            if row:
                adopted.add(row.pk)
        maximum = spec["maximum"]
        # Храним расход, а не только остаток: повышение уровня не должно бесплатно восстанавливать весь запас.
        spent = (
            row.spent_uses
            if row and row.source_key
            else row.maximum - row.current if row else 0
        )
        result.append(
            dict(
                spec,
                id=row.pk if row else None,
                current=max(0, maximum - spent) if maximum is not None else None,
                spent=spent,
                refresh_label=REFRESH[spec["refresh_on"]],
            )
        )
    return result, adopted


def saved_resource(person, snapshot):
    # Запись создаётся только при действии игрока. source_key связывает её с конкретным умением.
    row = (
        CharacterResource.objects.get(pk=snapshot["id"], person=person)
        if snapshot["id"]
        else CharacterResource(person=person)
    )
    row.source_key = snapshot["key"]
    row.name = snapshot["name"][:80]
    row.maximum = max(1, snapshot["maximum"] or 1)
    row.spent_uses = snapshot["spent"]
    row.current = min(row.maximum, snapshot["current"] or 0)
    row.refresh_on = snapshot["refresh_on"]
    return row


def change_ability_resource(person, key, quantity, restore=False):
    # Нельзя доверять максимуму из браузера: заново проверяем, доступно ли умение персонажу.
    rows, _ = resource_snapshot(person)
    snapshot = next((r for r in rows if r["key"] == key), None)
    if not snapshot or snapshot["maximum"] is None:
        raise ValueError("Этот счётчик сейчас недоступен. Обнови страницу.")
    if not 1 <= quantity <= 9999:
        raise ValueError("Укажи количество от 1 до 9999.")
    if restore:
        if quantity > snapshot["spent"]:
            raise ValueError("Нельзя вернуть больше, чем потрачено.")
    elif quantity > snapshot["current"]:
        raise ValueError("Недостаточно оставшихся использований.")
    if (
        not restore
        and snapshot["code"] == "second_wind"
        and person.current_hit_points >= person.max_hit_points
    ):
        raise ValueError("Хиты уже полные. Использование не потрачено.")
    row = saved_resource(person, snapshot)
    row.spent_uses += -quantity if restore else quantity
    row.current = max(0, snapshot["maximum"] - row.spent_uses)
    row.save()
    if not restore and snapshot["code"] == "second_wind":
        # Второе дыхание меняет ресурс и хиты в одной транзакции обработчика.
        roll = secrets.randbelow(10) + 1
        before = person.current_hit_points
        person.current_hit_points = min(
            person.max_hit_points, before + roll + snapshot["class_level"]
        )
        return f'Второе дыхание: 1d10 ({roll}) + {snapshot["class_level"]}. Восстановлено хитов: {person.current_hit_points - before}.'
    return f'{snapshot["name"]}: {"возвращено" if restore else "потрачено"} {quantity}.'


def refresh_ability_resources(person, kind):
    # Правило отдыха принадлежит самому умению; ручные и автоматические ресурсы не смешиваются.
    rows, _ = resource_snapshot(person)
    count = 0
    for snapshot in rows:
        if not snapshot["spent"] or snapshot["maximum"] is None:
            continue
        if (
            snapshot["refresh_on"] == "short"
            or kind == "long"
            and snapshot["refresh_on"] == "long"
        ):
            spent = 0
        elif (
            kind == "short"
            and snapshot["code"] == "sorcery"
            and snapshot["class_level"] >= 20
        ):
            spent = max(0, snapshot["spent"] - 4)
        else:
            continue
        row = saved_resource(person, snapshot)
        row.spent_uses = spent
        row.current = max(0, snapshot["maximum"] - spent)
        row.save()
        count += 1
    return count


def toggle_optional_feature(person, feature_id, enabled):
    # Разрешаем выбирать только те опциональные умения, которые уже доступны по классу и уровню.
    sheet = ability_sheet(person)
    available = [
        r
        for g in sheet["classes"] + sheet["subclasses"]
        for r in g["features"]
        if r.get("optional")
    ]
    if not any(r["id"] == feature_id for r in available):
        raise ValueError("Это опциональное умение сейчас недоступно персонажу.")
    if enabled:
        person.selected_optional_features.add(feature_id)
    else:
        person.selected_optional_features.remove(feature_id)
