import json
from urllib.parse import unquote
from django.test import TestCase,Client
from django.contrib.auth.models import User,AnonymousUser
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.db import IntegrityError
from unittest.mock import patch
from spells.models import Spell,SpellTime,MagicSchool,CharacterClass,Effect,Trait,DamageType,MaterialComponent,Player
from spells.import_links import ImportLinker,dice_formula
from spells.description import DESCRIPTION_PREFIX
from spells.templatetags.description_tags import render_description,description_text
from spells.bulk_import import import_spell_records
from spells.views.bulk_import import BulkSpellImportForm

class JsonImportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin=User.objects.create_user('json-admin',is_staff=True)
        cls.user=User.objects.create_user('json-user')
        cls.player=Player.objects.create(user=cls.user)
        cls.time=SpellTime.objects.create(time='Действие')
        cls.school=MagicSchool.objects.create(name='Воплощение')
        cls.cls=CharacterClass.objects.create(name='Воин')
        cls.private_cls=CharacterClass.objects.create(name='Секретный класс',is_official=False,created_by=cls.player)
        cls.condition=Effect.objects.create(name='Испуганный',category='COND')
        cls.effect=Effect.objects.create(name='Замедление',category='CTRL')
        cls.damage=DamageType.objects.create(name='Некротический')
        cls.trait=Trait.objects.create(name='Бдительный')
        cls.component=MaterialComponent.objects.create(name='Алмаз')
        cls.private=Spell.objects.create(name='Тайное заклинание',description='Текст',duration='Миг',is_official=False,created_by=cls.player)

    def native(self,name='Импорт',**overrides):
        data={'name':name,'description':'Брось 2к6+3. Цель становится испуганным. Для воина. Воплощение. Бдительный. Замедление. Некротический. Алмаз. Действие.','level':1,'school':'Воплощение','time':'Действие','duration':'Минута','higher_level':'Добавь 1d8.'}
        data.update(overrides);return data

    def upload(self,data):
        return SimpleUploadedFile('spells.json',json.dumps(data,ensure_ascii=False).encode(),content_type='application/json')

    def test_dice_notations_limits_and_sentence_end(self):
        linker=ImportLinker(AnonymousUser())
        for text in ['2d6','2D6','2к6','2К6','2д6','2k6','d20','2 к 6 + 3','2d6+1к4-3','2d20kh1']:
            html=str(render_description(linker.description(text+'.')))
            self.assertIn('data-dice-expression=',html,text)
            self.assertIn(text,description_text(linker.description(text)),text)
        for text in ['101d6','1d1','1d1001','2d6kh3','200d6','1d6+1000001']:
            self.assertIsNone(dice_formula(text),text)
        for text in ['код2d6','2d6текст','1d6.5','https://example.test/d20file']:
            self.assertNotIn('[[dice:',linker.description(text),text)
        value=linker.description('[[/r 2к6+3]] и [[1d20]]')
        self.assertEqual(value.count('[[dice:'),2)

    def test_catalog_links_inflections_original_labels_and_privacy(self):
        poison=DamageType.objects.create(name='Яд')
        self.assertIn('[[damage:'+str(poison.pk)+'|',ImportLinker(AnonymousUser()).description('Яд.'))
        value=ImportLinker(AnonymousUser()).description(self.native()['description']+' Тайное заклинание. Секретный класс.')
        for kind in ('dice','condition','class','school','trait','effect','damage','time'):
            self.assertIn('[['+kind+':',value,kind)
        self.assertNotIn('[[spell:',value)
        self.assertEqual(value.count('[[class:'),1)
        html=str(render_description(value))
        for slug,item in [('conditions',self.condition),('effects',self.effect),('classes',self.cls),('schools',self.school),('traits',self.trait),('damage-types',self.damage),('casting-times',self.time)]:
            self.assertIn(reverse('catalog_detail_page',args=[slug,item.pk]),html)
        self.assertIn('испуганным',html)
        self.assertIn('воина',html)
        self.assertNotIn('data-catalog-kind="classes"',html)

    def test_ambiguity_is_reported_and_existing_tokens_are_idempotent(self):
        Trait.objects.create(name='Воин')
        linker=ImportLinker(AnonymousUser());text='Воин. [[condition:12|'+ 'испуганным' +']] 2к6.'
        value=linker.description(text)
        self.assertTrue(value.startswith('Воин.'))
        self.assertTrue(any('Неоднозначная' in warning for warning in linker.warnings))
        self.assertEqual(linker.description(value),value)
        self.assertIn('[[condition:12|испуганным]]',value)

    def test_links_in_structured_blocks_and_html_escaping(self):
        text='Испуганный 2d6'
        blocks=[{'type':'text','text':text},{'type':'heading','text':text},{'type':'quote','text':text},{'type':'list','items':[text]},{'type':'table','rows':[[text]]}]
        value=ImportLinker(AnonymousUser()).description(DESCRIPTION_PREFIX+json.dumps(blocks))
        self.assertEqual(value.count('[[condition:'),5)
        self.assertEqual(value.count('[[dice:'),5)
        html=str(render_description('[[effect:1|%3Cscript%3Ealert%281%29%3C%2Fscript%3E]]'))
        self.assertNotIn('<script>',html);self.assertIn('&lt;script&gt;',html)
        for kind in ('class','effect','component','time'):
            self.assertNotIn('<a',str(render_description('[['+kind+':javascript%3Aalert%281%29|X]]')))

    def test_bulk_partial_success_forward_links_and_duplicate_protection(self):
        original=Spell.objects.create(name='Уже есть',description='Не менять',duration='Миг')
        report=import_spell_records([self.native('Первое',description='Второе наносит 2к6.'),self.native('Второе'),self.native('  УЖЕ   ЕСТЬ  '),self.native('Плохое',school='Нет школы'),self.native('первое'),42],self.admin)
        self.assertEqual((report['created'],report['duplicates'],report['errors']),(2,2,2))
        first=Spell.objects.get(name='Первое');second=Spell.objects.get(name='Второе')
        self.assertIn('[[spell:'+str(second.pk)+'|',first.description)
        self.assertTrue(first.is_official);self.assertFalse(first.is_public)
        original.refresh_from_db();self.assertEqual(original.description,'Не менять')
        self.assertFalse(Spell.objects.filter(name='Плохое').exists())
        self.assertTrue(report['rows'][3]['messages'])
        self.assertEqual(import_spell_records([self.native('Первое'),self.native('Второе')],self.admin)['duplicates'],2)

    def test_foundry_payload_and_invalid_records(self):
        data={'name':'Foundry','type':'spell','system':{'school':'evo','level':3,'activation':{'type':'action','cost':1},'duration':{'units':'inst'},'description':{'value':'<p>Испуганный: 8d6.</p>'}}}
        report=import_spell_records([data,{'name':'Не заклинание','type':'weapon'},self.native('Неверный уровень',level=99),self.native('Неверная школа',school=99999),self.native('Булево',ritual='false'),self.native('Нет описания',description=None)],self.admin)
        self.assertEqual((report['created'],report['errors']),(1,5),report)
        self.assertIn('[[dice:8d6|8d6]]',Spell.objects.get(name='Foundry').description)

    def test_native_metadata_cannot_change_authority(self):
        report=import_spell_records([self.native('Без подмены',is_official=False,is_public=True,created_by=self.player.pk)],self.admin)
        self.assertEqual(report['created'],1)
        spell=Spell.objects.get(name='Без подмены')
        self.assertTrue(spell.is_official);self.assertFalse(spell.is_public)
        self.assertEqual(spell.created_by.user,self.admin)

    def test_admin_report_and_authorization(self):
        url=reverse('bulk_spell_import_page')
        self.assertEqual(self.client.get(url).status_code,302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(url,{'json_file':self.upload([self.native()])}).status_code,403)
        self.client.force_login(self.admin)
        response=self.client.post(url,{'json_file':self.upload({'spells':[self.native(),self.native('Ошибка',time='Нет времени')]})})
        self.assertContains(response,'Загружено: 1')
        self.assertContains(response,'Ошибок: 1')
        self.assertContains(response,'Нет времени')
        self.assertNotContains(response,'Traceback')
        client=Client(enforce_csrf_checks=True);client.force_login(self.admin)
        self.assertEqual(client.post(url,{'json_file':self.upload([self.native('CSRF')])}).status_code,403)

    def test_invalid_files_limits_and_wrappers(self):
        for data in [[],{'spells':'wrong'},[{}]*501]:
            form=BulkSpellImportForm(files={'json_file':self.upload(data)})
            self.assertFalse(form.is_valid())
        for data in [[self.native()],{'items':[self.native()]},self.native()]:
            form=BulkSpellImportForm(files={'json_file':self.upload(data)})
            self.assertTrue(form.is_valid(),form.errors)
        form=BulkSpellImportForm(files={'json_file':SimpleUploadedFile('x.json',b'{bad')})
        self.assertFalse(form.is_valid())
        form=BulkSpellImportForm(files={'json_file':SimpleUploadedFile('x.json',b' '*(5*1024*1024+1))})
        self.assertFalse(form.is_valid())

    def test_single_import_links_and_conversion_errors_return_form(self):
        self.client.force_login(self.admin)
        response=self.client.post(reverse('official_spell_import_page'),{'json_file':self.upload(self.native())})
        self.assertEqual(response.status_code,200)
        self.assertIn('[[dice:',response.context['form'].initial['description'])
        self.assertFalse(Spell.objects.filter(name='Импорт').exists())
        response=self.client.post(reverse('official_spell_import_page'),{'json_file':self.upload(self.native(school='Нет школы'))})
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.context['form'].errors)

    def test_unexpected_failure_rolls_back_batch_and_reports_to_admin(self):
        self.client.force_login(self.admin)
        with self.assertLogs('spells.views.bulk_import',level='ERROR'), patch('spells.bulk_import.ImportLinker',side_effect=RuntimeError('internal')):
            response=self.client.post(reverse('bulk_spell_import_page'),{'json_file':self.upload([self.native('Откат')])})
        self.assertContains(response,'Изменения этой загрузки отменены')
        self.assertFalse(Spell.objects.filter(name='Откат').exists())
