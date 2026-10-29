from copy import deepcopy
from django.test import TestCase,Client
from django.contrib.auth.models import User
from django.urls import reverse
from spells.models import Person,Player
from spells.forms import CharacterEditForm
from spells.training_widgets import TrainingCircles


class TrainingCircleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user=User.objects.create_user('circle-owner');cls.other=User.objects.create_user('circle-other')
        cls.person=Person.objects.create(name='Кружочки',player=Player.objects.create(user=cls.user),dexterity=16,wisdom=14,primary_class_level=5,check_settings={'skills':{'sleight_of_hand':{'training':'none','bonus':2}},'speeds':{'fly':{'base':60}},'passives':{'perception':{'bonus':5}}})
    def setUp(self):self.client.force_login(self.user)
    def url(self):return reverse('character_resource_change',args=[self.person.pk])
    def test_skills_grouped_below_corresponding_ability(self):
        response=self.client.get(reverse('character_detail_page',args=[self.person.pk]))
        cards={x['key']:x for x in response.context['ability_cards']}
        self.assertEqual([x['key'] for x in cards['dexterity']['skills']],['acrobatics','sleight_of_hand','stealth'])
        self.assertEqual(cards['constitution']['skills'],[])
        self.assertContains(response,'class="training-cycle"',count=24)
        self.assertNotContains(response,'>Навыки и спасброски</button>')
    def test_cycle_persists_bonus_and_other_settings(self):
        for training,total in [('proficient',8),('expertise',11),('half',6),('none',5)]:
            response=self.client.post(self.url(),{'action':'training','group':'skills','key':'sleight_of_hand','training':training})
            self.assertEqual(response.status_code,200)
            row=next(x for x in response.json()['checks']['skills'] if x['key']=='sleight_of_hand')
            self.assertEqual(row['total'],total)
            self.person.refresh_from_db()
            self.assertEqual(self.person.check_settings['skills']['sleight_of_hand']['bonus'],2)
            self.assertEqual(self.person.check_settings['speeds']['fly']['base'],60)
    def test_passive_updates_and_save_toggle(self):
        response=self.client.post(self.url(),{'action':'training','group':'skills','key':'perception','training':'expertise'})
        row=next(x for x in response.json()['checks']['passives'] if x['key']=='perception')
        self.assertEqual(row['total'],23)
        response=self.client.post(self.url(),{'action':'training','group':'saves','key':'dexterity','training':'proficient'})
        self.assertEqual(response.json()['checks']['saves'][1]['total'],6)
    def test_invalid_requests_make_no_change(self):
        old=deepcopy(self.person.check_settings)
        for group,key,training in [('saves','dexterity','expertise'),('skills','bad','proficient'),('wrong','dexterity','proficient'),('skills','arcana','invalid')]:
            self.assertEqual(self.client.post(self.url(),{'action':'training','group':group,'key':key,'training':training}).status_code,400)
        self.person.refresh_from_db();self.assertEqual(self.person.check_settings,old)
    def test_ownership_authentication_and_csrf(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.url(),{'action':'training','group':'skills','key':'arcana','training':'proficient'}).status_code,404)
        self.client.logout();self.assertEqual(self.client.post(self.url(),{'action':'training'}).status_code,302)
        client=Client(enforce_csrf_checks=True);client.force_login(self.user)
        self.assertEqual(client.post(self.url(),{'action':'training'}).status_code,403)
    def test_form_uses_native_radio_groups_and_preserves_initial(self):
        self.person.check_settings['skills']['sleight_of_hand']['training']='expertise'
        form=CharacterEditForm(instance=self.person)
        self.assertIsInstance(form.fields['checks_skills_sleight_of_hand_training'].widget,TrainingCircles)
        html=str(form['checks_skills_sleight_of_hand_training'])
        self.assertIn('value="expertise"',html);self.assertIn('checked',html)
        self.assertEqual(html.count('type="radio"'),4)
