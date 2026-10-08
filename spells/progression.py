"""Class-specific progression layouts; only cell text is stored."""
import re

from django.core.exceptions import ValidationError


TABLE_TYPES = [
    ("basic", "Базовая таблица"),
    ("barbarian", "Варвар"),
    ("bard", "Бард"),
    ("fighter", "Воин"),
    ("wizard", "Волшебник"),
    ("druid", "Друид"),
    ("cleric", "Жрец"),
    ("artificer", "Изобретатель"),
    ("warlock", "Колдун"),
    ("monk", "Монах"),
    ("paladin", "Паладин"),
    ("rogue", "Плут"),
    ("ranger", "Следопыт"),
    ("sorcerer", "Чародей"),
    ("custom", "Своя таблица"),
]


def custom_column(key, title):
    return {"key": key, "kind": "text", "title": title, "values": [""] * 20}


def base_columns():
    return [
        {"key": "level", "kind": "level", "title": "Уровень"},
        {"key": "proficiency", "kind": "proficiency", "title": "Бонус мастерства"},
        {"key": "features", "kind": "features", "title": "Умения"},
    ]


def preset_columns(kind):
    columns = base_columns()
    labels = []
    if kind == "barbarian":
        labels = [("rages", "Ярость"), ("rage_damage", "Урон ярости")]
    elif kind == "monk":
        labels = [("martial_arts", "Боевые искусства"), ("ki", "Очки ци"),
                  ("unarmored_speed", "Скорость без доспехов")]
    elif kind == "rogue":
        labels = [("sneak_attack", "Скрытая атака")]
    elif kind == "warlock":
        labels = [("cantrips", "Известные заговоры"), ("spells_known", "Известные заклинания"),
                  ("pact_slots", "Ячейки заклинаний"), ("pact_level", "Уровень ячеек"),
                  ("invocations", "Известные воззвания")]
    elif kind in {"bard", "wizard", "druid", "cleric", "sorcerer", "artificer", "paladin", "ranger"}:
        if kind == "sorcerer":
            labels.append(("sorcery_points", "Единицы чародейства"))
        if kind == "artificer":
            labels.extend([("infusions_known", "Известные инфузии"),
                           ("infused_items", "Инфузированные предметы")])
        if kind not in {"paladin", "ranger"}:
            labels.append(("cantrips", "Известные заговоры"))
        if kind in {"bard", "sorcerer", "ranger"}:
            labels.append(("spells_known", "Известные заклинания"))
        last_slot = 5 if kind in {"paladin", "ranger", "artificer"} else 9
        labels.extend((f"slots_{level}", f"Ячейки {level}-го уровня") for level in range(1, last_slot + 1))
    extras = [custom_column(key, title) for key, title in labels]
    if kind in {"monk", "rogue"}:
        return columns[:2] + extras + columns[2:]
    if kind == "sorcerer":
        return columns[:2] + extras[:1] + columns[2:] + extras[1:]
    return columns + extras


def validate_progression_columns(columns, *, subclass=False):
    if not isinstance(columns, list) or len(columns) > 24:
        raise ValidationError("Неверный формат столбцов таблицы.")
    if not columns:
        return
    keys = set()
    kinds = []
    for column in columns:
        if not isinstance(column, dict):
            raise ValidationError("Неверный формат столбца.")
        key, kind, title = (column.get(name) for name in ("key", "kind", "title"))
        if not isinstance(key, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", key) or key in keys:
            raise ValidationError("У каждого столбца должен быть уникальный идентификатор.")
        keys.add(key)
        if not isinstance(title, str) or not title.strip() or len(title) > 80:
            raise ValidationError("Укажи название каждого столбца (до 80 символов).")
        if kind == "text":
            values = column.get("values")
            if not isinstance(values, list) or len(values) != 20 or any(
                not isinstance(value, str) or len(value) > 200 for value in values
            ):
                raise ValidationError("Для столбца нужно 20 текстовых значений, по одному на уровень (до 200 символов).")
        elif kind in {"level", "proficiency", "features"} and not subclass:
            if key != kind:
                raise ValidationError("Неверный идентификатор системного столбца.")
            kinds.append(kind)
        else:
            raise ValidationError("Неизвестный вид столбца.")
    if not subclass and sorted(kinds) != ["features", "level", "proficiency"]:
        raise ValidationError("В таблице должны быть уровень, бонус мастерства и умения — по одному столбцу.")


def validate_class_columns(columns):
    validate_progression_columns(columns)


def validate_subclass_columns(columns):
    validate_progression_columns(columns, subclass=True)


def progression_headers(character_class, subclass=None):
    columns = [dict(column, source="class") for column in (
        character_class.progression_columns or preset_columns(character_class.progression_table_type)
    )]
    if subclass:
        columns.extend(dict(column, source="subclass") for column in subclass.progression_columns)
    return columns


def progression_cells(columns, level, features, subclass=None):
    cells = []
    for column in columns:
        kind = column["kind"]
        if kind == "level":
            value = str(level)
        elif kind == "proficiency":
            value = f"+{2 + (level - 1) // 4}"
        elif kind == "features":
            value = ""
        elif column["source"] == "subclass" and level < subclass.level_gained:
            value = "—"
        else:
            value = column["values"][level - 1] or "—"
        cells.append({"kind": kind, "value": value, "features": features,
                      "source": column["source"]})
    return cells
