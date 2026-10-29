from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import TestCase,Client
from django.urls import reverse
from spells.models import Person,Player,Spellbook,CharacterClass,CharacterResource
from spells.rests import rest_state


class RestTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('rest-owner')
        self.other=User.objects.create_user('rest-other')
        warrior=CharacterClass.objects.create(name='Воин',hit_die=10)
        mage=CharacterClass.objects.create(name='Маг',hit_die=6)
        self.person=Person.objects.create(name='Герой',player=Player.objects.create(user=self.user),character_class=warrior,primary_class_level=3,second_class=mage,second_class_level=2,warlock_level=1,constitution=14,max_hit_points=40,current_hit_points=10,temporary_hit_points=5)
        self.book=Spellbook.objects.create(owner=self.person,name='Основной',max_spell_slots_1=4,current_spell_slots_1=1,warlock_max_slots=2,warlock_current_slots=0)
        self.reserve=Spellbook.objects.create(owner=self.person,name='Запасной',is_active=False,max_spell_slots_1=3,current_spell_slots_1=0,warlock_max_slots=1,warlock_current_slots=0)
        self.short=CharacterResource.objects.create(person=self.person,name='Второе дыхание',maximum=1,current=0,refresh_on='short')
        self.long=CharacterResource.objects.create(person=self.person,name='Ярость',maximum=3,current=0,refresh_on='long')
        self.manual=CharacterResource.objects.create(person=self.person,name='Особый',maximum=2,current=0,refresh_on='manual')
        self.url=reverse('character_rest_change',args=[self.person.pk]);self.client.force_login(self.user)

    def post(self,action,**values):
        self.person.refresh_from_db()
        response=self.client.post(self.url,{'revision':self.person.rest_revision,'action':action,**values})
        self.person.refresh_from_db();return response

    def test_sequential_dice_rolls_and_hp_cap(self):
        with patch('spells.rests.secrets.randbelow',return_value=9):
            for expected in (22,34,40):
                result=self.post('spend_hit_die',die=10);self.assertEqual(result.status_code,200);self.assertEqual(self.person.current_hit_points,expected)
        self.assertEqual(self.person.spent_hit_dice['10'],3)
        self.assertEqual(self.post('spend_hit_die',die=10).status_code,400)
        self.assertEqual(self.post('spend_hit_die',die=6).status_code,400)
        self.assertEqual(self.person.temporary_hit_points,5)

    def test_negative_constitution_does_not_harm(self):
        self.person.constitution=3;self.person.save()
        with patch('spells.rests.secrets.randbelow',return_value=0):response=self.post('spend_hit_die',die=6)
        self.assertEqual(response.status_code,200);self.assertEqual(self.person.current_hit_points,10);self.assertEqual(self.person.spent_hit_dice['6'],1)

    def test_short_rest_selected_pact_slots_and_policy_only(self):
        self.assertEqual(self.post('short_rest',completed='on',book_ids=[self.book.pk]).status_code,200)
        self.book.refresh_from_db();self.reserve.refresh_from_db()
        self.assertEqual((self.book.current_spell_slots_1,self.book.warlock_current_slots),(1,2))
        self.assertEqual(self.reserve.warlock_current_slots,0)
        self.short.refresh_from_db();self.long.refresh_from_db();self.manual.refresh_from_db()
        self.assertEqual((self.short.current,self.long.current,self.manual.current),(1,0,0))
        self.assertEqual((self.person.current_hit_points,self.person.temporary_hit_points),(10,5))
        self.assertIsNotNone(self.person.last_short_rest_at)

    def test_long_rest_multiclass_choice_and_all_resources(self):
        self.person.spent_hit_dice={'10':3,'6':2,'8':1};self.person.save()
        self.assertEqual(self.post('long_rest',completed='on',book_ids=[self.book.pk],recover_10=1,recover_6=1,recover_8=1).status_code,200)
        self.assertEqual(self.person.spent_hit_dice,{'10':2,'6':1,'8':0});self.assertEqual((self.person.current_hit_points,self.person.temporary_hit_points),(40,0))
        self.book.refresh_from_db();self.reserve.refresh_from_db()
        self.assertEqual((self.book.current_spell_slots_1,self.book.warlock_current_slots,self.book.max_spell_slots_1,self.book.warlock_max_slots),(4,2,4,2))
        self.assertEqual(self.reserve.current_spell_slots_1,0)
        self.short.refresh_from_db();self.long.refresh_from_db();self.manual.refresh_from_db()
        self.assertEqual((self.short.current,self.long.current,self.manual.current),(1,3,0))
        self.assertIsNotNone(self.person.last_long_rest_at)

    def test_recovery_limits_and_zero_hp_reject_without_side_effects(self):
        self.person.spent_hit_dice={'10':3,'6':2,'8':1};self.person.save()
        for data in ({'recover_10':3,'recover_6':1},{'recover_6':3},{'recover_10':-1},{'recover_10':'1.5'}):
            self.assertEqual(self.post('long_rest',completed='on',book_ids=[self.book.pk],**data).status_code,400)
        self.assertEqual(self.person.spent_hit_dice,{'10':3,'6':2,'8':1});self.assertEqual(self.person.rest_revision,0)
        self.book.refresh_from_db();self.assertEqual(self.book.warlock_current_slots,0)
        self.person.current_hit_points=0;self.person.save()
        self.assertEqual(self.post('long_rest',completed='on').status_code,400)

    def test_empty_selection_does_not_reset_books(self):
        self.assertEqual(self.post('long_rest',completed='on').status_code,200)
        self.book.refresh_from_db();self.assertEqual((self.book.current_spell_slots_1,self.book.warlock_current_slots),(1,0))

    def test_revision_prevents_replay(self):
        values={'revision':0,'action':'short_rest','completed':'on','book_ids':[self.book.pk]}
        self.assertEqual(self.client.post(self.url,values).status_code,200)
        self.book.warlock_current_slots=0;self.book.save()
        result=self.client.post(self.url,values);self.assertEqual(result.status_code,409);self.assertEqual(result.json()['rest']['revision'],1)
        self.book.refresh_from_db();self.assertEqual(self.book.warlock_current_slots,0)

    def test_external_hp_change_invalidates_rest_revision(self):
        self.client.post(reverse('character_resource_change',args=[self.person.pk]),{'action':'damage','amount':1})
        self.assertEqual(self.client.post(self.url,{'revision':0,'action':'long_rest','completed':'on'}).status_code,409)

    def test_resources_bounds_and_manual_reset(self):
        response=self.post('resource_create',name='Удача',maximum=2,refresh_on='manual');self.assertEqual(response.status_code,200)
        resource=self.person.rest_resources.get(name='Удача')
        self.assertEqual(self.post('resource_change',resource_id=resource.pk,operation='restore').status_code,400)
        for _ in range(2):self.assertEqual(self.post('resource_change',resource_id=resource.pk,operation='spend').status_code,200)
        self.assertEqual(self.post('resource_change',resource_id=resource.pk,operation='spend').status_code,400)
        self.assertEqual(self.post('resource_change',resource_id=resource.pk,operation='restore').status_code,200)
        resource.refresh_from_db();self.assertEqual(resource.current,1)
        self.assertEqual(self.post('resource_delete',resource_id=resource.pk).status_code,200);self.assertFalse(CharacterResource.objects.filter(pk=resource.pk).exists())
        for values in ({'name':'','maximum':1,'refresh_on':'long'},{'name':'x','maximum':0,'refresh_on':'long'},{'name':'x','maximum':10000,'refresh_on':'long'},{'name':'x','maximum':1,'refresh_on':'bad'}):
            self.assertEqual(self.post('resource_create',**values).status_code,400)

    def test_owner_csrf_methods_and_foreign_objects(self):
        other_person=Person.objects.create(name='Чужой',player=Player.objects.create(user=self.other))
        foreign_book=Spellbook.objects.create(owner=other_person,name='Чужая книга')
        foreign_resource=CharacterResource.objects.create(person=other_person,name='Чужой ресурс')
        self.assertEqual(self.post('short_rest',completed='on',book_ids=[foreign_book.pk]).status_code,400)
        self.assertEqual(self.post('resource_delete',resource_id=foreign_resource.pk).status_code,404)
        self.assertEqual(self.client.get(self.url).status_code,405)
        client=Client(enforce_csrf_checks=True);client.force_login(self.user);self.assertEqual(client.post(self.url,{'action':'long_rest'}).status_code,403)
        self.client.force_login(self.other);self.assertEqual(self.post('long_rest',completed='on').status_code,404)
        self.client.logout();self.assertEqual(self.post('long_rest').status_code,302)

    def test_rest_buttons_need_no_confirmation_but_revision_required(self):
        self.assertEqual(self.post('short_rest').status_code,200)
        self.assertEqual(self.post('long_rest').status_code,200)
        self.assertEqual(self.client.post(self.url,{'action':'long_rest','completed':'on'}).status_code,400)
        self.assertEqual(self.person.current_hit_points,40)

    def test_pools_adjust_to_class_levels_and_first_level_recovers_one(self):
        self.person.character_class=None;self.person.second_class=None;self.person.second_class_level=0;self.person.warlock_level=0;self.person.primary_class_level=1;self.person.fallback_hit_die=12;self.person.spent_hit_dice={'12':4,'10':2};self.person.save()
        result=rest_state(self.person);self.assertEqual(result['dice'],[{'die':12,'maximum':1,'spent':1,'available':0,'recover':1}]);self.assertEqual(result['recovery_budget'],1)
        self.assertEqual(self.post('long_rest',completed='on',recover_12=1).status_code,200);self.assertEqual(self.person.spent_hit_dice,{'12':0})

    def test_transaction_rolls_back_book_on_unexpected_failure(self):
        with patch('spells.models.Person.save',side_effect=RuntimeError('db failure')):
            with self.assertRaises(RuntimeError):self.post('long_rest',completed='on',book_ids=[self.book.pk])
        self.book.refresh_from_db();self.short.refresh_from_db();self.assertEqual(self.book.current_spell_slots_1,1);self.assertEqual(self.short.current,0)

    def test_rest_interface_rendered_for_owner(self):
        response=self.client.get(reverse('character_detail_page',args=[self.person.pk]));self.assertEqual(response.status_code,200)
        self.assertContains(response,'character-rest-state');self.assertContains(response,'Короткий отдых');self.assertContains(response,'character_rests.js')
