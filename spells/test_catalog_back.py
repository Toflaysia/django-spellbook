from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from spells.models import CharacterClass, DamageType, ClassFeature, ClassSection, Subclass, Spell
from spells.views.catalog import CATALOGS


class CatalogBackTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user('back-admin', is_staff=True)
        cls.character_class = CharacterClass.objects.create(name='Воин', description='Текст')
        cls.subclass = Subclass.objects.create(character_class=cls.character_class, name='Архетип', description='Текст')
        cls.feature = ClassFeature.objects.create(character_class=cls.character_class, name='Умение', description='Текст', level=1)
        cls.section = ClassSection.objects.create(character_class=cls.character_class, title='Раздел', description='Текст')
        cls.spell = Spell.objects.create(name='Огонь', description='Текст', duration='Минута', is_official=True)

    def test_all_catalogs_have_back_link_in_detail_and_edit(self):
        self.client.force_login(self.staff)
        for slug, catalog in CATALOGS.items():
            item = catalog['model'].objects.create(**{catalog['name_field']:'Название', 'description':'Текст'})
            with self.subTest(slug=slug):
                target = reverse('catalog_list_page', args=[slug])
                detail = self.client.get(reverse('catalog_detail_page', args=[slug, item.pk]), follow=True)
                self.assertContains(detail, f'href="{target}"')
                edit = self.client.get(reverse('catalog_edit_page', args=[slug, item.pk]))
                self.assertContains(edit, 'data-confirm-unsaved')
                self.assertContains(edit, f'href="{target}"')

    def test_class_entry_and_table_forms_have_guard_and_return_to_class_list(self):
        self.client.force_login(self.staff)
        for name, args in (
            ('subclass_edit_page', [self.character_class.pk, self.subclass.pk]),
            ('class_feature_edit_page', [self.character_class.pk, self.feature.pk]),
            ('class_section_edit_page', [self.character_class.pk, self.section.pk]),
            ('class_table_edit_page', [self.character_class.pk]),
            ('subclass_table_edit_page', [self.character_class.pk, self.subclass.pk]),
        ):
            with self.subTest(name=name):
                response=self.client.get(reverse(name,args=args))
                self.assertContains(response, 'data-confirm-unsaved')
                self.assertContains(response, f'href="{reverse("catalog_list_page", args=["classes"])}"')

    def test_official_spell_detail_and_edit_have_return_link(self):
        self.client.force_login(self.staff)
        for name in ('spell_detail_page', 'spell_edit_page'):
            response = self.client.get(reverse(name,args=[self.spell.pk]))
            self.assertContains(response, 'Назад к списку заклинаний')
            if name == 'spell_edit_page':
                self.assertContains(response, 'data-confirm-unsaved')

    def test_catalog_list_has_no_unsaved_guard(self):
        response=self.client.get(reverse('catalog_list_page',args=['damage-types']))
        self.assertNotContains(response,'data-confirm-unsaved')
