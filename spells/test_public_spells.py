from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APIClient
from spells.models import Spell, Player, Person, Spellbook, MagicSchool, SpellTime
from spells.forms import CustomSpellForm, SpellbookForm

class PublicSpellTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author=User.objects.create_user('spell-author')
        cls.reader=User.objects.create_user('spell-reader')
        cls.staff=User.objects.create_user('spell-admin',is_staff=True)
        cls.player=Player.objects.create(user=cls.author)
        cls.reader_player=Player.objects.create(user=cls.reader)
        cls.school=MagicSchool.objects.create(name='Воплощение')
        cls.time=SpellTime.objects.create(time='Действие')
        cls.official=Spell.objects.create(name='Официальный огонь',description='Текст',duration='Миг',is_official=True,school=cls.school,level=3)
        cls.public=Spell.objects.create(name='Публичная искра',description='Описание',duration='Миг',is_official=False,is_public=True,created_by=cls.player,school=cls.school,level=1)
        cls.private=Spell.objects.create(name='Приватная тайна',description='Секрет',duration='Миг',is_official=False,created_by=cls.player)
        cls.person=Person.objects.create(name='Читатель',player=cls.reader_player)
        cls.book=Spellbook.objects.create(name='Книга',owner=cls.person)
        cls.book.spells.add(cls.public)

    def url(self,name,*args):
        return reverse(name,args=args)

    def form_data(self,spell=None,**changes):
        spell=spell or self.public
        data={'school':self.school.pk,'time':self.time.pk,'name':spell.name,'level':spell.level,'description':spell.description,'duration':spell.duration,'attack_type':spell.attack_type}
        data.update(changes)
        return data

    def test_visibility_matrix_and_search_preview_api(self):
        for user in (None,self.reader,self.staff,self.author):
            if user:self.client.force_login(user)
            else:self.client.logout()
            for spell in (self.official,self.public,self.private):
                allowed=spell!=self.private or user==self.author
                for name in ('spell_detail_page','spell_preview','spells:spell_detail'):
                    self.assertEqual(self.client.get(self.url(name,spell.pk)).status_code,200 if allowed else 404,(user,name,spell.name))
            search=self.client.get(self.url('spell_link_search')).json()['spells']
            self.assertIn(self.public.pk,[item['id'] for item in search])
            self.assertEqual(self.private.pk in [item['id'] for item in search],user==self.author)

    def test_catalogs_filters_author_and_reset_stay_in_group(self):
        url=self.url('spell_list_page')
        official=self.client.get(url)
        self.assertContains(official,self.official.name)
        self.assertNotContains(official,self.public.name)
        public=self.client.get(url,{'group':'unofficial','level':'1','school':self.school.pk})
        self.assertContains(public,self.public.name)
        self.assertContains(public,'Автор: spell-author')
        self.assertNotContains(public,self.official.name)
        self.assertNotContains(public,self.private.name)
        self.assertContains(public,'type="hidden" name="group" value="unofficial"')
        self.assertContains(public,'href="/spells/?group=unofficial">Сбросить')
        self.assertNotContains(self.client.get(url,{'group':'unofficial','level':'3'}),self.public.name)
        self.assertEqual(self.client.get(url,{'group':'anything'}).status_code,404)
        api=self.client.get(self.url('spells:spell_list'),{'group':'unofficial'}).json()
        self.assertEqual([item['id'] for item in api],[self.public.pk])
        self.assertEqual(api[0]['author_name'],self.author.username)
        self.assertEqual(self.client.get(self.url('spells:spell_list'),{'group':'anything'}).status_code,400)

    def test_html_author_create_publish_unpublish_and_spoof_protection(self):
        self.client.force_login(self.author)
        form=self.client.get(self.url('spell_create_page')).context['form']
        self.assertFalse(form['is_public'].value())
        response=self.client.post(self.url('spell_create_page'),self.form_data(name='Новое приватное',created_by=self.reader_player.pk,is_official='on'))
        self.assertEqual(response.status_code,302,response.context["form"].errors if response.context else None)
        spell=Spell.objects.get(name='Новое приватное')
        self.assertFalse(spell.is_public)
        self.assertFalse(spell.is_official)
        self.assertEqual(spell.created_by,self.player)
        response=self.client.post(self.url('spell_edit_page',spell.pk),self.form_data(spell,is_public='on'))
        self.assertEqual(response.status_code,302)
        spell.refresh_from_db();self.assertTrue(spell.is_public)
        response=self.client.post(self.url('spell_edit_page',spell.pk),self.form_data(spell))
        self.assertEqual(response.status_code,302)
        spell.refresh_from_db();self.assertFalse(spell.is_public)
        self.client.force_login(self.staff)
        self.assertNotIn('is_public',self.client.get(self.url('spell_edit_page',self.official.pk)).context['form'].fields)

    def test_readers_can_save_but_cannot_edit_or_delete(self):
        self.client.force_login(self.reader)
        response=self.client.get(self.url('spell_detail_page',self.public.pk))
        self.assertContains(response,'Добавить в мои заклинания')
        self.assertNotContains(response,self.url('spell_edit_page',self.public.pk))
        for user in (self.reader,self.staff):
            self.client.force_login(user)
            for name in ('spell_edit_page','spell_delete_page'):
                for method in ('get','post'):
                    self.assertEqual(getattr(self.client,method)(self.url(name,self.public.pk),self.form_data()).status_code,404)
        self.client.force_login(self.reader)
        self.assertEqual(self.client.post(self.url('spell_save_page',self.private.pk)).status_code,404)
        self.assertEqual(self.client.get(self.url('spell_save_page',self.public.pk)).status_code,405)
        for _ in range(2):self.assertEqual(self.client.post(self.url('spell_save_page',self.public.pk)).status_code,302)
        self.assertEqual(self.reader_player.saved_spells.filter(pk=self.public.pk).count(),1)
        response=self.client.get(self.url('my_spell_list_page'))
        self.assertContains(response,self.public.name)
        self.assertContains(response,'Убрать из моих')
        self.assertNotContains(response,self.url('spell_edit_page',self.public.pk))
        self.assertIn(self.public,SpellbookForm(user=self.reader).fields['spells'].queryset)
        self.assertEqual(self.client.post(self.url('spell_unsave_page',self.public.pk)).status_code,302)
        self.assertNotContains(self.client.get(self.url('my_spell_list_page')),self.public.name)

    def test_withdrawal_hides_saved_and_book_entries_without_deleting_them(self):
        self.reader_player.saved_spells.add(self.public)
        self.public.is_public=False;self.public.save()
        self.client.force_login(self.reader)
        self.assertNotContains(self.client.get(self.url('my_spell_list_page')),self.public.name)
        self.assertNotContains(self.client.get(self.url('spellbook_detail_page',self.book.pk)),self.public.name)
        response=self.client.get(self.url('spells:spellbook_detail',self.book.pk))
        self.assertEqual(response.json()['spells'],[])
        self.assertEqual(response.json()['total_spells'],0)
        self.assertNotIn(self.public,SpellbookForm(user=self.reader).fields['spells'].queryset)
        self.assertTrue(self.book.spells.filter(pk=self.public.pk).exists())
        self.public.is_public=True;self.public.save()
        self.assertContains(self.client.get(self.url('my_spell_list_page')),self.public.name)

    def test_api_publication_and_book_private_validation(self):
        client=APIClient();client.force_authenticate(user=self.author)
        response=client.post(self.url('spells:custom_spell_list'),self.form_data(name='API запись',is_public=True,created_by=self.reader_player.pk,is_official=True),format='json')
        self.assertEqual(response.status_code,201,response.data)
        spell=Spell.objects.get(pk=response.data['id'])
        self.assertEqual(spell.created_by,self.player)
        self.assertFalse(spell.is_official);self.assertTrue(spell.is_public)
        response=client.patch(self.url('spells:custom_spell_detail',spell.pk),{'is_public':False},format='json')
        self.assertEqual(response.status_code,200,response.data)
        client.force_authenticate(user=self.reader)
        self.assertEqual(client.patch(self.url('spells:custom_spell_detail',spell.pk),{'is_public':True},format='json').status_code,404)
        url=self.url('spells:spellbook_detail',self.book.pk)
        response=client.patch(url,{'spells':[self.public.pk]},format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['spells'],[self.public.pk])
        response=client.patch(url,{'spells':[self.private.pk]},format='json')
        self.assertEqual(response.status_code,400,response.data)

    def test_csrf_for_publish_and_save(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.author)
        self.assertEqual(client.post(self.url('spell_edit_page',self.private.pk),self.form_data(self.private,is_public='on')).status_code,403)
        client.force_login(self.reader)
        self.assertEqual(client.post(self.url('spell_save_page',self.public.pk)).status_code,403)
