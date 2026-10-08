from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from spells.models import CharacterClass, ClassFeature, ClassSection, Subclass


class SubclassDeleteTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("staff", password="test", is_staff=True)
        self.user = User.objects.create_user("reader", password="test")
        self.character_class = CharacterClass.objects.create(name="Воин", description="Класс")
        self.subclass = Subclass.objects.create(
            character_class=self.character_class, name="Архетип", description="Описание",
        )
        self.common = ClassFeature.objects.create(
            character_class=self.character_class, name="Общее умение", description="Текст", level=1,
        )
        self.special = ClassFeature.objects.create(
            character_class=self.character_class, subclass=self.subclass,
            name="Особое умение", description="Текст", level=3,
        )
        self.section = ClassSection.objects.create(
            character_class=self.character_class, title="Раздел", description="Текст",
        )
        self.url = reverse("subclass_delete_page", args=[self.character_class.pk, self.subclass.pk])
        self.class_url = reverse("class_detail_page", args=[self.character_class.pk])

    def test_confirmation_does_not_delete(self):
        self.client.force_login(self.staff)
        response = self.client.get(self.url)
        self.assertContains(response, "Особое умение")
        self.assertContains(response, "csrfmiddlewaretoken")
        self.assertTrue(Subclass.objects.filter(pk=self.subclass.pk).exists())
        self.assertContains(
            self.client.get(f"{self.class_url}?subclass={self.subclass.pk}"),
            "Удалить подкласс",
        )

    def test_post_deletes_only_subclass_and_its_features(self):
        self.client.force_login(self.staff)
        self.assertRedirects(self.client.post(self.url), self.class_url)
        self.assertFalse(Subclass.objects.filter(pk=self.subclass.pk).exists())
        self.assertFalse(ClassFeature.objects.filter(pk=self.special.pk).exists())
        self.assertTrue(ClassFeature.objects.filter(pk=self.common.pk).exists())
        self.assertTrue(ClassSection.objects.filter(pk=self.section.pk).exists())
        self.assertTrue(CharacterClass.objects.filter(pk=self.character_class.pk).exists())

    def test_reader_cannot_delete(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url).status_code, 403)
        self.assertNotContains(
            self.client.get(f"{self.class_url}?subclass={self.subclass.pk}"),
            "Удалить подкласс",
        )
        self.assertTrue(Subclass.objects.filter(pk=self.subclass.pk).exists())

    def test_anonymous_cannot_delete(self):
        self.assertEqual(self.client.post(self.url).status_code, 302)
        self.assertTrue(Subclass.objects.filter(pk=self.subclass.pk).exists())

    def test_subclass_must_belong_to_class(self):
        other = CharacterClass.objects.create(name="Маг", description="Класс")
        self.client.force_login(self.staff)
        url = reverse("subclass_delete_page", args=[other.pk, self.subclass.pk])
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertTrue(Subclass.objects.filter(pk=self.subclass.pk).exists())
