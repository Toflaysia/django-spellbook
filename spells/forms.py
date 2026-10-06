from django import forms

from spells.models import Person


class CharacterCreateForm(forms.ModelForm):
    class Meta:
        model = Person
        fields = [
            "name",
            "race",
            "background",
            "character_class",
            "primary_class_level",
            "strength",
            "dexterity",
            "constitution",
            "intelligence",
            "wisdom",
            "charisma",
            "max_hit_points",
            "armor_class",
            "speed",
            "spellcasting_ability",
        ]
        labels = {
            "name": "Имя персонажа",
            "primary_class_level": "Уровень",
            "max_hit_points": "Максимальные хиты",
            "spellcasting_ability": "Заклинательная характеристика",
        }

    def clean_max_hit_points(self):
        value = self.cleaned_data["max_hit_points"]

        if value < 1:
            raise forms.ValidationError("Хиты должны быть не меньше 1.")

        return value

    def clean_armor_class(self):
        value = self.cleaned_data["armor_class"]

        if value < 0:
            raise forms.ValidationError("Класс доспеха не может быть отрицательным.")

        return value

    def clean_speed(self):
        value = self.cleaned_data["speed"]

        if value < 0:
            raise forms.ValidationError("Скорость не может быть отрицательной.")

        return value
class CharacterEditForm(CharacterCreateForm):
    class Meta(CharacterCreateForm.Meta):
        fields = CharacterCreateForm.Meta.fields + [
            "current_hit_points",
            "temporary_hit_points",
            "is_favorite",
            "is_public",
        ]

    def clean(self):
        cleaned_data = super().clean()

        maximum = cleaned_data.get("max_hit_points")
        current = cleaned_data.get("current_hit_points")
        temporary = cleaned_data.get("temporary_hit_points")

        if current is not None:
            if current < 0:
                self.add_error(
                    "current_hit_points",
                    "Хиты не могут быть отрицательными.",
                )
            elif maximum is not None and current > maximum:
                self.add_error(
                    "current_hit_points",
                    "Текущие хиты не могут превышать максимальные.",
                )

        if temporary is not None and temporary < 0:
            self.add_error(
                "temporary_hit_points",
                "Временные хиты не могут быть отрицательными.",
            )

        if self.instance.subclass_id:
            subclass = self.instance.subclass
            character_class = cleaned_data.get("character_class")
            level = cleaned_data.get("primary_class_level")

            if (
                character_class is None
                or subclass.character_class_id != character_class.pk
            ):
                self.add_error(
                    "character_class",
                    "Сначала убери текущий подкласс через API, "
                    "чтобы изменить класс.",
                )
            elif level is not None and level < subclass.level_gained:
                self.add_error(
                    "primary_class_level",
                    f"Текущий подкласс требует уровень "
                    f"не ниже {subclass.level_gained}.",
                )

        return cleaned_data