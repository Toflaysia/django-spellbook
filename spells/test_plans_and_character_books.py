from datetime import timedelta
from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from spells.models import HomePlan, Player, Person, Spellbook
from spells.forms import CharacterEditForm

class PlansAndBooksTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user=User.objects.create_user('planner')
        cls.other=User.objects.create_user('other-planner')
        cls.person=Person.objects.create(name='Барда',player=Player.objects.create(user=cls.user))
        cls.other_person=Person.objects.create(name='Чужой герой',player=Player.objects.create(user=cls.other))
        cls.book=Spellbook.objects.create(name='Магия барда',owner=cls.person)
        cls.other_book=Spellbook.objects.create(name='Секретная книга',owner=cls.other_person)
        cls.plan=HomePlan.objects.create(user=cls.user,title='Купить зелье',text='<script>alert(1)</script>',reminder_date=timezone.localdate())
        cls.other_plan=HomePlan.objects.create(user=cls.other,title='Чужие планы')

    def setUp(self):
        self.client.force_login(self.user)

    def test_home_private_safe_and_deadline(self):
        response=self.client.get(reverse('home_page'))
        self.assertContains(response,'Купить зелье')
        self.assertNotContains(response,'Чужие планы')
        self.assertNotContains(response,'<script>alert(1)</script>')
        self.assertContains(response,'Сегодня')
        self.assertEqual(self.plan.reminder_status,'Сегодня')
        self.plan.reminder_date=timezone.localdate()-timedelta(days=1)
        self.assertEqual(self.plan.reminder_status,'Просрочено')
        self.plan.is_done=True
        self.assertEqual(self.plan.reminder_status,'')
        self.client.logout()
        response=self.client.get(reverse('home_page'))
        self.assertNotContains(response,'Купить зелье')
        self.assertNotContains(response,'id="plans"')

    def test_create_invalid_edit_toggle_and_delete(self):
        url=reverse('plan_create_page')
        response=self.client.post(url,{'title':'','text':'Текст','reminder_date':'bad'})
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.context['plan_form'].errors)
        self.assertEqual(HomePlan.objects.filter(user=self.user).count(),1)
        response=self.client.post(url,{'title':'Подготовиться','text':'План','reminder_date':''})
        self.assertRedirects(response,reverse('home_page')+'#plans')
        created=HomePlan.objects.get(title='Подготовиться')
        self.assertEqual(created.user,self.user)
        self.assertIsNone(created.reminder_date)
        response=self.client.post(reverse('plan_edit_page',args=[created.pk]),{'title':'Исправлено','text':'Текст','reminder_date':timezone.localdate().isoformat()})
        self.assertEqual(response.status_code,302)
        created.refresh_from_db();self.assertEqual(created.title,'Исправлено')
        self.client.post(reverse('plan_toggle_page',args=[created.pk]));created.refresh_from_db();self.assertTrue(created.is_done)
        self.client.post(reverse('plan_toggle_page',args=[created.pk]));created.refresh_from_db();self.assertFalse(created.is_done)
        self.client.post(reverse('plan_delete_page',args=[created.pk]));self.assertFalse(HomePlan.objects.filter(pk=created.pk).exists())

    def test_cannot_read_or_change_another_users_plan(self):
        for name in ('plan_edit_page','plan_toggle_page','plan_delete_page'):
            url=reverse(name,args=[self.other_plan.pk])
            self.assertEqual(self.client.post(url,{'title':'Взлом'}).status_code,404)
        self.assertEqual(self.client.get(reverse('plan_edit_page',args=[self.other_plan.pk])).status_code,404)
        self.other_plan.refresh_from_db();self.assertEqual(self.other_plan.title,'Чужие планы')
        for name in ('plan_toggle_page','plan_delete_page'):
            self.assertEqual(self.client.get(reverse(name,args=[self.plan.pk])).status_code,405)
        client=Client(enforce_csrf_checks=True);client.force_login(self.user)
        self.assertEqual(client.post(reverse('plan_delete_page',args=[self.plan.pk])).status_code,403)

    def test_character_book_links_and_preselected_owner(self):
        response=self.client.get(reverse('character_detail_page',args=[self.person.pk]))
        self.assertContains(response,'Магия барда')
        self.assertNotContains(response,'Секретная книга')
        self.assertContains(response,reverse('spellbook_detail_page',args=[self.book.pk]))
        response=self.client.get(reverse('spellbook_detail_page',args=[self.book.pk]))
        self.assertContains(response,reverse('character_detail_page',args=[self.person.pk]))
        response=self.client.get(reverse('spellbook_create_page'),{'owner':self.person.pk})
        self.assertEqual(response.context['form'].initial['owner'],self.person.pk)
        self.assertEqual(self.client.get(reverse('spellbook_create_page'),{'owner':self.other_person.pk}).status_code,404)
        self.assertEqual(self.client.get(reverse('spellbook_create_page'),{'owner':'bad'}).status_code,404)
        self.assertIn('is_active',CharacterEditForm(instance=self.person).fields)

    def test_formatted_plan_roundtrip_and_validation(self):
        import json
        from spells.description import DESCRIPTION_PREFIX
        text=DESCRIPTION_PREFIX+json.dumps([{'type':'quote','text':'Цитата <script>bad</script>'},{'type':'table','rows':[['Зелье','2']]}])
        response=self.client.post(reverse('plan_create_page'),{'title':'План с таблицей','text':text,'reminder_date':''})
        self.assertEqual(response.status_code,302)
        plan=HomePlan.objects.get(title='План с таблицей')
        response=self.client.get(reverse('home_page'))
        self.assertContains(response,'<blockquote>')
        self.assertContains(response,'description-display-table')
        self.assertNotContains(response,'<script>bad</script>')
        self.assertContains(response,'data-description-editor="true"')
        self.assertContains(self.client.get(reverse('plan_edit_page',args=[plan.pk])),'data-description-editor="true"')
        bad=DESCRIPTION_PREFIX+json.dumps([{'type':'table','rows':[['a'], ['a', 'b']]}])
        response=self.client.post(reverse('plan_edit_page',args=[plan.pk]),{'title':'Испорчено','text':bad,'reminder_date':''})
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.context['form'].errors)
        plan.refresh_from_db();self.assertEqual(plan.title,'План с таблицей')
