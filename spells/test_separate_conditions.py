from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from spells.models import Effect

class SeparateConditionsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condition=Effect.objects.create(name='Испуганный',category='COND')
        cls.effect=Effect.objects.create(name='Усиление удара',category='BUFF')
        cls.staff=User.objects.create_user('conditions-admin',is_staff=True)

    def test_lists_remain_separate_under_search_and_filters(self):
        for slug,visible,hidden in [('conditions',self.condition,self.effect),('effects',self.effect,self.condition)]:
            for params in [{},{'search':hidden.name},{'category':'COND'}]:
                response=self.client.get(reverse('catalog_list_page',args=[slug]),params)
                self.assertNotContains(response,'<span class="catalog-entry-name">'+hidden.name+'</span>')
            self.assertContains(self.client.get(reverse('catalog_list_page',args=[slug])),visible.name)
        self.assertEqual(self.client.get(reverse('catalog_detail_page',args=['conditions',self.effect.pk])).status_code,404)
        self.assertRedirects(self.client.get(reverse('catalog_detail_page',args=['effects',self.condition.pk])),reverse('catalog_detail_page',args=['conditions',self.condition.pk]))

    def test_state_creation_forces_category_and_effects_reject_states(self):
        self.client.force_login(self.staff)
        url=reverse('catalog_create_page',args=['conditions'])
        response=self.client.get(url)
        self.assertNotIn('category',response.context['form'].fields)
        self.assertRedirects(self.client.post(url,{'name':'Невидимый','description':'Описание','category':'BUFF'}),reverse('catalog_list_page',args=['conditions']))
        state=Effect.objects.get(name='Невидимый')
        self.assertEqual(state.category,'COND')
        edit=reverse('catalog_edit_page',args=['conditions',state.pk])
        self.assertRedirects(self.client.post(edit,{'name':state.name,'description':'Новое','category':'BUFF'}),reverse('catalog_detail_page',args=['conditions',state.pk]))
        state.refresh_from_db();self.assertEqual(state.category,'COND')
        response=self.client.post(reverse('catalog_create_page',args=['effects']),{'name':'Не создавать состояние','category':'COND'})
        self.assertEqual(response.status_code,200)
        self.assertFalse(Effect.objects.filter(name='Не создавать состояние').exists())
        response=self.client.get(reverse('catalog_edit_page',args=['conditions',self.effect.pk]))
        self.assertEqual(response.status_code,404)

    def test_condition_picker_only_returns_states_and_preview_works(self):
        response=self.client.get(reverse('catalog_link_search',args=['conditions']))
        self.assertEqual([item['id'] for item in response.json()['items']],[self.condition.pk])
        self.assertEqual(self.client.get(reverse('catalog_preview',args=['conditions',self.condition.pk])).status_code,200)
        self.assertEqual(self.client.get(reverse('catalog_preview',args=['conditions',self.effect.pk])).status_code,404)
