from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from spells.models import Person, Spell

class RangeInput(forms.NumberInput):
    input_type = "range"
class PortraitInput(forms.ClearableFileInput):
    template_name = "spells/widgets/portrait_input.html"
class CharacterCreateForm(forms.ModelForm):
    class Meta:
        model = Person
        fields = [
            "name",
            "portrait",
            "portrait_position_x",
            "portrait_position_y",
            "portrait_zoom",
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
        widgets = {
            "portrait": PortraitInput(),
            "portrait_position_x": RangeInput(
                attrs={"min": 0, "max": 100, "step": 1}
            ),
            "portrait_position_y": RangeInput(
                attrs={"min": 0, "max": 100, "step": 1}
            ),
            "portrait_zoom": RangeInput(
                attrs={"min": 1, "max": 3, "step": 0.1}
            ),
        }
    @property
    def field_groups(self):
        groups = [
            (
                "basic",
                "Основное",
                [
                    "name",
                    "race",
                    "background",
                    "character_class",
                    "primary_class_level",
                    "is_favorite",
                    "is_public",
                ],
            ),
                        (
                "portrait",
                "Портрет",
                [
                    "portrait",
                    "portrait_position_x",
                    "portrait_position_y",
                    "portrait_zoom",
                ],
            ),
            (
                "abilities",
                "Характеристики",
                [
                    "strength",
                    "dexterity",
                    "constitution",
                    "intelligence",
                    "wisdom",
                    "charisma",
                ],
            ),
            (
                "combat",
                "Бой и магия",
                [
                    "max_hit_points",
                    "current_hit_points",
                    "temporary_hit_points",
                    "armor_class",
                    "speed",
                    "spellcasting_ability",
                ],
            ),
        ]

        return [
            {
                "id": group_id,
                "title": title,
                "fields": [
                    self[field_name]
                    for field_name in field_names
                    if field_name in self.fields
                ],
            }
            for group_id, title, field_names in groups
        ]
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
class RegistrationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ["username"]
        labels = {
            "username": "Имя пользователя",
        }
class CustomSpellForm(forms.ModelForm):
    class Meta:
        model = Spell
        fields = [
            "name",
            "level",
            "school",
            "time",
            "range",
            "duration",
            "concentration",
            "ritual",
            "verbal_component",
            "somatic_component",
            "material_components",
            "description",
            "higher_level",
            "attack_type",
            "saving_throw_ability",
            "effects",
            "aviable_classes",
            "aviable_subclasses",
            "source_book",
            "page_number",
        ]
        labels = {
            "name": "Название заклинания",
            "time": "Время накладывания",
            "material_components": "Материальные компоненты",
            "effects": "Эффекты",
            "aviable_classes": "Доступные классы",
            "aviable_subclasses": "Доступные подклассы",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6}),
            "higher_level": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["level"].choices = [
            (0, "Заговор"),
            *[(level, f"Уровень {level}") for level in range(1, 10)],
        ]

        for field_name in [
            "material_components",
            "effects",
            "aviable_classes",
            "aviable_subclasses",
        ]:
            self.fields[field_name].help_text = (
                "Для выбора нескольких значений удерживай Ctrl "
                "(на Mac — Command)."
            )

    @property
    def field_groups(self):
        groups = [
            (
                "basic",
                "Основное",
                [
                    "name",
                    "level",
                    "school",
                    "time",
                    "range",
                    "duration",
                    "concentration",
                    "ritual",
                ],
            ),
            (
                "components",
                "Компоненты",
                [
                    "verbal_component",
                    "somatic_component",
                    "material_components",
                ],
            ),
            (
                "description",
                "Описание",
                [
                    "description",
                    "higher_level",
                    "source_book",
                    "page_number",
                ],
            ),
            (
                "mechanics",
                "Механика",
                [
                    "attack_type",
                    "saving_throw_ability",
                    "effects",
                ],
            ),
            (
                "availability",
                "Доступность",
                [
                    "aviable_classes",
                    "aviable_subclasses",
                ],
            ),
        ]

        return [
            {
                "id": group_id,
                "title": title,
                "fields": [self[name] for name in field_names],
            }
            for group_id, title, field_names in groups
        ]

    def clean(self):
        cleaned_data = super().clean()

        if (
            cleaned_data.get("attack_type") == Spell.AttackType.SAVE_THROW
            and not cleaned_data.get("saving_throw_ability")
        ):
            self.add_error(
                "saving_throw_ability",
                "Выбери характеристику для спасброска.",
            )

        page_number = cleaned_data.get("page_number")

        if page_number is not None and page_number < 1:
            self.add_error(
                "page_number",
                "Номер страницы должен быть не меньше 1.",
            )

        return cleaned_data