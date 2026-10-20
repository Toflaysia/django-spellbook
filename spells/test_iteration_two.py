import json
from urllib.parse import quote
from django import forms
from django.contrib.auth.models import User
from django.test import TestCase, SimpleTestCase
from django.urls import reverse
from spells.description import DESCRIPTION_PREFIX, parse_description, DescriptionModelForm
from spells.models import DamageType, Effect, MagicSchool, Spell, Player
from spells.templatetags.description_tags import render_description, description_text
from spells.views.class_pages import ClassFeatureForm
from spells.models import CharacterClass

class InlineLinkTests(SimpleTestCase):
    def test_all_links_render_safely_in_every_block_and_plain_text(self):
        label = 'Огонь <script>alert(1)</script>'
        tokens = ' '.join([
            '[[spell:42|'+quote(label)+']]',
            '[[damage:3|'+quote(label)+']]',
            '[[condition:5|'+quote(label)+']]',
            '[[school:7|'+quote(label)+']]',
            '[[dice:2d6%2B3|2d6%2B3]]',
        ])
        blocks = [
            {'type': 'text', 'text': tokens},
            {'type': 'quote', 'text': tokens},
            {'type': 'heading', 'text': tokens},
            {'type': 'list', 'items': [tokens]},
            {'type': 'table', 'rows': [[tokens]]},
        ]
        encoded = DESCRIPTION_PREFIX + json.dumps(blocks)
        self.assertEqual(parse_description(encoded), blocks)
        for value in (tokens, encoded):
            html = render_description(value)
            self.assertNotIn('<script>', html)
            for attr in ['data-spell-id="42"', 'data-catalog-kind="damage-types"', 'data-catalog-kind="effects"', 'data-catalog-kind="schools"', 'data-dice-expression="2d6+3"']:
                self.assertIn(attr, html)
            self.assertNotIn('[[', description_text(value))
            self.assertIn('2d6+3', description_text(value))

    def test_admin_media_keeps_cache_query_out_of_static_filename(self):
        media = str(forms.Media(DescriptionModelForm.Media))
        self.assertIn('/static/spells/play_tools.js?v=', media)
        self.assertNotIn('%3F', media)

    def test_malformed_ids_and_dice_never_create_active_attributes(self):
        for token in ['[[damage:javascript:alert(1)|x]]', '[[school:1%22%20onclick%3Dx|x]]', '[[dice:eval(1)|x]]', '[[dice:2d6%22%20onclick%3Dx|x]]']:
            html = render_description(token)
            self.assertNotIn('data-catalog-id', html)
            self.assertNotIn('data-dice-expression', html)

class CatalogLinkTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.damage = DamageType.objects.create(name='Огонь', description='Пламя <script>x</script>')
        cls.condition = Effect.objects.create(name='Ослепление', category='COND', description='Текст', damage_type=cls.damage)
        cls.buff = Effect.objects.create(name='Усиление', category='BUFF', description='Текст')
        cls.school = MagicSchool.objects.create(name='Воплощение', description='Магия')
        cls.spell = Spell.objects.create(name='Тест', description='Описание', is_official=True, school=cls.school, duration='Миг')
        cls.owner = User.objects.create_user('owner')
        cls.player = Player.objects.create(user=cls.owner)
        cls.private = Spell.objects.create(name='Секрет', description='Приватно', is_official=False, created_by=cls.player, duration='Миг')

    def test_searches_and_previews_are_public_and_condition_specific(self):
        for slug, item in [('damage-types', self.damage), ('effects', self.condition), ('schools', self.school)]:
            response = self.client.get(reverse('catalog_link_search', args=[slug]), {'search': item.name})
            self.assertEqual(response.json()['items'], [{'id': item.pk, 'name': item.name}])
            response = self.client.get(reverse('catalog_preview', args=[slug, item.pk]))
            self.assertContains(response, item.name)
            self.assertNotContains(response, '<script>')
            self.assertNotContains(response, '<html')
        self.assertEqual(self.client.get(reverse('catalog_preview', args=['effects', self.buff.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('catalog_preview', args=['characters', 1])).status_code, 404)
        self.assertEqual(self.client.get(reverse('catalog_link_search', args=['components'])).status_code, 404)
        self.assertEqual(self.client.get(reverse('catalog_preview', args=['schools', 999999])).status_code, 404)

    def test_school_link_in_spell_page_and_preview_and_private_scope(self):
        for name in ['spell_detail_page', 'spell_preview']:
            response = self.client.get(reverse(name, args=[self.spell.pk]))
            self.assertContains(response, 'data-catalog-kind="schools"')
            self.assertContains(response, f'data-catalog-id="{self.school.pk}"')
        self.assertEqual(self.client.get(reverse('spell_preview', args=[self.private.pk])).status_code, 404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse('spell_preview', args=[self.private.pk])).status_code, 200)

    def test_editor_forms_expose_catalog_endpoints(self):
        form = ClassFeatureForm(character_class=CharacterClass(pk=1))
        attrs = form.fields['description'].widget.attrs
        self.assertEqual(attrs['data-catalog-search-url'], reverse('catalog_link_search', args=['schools']))
        self.assertEqual(attrs['data-catalog-preview-url'], reverse('catalog_preview', args=['schools', 0]))
