import json
from django import forms
from django.contrib.auth.models import User
from django.test import TestCase,SimpleTestCase
from django.urls import reverse
from spells.description import DESCRIPTION_PREFIX,parse_description,DescriptionFormMixin
from spells.models import MagicSchool,Person,Player
from spells.templatetags.description_tags import render_description,description_text

class RequiredDescription(DescriptionFormMixin,forms.Form):
    description=forms.CharField(widget=forms.Textarea)

class FormattingTests(SimpleTestCase):
    def test_formatting_round_trip_safe_and_readable(self):
        blocks=[{'type':'heading','text':'Заголовок <script>x</script>'},{'type':'rule'},{'type':'list','items':['Первый','[[spell:42|%D0%A8%D0%B0%D1%80]]']},{'type':'quote','text':'Цитата'},{'type':'table','rows':[['Текст']]}]
        value=DESCRIPTION_PREFIX+json.dumps(blocks)
        form=RequiredDescription({'description':value})
        self.assertTrue(form.is_valid(),form.errors)
        self.assertEqual(parse_description(form.cleaned_data['description']),blocks)
        html=render_description(value)
        self.assertIn('<h3>',html);self.assertIn('<ul>',html);self.assertIn('<blockquote>',html)
        self.assertIn('description-rule',html);self.assertIn('data-spell-id="42"',html)
        self.assertNotIn('<script>',html)
        self.assertIn('Шар',description_text(value));self.assertNotIn('SPELLBOOK_BLOCKS',description_text(value))

    def test_rule_alone_is_not_required_description_and_invalid_list_rejected(self):
        form=RequiredDescription({'description':DESCRIPTION_PREFIX+json.dumps([{'type':'rule'}])})
        self.assertFalse(form.is_valid())
        with self.assertRaises(ValueError):parse_description(DESCRIPTION_PREFIX+json.dumps([{'type':'list','items':[123]}]))

class SchoolAndHealthTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('school-admin',is_staff=True)
        self.school=MagicSchool.objects.create(name='Иллюзия',description='Текст',color='#b17fea')
        self.client.force_login(self.user)

    def test_school_color_used_in_list_detail_edit_but_hidden_in_detail(self):
        for url in (reverse('catalog_list_page',args=['schools']),reverse('catalog_detail_page',args=['schools',self.school.pk]),reverse('catalog_edit_page',args=['schools',self.school.pk])):
            response=self.client.get(url);self.assertEqual(response.status_code,200)
            self.assertContains(response,'--school-color:#b17fea')
        response=self.client.get(reverse('catalog_detail_page',args=['schools',self.school.pk]))
        self.assertNotContains(response,'name="color"')
        self.assertNotContains(response,'Цвет школы магии')
        response=self.client.post(reverse('catalog_edit_page',args=['schools',self.school.pk]),{'name':self.school.name,'description':'Текст','color':'#18ab9f'})
        self.assertEqual(response.status_code,302)
        self.school.refresh_from_db();self.assertEqual(self.school.color,'#18ab9f')
        response=self.client.post(reverse('catalog_edit_page',args=['schools',self.school.pk]),{'name':self.school.name,'description':'Текст','color':'bad'})
        self.assertTrue(response.context['form'].errors)

    def test_temporary_inline_and_half_hp_threshold(self):
        person=Person.objects.create(name='Воин',player=Player.objects.create(user=self.user),max_hit_points=21,current_hit_points=10,temporary_hit_points=5)
        url=reverse('character_detail_page',args=[person.pk])
        response=self.client.get(url)
        self.assertContains(response,'class="hp-low"',count=3)
        self.assertContains(response,'class="hp-temporary"',count=3)
        self.assertNotContains(response,'<p>Временные:')
        person.current_hit_points=11;person.save()
        self.assertNotContains(self.client.get(url),'class="hp-low"')
