from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.timezone import now

from spells.models.enums import Alignment, Characters, Dice, MagicType
from spells.models.users import Player


class CharacterClass(models.Model):
    """Класс персонажа"""

    id = models.AutoField(primary_key=True, verbose_name="id")
    name = models.CharField(max_length=50, unique=True, verbose_name="Название")
    description = models.TextField(verbose_name="Описание")
    magic_type = models.CharField(
        max_length=2,
        choices=MagicType.choices,
        default=MagicType.NON_CASTER,
        verbose_name="Магический тип",
    )
    hit_die = models.IntegerField(
        max_length=10,
        choices=Dice.choices,
        default=Dice.d8,
        help_text="Кость хитов",
        verbose_name="Кости хитов",
    )
    spellcasting_ability = models.CharField(
        max_length=3,
        choices=Characters.choices,
        default=Characters.WISDOM,
        help_text="Заклинательная характеристика",
        verbose_name="Заклинательная характеристика",
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Класс"
        verbose_name_plural = "Классы"


class Subclass(models.Model):
    """Подкласс/архетип персонажа"""

    id = models.AutoField(primary_key=True, verbose_name="id")
    name = models.CharField(max_length=100, verbose_name="Название")
    description = models.TextField(verbose_name="Описание")
    character_class = models.ForeignKey(
        CharacterClass,
        on_delete=models.CASCADE,
        related_name="subclasses",
        verbose_name="Класс",
    )
    features_description = models.TextField(
        blank=True, verbose_name="Описание характеристик"
    )
    level_gained = models.IntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(20)],
        help_text="На каком уровне класса получается этот подкласс",
        verbose_name="Уровень получения",
    )

    def __str__(self):
        return f"{self.name} ({self.character_class.name})"

    class Meta:
        verbose_name = "Подкласс"
        verbose_name_plural = "Подклассы"
        unique_together = ["name", "character_class"]


