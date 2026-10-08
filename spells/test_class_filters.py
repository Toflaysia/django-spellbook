from django.test import TestCase
from django.urls import reverse

from spells.models import CharacterClass, Subclass


class ClassCatalogFilterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.full = CharacterClass.objects.create(name="Жрец", description="Текст", magic_type="FC", hit_die=8, spellcasting_ability="WIS")
        cls.half = CharacterClass.objects.create(name="Паладин", description="Текст", magic_type="HC", hit_die=10, spellcasting_ability="CHA")
        cls.third = CharacterClass.objects.create(name="Тестовый маг", description="Текст", magic_type="TC", hit_die=10, spellcasting_ability="INT")
        cls.non = CharacterClass.objects.create(name="Воин", description="Текст", magic_type="NC", hit_die=8, spellcasting_ability="WIS")
        for name in ("Первый домен", "Второй домен"):
            Subclass.objects.create(character_class=cls.full, name=name, description="Текст")

    def setUp(self):
        self.url = reverse("catalog_list_page", args=["classes"])

    def names(self, **filters):
        response = self.client.get(self.url, filters)
        self.assertEqual(response.status_code, 200)
        return [entry["name"] for entry in response.context["entries"]]

    def test_magic_type(self):
        self.assertEqual(self.names(magic_type="FC"), ["Жрец"])

    def test_hit_die(self):
        self.assertEqual(set(self.names(hit_die="10")), {"Паладин", "Тестовый маг"})

    def test_ability_excludes_default_ability_of_noncasters(self):
        self.assertEqual(self.names(spellcasting_ability="WIS"), ["Жрец"])

    def test_combined_filters_and_search(self):
        self.assertEqual(self.names(search="Жрец", magic_type="FC", hit_die="8", spellcasting_ability="WIS", has_subclasses="1"), ["Жрец"])
        self.assertEqual(self.names(magic_type="FC", hit_die="10"), [])

    def test_subclasses_filter_does_not_duplicate_cards(self):
        response = self.client.get(self.url, {"has_subclasses": "1"})
        self.assertEqual(response.context["page"].paginator.count, 1)
        self.assertEqual(response.context["entries"][0]["subclass_count"], 2)

    def test_invalid_filter_shows_error(self):
        response = self.client.get(self.url, {"hit_die": "not-a-number"})
        self.assertTrue(response.context["class_filters"].errors)
        self.assertEqual(response.context["page"].paginator.count, 0)
        self.assertContains(response, "Сбросить")

    def test_pagination_preserves_filters(self):
        CharacterClass.objects.bulk_create([
            CharacterClass(name=f"Маг {index:02}", description="Текст", magic_type="FC", hit_die=8, spellcasting_ability="WIS")
            for index in range(25)
        ])
        response = self.client.get(self.url, {"magic_type": "FC", "hit_die": "8", "page": "1"})
        self.assertContains(response, '?magic_type=FC&amp;hit_die=8&amp;page=2')
        second = self.client.get(self.url, {"magic_type": "FC", "hit_die": "8", "page": "2"})
        self.assertEqual(len(second.context["entries"]), 2)
        self.assertContains(second, '?magic_type=FC&amp;hit_die=8&amp;page=1')

    def test_other_catalogs_do_not_have_class_filters(self):
        response = self.client.get(reverse("catalog_list_page", args=["schools"]), {"magic_type": "FC"})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["class_filters"])
        self.assertNotContains(response, 'name="hit_die"')
