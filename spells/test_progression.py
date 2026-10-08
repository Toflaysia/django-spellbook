import json

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from spells.models import CharacterClass, ClassFeature, Subclass
from spells.progression import TABLE_TYPES, custom_column, preset_columns, validate_progression_columns
from spells.views.progression_pages import ProgressionForm


class ProgressionLayoutTests(SimpleTestCase):
    def test_every_preset_is_valid(self):
        for kind, _ in TABLE_TYPES:
            with self.subTest(kind=kind):
                validate_progression_columns(preset_columns(kind))
        self.assertEqual(len(preset_columns("fighter")), 3)
        self.assertIn("rages", [column["key"] for column in preset_columns("barbarian")])
        self.assertIn("ki", [column["key"] for column in preset_columns("monk")])
        self.assertIn("pact_level", [column["key"] for column in preset_columns("warlock")])
        self.assertNotIn("slots_6", [column["key"] for column in preset_columns("paladin")])

    def test_invalid_schema_is_rejected(self):
        for columns in [[{}], [{"key": "custom", "kind": "text", "title": "Текст", "values": [""]}],
                        preset_columns("fighter") + preset_columns("fighter")]:
            with self.assertRaises(ValidationError):
                validate_progression_columns(columns)
        with self.assertRaises(ValidationError):
            validate_progression_columns(preset_columns("fighter"), subclass=True)


class ProgressionPageTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("staff", password="test", is_staff=True)
        self.reader = User.objects.create_user("reader", password="test")
        self.fighter = CharacterClass.objects.create(name="Воин", description="Текст", progression_table_type="fighter")
        self.monk = CharacterClass.objects.create(name="Монах", description="Текст", progression_table_type="monk")
        self.subclass = Subclass.objects.create(character_class=self.fighter, name="Архетип", description="Текст", level_gained=3)
        self.other_subclass = Subclass.objects.create(character_class=self.monk, name="Традиция", description="Текст")
        self.base_feature = ClassFeature.objects.create(character_class=self.fighter, name="Общее умение", description="Текст", level=1, levels=[1, 5])
        self.sub_feature = ClassFeature.objects.create(character_class=self.fighter, subclass=self.subclass, name="Особое умение", description="Текст", level=3)
        self.url = reverse("class_table_edit_page", args=[self.fighter.pk])
        self.sub_url = reverse("subclass_table_edit_page", args=[self.fighter.pk, self.subclass.pk])

    def test_save_applies_only_to_chosen_class(self):
        self.client.force_login(self.staff)
        columns = preset_columns("barbarian")
        columns[3]["values"][0] = "2"
        response = self.client.post(self.url, {"table_type": "barbarian", "columns": json.dumps(columns)})
        self.assertEqual(response.status_code, 302)
        self.fighter.refresh_from_db()
        self.monk.refresh_from_db()
        self.assertEqual(self.fighter.progression_table_type, "barbarian")
        self.assertEqual(self.fighter.progression_columns[3]["values"][0], "2")
        self.assertEqual(self.monk.progression_table_type, "monk")
        self.assertEqual(self.monk.progression_columns, [])
        self.assertContains(self.client.get(reverse("class_detail_page", args=[self.fighter.pk])), "Урон ярости")

    def test_subclass_adds_columns_and_preserves_class_and_features(self):
        self.client.force_login(self.staff)
        extra = custom_column("sub_resource", "Ресурс подкласса")
        extra["values"] = ["1"] * 20
        self.assertEqual(self.client.post(self.sub_url, {"columns": json.dumps([extra])}).status_code, 302)
        self.fighter.refresh_from_db()
        self.assertEqual(self.fighter.progression_columns, [])
        url = reverse("class_detail_page", args=[self.fighter.pk])
        base = self.client.get(url)
        selected = self.client.get(url, {"subclass": self.subclass.pk})
        self.assertNotContains(base, "Ресурс подкласса")
        self.assertContains(selected, "Ресурс подкласса")
        self.assertContains(selected, "Общее умение")
        self.assertContains(selected, "Особое умение")
        self.assertEqual(len(selected.context["table_columns"]), 4)
        self.assertEqual(selected.context["levels"][0]["cells"][-1]["value"], "—")
        self.assertEqual(selected.context["levels"][2]["cells"][-1]["value"], "1")
        self.assertIn(self.base_feature, selected.context["levels"][4]["features"])

    def test_cross_class_subclass_is_rejected(self):
        self.client.force_login(self.staff)
        foreign = reverse("subclass_table_edit_page", args=[self.fighter.pk, self.other_subclass.pk])
        self.assertEqual(self.client.post(foreign, {"columns": "[]"}).status_code, 404)
        self.assertEqual(self.client.get(reverse("class_detail_page", args=[self.fighter.pk]), {"subclass": self.other_subclass.pk}).status_code, 404)

    def test_reader_cannot_change_tables_but_can_view(self):
        self.client.force_login(self.reader)
        for url in [self.url, self.sub_url]:
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(url, {"columns": "[]", "table_type": "fighter"}).status_code, 403)
        self.assertContains(self.client.get(reverse("class_detail_page", args=[self.monk.pk])), "Очки ци")
        self.assertNotContains(self.client.get(reverse("class_detail_page", args=[self.monk.pk])), "Настроить таблицу класса")

    def test_invalid_post_does_not_modify_class(self):
        self.client.force_login(self.staff)
        response = self.client.post(self.url, {"table_type": "warlock", "columns": json.dumps([{}])})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.fighter.refresh_from_db()
        self.assertEqual(self.fighter.progression_table_type, "fighter")

    def test_subclass_cannot_be_moved_away_from_its_features(self):
        self.subclass.character_class = self.monk
        with self.assertRaises(ValidationError):
            self.subclass.full_clean()

    def test_cell_content_is_escaped(self):
        extra = custom_column("custom_value", "Параметр")
        extra["values"][0] = "<script>alert(1)</script>"
        self.fighter.progression_columns = preset_columns("fighter") + [extra]
        self.fighter.save()
        response = self.client.get(reverse("class_detail_page", args=[self.fighter.pk]))
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertNotContains(response, "<script>alert(1)</script>")

    def test_existing_standard_classes_receive_table_types(self):
        from django.apps import apps
        from django.db import connection
        from importlib import import_module
        from types import SimpleNamespace

        bard = CharacterClass.objects.create(name="Бард", description="Текст")
        custom = CharacterClass.objects.create(name="Домашний класс", description="Текст")
        migration = import_module("spells.migrations.0009_class_progression_tables")
        migration.assign_existing_table_types(apps, SimpleNamespace(connection=connection))
        bard.refresh_from_db()
        custom.refresh_from_db()
        self.assertEqual(bard.progression_table_type, "bard")
        self.assertEqual(custom.progression_table_type, "basic")
