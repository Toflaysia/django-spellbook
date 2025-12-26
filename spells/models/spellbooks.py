from django.db import models
from django.utils.timezone import now

from spells.models.characters import Person

from .spells import Spell


class Spellbook(models.Model):
    """
    Спеллбук - один из наборов заклинаний персонажа
    (у одного персонажа может быть несколько спеллбуков,
    у одного игрока - несколько персонажей)
    """

    id = models.AutoField(primary_key=True, verbose_name="id")
    name = models.CharField(max_length=100, verbose_name="Название")
    description = models.TextField(blank=True, verbose_name="Описание")
    spells = models.ManyToManyField(Spell, related_name="spellbooks", blank=True, verbose_name="Заклинания")
    owner = models.ForeignKey(
        Person, on_delete=models.CASCADE, related_name="spellbooks", verbose_name="Персонаж"
    )

    # Статус
    is_active = models.BooleanField(default=True, help_text="Активен ли этот спеллбук", verbose_name="Активен")
    is_shared = models.BooleanField(
        default=False, help_text="Доступен ли для других игроков", verbose_name="Публичный"
    )

    # Ячейки заклинаний в этом спеллбуке
    max_spell_slots_1 = models.IntegerField(default=0, verbose_name="Максимальное кол-во ячеек 1го уровня")
    max_spell_slots_2 = models.IntegerField(default=0, verbose_name="Максимальное кол-во ячеек 2го уровня")
    max_spell_slots_3 = models.IntegerField(default=0, verbose_name="Максимальное кол-во ячеек 3го уровня")
    max_spell_slots_4 = models.IntegerField(default=0, verbose_name="Максимальное кол-во ячеек 4го уровня")
    max_spell_slots_5 = models.IntegerField(default=0, verbose_name="Максимальное кол-во ячеек 5го уровня")
    max_spell_slots_6 = models.IntegerField(default=0, verbose_name="Максимальное кол-во ячеек 6го уровня")
    max_spell_slots_7 = models.IntegerField(default=0, verbose_name="Максимальное кол-во ячеек 7го уровня")
    max_spell_slots_8 = models.IntegerField(default=0, verbose_name="Максимальное кол-во ячеек 8го уровня")
    max_spell_slots_9 = models.IntegerField(default=0, verbose_name="Максимальное кол-во ячеек 9го уровня")

    current_spell_slots_1 = models.IntegerField(default=0, verbose_name="Текущее кол-во ячеек 1го уровня")
    current_spell_slots_2 = models.IntegerField(default=0, verbose_name="Текущее кол-во ячеек 2го уровня")
    current_spell_slots_3 = models.IntegerField(default=0, verbose_name="Текущее кол-во ячеек 3го уровня")
    current_spell_slots_4 = models.IntegerField(default=0, verbose_name="Текущее кол-во ячеек 4го уровня")
    current_spell_slots_5 = models.IntegerField(default=0, verbose_name="Текущее кол-во ячеек 5го уровня")
    current_spell_slots_6 = models.IntegerField(default=0, verbose_name="Текущее кол-во ячеек 6го уровня")
    current_spell_slots_7 = models.IntegerField(default=0, verbose_name="Текущее кол-во ячеек 7го уровня")
    current_spell_slots_8 = models.IntegerField(default=0, verbose_name="Текущее кол-во ячеек 8го уровня")
    current_spell_slots_9 = models.IntegerField(default=0, verbose_name="Текущее кол-во ячеек 9го уровня")

    # Колдовские ячейки
    warlock_slot_level = models.IntegerField(default=0, verbose_name="Уровень ячейки колдуна")
    warlock_max_slots = models.IntegerField(default=0, verbose_name="Максимальное кол-во ячеек колдуна")
    warlock_current_slots = models.IntegerField(default=0, verbose_name="Текущее кол-во ячеек колдуна")

    # Метаданные
    created_at = models.DateTimeField(default=now, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")
    last_used = models.DateTimeField(null=True, blank=True, verbose_name="Последний заход")

    def __str__(self):
        return f"{self.name} ({self.owner.name})"

    def reset_all_spell_slots(self):
        """Восстановить все ячейки"""
        self.current_spell_slots_1 = self.max_spell_slots_1
        self.current_spell_slots_2 = self.max_spell_slots_2
        self.current_spell_slots_3 = self.max_spell_slots_3
        self.current_spell_slots_4 = self.max_spell_slots_4
        self.current_spell_slots_5 = self.max_spell_slots_5
        self.current_spell_slots_6 = self.max_spell_slots_6
        self.current_spell_slots_7 = self.max_spell_slots_7
        self.current_spell_slots_8 = self.max_spell_slots_8
        self.current_spell_slots_9 = self.max_spell_slots_9
        self.warlock_current_slots = self.warlock_max_slots
        self.save()

    def use_spell_slot(self, spell_level, is_warlock=False):
        """Использовать ячейку заклинания"""
        if is_warlock and self.warlock_current_slots > 0:
            self.warlock_current_slots -= 1
            self.save()
            return True

        slot_field = f"current_spell_slots_{spell_level}"
        current = getattr(self, slot_field, 0)
        if current > 0:
            setattr(self, slot_field, current - 1)
            self.save()
            return True

        return False

    @property
    def total_spells(self):
        return self.spells.count()

    class Meta:
        verbose_name = "Спеллбук"
        verbose_name_plural = "Спеллбуки"
        ordering = ["-updated_at"]
