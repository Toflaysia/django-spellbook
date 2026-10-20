from urllib.parse import quote
from django.test import TestCase, SimpleTestCase
from django.urls import reverse
from spells.models import Effect
from spells.templatetags.description_tags import render_description
from spells.description import DESCRIPTION_PREFIX
import json

class StateNavigationTests(TestCase):
    def test_state_shortcut_filters_the_effect_catalog(self):
        condition=Effect.objects.create(name='Испуганный',category='COND')
        other=Effect.objects.create(name='Другой эффект')
        url=reverse('catalog_list_page',args=['conditions'])
        self.assertContains(self.client.get(reverse('catalog_list_page',args=['classes'])), 'href="'+url+'">Состояния</a>')
        response=self.client.get(url)
        self.assertContains(response,condition.name)
        self.assertNotContains(response,other.name)

class CustomLinkTextTests(SimpleTestCase):
    def test_custom_label_keeps_target_and_escapes_html_in_every_block(self):
        for kind,slug in [('condition','conditions'),('spell',None),('damage','damage-types'),('school','schools'),('trait','traits')]:
            label='испуганным <img src=x onerror=alert(1)> | ]]'
            token=f'[[{kind}:17|{quote(label,safe="")}]]'
            blocks=[{'type':'text','text':token},{'type':'heading','text':token},{'type':'quote','text':token},{'type':'list','items':[token]},{'type':'table','rows':[[token]]}]
            html=str(render_description(DESCRIPTION_PREFIX+json.dumps(blocks)))
            target=reverse('spell_detail_page',args=[17]) if slug is None else reverse('catalog_detail_page',args=[slug,17])
            self.assertEqual(html.count('href="'+target+'"'),5)
            self.assertEqual(html.count('испуганным &lt;img'),5)
            self.assertNotIn('<img',html)
