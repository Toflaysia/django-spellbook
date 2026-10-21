from django.test import TestCase
from django.contrib.auth.models import User
from django.http import QueryDict
from django.urls import reverse
from spells.models import Spell,Player,MagicSchool
from spells.filters import SpellFilterForm


class ComponentFiltersTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user=User.objects.create_user('component-filter-user')
        cls.other=User.objects.create_user('component-filter-other')
        cls.player=Player.objects.create(user=cls.user)
        cls.school=MagicSchool.objects.create(name='Воплощение')
        cls.v=Spell.objects.create(name='Только В',duration='Миг',description='Текст',verbal_component=True)
        cls.vs=Spell.objects.create(name='В и С',duration='Миг',description='Текст',verbal_component=True,somatic_component=True)
        cls.all=Spell.objects.create(name='Все компоненты',duration='Миг',description='Текст',school=cls.school,verbal_component=True,somatic_component=True,material_components=[{'name':'Алмаз','cost':'300'},{'name':'Перо','cost':None}])
        cls.m=Spell.objects.create(name='Только М',duration='Миг',description='Текст',material_components=[{'name':'Перо','cost':None}])
        cls.private=Spell.objects.create(name='Приватное',duration='Миг',description='Текст',is_official=False,created_by=cls.player,verbal_component=True,somatic_component=True,material_components=[{'name':'Тайный материал','cost':None}])
        cls.public=Spell.objects.create(name='Публичное',duration='Миг',description='Текст',is_official=False,is_public=True,created_by=cls.player,material_components=[{'name':'Пыль','cost':None}])

    def filter(self,*components):
        data=QueryDict('',mutable=True);data.setlist('components',components)
        return SpellFilterForm(data).apply(Spell.objects.filter(is_official=True))

    def test_selected_components_all_required_extras_allowed(self):
        self.assertEqual(set(self.filter('verbal')),{self.v,self.vs,self.all})
        self.assertEqual(set(self.filter('verbal','somatic')),{self.vs,self.all})
        self.assertEqual(set(self.filter('verbal','somatic','material')),{self.all})
        self.assertEqual(set(self.filter('material')),{self.m,self.all})
        self.assertEqual(set(self.filter()),{self.v,self.vs,self.m,self.all})
        self.assertFalse(self.filter('unknown').exists())

    def test_catalog_personal_scope_and_selection_persistence(self):
        response=self.client.get(reverse('spell_list_page'),{'components':['material']})
        self.assertEqual(set(response.context['spells']),{self.all,self.m})
        self.assertContains(response,'Материальный');self.assertContains(response,'checked')
        response=self.client.get(reverse('spell_list_page'),{'group':'unofficial','components':['material']})
        self.assertEqual(set(response.context['spells']),{self.public})
        self.assertNotContains(response,'Тайный материал')
        self.client.force_login(self.user)
        response=self.client.get(reverse('my_spell_list_page'),{'components':['verbal','material']})
        self.assertEqual(set(response.context['spells']),{self.private})

    def test_header_line_order_no_bullets_and_metadata_position(self):
        from django.utils.html import strip_tags
        import re
        response=self.client.get(reverse('spell_detail_page',args=[self.all.pk]))
        html=response.content.decode()
        self.assertRegex(html,r'<h1>Все компоненты</h1>\s*<p class="spell-components-line"')
        line=re.search(r'<p class="spell-components-line"[^>]*>(.*?)</p>',html,re.S)[1]
        self.assertEqual(strip_tags(line),'В, С, М (Алмаз — 300 зм; Перо)')
        self.assertNotIn('<li',line)
        self.assertGreater(html.index('class="spell-school-level"'),html.index('id="spell-parameters"'))
        preview=self.client.get(reverse('spell_preview',args=[self.all.pk]))
        self.assertContains(preview,'Алмаз — 300 зм')

    def test_component_names_escaped_and_optional_parts(self):
        from django.template.loader import render_to_string
        self.assertIn('В</span>',render_to_string('spells/includes/spell_components_line.html',{'spell':self.v}))
        self.m.material_components=[{'name':'<script>alert(1)</script>','cost':'0'}];self.m.save()
        response=self.client.get(reverse('spell_detail_page',args=[self.m.pk]))
        self.assertContains(response,'&lt;script&gt;alert(1)&lt;/script&gt; — 0 зм')
        self.assertNotContains(response,'<script>alert(1)</script>')
