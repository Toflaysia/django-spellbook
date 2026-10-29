from copy import deepcopy
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from spells.models import Person, Player
from spells.forms import CharacterEditForm


class CharacterEditFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user=User.objects.create_user('edit-owner');cls.other=User.objects.create_user('edit-other')
        cls.person=Person.objects.create(name='Карточка',player=Player.objects.create(user=cls.user),dexterity=16,primary_class_level=5,check_settings={'skills':{'sleight_of_hand':{'training':'expertise','bonus':3},'perception':{'training':'proficient','bonus':0}},'speeds':{'fly':{'base':60}}})
    def setUp(self):self.client.force_login(self.user)
    def payload(self):
        form=CharacterEditForm(instance=self.person);data={}
        # Submit only fields actually rendered in the simplified editor.
        for name in form.Meta.fields:
            value=form[name].value()
            if name=='portrait':continue
            if type(value) is bool:
                if value:data[name]='on'
            elif value is not None:data[name]=value
        data['checks_present']='on'
        for name,field in form.fields.items():
            if not name.startswith('checks_') or name.startswith('checks_skills_') or name=='checks_present':continue
            value=form[name].value()
            if type(value) is bool:
                if value:data[name]='on'
            elif value is not None:data[name]=value
        return data
    def test_save_redirects_to_character_and_preserves_skills(self):
        skills=deepcopy(self.person.check_settings['skills'])
        data=self.payload();data['dexterity']='18'
        response=self.client.post(reverse('character_edit_page',args=[self.person.pk]),data)
        self.assertRedirects(response,reverse('character_detail_page',args=[self.person.pk]))
        self.person.refresh_from_db();self.assertEqual(self.person.check_settings['skills'],skills)
        row=next(r for r in self.person.computed_checks['skills'] if r['key']=='sleight_of_hand')
        self.assertEqual(row['total'],13)
    def test_ability_and_save_rows_are_paired_and_skills_tab_absent(self):
        form=CharacterEditForm(instance=self.person)
        groups=form.field_groups
        self.assertNotIn('skills',[g['id'] for g in groups])
        rows=next(g for g in groups if g['id']=='abilities')['ability_rows']
        self.assertEqual(len(rows),6)
        for row in rows:self.assertEqual(row['field'].name,row['save']['key'])
        html=self.client.get(reverse('character_edit_page',args=[self.person.pk]))
        self.assertNotContains(html,'name="checks_skills_sleight_of_hand_training"')
        self.assertContains(html,'class="ability-edit-card"',count=6)
    def test_bonus_updates_preserve_training_and_other_settings(self):
        url=reverse('character_resource_change',args=[self.person.pk])
        response=self.client.post(url,{'action':'check_bonus','group':'skills','key':'perception','bonus':'-2'})
        self.assertEqual(response.status_code,200)
        self.person.refresh_from_db()
        self.assertEqual(self.person.check_settings['skills']['perception'],{'training':'proficient','bonus':-2})
        self.assertEqual(self.person.check_settings['speeds']['fly']['base'],60)
        self.assertEqual(next(r for r in response.json()['checks']['passives'] if r['key']=='perception')['total'],11)
    def test_invalid_bonus_is_rejected_without_changes(self):
        old=deepcopy(self.person.check_settings);url=reverse('character_resource_change',args=[self.person.pk])
        for group,key,value in [('skills','perception','1001'),('skills','perception','1.5'),('skills','perception',''),('skills','wrong','3'),('other','perception','3')]:
            self.assertEqual(self.client.post(url,{'action':'check_bonus','group':group,'key':key,'bonus':value}).status_code,400)
        self.person.refresh_from_db();self.assertEqual(self.person.check_settings,old)
    def test_bonus_update_requires_owner_and_csrf(self):
        url=reverse('character_resource_change',args=[self.person.pk]);payload={'action':'check_bonus','group':'skills','key':'perception','bonus':'4'}
        self.client.force_login(self.other);self.assertEqual(self.client.post(url,payload).status_code,404)
        client=Client(enforce_csrf_checks=True);client.force_login(self.user);self.assertEqual(client.post(url,payload).status_code,403)
