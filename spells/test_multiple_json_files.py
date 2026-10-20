import json
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from spells.models import MagicSchool,SpellTime,Spell
from spells.views.bulk_import import BulkSpellImportForm

class MultipleJSONFilesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin=User.objects.create_user('multi-json',is_staff=True)
        MagicSchool.objects.create(name='Воплощение')
        SpellTime.objects.create(time='Действие')

    def record(self,name,**changes):
        data={'name':name,'description':'Текст 2к6.','school':'Воплощение','time':'Действие','duration':'Миг'}
        data.update(changes);return data

    def file(self,name,data):
        return SimpleUploadedFile(name,json.dumps(data,ensure_ascii=False).encode(),content_type='application/json')

    def test_picker_allows_multiple_and_all_files_import_with_cross_references(self):
        self.client.force_login(self.admin)
        url=reverse('bulk_spell_import_page')
        self.assertContains(self.client.get(url),'multiple')
        response=self.client.post(url,{'json_file':[self.file('one.json',self.record('Первый',description='Второй: 2к6.')),self.file('two.json',{'spells':[self.record('Второй'),self.record('ПЕРВЫЙ')]})]})
        self.assertContains(response,'Загружено: 2')
        self.assertContains(response,'Дубликатов: 1')
        self.assertContains(response,'Файл: one.json')
        self.assertContains(response,'Файл: two.json')
        second=Spell.objects.get(name='Второй')
        self.assertIn('[[spell:'+str(second.pk)+'|',Spell.objects.get(name='Первый').description)

    def test_broken_or_empty_file_does_not_block_valid_files(self):
        self.client.force_login(self.admin)
        response=self.client.post(reverse('bulk_spell_import_page'),{'json_file':[self.file('valid.json',self.record('Рабочий')),SimpleUploadedFile('broken.json',b'{bad'),SimpleUploadedFile('empty.json',b'')]})
        self.assertContains(response,'Загружено: 1')
        self.assertContains(response,'Ошибок: 2')
        self.assertContains(response,'broken.json')
        self.assertContains(response,'empty.json')
        self.assertContains(response,'Не удалось прочитать JSON')
        self.assertTrue(Spell.objects.filter(name='Рабочий').exists())

    def test_global_limits_do_not_import_partial_selection(self):
        self.client.force_login(self.admin)
        files=[self.file('a.json',[self.record('A')]*300),self.file('b.json',[self.record('B')]*201)]
        response=self.client.post(reverse('bulk_spell_import_page'),{'json_file':files})
        self.assertContains(response,'больше 500 записей')
        self.assertEqual(Spell.objects.count(),0)
        form=BulkSpellImportForm(files={'json_file':[self.file(str(n)+'.json',self.record(str(n))) for n in range(101)]})
        self.assertFalse(form.is_valid())
        form=BulkSpellImportForm(files={'json_file':[SimpleUploadedFile(str(n)+'.json',b' '*(5*1024*1024)) for n in range(5)]})
        self.assertFalse(form.is_valid())
