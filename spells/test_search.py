from django.contrib.auth.models import User
from django.db import connection
from django.db.models import F, Value
from django.test import TestCase
from django.urls import reverse

from spells.models import (
    CharacterClass, DamageType, Effect, MagicSchool, MaterialComponent,
    Person, Player, Spell, Spellbook, SpellTime,
)


class UnicodeSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('search-owner')
        cls.other_user = User.objects.create_user('search-other')
        cls.player = Player.objects.create(user=cls.user)
        cls.other_player = Player.objects.create(user=cls.other_user)
        cls.character_class = CharacterClass.objects.create(name='Варвар', description='Описание')
        cls.person = Person.objects.create(name='Варвара', player=cls.player)
        cls.other_person = Person.objects.create(name='Варвара чужая', player=cls.other_player)
        cls.book = Spellbook.objects.create(name='Книга Варвара', owner=cls.person)
        Spellbook.objects.create(name='Книга Варвара чужая', owner=cls.other_person)
        cls.official = Spell.objects.create(name='Варварская сила', description='Мощь', duration='Минута', is_official=True)
        cls.custom = Spell.objects.create(name='Варварский крик', description='Мощь', duration='Минута', is_official=False, created_by=cls.player)
        Spell.objects.create(name='Варварский чужой крик', description='Мощь', duration='Минута', is_official=False, created_by=cls.other_player)

    def test_class_search_partial_and_case_insensitive(self):
        url = reverse('catalog_list_page', args=['classes'])
        for term in ('ва', 'варвар', 'ВАРВАР', 'рв', '  вАр  '):
            with self.subTest(term=term):
                response = self.client.get(url, {'search': term})
                self.assertEqual([x['pk'] for x in response.context['entries']], [self.character_class.pk])

    def test_every_reference_catalog(self):
        fixtures = [
            ('schools', MagicSchool, {'name': 'Варварская магия'}),
            ('effects', Effect, {'name': 'Варварская ярость'}),
            ('components', MaterialComponent, {'name': 'Варварский амулет'}),
            ('casting-times', SpellTime, {'time': 'Варварское действие'}),
            ('damage-types', DamageType, {'name': 'Варварский урон'}),
        ]
        for slug, model, fields in fixtures:
            with self.subTest(slug=slug):
                item = model.objects.create(description='Описание', **fields)
                response = self.client.get(reverse('catalog_list_page', args=[slug]), {'search': 'вар'})
                self.assertEqual([x['pk'] for x in response.context['entries']], [item.pk])

    def test_personal_pages_keep_ownership_filter(self):
        self.client.force_login(self.user)
        for name, key, item in (
            ('character_list_page', 'characters', self.person),
            ('my_spell_list_page', 'spells', self.custom),
            ('spellbook_list_page', 'spellbooks', self.book),
        ):
            with self.subTest(page=name):
                response = self.client.get(reverse(name), {'search': 'вар'})
                self.assertEqual([x.pk for x in response.context[key]], [item.pk])

    def test_official_spells_page(self):
        response = self.client.get(reverse('spell_list_page'), {'search': 'вар'})
        self.assertEqual([x.pk for x in response.context['spells']], [self.official.pk])

    def test_spellbook_search_by_owner_name(self):
        self.book.name = 'Запас магии'
        self.book.save(update_fields=['name'])
        self.client.force_login(self.user)
        response = self.client.get(reverse('spellbook_list_page'), {'search': 'ВАРВАРА'})
        self.assertEqual([x.pk for x in response.context['spellbooks']], [self.book.pk])

    def test_api_search_uses_same_unicode_matching(self):
        self.client.force_login(self.user)
        for name, item in (
            ('spells:spell_list', self.official),
            ('spells:character_list', self.person),
            ('spells:custom_spell_list', self.custom),
        ):
            with self.subTest(api=name):
                response = self.client.get(reverse(name), {'search': 'вар'})
                self.assertEqual(response.status_code, 200)
                data = response.json()
                if isinstance(data, dict):
                    data = data['results']
                self.assertEqual([x['id'] for x in data], [item.pk])

    def test_literal_special_characters_and_sql_parameters(self):
        item = CharacterClass.objects.create(name="Маг 100%_\\'", description='Текст')
        for term in ('%', '_', '\\', "'"):
            with self.subTest(term=term):
                self.assertEqual(list(CharacterClass.objects.filter(name__icontains=term)), [item])
        self.assertFalse(CharacterClass.objects.filter(name__icontains="' OR 1=1 --").exists())
        self.assertFalse(CharacterClass.objects.filter(name__icontains='неизвестное').exists())
        self.assertTrue(CharacterClass.objects.filter(name__icontains=Value('вар')).exists())
        self.assertEqual(CharacterClass.objects.filter(name__icontains=F('name')).count(), 2)
        self.assertEqual(CharacterClass.objects.exclude(name__icontains='ВАР').count(), 1)

    def test_unicode_text_nulls_and_connection_function(self):
        MaterialComponent.objects.create(name='Ёлка', description=None)
        self.assertTrue(MaterialComponent.objects.filter(name__icontains='ёл').exists())
        self.assertFalse(MaterialComponent.objects.filter(description__icontains='текст').exists())
        if connection.vendor == 'sqlite':
            with connection.cursor() as cursor:
                cursor.execute('SELECT spellbook_casefold(%s)', ['ВАРВАР'])
                self.assertEqual(cursor.fetchone()[0], 'варвар')
