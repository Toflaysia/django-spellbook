from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from spells.models import Person, Player
from spells.forms import CharacterCreateForm

class CharacterDashboardTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('dashboard')
        self.person=Person.objects.create(player=Player.objects.create(user=self.user),name='Активный герой',max_hit_points=20,current_hit_points=10)
        other=User.objects.create_user('foreign-dashboard')
        self.foreign=Person.objects.create(player=Player.objects.create(user=other),name='Чужой герой')
        self.client.force_login(self.user)

    def test_active_status_controls_private_dashboard(self):
        home=reverse('home_page')
        response=self.client.get(home)
        self.assertContains(response,'Активный герой')
        self.assertNotContains(response,'Чужой герой')
        self.assertContains(response,'Планы и напоминания')
        url=reverse('character_resource_change',args=[self.person.pk])
        self.assertEqual(self.client.post(url,{'action':'active','is_active':'false'}).status_code,200)
        self.assertNotContains(self.client.get(home),'Активный герой')
        self.assertEqual(self.client.post(url,{'action':'active','is_active':'true'}).status_code,200)
        self.assertContains(self.client.get(home),'Активный герой')
        self.assertEqual(self.client.post(reverse('character_resource_change',args=[self.foreign.pk]),{'action':'active','is_active':'false'}).status_code,404)
        self.assertIn('is_active',CharacterCreateForm().fields)

    def test_cancel_and_low_health_rendering(self):
        response=self.client.get(reverse('spellbook_create_page'),{'owner':self.person.pk})
        self.assertContains(response,reverse('character_detail_page',args=[self.person.pk])+'#character-spellbooks')
        response=self.client.post(reverse('spellbook_create_page')+'?owner='+str(self.person.pk),{})
        self.assertContains(response,reverse('character_detail_page',args=[self.person.pk])+'#character-spellbooks')
        response=self.client.get(reverse('character_detail_page',args=[self.person.pk]))
        self.assertContains(response,'data-hp-current class="hp-low"',count=2)
        self.assertContains(self.client.get(reverse('character_list_page')),'class="hp-current hp-low"')
