from io import BytesIO
from tempfile import TemporaryDirectory
from urllib.parse import quote
from PIL import Image
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from spells.models import CharacterClass, ClassFeature, ClassSection, Subclass, Player, Trait, Person, Spell
from spells.templatetags.description_tags import render_description, description_text
from spells.forms import CharacterCreateForm, CustomSpellForm
from spells.progression import preset_columns
import json

class ClassOwnershipTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner=User.objects.create_user('owner',password='password123')
        cls.reader=User.objects.create_user('reader',password='password123')
        cls.staff=User.objects.create_user('staff',is_staff=True)
        cls.player=Player.objects.create(user=cls.owner)
        cls.other_player=Player.objects.create(user=cls.reader)
        cls.official=CharacterClass.objects.create(name='Бард',description='Общий')
        cls.unofficial=CharacterClass.objects.create(name='Мистик',description='Неофициальный',is_official=False)
        cls.private=CharacterClass.objects.create(name='Скрытый класс',description='Секрет',is_official=False,created_by=cls.player)
        cls.public=CharacterClass.objects.create(name='Открытый класс',description='Публичный',is_official=False,created_by=cls.player,is_public=True)
        cls.sub=Subclass.objects.create(name='Архетип',description='Описание',character_class=cls.private)
        cls.feature=ClassFeature.objects.create(character_class=cls.private,subclass=cls.sub,name='Умение',description='Описание',level=3)
        cls.section=ClassSection.objects.create(character_class=cls.private,title='Раздел',description='Описание')

    def test_catalog_groups_and_api_privacy(self):
        url=reverse('catalog_list_page',args=['classes'])
        self.assertEqual([e['pk'] for e in self.client.get(url).context['entries']],[self.official.pk])
        unofficial=self.client.get(url,{'group':'unofficial'})
        self.assertEqual({e['pk'] for e in unofficial.context['entries']},{self.unofficial.pk,self.public.pk})
        self.assertNotContains(unofficial,self.private.name)
        self.client.force_login(self.owner)
        own=self.client.get(url,{'group':'mine'})
        self.assertEqual({e['pk'] for e in own.context['entries']},{self.private.pk,self.public.pk})
        self.client.force_login(self.reader)
        data=self.client.get(reverse('spells:character_class_list')).json()
        rows=data.get('results',[]) if isinstance(data,dict) else data
        self.assertNotIn(self.private.pk,{row['id'] for row in rows})
        data=self.client.get(reverse('spells:subclass_list')).json()
        rows=data.get('results',[]) if isinstance(data,dict) else data
        self.assertNotIn(self.sub.pk,{row['id'] for row in rows})
        for item,status in [(self.private,404),(self.public,200)]:
            self.assertEqual(self.client.get(reverse('class_detail_page',args=[item.pk])).status_code,status)
        self.assertEqual(self.client.get(reverse('class_detail_page',args=[self.private.pk]),{'subclass':self.sub.pk}).status_code,404)

    def test_create_class_sets_owner_and_rejects_spoofed_official_flag(self):
        self.client.force_login(self.reader)
        data={'name':'Бард','description':'Мой бард','magic_type':'NC','hit_die':'8','spellcasting_ability':'WIS','is_official':'on','created_by':self.player.pk,'is_public':'on'}
        response=self.client.post(reverse('user_class_create_page'),data)
        self.assertEqual(response.status_code,302)
        item=CharacterClass.objects.get(name='Бард',created_by=self.other_player)
        self.assertFalse(item.is_official);self.assertTrue(item.is_public)
        response=self.client.post(reverse('user_class_create_page'),data)
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.context['form'].errors)
        self.client.force_login(self.owner)
        data['is_public']=''
        self.assertEqual(self.client.post(reverse('user_class_create_page'),data).status_code,302)
        self.assertFalse(CharacterClass.objects.get(name='Бард',created_by=self.player).is_public)

    def test_ownership_applies_to_all_child_editors(self):
        edit_routes=[('class_feature_edit_page',[self.private.pk,self.feature.pk]),('class_section_edit_page',[self.private.pk,self.section.pk]),('subclass_edit_page',[self.private.pk,self.sub.pk]),('subclass_table_edit_page',[self.private.pk,self.sub.pk]),('class_table_edit_page',[self.private.pk]),('catalog_edit_page',['classes',self.private.pk])]
        for user,status in [(self.reader,404),(self.owner,200),(self.staff,200)]:
            self.client.force_login(user)
            for name,args in edit_routes:
                with self.subTest(user=user.username,route=name):self.assertEqual(self.client.get(reverse(name,args=args)).status_code,status)
        self.client.force_login(self.reader)
        self.assertEqual(self.client.post(reverse('catalog_edit_page',args=['classes',self.public.pk]),{}).status_code,403)
        self.assertEqual(self.client.post(reverse('class_section_create_page',args=[self.official.pk]),{}).status_code,403)

    def test_owner_can_create_edit_and_keep_child_bindings(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(reverse('class_feature_edit_page',args=[self.private.pk,self.feature.pk]),{'name':'Новое умение','levels':'3, 5','subclass':self.sub.pk,'description':'Текст','is_optional':'on'}).status_code,302)
        self.feature.refresh_from_db();self.assertEqual(self.feature.character_class_id,self.private.pk);self.assertEqual(self.feature.subclass_id,self.sub.pk)
        self.assertEqual(self.client.post(reverse('class_table_edit_page',args=[self.private.pk]),{'table_type':'fighter','columns':json.dumps(preset_columns('fighter'))}).status_code,302)
        other=Subclass.objects.create(character_class=self.public,name='Чужая ветка',description='Текст')
        response=self.client.post(reverse('class_feature_edit_page',args=[self.private.pk,self.feature.pk]),{'name':'Тест','levels':'3','subclass':other.pk,'description':'Текст'})
        self.assertEqual(response.status_code,200);self.feature.refresh_from_db();self.assertEqual(self.feature.subclass_id,self.sub.pk)

    def test_private_choices_not_exposed_and_hidden_ids_rejected(self):
        self.assertNotIn(self.private,CharacterCreateForm(user=self.reader).fields['character_class'].queryset)
        self.assertIn(self.private,CharacterCreateForm(user=self.owner).fields['character_class'].queryset)
        self.assertNotIn(self.private,CustomSpellForm(user=self.reader).fields['aviable_classes'].queryset)
        from spells.serializers import CharacterSerializer
        from rest_framework.test import APIRequestFactory
        request=APIRequestFactory().post('/');request.user=self.reader
        form=CharacterSerializer(data={'name':'Тест','character_class':self.private.pk},context={'request':request})
        self.assertFalse(form.is_valid());self.assertIn('character_class',form.errors)
        spell=Spell.objects.create(name='Тест',description='Описание',is_official=True,duration='Миг')
        spell.aviable_classes.add(self.private)
        self.assertNotContains(self.client.get(reverse('spell_detail_page',args=[spell.pk])),self.private.name)
        self.assertNotContains(self.client.get(reverse('spell_preview',args=[spell.pk])),self.private.name)
        data=self.client.get(reverse('spells:spell_detail',args=[spell.pk])).json()
        self.assertEqual(data['aviable_classes'],[])

    def test_upload_image_and_public_toggle(self):
        self.client.force_login(self.owner)
        image=BytesIO();Image.new('RGB',(8,8),'red').save(image,'PNG')
        with TemporaryDirectory() as directory,override_settings(MEDIA_ROOT=directory):
            response=self.client.post(reverse('catalog_edit_page',args=['classes',self.private.pk]),{'name':self.private.name,'description':'Секрет','magic_type':'NC','hit_die':'8','spellcasting_ability':'WIS','is_public':'on','image':SimpleUploadedFile('image.png',image.getvalue(),content_type='image/png')})
            self.assertEqual(response.status_code,302)
            self.private.refresh_from_db();self.assertTrue(self.private.image);self.assertTrue(self.private.is_public)
            self.assertContains(self.client.get(reverse('class_detail_page',args=[self.private.pk])),self.private.image.url)
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get(reverse('class_detail_page',args=[self.private.pk])).status_code,200)

    def test_default_emblems_exist_and_are_distinct(self):
        from django.contrib.staticfiles import finders
        for name in ['Бард','Воин','Жрец','Изобретатель','Мой класс']:
            item=CharacterClass(name=name)
            self.assertTrue(finders.find(item.display_image_url.removeprefix('/static/')))
        self.assertNotEqual(CharacterClass(name='Бард').display_image_url,CharacterClass(name='Воин').display_image_url)

