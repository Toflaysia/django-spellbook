from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse
from spells.models import DamageType, Effect


class DamageCatalogTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user('damage-catalog-admin', is_staff=True)
        cls.reader = User.objects.create_user('damage-catalog-reader')
        cls.magic = DamageType.objects.create(name='Магический огонь', is_magic=True)
        cls.regular = DamageType.objects.create(name='Обычный огонь', is_magic=False, is_regular=True)
        cls.both = DamageType.objects.create(name='Огонь', is_magic=True, is_regular=True)
        cls.effect = Effect.objects.create(name='Горение', description='Текст', damage_type=cls.both)

    def setUp(self):
        self.list_url = reverse('catalog_list_page', args=['damage-types'])
        self.detail_url = reverse('catalog_detail_page', args=['damage-types', self.both.pk])
        self.delete_url = reverse('catalog_delete_page', args=['damage-types', self.both.pk])

    def ids(self, **params):
        response = self.client.get(self.list_url, params)
        self.assertEqual(response.status_code, 200)
        return {x['pk'] for x in response.context['entries']}

    def test_filters_combine_with_search_and_support_no(self):
        self.assertEqual(self.ids(is_magic='yes'), {self.magic.pk, self.both.pk})
        self.assertEqual(self.ids(is_regular='yes'), {self.regular.pk, self.both.pk})
        self.assertEqual(self.ids(is_magic='yes', is_regular='yes', search='ог'), {self.both.pk})
        self.assertEqual(self.ids(is_magic='no', is_regular='yes'), {self.regular.pk})
        self.assertEqual(self.ids(is_regular='no'), {self.magic.pk})

    def test_invalid_filter_is_reported(self):
        response = self.client.get(self.list_url, {'is_magic':'invalid'})
        self.assertTrue(response.context['damage_filters'].errors)
        self.assertEqual(response.context['page'].paginator.count, 0)

    def test_pagination_keeps_filters_and_search(self):
        DamageType.objects.bulk_create([DamageType(name=f'Огонь {i}', is_magic=True, is_regular=True) for i in range(25)])
        response = self.client.get(self.list_url, {'is_magic':'yes', 'is_regular':'yes', 'search':'Огонь'})
        self.assertIn('is_magic=yes', response.context['page_query'])
        self.assertIn('is_regular=yes', response.context['page_query'])
        self.assertIn('search=', response.context['page_query'])
        self.assertContains(response, '&amp;page=2')

    def test_creation_redirects_to_unfiltered_list(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse('catalog_create_page', args=['damage-types']), {'name':'Холод', 'is_regular':'on'})
        self.assertRedirects(response, self.list_url)
        self.assertTrue(DamageType.objects.filter(name='Холод', is_regular=True).exists())

    def test_admin_actions_exist_in_both_places(self):
        self.client.force_login(self.staff)
        for url in (self.list_url, self.detail_url):
            self.assertContains(self.client.get(url), self.delete_url)
            self.assertContains(self.client.get(url), reverse('catalog_edit_page', args=['damage-types', self.both.pk]))

    def test_confirmation_get_does_not_delete_post_keeps_effect(self):
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(self.delete_url), 'csrfmiddlewaretoken')
        self.assertTrue(DamageType.objects.filter(pk=self.both.pk).exists())
        self.assertRedirects(self.client.post(self.delete_url), self.list_url)
        self.assertFalse(DamageType.objects.filter(pk=self.both.pk).exists())
        self.effect.refresh_from_db()
        self.assertIsNone(self.effect.damage_type_id)

    def test_readers_cannot_delete_or_see_actions(self):
        self.assertEqual(self.client.post(self.delete_url).status_code, 302)
        self.client.force_login(self.reader)
        for method in (self.client.get, self.client.post):
            self.assertEqual(method(self.delete_url).status_code, 403)
        for url in (self.list_url, self.detail_url):
            self.assertNotContains(self.client.get(url), self.delete_url)
        self.assertTrue(DamageType.objects.filter(pk=self.both.pk).exists())

    def test_delete_requires_csrf_and_rejects_other_catalogs(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.staff)
        self.assertEqual(client.post(self.delete_url).status_code, 403)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.post(reverse('catalog_delete_page', args=['classes', 1])).status_code, 404)
