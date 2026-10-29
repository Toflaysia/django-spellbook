from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse
from spells.models import Person,Player,Spell,Effect,CharacterCondition,ConcentrationCheck
from spells.combat import combat_state


class ConditionsConcentrationTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('combat-owner');self.other=User.objects.create_user('combat-other')
        self.person=Person.objects.create(name='Маг',player=Player.objects.create(user=self.user),constitution=14,primary_class_level=5,max_hit_points=60,current_hit_points=60,temporary_hit_points=5,check_settings={'saves':{'constitution':{'training':'proficient','bonus':1}}})
        self.foreign=Person.objects.create(name='Чужой',player=Player.objects.create(user=self.other))
        self.spell=Spell.objects.create(name='Удержание',concentration=True,is_official=True)
        self.spell2=Spell.objects.create(name='Полёт',concentration=True,is_official=True)
        self.instant=Spell.objects.create(name='Стрела',concentration=False,is_official=True)
        self.private=Spell.objects.create(name='Секрет',concentration=True,is_official=False,is_public=False,created_by=self.foreign.player)
        self.condition=Effect.objects.create(name='Отравлен',description='Помеха на проверки.',category='COND')
        self.effect=Effect.objects.create(name='Лечение',category='HEAL')
        self.url=reverse('character_combat_change',args=[self.person.pk]);self.client.force_login(self.user)

    def post(self,action,**data):
        self.person.refresh_from_db()
        response=self.client.post(self.url,{'revision':self.person.combat_revision,'action':action,**data})
        self.person.refresh_from_db();return response

    def start(self):
        self.assertEqual(self.post('concentration_start',spell_id=self.spell.pk).status_code,200)

    def damage(self,value):
        response=self.client.post(reverse('character_resource_change',args=[self.person.pk]),{'action':'damage','amount':value});self.person.refresh_from_db();return response

    def test_condition_add_update_remove_and_no_duplicates(self):
        self.assertEqual(self.post('condition_add',condition_id=self.condition.pk,note='Яд, 2 раунда').status_code,200)
        self.post('condition_add',condition_id=self.condition.pk,note='Ещё раунд')
        row=self.person.active_conditions.get();self.assertEqual(row.note,'Ещё раунд')
        data=combat_state(self.person,self.user)['conditions'][0];self.assertIn('Помеха',data['description']);self.assertEqual(data['url'],f'/catalog/conditions/{self.condition.pk}/')
        self.assertEqual(self.post('condition_remove',condition_row_id=row.pk).status_code,200);self.assertFalse(self.person.active_conditions.exists())

    def test_only_conditions_and_note_limit(self):
        self.assertEqual(self.post('condition_add',condition_id=self.effect.pk).status_code,404)
        self.assertEqual(self.post('condition_add',condition_id=self.condition.pk,note='x'*201).status_code,400)
        self.assertFalse(self.person.active_conditions.exists())

    def test_start_replace_requires_confirmation_and_keeps_one(self):
        self.start();self.damage(2)
        self.assertEqual(self.post('concentration_start',spell_id=self.spell2.pk).status_code,400)
        self.assertEqual(self.person.concentration_spell,self.spell)
        self.assertEqual(self.post('concentration_start',spell_id=self.spell2.pk,replace='on').status_code,200)
        self.assertEqual(self.person.concentration_spell,self.spell2);self.assertFalse(self.person.concentration_checks.exists())

    def test_start_rejects_private_nonconcentration_and_zero_hp(self):
        for spell in (self.private,self.instant):self.assertEqual(self.post('concentration_start',spell_id=spell.pk).status_code,404)
        self.person.current_hit_points=0;self.person.save()
        self.assertEqual(self.post('concentration_start',spell_id=self.spell.pk).status_code,400)

    def test_damage_each_source_counts_temporary_hp_and_rounds_down(self):
        self.start();response=self.damage(3);self.assertEqual(response.status_code,200)
        self.assertEqual(self.person.current_hit_points,60);self.assertEqual(self.person.temporary_hit_points,2)
        self.damage(27)
        self.assertEqual(list(self.person.concentration_checks.values_list('damage','dc')),[(3,10),(27,13)])
        self.assertEqual(len(response.json()['combat']['checks']),1)
        count=self.person.concentration_checks.count();self.damage(0);self.assertEqual(self.person.concentration_checks.count(),count)

    def test_zero_hp_ends_concentration_and_clears_pending(self):
        self.start();self.damage(1);response=self.damage(1000)
        self.assertEqual(self.person.current_hit_points,0);self.assertEqual(self.person.concentration_name,'');self.assertIsNone(self.person.concentration_spell)
        self.assertFalse(self.person.concentration_checks.exists());self.assertIn('прекращена',response.json()['message'])

    def test_save_uses_constitution_mastery_bonus_and_equality_passes(self):
        self.start();self.damage(1);check=self.person.concentration_checks.get()
        self.assertEqual(combat_state(self.person,self.user)['save_bonus'],6)
        with patch('spells.combat.secrets.randbelow',return_value=3):response=self.post('concentration_roll',check_id=check.pk,mode='normal')
        self.assertEqual(response.status_code,200);self.assertIn('= 10, СЛ 10',response.json()['message']);self.assertEqual(self.person.concentration_name,'Удержание');self.assertFalse(self.person.concentration_checks.exists())

    def test_advantage_success_and_disadvantage_failure_clears_all(self):
        self.start();self.damage(1)
        with patch('spells.combat.secrets.randbelow',side_effect=[0,19]):response=self.post('concentration_roll',check_id=self.person.concentration_checks.first().pk,mode='advantage')
        self.assertIn('сохранена',response.json()['message'])
        self.damage(1);self.damage(1)
        with patch('spells.combat.secrets.randbelow',side_effect=[0,19]):response=self.post('concentration_roll',check_id=self.person.concentration_checks.first().pk,mode='disadvantage')
        self.assertIn('прекращена',response.json()['message']);self.assertEqual(self.person.concentration_name,'');self.assertFalse(self.person.concentration_checks.exists())

    def test_natural_twenty_not_automatic_success_on_saving_throw(self):
        self.start();self.post('concentration_check_add',dc=30)
        with patch('spells.combat.secrets.randbelow',return_value=19):response=self.post('concentration_roll',check_id=self.person.concentration_checks.first().pk,mode='normal')
        self.assertIn('прекращена',response.json()['message'])

    def test_manual_results_external_dice(self):
        self.start();self.post('concentration_check_add',dc=15);check=self.person.concentration_checks.get()
        self.assertEqual(self.post('concentration_manual',check_id=check.pk,outcome='success').status_code,200)
        self.assertTrue(self.person.concentration_name)
        self.post('concentration_check_add',dc=10)
        self.assertEqual(self.post('concentration_manual',check_id=self.person.concentration_checks.get().pk,outcome='failure').status_code,200)
        self.assertEqual(self.person.concentration_name,'')

    def test_incapacitating_condition_ends_and_blocks_concentration(self):
        self.start();self.damage(1)
        self.post('condition_add',condition_id=self.condition.pk,incapacitates='on')
        self.assertEqual(self.person.concentration_name,'');self.assertFalse(self.person.concentration_checks.exists())
        self.assertEqual(self.post('concentration_start',spell_id=self.spell.pk).status_code,400)
        self.post('condition_remove',condition_row_id=self.person.active_conditions.get().pk);self.start()

    def test_normal_condition_does_not_change_concentration(self):
        self.start();self.post('condition_add',condition_id=self.condition.pk)
        self.assertEqual(self.person.concentration_name,self.spell.name)

    def test_stop_clears_pending_and_rest_does_not_remove_conditions(self):
        self.start();self.damage(1);self.post('concentration_end');self.assertFalse(self.person.concentration_checks.exists())
        self.post('condition_add',condition_id=self.condition.pk);self.start()
        rest=reverse('character_rest_change',args=[self.person.pk])
        self.assertEqual(self.client.post(rest,{'revision':self.person.rest_revision,'action':'short_rest','completed':'on'}).status_code,200)
        self.person.refresh_from_db();self.assertTrue(self.person.concentration_name)
        response=self.client.post(rest,{'revision':self.person.rest_revision,'action':'long_rest','completed':'on'})
        self.person.refresh_from_db();self.assertEqual(response.status_code,200);self.assertEqual(self.person.concentration_name,'');self.assertEqual(response.json()['combat']['concentration']['name'],'');self.assertTrue(self.person.active_conditions.exists())

    def test_replay_and_stale_damage_are_not_applied(self):
        self.start();revision=self.person.combat_revision;self.damage(1)
        self.assertEqual(self.client.post(self.url,{'revision':revision,'action':'concentration_end'}).status_code,409)
        check=self.person.concentration_checks.get();self.person.refresh_from_db();revision=self.person.combat_revision
        body={'revision':revision,'action':'concentration_manual','check_id':check.pk,'outcome':'success'}
        self.assertEqual(self.client.post(self.url,body).status_code,200);self.assertEqual(self.client.post(self.url,body).status_code,409)

    def test_owner_methods_csrf_and_foreign_rows(self):
        row=CharacterCondition.objects.create(person=self.foreign,condition=self.condition)
        check=ConcentrationCheck.objects.create(person=self.foreign)
        self.assertEqual(self.post('condition_remove',condition_row_id=row.pk).status_code,404)
        self.assertEqual(self.post('concentration_manual',check_id=check.pk,outcome='failure').status_code,404)
        self.assertEqual(self.client.get(self.url).status_code,405)
        client=Client(enforce_csrf_checks=True);client.force_login(self.user);self.assertEqual(client.post(self.url,{'action':'concentration_end'}).status_code,403)
        self.client.force_login(self.other);self.assertEqual(self.post('concentration_end').status_code,404)
        self.client.logout();self.assertEqual(self.post('concentration_end').status_code,302)

    def test_search_visibility_concentration_and_owner(self):
        url=reverse('concentration_spell_search',args=[self.person.pk])
        result=self.client.get(url).json()['spells'];self.assertEqual({r['name'] for r in result},{'Удержание','Полёт'})
        self.assertEqual(len(self.client.get(url,{'search':'Пол'}).json()['spells']),1)
        self.client.force_login(self.other);self.assertEqual(self.client.get(url).status_code,404)

    def test_validation_invalid_roll_does_not_consume_check(self):
        self.start();self.post('concentration_check_add',dc=10);check=self.person.concentration_checks.get()
        self.assertEqual(self.post('concentration_roll',check_id=check.pk,mode='bad').status_code,400)
        self.assertTrue(self.person.concentration_checks.filter(pk=check.pk).exists())
        for value in ('-1','x','0','1.5'):self.assertEqual(self.post('concentration_check_add',dc=value).status_code,400)
        self.assertEqual(self.client.post(self.url,{'action':'concentration_end'}).status_code,400)

    def test_atomic_damage_rollback_if_saving_person_fails(self):
        self.start()
        with patch('spells.models.Person.save',side_effect=RuntimeError('failure')):
            with self.assertRaises(RuntimeError):self.damage(1)
        self.person.refresh_from_db();self.assertEqual(self.person.temporary_hit_points,5);self.assertFalse(self.person.concentration_checks.exists())

    def test_rendering_includes_states_but_not_effects(self):
        response=self.client.get(reverse('character_detail_page',args=[self.person.pk]));self.assertEqual(response.status_code,200)
        html=response.content.decode();overview=html.split('id="overview"',1)[1].split('id="character-spellbooks"',1)[0];health=html.split('id="health"',1)[1]
        self.assertNotIn('data-condition-list',overview);self.assertIn('data-condition-list',health)
        catalog=response.context['condition_catalog'];self.assertEqual([r['id'] for r in catalog],[self.condition.pk])

    def test_edit_to_zero_hp_ends_concentration_and_preserves_conditions(self):
        from spells.forms import CharacterEditForm
        self.start();self.damage(1);self.post('condition_add',condition_id=self.condition.pk)
        form=CharacterEditForm(instance=self.person,user=self.user);data={}
        for name in form.fields:
            if name=='portrait':continue
            value=form[name].value()
            if isinstance(value,bool):
                if value:data[name]='on'
            elif value is not None:data[name]=value
        data['current_hit_points']=0;data['checks_present']='on'
        response=self.client.post(reverse('character_edit_page',args=[self.person.pk]),data)
        self.assertEqual(response.status_code,302);self.person.refresh_from_db()
        self.assertEqual(self.person.concentration_name,'');self.assertFalse(self.person.concentration_checks.exists());self.assertTrue(self.person.active_conditions.exists())
