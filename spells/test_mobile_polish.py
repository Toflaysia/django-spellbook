from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from spells.models import Person, Player


class CharacterCancelTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('cancel-owner')
        self.person=Person.objects.create(name='Отмена',player=Player.objects.create(user=self.user))
        self.client.force_login(self.user)

    def test_edit_cancel_returns_to_existing_character(self):
        response=self.client.get(reverse('character_edit_page',args=[self.person.pk]))
        url=reverse('character_detail_page',args=[self.person.pk])
        self.assertContains(response,f'href="{url}">Отмена</a>')

    def test_create_cancel_returns_to_list(self):
        response=self.client.get(reverse('character_create_page'))
        url=reverse('character_list_page')
        self.assertContains(response,f'href="{url}">Отмена</a>')
