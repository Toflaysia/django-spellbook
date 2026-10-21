import json
from unittest.mock import patch
from urllib.parse import quote
from django.contrib.auth.models import User
from django.test import TestCase, SimpleTestCase, Client
from django.urls import reverse
from spells.models import Player, Person, Spellbook, Spell, MagicSchool, CharacterClass, MaterialComponent, Effect, DamageType, SpellTime
from spells.templatetags.description_tags import render_description,description_text
from spells.description import DESCRIPTION_PREFIX
from spells.views.play_tools import amount

class CharacterToolsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user=User.objects.create_user('tools-owner')
        cls.other=User.objects.create_user('tools-other')
        cls.person=Person.objects.create(name='Варвара',player=Player.objects.create(user=cls.user),max_hit_points=40,current_hit_points=25,temporary_hit_points=6,gold_coins=10)

    def setUp(self):
        self.client.force_login(self.user)
        self.url=reverse('character_resource_change',args=[self.person.pk])

    def change(self,action,**data):
        response=self.client.post(self.url,{'action':action,**data})
        self.person.refresh_from_db()
        return response

    def test_health_persists_and_uses_temporary_first(self):
        self.assertEqual(self.change('damage',amount='10').status_code,200)
        self.assertEqual((self.person.current_hit_points,self.person.temporary_hit_points),(21,0))
        self.change('heal',amount='10+20')
        self.assertEqual(self.person.current_hit_points,40)
        self.change('temporary',amount='12')
        self.change('temporary',amount='5')
        self.assertEqual(self.person.temporary_hit_points,12)
        self.change('damage',amount='999')
        self.assertEqual((self.person.current_hit_points,self.person.temporary_hit_points),(0,0))

    def test_maximum_and_potion(self):
        self.change('maximum',amount='20')
        self.assertEqual(self.person.current_hit_points,20)
        self.change('damage',amount='21')
        with patch('spells.views.play_tools.secrets.randbelow',return_value=3):
            response=self.change('potion',potion='small')
        self.assertEqual(self.person.current_hit_points,15)
        self.assertIn('10 хитов',response.json()['message'])
        self.assertEqual(self.change('maximum',amount='0').status_code,400)
        self.assertEqual(self.change('potion',potion='invalid').status_code,400)

    def test_coin_balances_exact_and_insufficient_rejected(self):
        self.change('take',coin='silver',amount='85')
        self.change('take',coin='copper',amount='145')
        self.change('give',coin='gold',amount='2')
        result=self.change('take',coin='electrum',amount='1').json()
        self.assertEqual(result['gold_total'],'18.45')
        self.assertEqual(self.change('give',coin='gold',amount='9').status_code,400)
        self.assertEqual(self.person.gold_coins,8)
        self.change('coin_set',coin='copper',amount='0')
        self.assertEqual(self.person.copper_coins,0)
        self.assertEqual(self.change('take',coin='wrong',amount='1').status_code,400)
        self.assertEqual(self.change('take',coin='gold',amount='-2').status_code,400)

    def test_owner_only_and_get_cannot_change(self):
        self.assertEqual(self.client.get(self.url).status_code,405)
        self.client.force_login(self.other)
        self.assertEqual(self.change('heal',amount='1').status_code,404)
        self.assertEqual(self.client.get(reverse('character_detail_page',args=[self.person.pk])).status_code,404)
        self.client.logout()
        self.assertEqual(self.change('take',coin='gold',amount='1').status_code,302)

    def test_csrf_required_for_resource_changes(self):
        client=Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(self.url,{'action':'take','coin':'gold','amount':'100'}).status_code,403)
        self.person.refresh_from_db()
        self.assertEqual(self.person.gold_coins,10)

    def test_character_and_spellbook_lists_open_with_existing_records(self):
        book=Spellbook.objects.create(name='Книга Варвары',owner=self.person)
        characters=self.client.get(reverse('character_list_page'))
        books=self.client.get(reverse('spellbook_list_page'))
        self.assertEqual(characters.status_code,200)
        self.assertEqual(books.status_code,200)
        self.assertContains(characters,self.person.name)
        self.assertContains(books,book.name)
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(reverse('character_list_page')),self.person.name)
        self.assertNotContains(self.client.get(reverse('spellbook_list_page')),book.name)

    def test_equipment_tables_persist_and_card_has_tools(self):
        value=DESCRIPTION_PREFIX+json.dumps([{'type':'text','text':'Рюкзак'},{'type':'table','rows':[['Меч','1']]}])
        self.assertEqual(self.change('equipment',equipment_description=value).status_code,200)
        self.assertIn('Меч',self.person.equipment_description)
        response=self.client.get(reverse('character_detail_page',args=[self.person.pk]))
        self.assertContains(response,'Снаряжение и монеты')
        self.assertContains(response,'coin-calculator')
        self.assertContains(response,'data-description-editor')
        self.assertContains(response,'dice-widget')
        self.assertEqual(self.change('equipment',equipment_description=DESCRIPTION_PREFIX+'bad').status_code,400)
        response=self.client.get(reverse('character_edit_page',args=[self.person.pk]))
        self.assertNotContains(response,'class="dice-widget"')

class SpellFilterAndPreviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user=User.objects.create_user('spell-owner')
        cls.other=User.objects.create_user('spell-other')
        cls.player=Player.objects.create(user=cls.user)
        cls.other_player=Player.objects.create(user=cls.other)
        cls.school=MagicSchool.objects.create(name='Воплощение',description='Огненная магия')
        cls.school2=MagicSchool.objects.create(name='Иллюзия',description='Обман чувств')
        cls.character_class=CharacterClass.objects.create(name='Варвар',description='Воин')
        cls.time=SpellTime.objects.create(time='Действие')
        cls.damage=DamageType.objects.create(name='Огонь')
        cls.effect=Effect.objects.create(name='Ожог',damage_type=cls.damage)
        cls.spell=Spell.objects.create(name='Огненный шар',description='Урон <script>alert(1)</script>',is_official=True,school=cls.school,level=3,time=cls.time,duration='Мгновенно',concentration=True)
        cls.spell.aviable_classes.add(cls.character_class);cls.spell.effects.add(cls.effect)
        cls.custom=Spell.objects.create(name='Огненная искра',description='Моё',is_official=False,created_by=cls.player,school=cls.school,level=0,duration='Мгновенно')
        cls.private=Spell.objects.create(name='Огненный секрет',description='Чужое',is_official=False,created_by=cls.other_player,school=cls.school2,level=1,duration='Минута')
        cls.player.saved_spells.add(cls.spell)
        cls.component=MaterialComponent.objects.create(name='Огненная пыль',cost='10.50',is_consumable=True,is_focus=False)

    def test_combined_filters_and_lowercase_partial(self):
        params={'search':'огн','level':'3','school':self.school.pk,'character_class':self.character_class.pk,'effect':self.effect.pk,'damage_type':self.damage.pk,'concentration':'yes','ritual':'no','time':self.time.pk}
        response=self.client.get(reverse('spell_list_page'),params)
        self.assertEqual(list(response.context['spells']),[self.spell])
        self.assertContains(response,'shared-filter-actions')
        params['ritual']='yes'
        self.assertFalse(self.client.get(reverse('spell_list_page'),params).context['spells'].exists())

    def test_mine_keeps_scope_and_origin(self):
        self.client.force_login(self.user)
        response=self.client.get(reverse('my_spell_list_page'),{'search':'огн'})
        self.assertEqual(set(response.context['spells']),{self.custom,self.spell})
        response=self.client.get(reverse('my_spell_list_page'),{'origin':'custom'})
        self.assertEqual(list(response.context['spells']),[self.custom])
        self.assertFalse(self.client.get(reverse('my_spell_list_page'),{'school':'999999'}).context['spells'].exists())

    def test_link_search_and_preview_scope(self):
        url=reverse('spell_link_search')
        self.assertEqual([s['id'] for s in self.client.get(url,{'search':'огн'}).json()['spells']],[self.spell.pk])
        self.client.force_login(self.user)
        self.assertEqual({s['id'] for s in self.client.get(url,{'search':'огн'}).json()['spells']},{self.spell.pk,self.custom.pk})
        self.assertEqual(self.client.get(reverse('spell_preview',args=[self.private.pk])).status_code,404)
        response=self.client.get(reverse('spell_preview',args=[self.spell.pk]))
        self.assertContains(response,'Огненный шар')
        self.assertNotContains(response,'<script>')
        self.assertNotContains(response,'<html')
        self.client.logout()
        self.assertEqual(self.client.get(reverse('spell_preview',args=[self.custom.pk])).status_code,404)

    def test_component_and_school_filters(self):
        url=reverse('catalog_list_page',args=['components'])
        self.assertEqual(self.client.get(url).status_code,404)
        Spell.objects.create(name='Без школы',description='Текст',is_official=True,duration='Миг')
        url=reverse('catalog_list_page',args=['schools'])
        response=self.client.get(url,{'description':'ОГН','has_spells':'yes','level':'3'})
        self.assertEqual([s['pk'] for s in response.context['entries']],[self.school.pk])
        response=self.client.get(url,{'has_spells':'no'})
        self.assertEqual([s['pk'] for s in response.context['entries']],[self.school2.pk])

class SpellLinkRenderingTests(SimpleTestCase):
    def test_links_in_text_and_table_safe_and_readable(self):
        token='[[spell:42|'+quote('Огненный шар <img src=x onerror=alert(1)>')+']]'
        html=render_description('До '+token+' после <script>x</script>')
        self.assertIn('data-spell-id="42"',html)
        self.assertNotIn('<img',html);self.assertNotIn('<script>',html)
        self.assertIn('Огненный шар',description_text(token))
        value=DESCRIPTION_PREFIX+json.dumps([{'type':'table','rows':[[token]]}])
        self.assertIn('data-spell-id="42"',render_description(value))

    def test_amount_never_evaluates_code(self):
        self.assertEqual(amount('10+5-2'),13)
        for value in ('-1','1.5','1/0','__import__("os")','1e10','1000000001','1-2'):
            with self.assertRaises(ValueError):amount(value)
