from importlib import import_module
from types import SimpleNamespace
from django.apps import apps
from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.urls import reverse
from spells.models import DamageType


class DamageTypeVariantTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user('damage-admin', is_staff=True)
        self.item = DamageType.objects.create(name='Огонь', is_magic=True, is_regular=True)
        self.url = reverse('catalog_edit_page', args=['damage-types', self.item.pk])

    def test_both_variants_can_be_saved_and_selected_independently(self):
        self.client.force_login(self.staff)
        for magic, regular in ((True, True), (False, True), (True, False), (False, False)):
            data = {'name': 'Огонь', 'description': 'Текст'}
            if magic:
                data['is_magic'] = 'on'
            if regular:
                data['is_regular'] = 'on'
            response = self.client.post(self.url, data)
            self.assertEqual(response.status_code, 302)
            self.item.refresh_from_db()
            self.assertEqual((self.item.is_magic, self.item.is_regular), (magic, regular))

    def test_form_has_both_checkboxes(self):
        self.client.force_login(self.staff)
        response = self.client.get(self.url)
        for name in ('is_magic', 'is_regular'):
            self.assertContains(response, f'name="{name}"')
        self.assertContains(response, 'Обычный урон')

    def test_public_detail_shows_both_parameters(self):
        response = self.client.get(reverse('catalog_detail_page', args=['damage-types', self.item.pk]))
        self.assertEqual(response.context['attributes'], [
            {'label': 'Магический урон', 'value': 'Да'},
            {'label': 'Обычный урон', 'value': 'Да'},
        ])

    def test_readers_cannot_edit(self):
        user = User.objects.create_user('damage-reader')
        self.client.force_login(user)
        self.assertEqual(self.client.post(self.url, {'name': 'Чужой'}).status_code, 403)
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, 'Огонь')

    def test_selector_label_lists_both_variants(self):
        self.assertEqual(str(self.item), 'Огонь (маг., обычный)')
        self.item.is_magic = False
        self.assertEqual(str(self.item), 'Огонь (обычный)')

    def test_data_migration_preserves_existing_nonmagical_records(self):
        regular = DamageType.objects.create(name='Дробящий', is_magic=False)
        magical = DamageType.objects.create(name='Силовое поле', is_magic=True)
        migration = import_module('spells.migrations.0010_damagetype_is_regular')
        migration.mark_existing_regular_damage(apps, SimpleNamespace(connection=connection))
        regular.refresh_from_db()
        magical.refresh_from_db()
        self.assertTrue(regular.is_regular)
        self.assertFalse(magical.is_regular)
