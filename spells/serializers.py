from rest_framework import serializers

from spells.models import CharacterClass, Person, Spell, Subclass


class CharacterSerializer(serializers.ModelSerializer):
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
    class Meta:
        model = CharacterClass
        fields = [
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
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields