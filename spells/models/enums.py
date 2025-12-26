from django.db import models


class SpellLevels(models.IntegerChoices):
    CONTRIP = 0, "lv0"
    LV1 = 1, "lv1"
    LV2 = 2, "lv2"
    LV3 = 3, "lv3"
    LV4 = 4, "lv4"
    LV5 = 5, "lv5"
    LV6 = 6, "lv6"
    LV7 = 7, "lv7"
    LV8 = 8, "lv8"
    LV9 = 9, "lv9"


class MagicType(models.TextChoices):
    FULL_CASTER = "FC", "Полный заклинатель"
    HALF_CASTER = "HC", "Полузаклинатель"
    THIRD_CASTER = "TC", "Треть-заклинатель"
    NON_CASTER = "NC", "Немагический класс"


class Dice(models.IntegerChoices):
    d2 = 2, "d2"
    d4 = 4, "d4"
    d6 = 6, "d6"
    d8 = 8, "d8"
    d10 = 10, "d10"
    d12 = 12, "d12"
    d20 = 20, "d20"
    d100 = 100, "d100"


class Characters(models.TextChoices):
    STRENGTH = "STR", "Сила"
    DEXTERITY = "DEX", "Ловкость"
    CONSTITUTION = "CON", "Телосложение"
    INTELLIGENCE = "INT", "Интеллект"
    WISDOM = "WIS", "Мудрость"
    CHARISMA = "CHA", "Харизма"


class EffectCategory(models.TextChoices):
    CONDITION = "COND", "Состояние"  # добавление существу любого состояния
    CONTROL = "CTRL", "Контроль"  # эффекты контроля
    DEBUFF = "DEBF", "Ослабление"  # эффекты ослабления
    BUFF = "BUFF", "Усиление"  # эффекты усиления
    UTILITY = (
        "UTIL",
        "Полезный эффект",
    )  # любой эффект не предназначенный непосредственно для боя
    MOVEMENT = "MOVE", "Перемещение"  # перемещение существа
    TELEPORT = "TP", "Телепортация"  # телепортация себя или другого существа
    HEALING = "HEAL", "Исцеление"  # восстановление хитов
    DEMAGE = "DMG", "Урон"  # урон
    PROTECTION = "PROT", "Защита"  # (каменная кожа, щит)
    TRANSMUTATION = (
        "TMUT",
        "Трансмутация",
    )  # заклинание, изменяющее характеристики существа (полиморф)


class Alignment(models.TextChoices):
    LAWFUL_GOOD = "LG", "Законно-добрый"
    NEUTRAL_GOOD = "NG", "Нейтрально-добрый"
    CHAOTIC_GOOD = "CG", "Хаотично-добрый"
    LAWFUL_NEUTRAL = "LN", "Законно-нейтральный"
    TRUE_NEUTRAL = "TN", "Истинно-нейтральный"
    CHAOTIC_NEUTRAL = "CN", "Хаотично-нейтральный"
    LAWFUL_EVIL = "LE", "Законно-злой"
    NEUTRAL_EVIL = "NE", "Нейтрально-злой"
    CHAOTIC_EVIL = "CE", "Хаотично-злой"