class Person(models.Model):
    """Персонаж игрока"""

    id = models.AutoField(primary_key=True, verbose_name="id")
    name = models.CharField(max_length=100, verbose_name="Название")
    player = models.ForeignKey(
        Player,
        on_delete=models.SET_NULL,
        null=True,
        related_name="characters",
        verbose_name="Игрок",
    )

    # Основные характеристики
    character_class = models.ForeignKey(
        CharacterClass,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="characters",
        verbose_name="Класс",
    )
    subclass = models.ForeignKey(
        Subclass,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="characters",
        verbose_name="Подкласс",
    )
    primary_class_level = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(20)],
        verbose_name="Уровень основного класса",
    )

    # Раса
    race = models.CharField(max_length=100, blank=True, verbose_name="Раса")
    subrace = models.CharField(max_length=100, blank=True, verbose_name="Подраса")
    alignment = models.CharField(
        max_length=2,
        choices=Alignment.choices,
        blank=True,
        verbose_name="Мировоззрение",
    )
    background = models.CharField(
        max_length=100, blank=True, verbose_name="Предыстория"
    )

    # Характеристики (ability scores)
    strength = models.IntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(30)],
        verbose_name="Сила",
    )
    dexterity = models.IntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(30)],
        verbose_name="Ловкость",
    )
    constitution = models.IntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(30)],
        verbose_name="Телосложение",
    )
    intelligence = models.IntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(30)],
        verbose_name="Интеллект",
    )
    wisdom = models.IntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(30)],
        verbose_name="Мудрость",
    )
    charisma = models.IntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(30)],
        verbose_name="Харизма",
    )

    max_hit_points = models.IntegerField(
        default=10, verbose_name="Макисмальное кол-во хитов"
    )
    current_hit_points = models.IntegerField(
        default=10, verbose_name="Текущее кол-во хитов"
    )
    temporary_hit_points = models.IntegerField(
        default=0, verbose_name="Временное кол-во хитов"
    )

    armor_class = models.IntegerField(default=10, verbose_name="Класс доспеха (КД)")
    initiative_bonus = models.IntegerField(
        default=0, verbose_name="Модификатор инициативы"
    )
    speed = models.IntegerField(
        default=30, help_text="Скорость в футах", verbose_name="Скорость"
    )
    proficiency_bonus = models.IntegerField(
        default=2,
        validators=[MinValueValidator(2), MaxValueValidator(6)],
        verbose_name="Бонус мастерства",
    )

    spellcasting_ability = models.CharField(
        max_length=3,
        choices=Characters.choices,
        blank=True,
        help_text="Заклинательная характеристика",
        verbose_name="Характеристика",
    )

    # Мультикласс
    is_multiclass = models.BooleanField(default=False, verbose_name="Мультикласс")
    second_class = models.ForeignKey(
        CharacterClass,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="secondary_characters",
        verbose_name="Дополнительный класс",
    )
    second_subclass = models.ForeignKey(
        Subclass,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="secondary_characters",
        verbose_name="Дополнительный подкласс",
    )
    second_class_level = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(19)],
        verbose_name="Второй уровень класса",
    )

    # Колдун
    warlock_level = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(20)],
        help_text="Уровень колдуна (если мультикласс)",
        verbose_name="Уровень колдуна",
    )

    # Метаданные
    is_active = models.BooleanField(default=True, verbose_name="Активный")
    is_favorite = models.BooleanField(default=False, verbose_name="Любимый")
    is_public = models.BooleanField(
        default=False,
        help_text="Могут ли другие игроки видеть",
        verbose_name="Публичный",
    )
    created_at = models.DateTimeField(default=now, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        class_str = f" {self.character_class.name}" if self.character_class else ""
        level_str = f" ур.{self.primary_class_level}"
        if self.second_class:
            level_str += f"/{self.second_class_level} {self.second_class.name}"
        return f"{self.name}{class_str}{level_str}"

    @property
    def level(self) -> int:
        return self.primary_class_level + self.second_class_level + self.warlock_level

    @property
    def spellcasting_modifier(self):
        """Модификатор заклинательной характеристики"""
        if not self.spellcasting_ability:
            return 0

        ability_score = getattr(self, self.spellcasting_ability.lower(), 10)
        return (ability_score - 10) // 2

    @property
    def spell_save_dc(self):
        """Сложность спасбросков от заклинаний"""
        if not self.spellcasting_ability:
            return 0
        return 8 + self.proficiency_bonus + self.spellcasting_modifier

    @property
    def spell_attack_bonus(self):
        """Бонус атаки заклинаниями"""
        if not self.spellcasting_ability:
            return 0
        return self.proficiency_bonus + self.spellcasting_modifier

    @property
    def max_spell_slots(self):
        """Рассчитать максимальное количество ячеек заклинаний по уровням"""
        if not self.character_class:
            return {}

        # Базовая логика расчета ячеек (упрощенная)
        slots = {}

        # Учитываем основной класс
        if self.character_class.magic_type == MagicType.FULL_CASTER:
            slots = self._calculate_full_caster_slots(self.level)
        elif self.character_class.magic_type == MagicType.HALF_CASTER:
            slots = self._calculate_half_caster_slots(self.level)

        # Добавляем ячейки второго класса
        if self.second_class:
            if self.second_class.magic_type == MagicType.FULL_CASTER:
                second_slots = self._calculate_full_caster_slots(
                    self.second_class_level
                )
            elif self.second_class.magic_type == MagicType.HALF_CASTER:
                second_slots = self._calculate_half_caster_slots(
                    self.second_class_level
                )
            else:
                second_slots = {}

            # Объединяем ячейки (упрощенная логика)
            for level, count in second_slots.items():
                slots[level] = slots.get(level, 0) + count

        # Ячейки колдуна (рассчитываются отдельно)
        if self.warlock_level > 0:
            warlock_slot_level = min(5, (self.warlock_level + 1) // 2)
            warlock_count = 1
            if self.warlock_level >= 2:
                warlock_count = 2
            if self.warlock_level >= 11:
                warlock_count = 3
            if self.warlock_level >= 17:
                warlock_count = 4

            slots[f"warlock_{warlock_slot_level}"] = warlock_count

        return slots

    def _calculate_full_caster_slots(self, level):
        """Таблица ячеек для полных заклинателей"""
        # Упрощенная таблица (реальная таблица более сложная)
        slots_table = {
            1: {1: 2},
            2: {1: 3},
            3: {1: 4, 2: 2},
            4: {1: 4, 2: 3},
            5: {1: 4, 2: 3, 3: 2},
            6: {1: 4, 2: 3, 3: 3},
            7: {1: 4, 2: 3, 3: 3, 4: 1},
            8: {1: 4, 2: 3, 3: 3, 4: 2},
            9: {1: 4, 2: 3, 3: 3, 4: 3, 5: 1},
            10: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2},
            11: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1},
            12: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1},
            13: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1},
            14: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1},
            15: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1},
            16: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1},
            17: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1, 9: 1},
            18: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 1, 7: 1, 8: 1, 9: 1},
            19: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 2, 7: 1, 8: 1, 9: 1},
            20: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 2, 7: 2, 8: 1, 9: 1},
        }
        return slots_table.get(level, {})

    def _calculate_half_caster_slots(self, level):
        """Таблица ячеек для полузаклинателей"""
        half_caster_table = {
            2: {1: 2},
            3: {1: 3},
            4: {1: 3},
            5: {1: 4, 2: 2},
            6: {1: 4, 2: 2},
            7: {1: 4, 2: 3},
            8: {1: 4, 2: 3},
            9: {1: 4, 2: 3, 3: 2},
            10: {1: 4, 2: 3, 3: 2},
            11: {1: 4, 2: 3, 3: 3},
            12: {1: 4, 2: 3, 3: 3},
            13: {1: 4, 2: 3, 3: 3, 4: 1},
            14: {1: 4, 2: 3, 3: 3, 4: 1},
            15: {1: 4, 2: 3, 3: 3, 4: 2},
            16: {1: 4, 2: 3, 3: 3, 4: 2},
            17: {1: 4, 2: 3, 3: 3, 4: 3, 5: 1},
            18: {1: 4, 2: 3, 3: 3, 4: 3, 5: 1},
            19: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2},
            20: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2},
        }
        return half_caster_table.get(level, {})

    class Meta:
        verbose_name = "Персонаж"
        verbose_name_plural = "Персонажи"
        ordering = ["-is_favorite", "-updated_at"]
