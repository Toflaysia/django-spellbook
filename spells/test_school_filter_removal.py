from django.test import TestCase
from django.urls import reverse
from spells.models import MagicSchool, Spell

class SchoolFilterRemovalTests(TestCase):
    def test_description_query_is_ignored_and_other_filters_still_work(self):
        school=MagicSchool.objects.create(name='Воплощение',description='Огонь')
        other=MagicSchool.objects.create(name='Прорицание',description='Видение')
        Spell.objects.create(name='Огненный шар',description='Текст',duration='Мгновенно',school=school,level=3,is_official=True)
        url=reverse('catalog_list_page',args=['schools'])
        response=self.client.get(url,{'description':'нет такого текста'})
        self.assertContains(response,school.name)
        self.assertContains(response,other.name)
        self.assertNotContains(response,'Слова в описании')
        self.assertNotIn('description',response.context['extra_filters'].fields)
        response=self.client.get(url,{'level':'3','description':'нет такого текста'})
        self.assertContains(response,school.name)
        self.assertNotContains(response,other.name)
