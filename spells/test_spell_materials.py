from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APIClient
from spells.models import Player,Spell,MagicSchool,SpellTime,MaterialComponent
from spells.forms import CustomSpellForm
from spells.bulk_import import import_spell_records
from spells.materials import normalize_materials
from spells.templatetags.description_tags import render_description


class SpellMaterialsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user=User.objects.create_user('materials-owner',password='qa-password')
        cls.other=User.objects.create_user('materials-other')
        cls.player=Player.objects.create(user=cls.user)
        cls.school=MagicSchool.objects.create(name='Воплощение')
        cls.time=SpellTime.objects.create(time='Действие')

    def fields(self,**extra):
        return {'name':'С компонентами','level':1,'school':self.school.pk,'time':self.time.pk,'duration':'Мгновенная','description':'Описание','attack_type':'NONE',**extra}

    def test_direct_form_saves_names_and_optional_prices_without_catalog(self):
        form=CustomSpellForm(self.fields(material_components=[{'name':'Алмаз','cost':'300'},{'name':'Щепотка пыли'}]),user=self.user)
        self.assertTrue(form.is_valid(),form.errors)
        spell=form.save()
        self.assertEqual(spell.material_components,[{'name':'Алмаз','cost':'300'},{'name':'Щепотка пыли','cost':None}])
        self.assertEqual(MaterialComponent.objects.count(),0)
        response=self.client.get(reverse('spell_detail_page',args=[spell.pk]))
        self.assertContains(response,'Алмаз');self.assertContains(response,'300 зм');self.assertContains(response,'Щепотка пыли')
        preview=self.client.get(reverse('spell_preview',args=[spell.pk]))
        self.assertContains(preview,'300 зм');self.assertContains(preview,'Щепотка пыли')

    def test_repeated_html_inputs_update_and_clear_materials(self):
        from django.http import QueryDict
        data=QueryDict('',mutable=True);data.update(self.fields())
        data['material_components__present']='1'
        data.setlist('material_components_name',['Алмаз','Перо'])
        data.setlist('material_components_cost',['0',''])
        form=CustomSpellForm(data,user=self.user);self.assertTrue(form.is_valid(),form.errors)
        spell=form.save();self.assertEqual(spell.material_components[0]['cost'],'0')
        data.setlist('material_components_name',['']);data.setlist('material_components_cost',[''])
        form=CustomSpellForm(data,instance=spell,user=self.user);self.assertTrue(form.is_valid(),form.errors)
        spell=form.save();self.assertEqual(spell.material_components,[])

    def test_validation_does_not_drop_invalid_data(self):
        for value in ([{'name':'Алмаз','cost':'-1'}],[{'name':'','cost':'100'}],[12],[{'name':'Алмаз','cost':'NaN'}],[{'name':'Алмаз','cost':'1.234'}]):
            with self.subTest(value=value):
                form=CustomSpellForm(self.fields(material_components=value),user=self.user)
                self.assertFalse(form.is_valid());self.assertIn('material_components',form.errors)
        self.assertEqual(normalize_materials([{'name':'Пыль','cost':'2,50'}])[0]['cost'],'2.50')

    def test_foundry_import_saves_materials_separately(self):
        data={'name':'Из Foundry','type':'spell','system':{'school':'evo','level':1,'activation':{'type':'action'},'duration':{'units':'inst'},'description':{'value':'<p>Текст</p>'},'materials':{'value':'<p>Алмаз</p>','cost':300}}}
        report=import_spell_records([data],self.user);self.assertEqual(report['created'],1,report)
        spell=Spell.objects.get(name='Из Foundry')
        self.assertEqual(spell.material_components,[{'name':'Алмаз','cost':'300'}])
        self.assertNotIn('Материальные компоненты:',spell.description)

    def test_native_import_strings_objects_and_error_report(self):
        a=self.fields(name='Нативный',material_components=[{'name':'Алмаз','cost':300},'Перо'])
        b=self.fields(name='Текстовый',materials='Немного пыли')
        c=self.fields(name='Невалидный',material_components=[{'name':'Алмаз','cost':-10}])
        report=import_spell_records([a,b,c],self.user);self.assertEqual((report['created'],report['errors']),(2,1),report)
        self.assertEqual(Spell.objects.get(name='Текстовый').material_components,[{'name':'Немного пыли','cost':None}])
        self.assertTrue(report['rows'][2]['messages'])

    def test_api_materials_are_owned_by_spell_and_permissions_hold(self):
        client=APIClient();client.force_authenticate(self.user)
        response=client.post(reverse('spells:custom_spell_list'),self.fields(material_components=[{'name':'Перо','cost':None}]),format='json')
        self.assertEqual(response.status_code,201,response.data)
        spell=Spell.objects.get(pk=response.data['id']);self.assertEqual(spell.material_components,[{'name':'Перо','cost':None}])
        client.force_authenticate(self.other)
        self.assertEqual(client.patch(reverse('spells:custom_spell_detail',args=[spell.pk]),{'material_components':[]},format='json').status_code,404)

    def test_catalog_removed_and_old_tokens_remain_readable(self):
        for name,args in [('catalog_list_page',['components']),('catalog_detail_page',['components',1]),('catalog_create_page',['components'])]:
            self.assertEqual(self.client.get(reverse(name,args=args)).status_code,404 if 'create' not in name else 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('catalog_create_page',args=['components'])).status_code,403)
        self.user.is_staff=True;self.user.save()
        self.assertEqual(self.client.get(reverse('catalog_create_page',args=['components'])).status_code,404)
        self.assertEqual(self.client.get('/api/spells/material_component/').status_code,404)
        menu=self.client.get(reverse('home_page'))
        self.assertNotContains(menu,'/catalog/components/')
        html=str(render_description('[[component:1|Алмаз]]'))
        self.assertIn('Алмаз',html);self.assertNotIn('<a',html)
