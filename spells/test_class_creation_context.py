from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from spells.models import CharacterClass

class ClassCreationContextTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_user('context-editor',is_staff=True))
        self.catalog=reverse('catalog_list_page',args=['classes'])
        self.create=reverse('catalog_create_page',args=['classes'])

    def test_own_create_button_only_on_my_tab(self):
        for group in ('official','unofficial','mine'):
            response=self.client.get(self.catalog,{'group':group})
            self.assertContains(response,'Мои классы')
            self.assertNotContains(response,'Созданные мной')
            if group=='mine':
                self.assertContains(response,reverse('user_class_create_page'))
                self.assertNotContains(response,'+ Добавить запись')
            else:
                self.assertNotContains(response,reverse('user_class_create_page'))
                self.assertContains(response,self.create+'?group='+group)

    def test_initial_checkbox_and_cancel_return_to_group(self):
        official=self.client.get(self.create,{'group':'official'})
        self.assertTrue(official.context['form']['is_official'].value())
        self.assertContains(official,self.catalog+'?group=official')
        unofficial=self.client.get(self.create,{'group':'unofficial'})
        self.assertNotIn('is_official',unofficial.context['form'].fields)
        self.assertContains(unofficial,self.catalog+'?group=unofficial')
        own=self.client.get(reverse('user_class_create_page'))
        self.assertNotIn('is_official',own.context['form'].fields)
        self.assertContains(own,self.catalog+'?group=mine')

    def test_unofficial_post_ignores_forged_official_flag(self):
        data={'name':'Контекстный класс','description':'Описание','magic_type':'NC','hit_die':'8','spellcasting_ability':'WIS','is_official':'on'}
        response=self.client.post(self.create+'?group=unofficial',data)
        self.assertEqual(response.status_code,302)
        self.assertFalse(CharacterClass.objects.get(name=data['name']).is_official)
        data['name']='Официальный по выбору'
        self.assertEqual(self.client.post(self.create+'?group=official',data).status_code,302)
        self.assertTrue(CharacterClass.objects.get(name=data['name']).is_official)
