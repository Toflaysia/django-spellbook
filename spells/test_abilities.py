from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse
from spells.models import (
    CharacterClass,
    CharacterResource,
    ClassFeature,
    Person,
    Player,
    Subclass,
)
from spells.abilities import ability_sheet, resource_snapshot
from spells.forms import CharacterEditForm
from spells.rests import rest_state
from spells.views.class_pages import ClassFeatureForm


class AbilityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ability-owner")
        self.other = User.objects.create_user("ability-other")
        self.cls = CharacterClass.objects.create(name="Монах", ability_rules="monk")
        self.person = Person.objects.create(
            name="Герой",
            player=Player.objects.create(user=self.user),
            character_class=self.cls,
            primary_class_level=5,
            max_hit_points=40,
            current_hit_points=10,
            wisdom=16,
        )
        self.url = reverse("character_rest_change", args=[self.person.pk])
        self.client.force_login(self.user)

    def post(self, action, **values):
        self.person.refresh_from_db()
        response = self.client.post(
            self.url,
            {"action": action, "revision": self.person.rest_revision, **values},
        )
        self.person.refresh_from_db()
        return response

    def pool(self, code):
        return next(
            row for row in resource_snapshot(self.person)[0] if row["code"] == code
        )

    def test_read_only_and_new_tab_order(self):
        url = reverse("character_detail_page", args=[self.person.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(CharacterResource.objects.count(), 0)
        html = response.content.decode()
        self.assertLess(
            html.index('id="tab-overview"'), html.index('id="tab-abilities"')
        )
        self.assertLess(html.index('id="tab-abilities"'), html.index('id="tab-checks"'))
        self.assertEqual(html.count("data-resource-list"), 1)
        self.assertContains(response, "Ци")
        self.assertEqual(self.pool("ki")["maximum"], 5)
        self.assertIn("14", self.pool("ki")["note"])

    def test_ki_spend_restore_bounds_and_short_rest(self):
        key = self.pool("ki")["key"]
        self.assertEqual(
            self.post("ability_spend", key=key, quantity=3).status_code, 200
        )
        self.assertEqual(self.pool("ki")["current"], 2)
        self.assertEqual(
            self.post("ability_spend", key=key, quantity=3).status_code, 400
        )
        self.assertEqual(
            self.post("ability_restore", key=key, quantity=2).status_code, 200
        )
        self.assertEqual(self.pool("ki")["current"], 4)
        self.assertEqual(
            self.post("ability_restore", key=key, quantity=2).status_code, 400
        )
        self.assertEqual(self.post("short_rest").status_code, 200)
        self.assertEqual(self.pool("ki")["current"], 5)

    def test_level_change_keeps_expended_amount(self):
        key = self.pool("ki")["key"]
        self.post("ability_spend", key=key, quantity=4)
        for level, current in ((8, 4), (2, 0), (6, 2)):
            self.person.primary_class_level = level
            self.person.save()
            self.assertEqual(self.pool("ki")["current"], current)
        self.person.primary_class_level = 1
        self.person.save()
        self.assertEqual(resource_snapshot(self.person)[0], [])
        self.assertEqual(self.post("ability_spend", key=key).status_code, 400)

    def test_legacy_manual_resource_is_adopted_without_reset(self):
        old = CharacterResource.objects.create(
            person=self.person, name="Ци", maximum=5, current=2, refresh_on="short"
        )
        self.assertEqual(rest_state(self.person)["resources"], [])
        self.assertEqual(self.pool("ki")["current"], 2)
        self.assertEqual(
            self.post("resource_delete", resource_id=old.pk).status_code, 400
        )
        self.post("ability_spend", key=self.pool("ki")["key"])
        old.refresh_from_db()
        self.assertEqual(old.spent_uses, 4)
        self.assertEqual(CharacterResource.objects.count(), 1)

    def test_second_wind_heals_atomically_and_caps_hp(self):
        self.cls.ability_rules = "fighter"
        self.cls.save()
        key = self.pool("second_wind")["key"]
        with patch("spells.abilities.secrets.randbelow", return_value=9):
            response = self.post("ability_spend", key=key)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.person.current_hit_points, 25)
        self.assertEqual(response.json()["health"]["current"], 25)
        self.assertEqual(self.post("ability_spend", key=key).status_code, 400)
        self.post("short_rest")
        self.person.current_hit_points = 39
        self.person.save()
        with patch("spells.abilities.secrets.randbelow", return_value=9):
            self.post("ability_spend", key=key)
        self.assertEqual(self.person.current_hit_points, 40)
        self.post("short_rest")
        self.assertEqual(self.post("ability_spend", key=key).status_code, 400)
        self.assertEqual(self.pool("second_wind")["current"], 1)

    def test_fighter_thresholds(self):
        self.cls.ability_rules = "fighter"
        self.cls.save()
        for level, surge, indomitable in (
            (1, 0, 0),
            (2, 1, 0),
            (9, 1, 1),
            (13, 1, 2),
            (17, 2, 3),
        ):
            self.person.primary_class_level = level
            rows = resource_snapshot(self.person)[0]
            values = {r["code"]: r["maximum"] for r in rows}
            self.assertEqual(values.get("action_surge", 0), surge)
            self.assertEqual(values.get("indomitable", 0), indomitable)

    def test_multiclass_channel_divinity_is_one_shared_pool(self):
        self.cls.ability_rules = "cleric"
        self.cls.save()
        self.person.primary_class_level = 6
        second = CharacterClass.objects.create(name="Паладин", ability_rules="paladin")
        self.person.second_class = second
        self.person.second_class_level = 4
        self.person.save()
        channel = [
            r
            for r in resource_snapshot(self.person)[0]
            if r["code"] == "channel_divinity"
        ]
        self.assertEqual(len(channel), 1)
        self.assertEqual(channel[0]["maximum"], 2)
        self.post("ability_spend", key=channel[0]["key"], quantity=2)
        self.assertEqual(self.pool("channel_divinity")["current"], 0)

    def test_subclass_features_level_ownership_order_and_optional(self):
        sub = Subclass.objects.create(
            character_class=self.cls, name="Путь", level_gained=3
        )
        wrong = Subclass.objects.create(
            character_class=self.cls, name="Другой путь", level_gained=3
        )
        base = ClassFeature.objects.create(
            character_class=self.cls, name="Основное", level=1, description="Описание"
        )
        feature = ClassFeature.objects.create(
            character_class=self.cls,
            subclass=sub,
            name="Приём",
            level=3,
            description="Приём",
            resource_formula="class_level",
            resource_refresh_on="short",
            is_optional=True,
        )
        ClassFeature.objects.create(
            character_class=self.cls, subclass=wrong, name="Чужое", level=3
        )
        ClassFeature.objects.create(
            character_class=self.cls, subclass=sub, name="Позднее", level=6
        )
        self.person.subclass = sub
        self.person.save()
        sheet = ability_sheet(self.person)
        self.assertIn("Основное", [r["name"] for r in sheet["classes"][0]["features"]])
        self.assertEqual(
            [r["name"] for r in sheet["subclasses"][0]["features"]], ["Приём"]
        )
        self.assertFalse(
            any(r["code"] == "catalog" for r in resource_snapshot(self.person)[0])
        )
        self.assertEqual(
            self.post(
                "ability_toggle", feature_id=feature.pk, enabled="true"
            ).status_code,
            200,
        )
        self.assertEqual(self.pool("catalog")["maximum"], 5)
        self.assertEqual(
            self.post("ability_toggle", feature_id=base.pk, enabled="true").status_code,
            400,
        )
        self.assertEqual(
            self.post(
                "ability_toggle", feature_id=feature.pk, enabled="false"
            ).status_code,
            200,
        )
        self.assertFalse(
            any(r["code"] == "catalog" for r in resource_snapshot(self.person)[0])
        )

    def test_catalog_formula_and_bard_charisma(self):
        ClassFeature.objects.create(
            character_class=self.cls,
            name="Сила духа",
            level=1,
            resource_formula="wisdom",
            resource_amount=2,
        )
        self.assertEqual(self.pool("catalog")["maximum"], 6)
        self.cls.ability_rules = "bard"
        self.cls.save()
        self.person.charisma = 8
        self.assertEqual(self.pool("inspiration")["maximum"], 1)
        self.assertEqual(self.pool("inspiration")["refresh_on"], "short")
        self.person.primary_class_level = 4
        self.assertEqual(self.pool("inspiration")["refresh_on"], "long")

    def test_sorcerer_level20_short_rest_returns_four(self):
        self.cls.ability_rules = "sorcerer"
        self.cls.save()
        self.person.primary_class_level = 20
        self.person.save()
        key = self.pool("sorcery")["key"]
        self.post("ability_spend", key=key, quantity=10)
        self.post("short_rest")
        self.assertEqual(self.pool("sorcery")["current"], 14)
        self.post("long_rest")
        self.assertEqual(self.pool("sorcery")["current"], 20)

    def test_unlimited_and_zero_pool(self):
        self.cls.ability_rules = "barbarian"
        self.cls.save()
        self.person.primary_class_level = 20
        self.assertIsNone(self.pool("rage")["maximum"])
        self.person.save()
        self.assertEqual(
            self.post("ability_spend", key=self.pool("rage")["key"]).status_code, 400
        )
        self.cls.ability_rules = "paladin"
        self.cls.save()
        self.person.charisma = 3
        self.person.save()
        self.assertEqual(self.pool("divine_sense")["maximum"], 0)
        self.assertEqual(
            self.post(
                "ability_spend", key=self.pool("divine_sense")["key"]
            ).status_code,
            400,
        )

    def test_authentication_owner_csrf_and_replay(self):
        key = self.pool("ki")["key"]
        payload = {"action": "ability_spend", "key": key, "revision": 0}
        self.assertEqual(self.client.post(self.url, payload).status_code, 200)
        self.assertEqual(self.client.post(self.url, payload).status_code, 409)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.url, payload).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.post(self.url, payload).status_code, 302)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(self.url, payload).status_code, 403)

    def test_invalid_quantity_or_source_changes_nothing(self):
        key = self.pool("ki")["key"]
        for quantity in ("0", "-1", "1.5", "NaN", "10000"):
            self.assertEqual(
                self.post("ability_spend", key=key, quantity=quantity).status_code, 400
            )
        self.assertEqual(
            self.post("ability_spend", key="feature:9999").status_code, 400
        )
        self.assertEqual(CharacterResource.objects.count(), 0)

    def test_optional_disable_reenable_does_not_reset(self):
        feature = ClassFeature.objects.create(
            character_class=self.cls,
            name="Опция",
            level=1,
            is_optional=True,
            resource_formula="fixed",
            resource_amount=3,
        )
        self.post("ability_toggle", feature_id=feature.pk, enabled="true")
        key = self.pool("catalog")["key"]
        self.post("ability_spend", key=key, quantity=2)
        self.post("ability_toggle", feature_id=feature.pk, enabled="false")
        self.post("long_rest")
        self.post("ability_toggle", feature_id=feature.pk, enabled="true")
        self.assertEqual(self.pool("catalog")["current"], 1)

    def test_custom_named_class_has_no_implicit_standard_rules(self):
        self.cls.ability_rules = ""
        self.cls.save()
        self.assertEqual(resource_snapshot(self.person)[0], [])

    def test_feature_form_exposes_counter_configuration(self):
        form = ClassFeatureForm(character_class=self.cls)
        self.assertIn("resource_formula", form.fields)
        self.assertIn("resource_refresh_on", form.fields)

    def test_editor_subclass_validation(self):
        sub = Subclass.objects.create(
            character_class=self.cls, name="Путь", level_gained=3
        )
        form = CharacterEditForm(instance=self.person, user=self.user)
        data = {
            key: form[key].value()
            for key in form.fields
            if form[key].value() is not None
        }
        data.update(name="Герой", subclass=sub.pk, second_class_level=0)
        bound = CharacterEditForm(data, instance=self.person, user=self.user)
        self.assertTrue(bound.is_valid(), bound.errors)
        data["primary_class_level"] = 2
        bound = CharacterEditForm(data, instance=self.person, user=self.user)
        self.assertFalse(bound.is_valid())
        self.assertIn("subclass", bound.errors)
