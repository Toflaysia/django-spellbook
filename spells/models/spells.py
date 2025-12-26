from django.db import models
from django.utils.timezone import now

from spells.models.characters import CharacterClass, Subclass
from spells.models.enums import Characters, EffectCategory, SpellLevels
from spells.models.users import Player


class MaterialComponent(models.Model):
    "Материальный компонент"

    id = models.AutoField(primary_key=True, verbose_name="id")
    name = models.TextField(max_length=49, verbose_name="Название")
    description = models.TextField(blank=True, null=True, verbose_name="Описание компонента")
    cost = models.DecimalField(
        default=0, max_digits=7, decimal_places=2, help_text="Стоимость в ЗМ", null=True, verbose_name="Стоимость"
    )

    is_consumable = models.BooleanField(
        default=False, help_text="Расходуется ли компонент при касте заклинания", verbose_name="Потребляемый"
    )
    is_focus = models.BooleanField(
        default=False, help_text="Является ли фокусировкой для заклинания", verbose_name="Фокус"
    )

    def truncate_description(self, description: str = "", max_length: int = 20) -> str:
        if not description:
            description = self.description

        if len(description) > max_length:
            return description[:max_length] + "..."
        return description

    def __str__(self):
        cost_str = f"| ({self.cost} зм) " if self.cost else ""
        description_str = self.truncate_description()
        return f"{self.name} {cost_str}({description_str})"

    class Meta:
        verbose_name = "Материальный компонент"
        verbose_name_plural = "Материальные компоненты"


class SpellTime(models.Model):
    "Время накладывания заклинания"

    id = models.AutoField(primary_key=True, verbose_name="id")
    time = models.CharField(max_length=49, verbose_name="Время")
    description = models.TextField(verbose_name="Описание", blank=True)

    def __str__(self):
        return self.time
    
    class Meta:
        verbose_name = "Время накладывания заклинания"
        verbose_name_plural = "Время накладывания заклинаний"


class MagicSchool(models.Model):
    "Школа заклинания"

    id = models.AutoField(primary_key=True, verbose_name="id")
    name = models.CharField(max_length=99, verbose_name="Название")
    description = models.TextField(verbose_name="Описание")
    color = models.CharField(max_length=7, default="#3498db", verbose_name="Цвет школы магии")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Школа магии"
        verbose_name_plural = "Школы магии"


class DamageType(models.Model):
    "Тип наносимого урона"

    id = models.AutoField(primary_key=True, verbose_name="id")
    name = models.CharField(max_length=30, verbose_name="Название")
    description = models.TextField(blank=True, verbose_name="Описание")
    is_magic = models.BooleanField(default=True, verbose_name="Магический урон")

    def __str__(self):
        magic_str = " (маг.)" if self.is_magic else " (не маг.)"
        return f"{self.name} - {magic_str}"

    class Meta:
        verbose_name = "Тип урона"
        verbose_name_plural = "Типы урона"


class Effect(models.Model):
    """Эффекты от заклинания"""

    id = models.AutoField(primary_key=True, verbose_name="id")
    name = models.CharField(max_length=49, verbose_name="Название")
    description = models.TextField(verbose_name="Описание")
    category = models.CharField(
        max_length=4, choices=EffectCategory.choices, blank=True, verbose_name="Категория"
    )
    duration = models.CharField(
        max_length=100, blank=True, help_text="Время действия эффекта", verbose_name="Продолжительность"
    )
    damage_type = models.ForeignKey(
        DamageType,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="effects",
        help_text="Тип урона при наличии",
        verbose_name="Тип урона"
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Эффект заклинания"
        verbose_name_plural = "Эффекты заклинаний"


class Spell(models.Model):
    """Заклинание"""

    class AttackType(models.TextChoices):
        ATTACK_ROLL = "ATTACK", "Бросок атаки"
        SAVE_THROW = "SAVE", "Спасбросок"
        AUTOMATIC = "AUTO", "Автоматическое"
        MIXED = "MIXED", "Комбинированное"
        NONE = "NONE", "Нет броска"

    id = models.AutoField(primary_key=True, verbose_name="id")
    name = models.CharField(max_length=150, unique=True, verbose_name="Название")
    level = models.IntegerField(
        choices=SpellLevels.choices, default=SpellLevels.CONTRIP, verbose_name="Уровень"
    )
    time = models.ForeignKey(SpellTime, on_delete=models.SET_NULL, null=True, verbose_name="Время")
    school = models.ForeignKey(MagicSchool, on_delete=models.SET_NULL, null=True, verbose_name="Школа магии")

    # Компоненты
    verbal_component = models.BooleanField(
        default=False, help_text="Вербальный компонент", verbose_name="Вербальный компонент"
    )
    somatic_component = models.BooleanField(
        default=False, help_text="Соматический компонент", verbose_name="Соматический компонент"
    )
    material_components = models.ManyToManyField(MaterialComponent, verbose_name="Материальный компонент")

    # Дистанция
    range = models.CharField(
        max_length=100, blank=True, help_text="Дистанция (по умолчанию в футах)", verbose_name="Дистанция"
    )

    # Длительность
    duration = models.CharField(max_length=100, verbose_name="Длительность")
    concentration = models.BooleanField(default=False, verbose_name="Концентрация")
    ritual = models.BooleanField(default=False, verbose_name="Ритуал")

    # Описание
    description = models.TextField(verbose_name="Описание")
    higher_level = models.TextField(blank=True, help_text="На более высоком уровне", verbose_name="На более высоком уровне")

    # Механика
    attack_type = models.CharField(
        max_length=10, choices=AttackType.choices, default=AttackType.NONE, verbose_name="Механика"
    )
    saving_throw_ability = models.CharField(
        max_length=3,
        choices=Characters.choices,
        blank=True,
        help_text="Характеристика для спасброска (если требуется)", 
        verbose_name="Характеристика для спасброска"
    )

    # Эффекты
    effects = models.ManyToManyField(Effect, related_name="spells", blank=True, verbose_name="Эффект заклинания")

    # Кто может использовать заклинание
    aviable_classes = models.ManyToManyField(
        CharacterClass, related_name="aviable_spells", blank=True, verbose_name="Класс"
    )
    aviable_subclasses = models.ManyToManyField(
        Subclass, related_name="aviable_spells", blank=True, verbose_name="Подкласс"
    )

    # Источник
    source_book = models.CharField(max_length=100, blank=True, verbose_name="Источник")
    page_number = models.IntegerField(null=True, blank=True, verbose_name="Страница источника")

    # Метаданные
    is_official = models.BooleanField(default=True, verbose_name="Официальное")
    created_by = models.ForeignKey(
        Player,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_spells",
        help_text="Пользователь, добавивший заклинание", 
        verbose_name="Пользователь, добавивший заклинание"
    )
    created_at = models.DateTimeField(default=now, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        level_str = "Заговор" if self.level == 0 else f"{self.level} уровень"
        return f"{self.name} ({level_str}, {self.school.name})"

    @property
    def is_cantrip(self):
        return self.level == 0

    class Meta:
        verbose_name = "Заклинание"
        verbose_name_plural = "Заклинания"
        ordering = ["level", "name"]
        indexes = [
            models.Index(fields=["level"]),
            models.Index(fields=["school"]),
            models.Index(fields=["attack_type"]),
            models.Index(fields=["concentration"]),
            models.Index(fields=["ritual"]),
        ]
