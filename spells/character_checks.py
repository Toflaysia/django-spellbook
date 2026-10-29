"""Расчёт навыков, спасбросков, инициативы, пассивных значений и скорости."""

from django.core.exceptions import ValidationError

ABILITIES = {
    "strength": "Сила",
    "dexterity": "Ловкость",
    "constitution": "Телосложение",
    "intelligence": "Интеллект",
    "wisdom": "Мудрость",
    "charisma": "Харизма",
}
SKILLS = (
    ("acrobatics", "Акробатика", "dexterity"),
    ("investigation", "Анализ", "intelligence"),
    ("athletics", "Атлетика", "strength"),
    ("perception", "Внимательность", "wisdom"),
    ("survival", "Выживание", "wisdom"),
    ("performance", "Выступление", "charisma"),
    ("intimidation", "Запугивание", "charisma"),
    ("history", "История", "intelligence"),
    ("sleight_of_hand", "Ловкость рук", "dexterity"),
    ("arcana", "Магия", "intelligence"),
    ("medicine", "Медицина", "wisdom"),
    ("deception", "Обман", "charisma"),
    ("nature", "Природа", "intelligence"),
    ("insight", "Проницательность", "wisdom"),
    ("religion", "Религия", "intelligence"),
    ("stealth", "Скрытность", "dexterity"),
    ("persuasion", "Убеждение", "charisma"),
    ("animal_handling", "Уход за животными", "wisdom"),
)
TRAINING = (
    ("none", "Без владения"),
    ("half", "Половина мастерства"),
    ("proficient", "Владение"),
    ("expertise", "Компетентность"),
)
SPEEDS = {
    "walk": "Ходьба",
    "fly": "Полёт",
    "swim": "Плавание",
    "climb": "Лазание",
    "burrow": "Копание",
}
FACTORS = (
    ("normal", "Обычная"),
    ("half", "Половина"),
    ("double", "Удвоенная"),
    ("stopped", "Обездвижен"),
)
PASSIVES = ("perception", "investigation", "insight")


def level_proficiency(level):
    # Бонус мастерства растёт раз в четыре уровня: +2, +3, +4, +5, +6.
    return 2 + (max(1, min(20, level)) - 1) // 4


def validate_check_settings(value):
    # Проверяем структуру JSON на сервере: в нём допустимы только известные навыки и настройки.
    def fail():
        raise ValidationError("Неверные настройки расчёта персонажа.")

    def integer(n, low=-1000, high=1000):
        if type(n) is not int or not low <= n <= high:
            fail()

    if not isinstance(value, dict):
        fail()
    if set(value) - {
        "skills",
        "saves",
        "passives",
        "speeds",
        "proficiency_override",
        "initiative_half",
    }:
        fail()
    if value.get("proficiency_override") is not None:
        integer(value["proficiency_override"], 0, 20)
    if "initiative_half" in value and type(value["initiative_half"]) is not bool:
        fail()
    for group, allowed in [
        ("skills", {x[0] for x in SKILLS}),
        ("saves", set(ABILITIES)),
        ("passives", set(PASSIVES)),
        ("speeds", set(SPEEDS)),
    ]:
        items = value.get(group, {})
        if not isinstance(items, dict) or set(items) - allowed:
            fail()
        for name, item in items.items():
            if not isinstance(item, dict):
                fail()
            keys = (
                {"training", "bonus"}
                if group in ("skills", "saves")
                else (
                    {"bonus", "advantage", "disadvantage"}
                    if group == "passives"
                    else {"base", "bonus", "factor"}
                )
            )
            if set(item) - keys:
                fail()
            if "bonus" in item:
                integer(item["bonus"])
            if group in ("skills", "saves"):
                training = item.get("training", "none")
                if not isinstance(training, str) or training not in dict(
                    TRAINING if group == "skills" else (TRAINING[0], TRAINING[2])
                ):
                    fail()
            if group == "passives":
                for k in ("advantage", "disadvantage"):
                    if k in item and type(item[k]) is not bool:
                        fail()
            if group == "speeds":
                if "base" in item:
                    integer(item["base"], 0, 10000)
                factor = item.get("factor", "normal")
                if not isinstance(factor, str) or factor not in dict(FACTORS):
                    fail()


