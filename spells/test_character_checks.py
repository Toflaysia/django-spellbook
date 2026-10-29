from django.test import TestCase, SimpleTestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.urls import reverse
from spells.models import Person, Player
from spells.character_checks import calculated_checks, level_proficiency, validate_check_settings
from spells.forms import CharacterCreateForm, CharacterEditForm
from spells.serializers import CharacterSerializer


class CheckRulesTests(SimpleTestCase):
    def person(self,**kw):return Person(**kw)
    def skill(self,p,key):return next(x for x in calculated_checks(p)['skills'] if x['key']==key)
    def test_proficiency_all_levels_and_multiclass(self):
        self.assertEqual([level_proficiency(i) for i in range(1,21)],[2]*4+[3]*4+[4]*4+[5]*4+[6]*4)
        p=self.person(primary_class_level=3,second_class_level=2)
        self.assertEqual(p.effective_proficiency_bonus,3)
    def test_all_skills_and_saves_correct_ability(self):
        p=self.person(strength=8,dexterity=16,constitution=13,intelligence=18,wisdom=15,charisma=6)
        checks=calculated_checks(p)
        self.assertEqual(len(checks['skills']),18);self.assertEqual(len(checks['saves']),6)
        self.assertEqual(self.skill(p,'sleight_of_hand')['total'],3)
        self.assertEqual(self.skill(p,'perception')['total'],2)
        self.assertEqual(self.skill(p,'investigation')['total'],4)
        self.assertEqual(self.skill(p,'athletics')['total'],-1)
    def test_training_modes_negative_mod_and_bonus(self):
        p=self.person(primary_class_level=5,dexterity=9)
        for training,expected in [('none',-1),('half',0),('proficient',2),('expertise',5)]:
            p.check_settings={'skills':{'sleight_of_hand':{'training':training,'bonus':-2}}}
            self.assertEqual(self.skill(p,'sleight_of_hand')['total'],expected-2)
    def test_passive_checks_specific_bonus_and_cancellation(self):
        p=self.person(wisdom=16,primary_class_level=5,check_settings={'skills':{'perception':{'training':'expertise','bonus':1}},'passives':{'perception':{'bonus':5,'advantage':True,'disadvantage':False}}})
        self.assertEqual(next(x for x in p.computed_checks['passives'] if x['key']=='perception')['total'],30)
        p.check_settings['passives']['perception']['disadvantage']=True
        self.assertEqual(p.computed_checks['passives'][0]['total'],25)
    def test_initiative_saves_and_spell_stats_share_proficiency(self):
        p=self.person(dexterity=16,wisdom=18,primary_class_level=5,initiative_bonus=2,spellcasting_ability='WIS',check_settings={'initiative_half':True,'saves':{'dexterity':{'training':'proficient','bonus':1}}})
        self.assertEqual(p.computed_checks['initiative']['total'],6)
        self.assertEqual(p.computed_checks['saves'][1]['total'],7)
        self.assertEqual(p.spell_save_dc,15);self.assertEqual(p.spell_attack_bonus,7)
        p.check_settings['proficiency_override']=5
        self.assertEqual(p.spell_save_dc,17)
    def test_speed_floor_minimum_and_factors(self):
        p=self.person(speed=31,check_settings={'speeds':{'walk':{'bonus':-2,'factor':'half'},'fly':{'base':60,'bonus':10,'factor':'double'},'swim':{'base':10,'bonus':-30}}})
        self.assertEqual([x['total'] for x in p.computed_checks['speeds']],[14,140,0,0,0])
        p.check_settings['speeds']['walk']['factor']='stopped'
        self.assertEqual(p.computed_checks['speeds'][0]['total'],0)
    def test_invalid_settings_rejected(self):
        for config in [[],{'skills':[]},{'skills':{'wrong':{}}},{'skills':{'arcana':{'training':[]}}},{'saves':{'strength':{'training':'expertise'}}},{'proficiency_override':True},{'passives':{'perception':{'advantage':'yes'}}},{'speeds':{'walk':{'factor':[]}}},{'skills':{'arcana':{'bonus':1001}}}]:
            with self.subTest(config=config),self.assertRaises(ValidationError):validate_check_settings(config)


class CheckFormsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user=User.objects.create_user('checks-owner');cls.other=User.objects.create_user('checks-other')
        cls.player=Player.objects.create(user=cls.user)
        cls.person=Person.objects.create(name='Навыки',player=cls.player)
    def data(self):
        form=CharacterEditForm(instance=self.person)
        result={}
        for key in form.Meta.fields:
            field=form[key];v=field.value()
            if isinstance(v,bool):
                if v:result[key]='on'
            elif v is not None:result[key]=v
        result.pop('portrait',None);return result
    def test_create_edit_and_commit_false_store_checked_settings(self):
        data=self.data();data.update(checks_present='on',checks_skills_sleight_of_hand_training='expertise',checks_skills_sleight_of_hand_bonus='2',checks_proficiency_override='',checks_initiative_bonus='3')
        form=CharacterEditForm(data,instance=self.person,user=self.user)
        self.assertTrue(form.is_valid(),form.errors)
        p=form.save(commit=False);self.assertEqual(p.check_settings['skills']['sleight_of_hand']['training'],'expertise');p.save()
        p.refresh_from_db();self.assertEqual(p.computed_checks['initiative']['total'],3)
        self.assertEqual(p.check_settings['skills']['sleight_of_hand']['bonus'],2)
    def test_old_submission_and_omitted_settings_do_not_reset(self):
        self.person.check_settings={'proficiency_override':4};self.person.save()
        f=CharacterEditForm(self.data(),instance=self.person,user=self.user)
        self.assertTrue(f.is_valid(),f.errors);f.save();self.person.refresh_from_db()
        self.assertEqual(self.person.check_settings,{'proficiency_override':4})
    def test_numeric_field_validation(self):
        data=self.data();data.update(checks_present='on',checks_skills_arcana_bonus='not a number')
        f=CharacterEditForm(data,instance=self.person,user=self.user)
        self.assertFalse(f.is_valid());self.assertIn('checks_skills_arcana_bonus',f.errors)
    def test_pages_and_ownership(self):
        self.client.force_login(self.user)
        response=self.client.get(reverse('character_detail_page',args=[self.person.pk]))
        self.assertContains(response,'Ловкость рук');self.assertContains(response,'Пассивные значения')
        response=self.client.get(reverse('character_edit_page',args=[self.person.pk]))
        self.assertNotContains(response,'name="checks_skills_investigation_training"');self.assertContains(response,'checks_present')
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('character_edit_page',args=[self.person.pk])).status_code,404)
        self.assertEqual(self.client.post(reverse('character_edit_page',args=[self.person.pk]),self.data()).status_code,404)
    def test_api_validates_settings_and_manual_bonus(self):
        serializer=CharacterSerializer(self.person,data={'check_settings':{'skills':{'arcana':{'training':[]}}}},partial=True)
        self.assertFalse(serializer.is_valid())
        serializer=CharacterSerializer(self.person,data={'proficiency_bonus':4},partial=True)
        self.assertTrue(serializer.is_valid(),serializer.errors);p=serializer.save()
        self.assertEqual(p.effective_proficiency_bonus,4)
        self.assertEqual(CharacterSerializer(p).data['proficiency_bonus'],4)
