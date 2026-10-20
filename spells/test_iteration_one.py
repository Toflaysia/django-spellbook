from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from spells.models import CharacterClass, ClassFeature

class OptionalFeatureTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user('editor', is_staff=True)
        self.character_class = CharacterClass.objects.create(name='Воин', description='Описание')
        self.client.force_login(self.staff)

    def test_optional_feature_creation_display_and_edit(self):
        create_url = reverse('class_feature_create_page', args=[self.character_class.pk])
        self.assertContains(self.client.get(create_url), 'Опциональное умение')
        data = {'name': 'Особое Умение', 'levels': '1, 3', 'description': 'Текст', 'is_optional': 'on'}
        self.assertEqual(self.client.post(create_url, data).status_code, 302)
        feature = ClassFeature.objects.get(character_class=self.character_class)
        self.assertTrue(feature.is_optional)
        self.assertEqual(feature.name, 'Особое Умение')
        detail_url = reverse('class_detail_page', args=[self.character_class.pk])
        response = self.client.get(detail_url)
        self.assertContains(response, 'ОСОБОЕ УМЕНИЕ', count=3)
        self.assertRegex(response.content.decode(), r'<a class="class-feature-link class-feature-link-optional')
        self.assertContains(response, 'Опциональное умение')
        data.pop('is_optional')
        edit_url = reverse('class_feature_edit_page', args=[self.character_class.pk, feature.pk])
        self.assertEqual(self.client.post(edit_url, data).status_code, 302)
        feature.refresh_from_db()
        self.assertFalse(feature.is_optional)
        self.assertNotContains(self.client.get(detail_url), 'Опциональное умение')

    def test_reader_cannot_set_optional_flag(self):
        self.client.force_login(User.objects.create_user('reader'))
        url = reverse('class_feature_create_page', args=[self.character_class.pk])
        self.assertEqual(self.client.post(url, {'is_optional': 'on'}).status_code, 403)
        self.assertFalse(ClassFeature.objects.exists())
