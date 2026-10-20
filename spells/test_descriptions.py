import json

from django import forms
from django.contrib.auth.models import User
from django.template.loader import get_template
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from spells.description import DESCRIPTION_PREFIX, DescriptionFormMixin, parse_description
from spells.forms import CustomSpellForm, SpellbookForm
from spells.models import CharacterClass, ClassSection
from spells.templatetags.description_tags import description_text, render_description
from spells.views.catalog import CATALOGS, build_catalog_form
from spells.views.class_pages import ClassFeatureForm, ClassSectionForm, SubclassForm


def encoded(blocks):
    return DESCRIPTION_PREFIX + json.dumps(blocks)


class SampleForm(DescriptionFormMixin, forms.Form):
    description = forms.CharField(widget=forms.Textarea)


class DescriptionTests(SimpleTestCase):
    def test_plain_text_and_old_tables(self):
        self.assertIn('<p>Старый текст</p>', render_description('Старый текст'))
        value = encoded([
            {'type': 'text', 'text': 'До'},
            {'type': 'table', 'rows': [['Ячейка', 'Вторая']]},
            {'type': 'text', 'text': 'После'},
        ])
        result = render_description(value)
        self.assertLess(result.index('До'), result.index('<table'))
        self.assertLess(result.index('</table>'), result.index('После'))
        self.assertEqual(description_text(value), 'До\nЯчейка | Вторая\nПосле')
        self.assertTrue(SampleForm({'description': value}).is_valid())

    def test_text_is_escaped_including_cells(self):
        value = encoded([{'type': 'table', 'rows': [['<script>alert(1)</script>']]}])
        self.assertNotIn('<script>', render_description(value))
        self.assertIn('&lt;script&gt;', render_description(value))
        self.assertNotIn('<img', render_description('<img src=x onerror=alert(1)>'))

    def test_large_tables_rectangular_shape_and_empty_required(self):
        self.assertTrue(SampleForm({'description': encoded([
            {'type': 'table', 'rows': [['x'] * 12 for _ in range(15)]}
        ])}).is_valid())
        for rows in [[['x'], ['x', 'y']], [], [[]]]:
            form = SampleForm({'description': encoded([{'type': 'table', 'rows': rows}])})
            self.assertFalse(form.is_valid())
        self.assertFalse(SampleForm({'description': encoded([
            {'type': 'table', 'rows': [['']]}
        ])}).is_valid())

    def test_all_catalog_and_personal_forms_enable_editor(self):
        for catalog in CATALOGS.values():
            form = build_catalog_form(catalog)()
            self.assertEqual(form.fields['description'].widget.attrs['data-description-editor'], 'true')
        for form in [CustomSpellForm(), SubclassForm(), ClassSectionForm(),
                     SpellbookForm(user=User(pk=1)),
                     ClassFeatureForm(character_class=CharacterClass(pk=1))]:
            self.assertEqual(form.fields['description'].widget.attrs['data-description-editor'], 'true')
        self.assertEqual(CustomSpellForm().fields['higher_level'].widget.attrs['data-description-editor'], 'true')

    def test_templates_compile(self):
        from pathlib import Path
        base = Path(__file__).parent / 'templates' / 'spells'
        for path in base.glob('*.html'):
            get_template('spells/' + path.name)


class SectionManagementTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user('staff', password='test', is_staff=True)
        self.user = User.objects.create_user('reader', password='test')
        self.character_class = CharacterClass.objects.create(name='Тестовый класс', description='Текст')
        self.section = ClassSection.objects.create(character_class=self.character_class, title='Раздел', description='Описание')
        self.detail_url = reverse('class_detail_page', args=[self.character_class.pk])
        self.delete_url = reverse('class_section_delete_page', args=[self.character_class.pk, self.section.pk])

    def test_staff_actions_are_outside_collapsible_and_delete_works(self):
        self.client.force_login(self.staff)
        response = self.client.get(self.detail_url)
        self.assertContains(response, 'Удалить раздел')
        html = response.content.decode()
        section_start = html.index(f'id="class-section-{self.section.pk}"')
        self.assertGreater(html.index(self.delete_url), html.index('</details>', section_start))
        self.assertEqual(self.client.post(self.delete_url).status_code, 302)
        self.assertFalse(ClassSection.objects.filter(pk=self.section.pk).exists())

    def test_reader_cannot_delete_or_edit(self):
        self.client.force_login(self.user)
        self.assertNotContains(self.client.get(self.detail_url), 'Удалить раздел')
        self.assertEqual(self.client.post(self.delete_url).status_code, 403)
        self.assertEqual(self.client.post(reverse('class_section_edit_page', args=[self.character_class.pk, self.section.pk])).status_code, 403)
        self.assertTrue(ClassSection.objects.filter(pk=self.section.pk).exists())

    def test_section_round_trip(self):
        self.client.force_login(self.staff)
        value = encoded([{'type': 'table', 'rows': [['Проверка']]}])
        url = reverse('class_section_edit_page', args=[self.character_class.pk, self.section.pk])
        response = self.client.post(url, {'title': 'Раздел', 'position': 0, 'description': value})
        self.assertEqual(response.status_code, 302)
        self.section.refresh_from_db()
        self.assertEqual(parse_description(self.section.description)[0]['rows'], [['Проверка']])
        self.assertContains(self.client.get(self.detail_url), '<td>Проверка</td>', html=True)
