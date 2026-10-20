from spells.spell_access import visible_spells
from spells.class_access import visible_classes
from rest_framework import serializers

from spells.models import CharacterClass, Person, Spell, Spellbook, Subclass


class CharacterSerializer(serializers.ModelSerializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        classes = visible_classes(request.user if request else None)
        if 'character_class' in self.fields:
            self.fields['character_class'].queryset = classes
        if 'subclass' in self.fields:
            self.fields['subclass'].queryset = Subclass.objects.filter(character_class__in=classes)
        if 'aviable_classes' in self.fields:
            self.fields['aviable_classes'].child_relation.queryset = classes
        if 'aviable_subclasses' in self.fields:
            self.fields['aviable_subclasses'].child_relation.queryset = Subclass.objects.filter(character_class__in=classes)


    character_class_name = serializers.CharField(
        source="character_class.name",
        read_only=True,
        default=None,
    )
    level = serializers.IntegerField(read_only=True)
    spellcasting_modifier = serializers.IntegerField(read_only=True)
    spell_save_dc = serializers.IntegerField(read_only=True)
    spell_attack_bonus = serializers.IntegerField(read_only=True)

    class Meta:
        model = Person
        fields = [
            "id",
            "player",
            "name",
            "character_class",
            "character_class_name",
            "subclass",
            "primary_class_level",
            "race",
            "subrace",
            "alignment",
            "background",
            "strength",
            "dexterity",
            "constitution",
            "intelligence",
            "wisdom",
            "charisma",
            "max_hit_points",
            "current_hit_points",
            "temporary_hit_points",
            "armor_class",
            "initiative_bonus",
            "speed",
            "proficiency_bonus",
            "spellcasting_ability",
            "is_active",
            "is_favorite",
            "is_public",
            "level",
            "spellcasting_modifier",
            "spell_save_dc",
            "spell_attack_bonus",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "player",
            "created_at",
            "updated_at",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if instance.character_class_id and not visible_classes(request.user if request else None).filter(pk=instance.character_class_id).exists():
            data['character_class'] = None
            data['character_class_name'] = None
            data['subclass'] = None
        return data

    def validate(self, attrs):
        def current_value(field_name):
            if field_name in attrs:
                return attrs[field_name]

            if self.instance is not None:
                return getattr(self.instance, field_name)

            return Person._meta.get_field(field_name).get_default()

        errors = {}

        for field_name in [
            "current_hit_points",
            "temporary_hit_points",
            "armor_class",
            "speed",
        ]:
            if current_value(field_name) < 0:
                errors[field_name] = "Значение не может быть отрицательным."

        max_hp = current_value("max_hit_points")
        current_hp = current_value("current_hit_points")

        if max_hp < 1:
            errors["max_hit_points"] = (
                "Максимальные хиты должны быть не меньше 1."
            )

        if current_hp > max_hp:
            errors["current_hit_points"] = (
                "Текущие хиты не могут превышать максимальные."
            )

        character_class = current_value("character_class")
        subclass = current_value("subclass")

        if subclass is not None:
            if (
                character_class is None
                or subclass.character_class_id != character_class.pk
            ):
                errors["subclass"] = (
                    "Подкласс должен принадлежать выбранному классу."
                )
            elif current_value("primary_class_level") < subclass.level_gained:
                errors["subclass"] = (
                    f"Этот подкласс доступен с уровня {subclass.level_gained}."
                )

        if errors:
            raise serializers.ValidationError(errors)

        return attrs


class CharacterClassSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()

    def get_author(self, instance):
        return str(instance.created_by) if instance.created_by_id else None

    class Meta:
        model = CharacterClass
        fields = [
            "author", "is_official", "is_public", "image",
            "id",
            "name",
            "description",
            "magic_type",
            "hit_die",
            "spellcasting_ability",
        ]
class SubclassSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subclass
        fields = [
            "id",
            "name",
            "description",
            "character_class",
            "features_description",
            "level_gained",
        ]
class SpellSerializer(serializers.ModelSerializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        classes = visible_classes(request.user if request else None)
        if 'character_class' in self.fields:
            self.fields['character_class'].queryset = classes
        if 'subclass' in self.fields:
            self.fields['subclass'].queryset = Subclass.objects.filter(character_class__in=classes)
        if 'aviable_classes' in self.fields:
            self.fields['aviable_classes'].child_relation.queryset = classes
        if 'aviable_subclasses' in self.fields:
            self.fields['aviable_subclasses'].child_relation.queryset = Subclass.objects.filter(character_class__in=classes)


    author_name = serializers.CharField(source="created_by.user.username", read_only=True, default=None)
    school_name = serializers.CharField(
        source="school.name",
        read_only=True,
        default=None,
    )
    casting_time = serializers.CharField(
        source="time.time",
        read_only=True,
        default=None,
    )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        classes = visible_classes(request.user if request else None)
        allowed = set(classes.values_list('pk', flat=True))
        for field in ('aviable_classes', 'aviable_subclasses'):
            if field in data:
                if field == 'aviable_classes':
                    data[field] = [pk for pk in data[field] if pk in allowed]
                else:
                    data[field] = list(Subclass.objects.filter(pk__in=data[field], character_class_id__in=allowed).values_list('pk',flat=True))
        return data

    class Meta:
        model = Spell
        fields = [
            "id",
            "name",
            "level",
            "time",
            "casting_time",
            "school",
            "school_name",
            "verbal_component",
            "somatic_component",
            "material_components",
            "range",
            "duration",
            "concentration",
            "ritual",
            "description",
            "higher_level",
            "attack_type",
            "saving_throw_ability",
            "effects",
            "aviable_classes",
            "aviable_subclasses",
            "source_book",
            "page_number",
            "is_official",
            "is_public",
            "author_name",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

class CustomSpellSerializer(SpellSerializer):
    class Meta(SpellSerializer.Meta):
        read_only_fields = [
            "id",
            "school_name",
            "casting_time",
            "is_official",
            "author_name",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        def current_value(field_name):
            if field_name in attrs:
                return attrs[field_name]

            if self.instance is not None:
                return getattr(self.instance, field_name)

            return Spell._meta.get_field(field_name).get_default()

        errors = {}

        if (
            current_value("attack_type") == Spell.AttackType.SAVE_THROW
            and not current_value("saving_throw_ability")
        ):
            errors["saving_throw_ability"] = (
                "Укажи характеристику для спасброска."
            )

        page_number = current_value("page_number")

        if page_number is not None and page_number < 1:
            errors["page_number"] = "Номер страницы должен быть не меньше 1."

        if errors:
            raise serializers.ValidationError(errors)

        return attrs
class SpellbookSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(
        source="owner.name",
        read_only=True,
    )
    total_spells = serializers.IntegerField(read_only=True)

    class Meta:
        model = Spellbook
        fields = [
            "id",
            "name",
            "description",
            "owner",
            "owner_name",
            "spells",
            "total_spells",
            "is_active",
            "is_shared",
            "max_spell_slots_1",
            "current_spell_slots_1",
            "max_spell_slots_2",
            "current_spell_slots_2",
            "max_spell_slots_3",
            "current_spell_slots_3",
            "max_spell_slots_4",
            "current_spell_slots_4",
            "max_spell_slots_5",
            "current_spell_slots_5",
            "max_spell_slots_6",
            "current_spell_slots_6",
            "max_spell_slots_7",
            "current_spell_slots_7",
            "max_spell_slots_8",
            "current_spell_slots_8",
            "max_spell_slots_9",
            "current_spell_slots_9",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]

    def validate_owner(self, owner):
        user = self.context["request"].user

        if owner.player_id is None or owner.player.user_id != user.pk:
            raise serializers.ValidationError(
                "Можно выбрать только своего персонажа."
            )

        return owner

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        self.fields['spells'].child_relation.queryset = visible_spells(request.user if request else None)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        allowed = visible_spells(request.user if request else None)
        data['spells'] = list(instance.spells.filter(pk__in=allowed).values_list('pk', flat=True))
        data['total_spells'] = len(data['spells'])
        return data

    def validate_spells(self, spells):
        return spells

    def validate(self, attrs):
        def current_value(field_name):
            if field_name in attrs:
                return attrs[field_name]

            if self.instance is not None:
                return getattr(self.instance, field_name)

            return Spellbook._meta.get_field(field_name).get_default()

        errors = {}

        for level in range(1, 10):
            max_field = f"max_spell_slots_{level}"
            current_field = f"current_spell_slots_{level}"

            maximum = current_value(max_field)
            remaining = current_value(current_field)

            if maximum < 0:
                errors[max_field] = (
                    "Количество ячеек не может быть отрицательным."
                )

            if remaining < 0:
                errors[current_field] = (
                    "Количество ячеек не может быть отрицательным."
                )
            elif remaining > maximum:
                errors[current_field] = (
                    "Остаток ячеек не может превышать максимум."
                )

        if errors:
            raise serializers.ValidationError(errors)

        return attrs
