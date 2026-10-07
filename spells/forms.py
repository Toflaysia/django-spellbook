import json

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db.models import Q

from spells.models import Person, Spell, Spellbook


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
            raise forms.ValidationError(
                "Хиты должны быть не меньше 1."
            )

        return value

    def clean_armor_class(self):
        value = self.cleaned_data["armor_class"]

        if value < 0:
            raise forms.ValidationError(
                "Класс доспеха не может быть отрицательным."
            )

        return value

    def clean_speed(self):
        value = self.cleaned_data["speed"]

        if value < 0:
            raise forms.ValidationError(
                "Скорость не может быть отрицательной."
            )

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
            "material_components": forms.CheckboxSelectMultiple(),
            "effects": forms.CheckboxSelectMultiple(),
            "aviable_classes": forms.CheckboxSelectMultiple(),
            "aviable_subclasses": forms.CheckboxSelectMultiple(),
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
                "Отметь необходимые значения."
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


class SpellImportForm(forms.Form):
    json_file = forms.FileField(
        label="Файл заклинания",
        help_text="Выбери файл в формате JSON. Максимальный размер — 1 МБ.",
        widget=forms.ClearableFileInput(
            attrs={"accept": ".json,application/json"}
        ),
    )

    def clean_json_file(self):
        uploaded_file = self.cleaned_data["json_file"]

        if uploaded_file.size > 1024 * 1024:
            raise forms.ValidationError(
                "Файл слишком большой. Максимальный размер — 1 МБ."
            )

        try:
            text = uploaded_file.read().decode("utf-8-sig")
            data = json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
            raise forms.ValidationError(
                "Не удалось прочитать JSON. Проверь формат файла."
            )

        if not isinstance(data, dict):
            raise forms.ValidationError(
                "Файл должен содержать одно заклинание."
            )

        if data.get("type") != "spell":
            raise forms.ValidationError(
                "Этот файл не является заклинанием."
            )

        name = data.get("name")

        if not isinstance(name, str) or not name.strip():
            raise forms.ValidationError(
                "В файле отсутствует название заклинания."
            )

        if not isinstance(data.get("system"), dict):
            raise forms.ValidationError(
                "В файле отсутствует раздел с данными заклинания."
            )

        self.import_data = data
        uploaded_file.seek(0)

        return uploaded_file


class SpellbookForm(forms.ModelForm):
    class Meta:
        model = Spellbook
        fields = [
            "name",
            "description",
            "owner",
            "spells",
            "max_spell_slots_1",
            "max_spell_slots_2",
            "max_spell_slots_3",
            "max_spell_slots_4",
            "max_spell_slots_5",
            "max_spell_slots_6",
            "max_spell_slots_7",
            "max_spell_slots_8",
            "max_spell_slots_9",
            "warlock_slot_level",
            "warlock_max_slots",
        ]
        labels = {
            "name": "Название спеллбука",
            "description": "Описание",
            "owner": "Персонаж",
            "spells": "Заклинания",
            "warlock_slot_level": "Уровень ячеек колдуна",
            "warlock_max_slots": "Количество ячеек колдуна",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "spells": forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["owner"].queryset = Person.objects.filter(
            player__user=user,
        ).order_by("name")

        self.fields["spells"].queryset = (
            Spell.objects.filter(
                Q(created_by__user=user, is_official=False)
                | Q(saved_by_players__user=user, is_official=True)
            )
            .distinct()
            .order_by("level", "name")
        )

        self.fields["spells"].help_text = (
            "Отметь заклинания, которые нужно включить в спеллбук."
        )

        for level in range(1, 10):
            field = self.fields[f"max_spell_slots_{level}"]
            field.label = f"Ячейки {level}-го уровня"
            field.widget.attrs["min"] = 0

        self.fields["warlock_slot_level"].widget.attrs.update(
            {"min": 0, "max": 5}
        )
        self.fields["warlock_max_slots"].widget.attrs["min"] = 0

    @property
    def field_groups(self):
        groups = [
            (
                "basic",
                "Основное",
                ["name", "description", "owner"],
            ),
            (
                "spells",
                "Заклинания",
                ["spells"],
            ),
            (
                "slots",
                "Ячейки заклинаний",
                [
                    f"max_spell_slots_{level}"
                    for level in range(1, 10)
                ],
            ),
            (
                "warlock",
                "Ячейки колдуна",
                ["warlock_slot_level", "warlock_max_slots"],
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

        slot_fields = [
            f"max_spell_slots_{level}"
            for level in range(1, 10)
        ] + ["warlock_max_slots"]

        for field_name in slot_fields:
            value = cleaned_data.get(field_name)

            if value is not None and value < 0:
                self.add_error(
                    field_name,
                    "Количество ячеек не может быть отрицательным.",
                )

        warlock_level = cleaned_data.get("warlock_slot_level")
        warlock_slots = cleaned_data.get("warlock_max_slots")

        if warlock_level is not None:
            if not 0 <= warlock_level <= 5:
                self.add_error(
                    "warlock_slot_level",
                    "Укажи уровень от 0 до 5.",
                )
            elif warlock_slots is not None and warlock_slots > 0:
                if warlock_level == 0:
                    self.add_error(
                        "warlock_slot_level",
                        "Для ячеек колдуна укажи уровень от 1 до 5.",
                    )

        return cleaned_data