def proficiency(person):
    # Ручной бонус имеет приоритет только когда он задан; значение 0 тоже считается заданным.
    override = (person.check_settings or {}).get("proficiency_override")
    return level_proficiency(person.level) if override is None else override


def training_bonus(training, pb):
    # Половина мастерства округляется вниз, компетентность даёт двойной бонус.
    return {"none": 0, "half": pb // 2, "proficient": pb, "expertise": pb * 2}[training]


def calculated_checks(person):
    # Один расчёт используется и на странице, и в API, чтобы итоговые значения не расходились.
    config = person.check_settings or {}
    pb = proficiency(person)
    # Модификатор характеристики = (значение − 10) // 2. Для нечётных значений округляем вниз.
    mods = {name: (getattr(person, name) - 10) // 2 for name in ABILITIES}
    result = {
        "proficiency": pb,
        "skills": [],
        "saves": [],
        "passives": [],
        "speeds": [],
    }
    for group, items in [
        ("skills", SKILLS),
        ("saves", [(k, v, k) for k, v in ABILITIES.items()]),
    ]:
        for key, label, ability in items:
            setting = config.get(group, {}).get(key, {})
            training = setting.get("training", "none")
            extra = setting.get("bonus", 0)
            trained = training_bonus(training, pb)
            # Итог навыка: модификатор характеристики + владение + дополнительный бонус.
            total = mods[ability] + trained + extra
            result[group].append(
                {
                    "key": key,
                    "label": label,
                    "ability": ABILITIES[ability],
                    "training": dict(TRAINING)[training],
                    "training_value": training,
                    "bonus": extra,
                    "total": total,
                    "formula": f"{mods[ability]:+d} ({ABILITIES[ability]}) {trained:+d} (мастерство) {extra:+d} (бонус)",
                    "dice": f"1d20{total:+d}",
                }
            )
    by_key = {skill["key"]: skill for skill in result["skills"]}
    for key in PASSIVES:
        skill = by_key[key]
        setting = config.get("passives", {}).get(skill["key"], {})
        # В пассивной проверке преимущество даёт +5, помеха −5; вместе они взаимно сокращаются.
        circumstance = 5 * (
            int(setting.get("advantage", False))
            - int(setting.get("disadvantage", False))
        )
        extra = setting.get("bonus", 0)
        result["passives"].append(
            {
                "key": skill["key"],
                "label": skill["label"],
                "total": 10 + skill["total"] + extra + circumstance,
                "formula": f'10 {skill["total"]:+d} (навык) {extra:+d} (бонус) {circumstance:+d} (преимущество/помеха)',
            }
        )
    half = pb // 2 if config.get("initiative_half", False) else 0
    initiative = mods["dexterity"] + person.initiative_bonus + half
    result["initiative"] = {
        "total": initiative,
        "dice": f"1d20{initiative:+d}",
        "formula": f'{mods["dexterity"]:+d} (Ловкость) {person.initiative_bonus:+d} (бонус) {half:+d} (половина мастерства)',
    }
    for key, label in SPEEDS.items():
        setting = config.get("speeds", {}).get(key, {})
        # Обычная ходьба берётся из поля персонажа, остальные виды движения — из отдельных настроек.
        base = person.speed if key == "walk" else setting.get("base", 0)
        extra = setting.get("bonus", 0)
        factor = setting.get("factor", "normal")
        amount = max(0, base + extra)
        total = {
            "normal": amount,
            "half": amount // 2,
            "double": amount * 2,
            "stopped": 0,
        }[factor]
        result["speeds"].append(
            {
                "key": key,
                "label": label,
                "total": total,
                "formula": f"({base} {extra:+d}) · {dict(FACTORS)[factor]}",
            }
        )
    return result