class TraitCatalogTests(TestCase):
    def test_trait_crud_permissions_and_direct_description_link(self):
        staff=User.objects.create_user('staff',is_staff=True)
        reader=User.objects.create_user('reader')
        url=reverse('catalog_create_page',args=['traits'])
        self.client.force_login(reader)
        self.assertEqual(self.client.post(url,{'name':'Бдительный','description':'Текст'}).status_code,403)
        self.client.force_login(staff)
        self.assertEqual(self.client.post(url,{'name':'Бдительный','description':'Описание','prerequisites':'Нет'}).status_code,302)
        trait=Trait.objects.get()
        token=f'[[trait:{trait.pk}|{quote(trait.name)}]]'
        html=render_description(token)
        self.assertIn(reverse('catalog_detail_page',args=['traits',trait.pk]),html)
        self.assertNotIn('data-catalog-kind',html);self.assertEqual(description_text(token),trait.name)
        self.client.logout()
        self.assertContains(self.client.get(reverse('catalog_detail_page',args=['traits',trait.pk])),'Бдительный')
        self.assertEqual(self.client.get(reverse('catalog_link_search',args=['traits']),{'search':'бдит'}).json()['items'][0]['id'],trait.pk)
        self.assertEqual(self.client.get(reverse('catalog_preview',args=['traits',trait.pk])).status_code,404)
        self.client.force_login(staff)
        self.assertEqual(self.client.post(reverse('catalog_delete_page',args=['traits',trait.pk])).status_code,302)
        self.assertFalse(Trait.objects.exists())
