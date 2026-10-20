from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from spells.models import Player,Person
from spells.views.play_tools import COINS

class ConversionTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('exchange')
        self.other=User.objects.create_user('other-exchange')
        self.person=Person.objects.create(name='Герой',player=Player.objects.create(user=self.user),silver_coins=15)
        self.client.force_login(self.user)
        self.url=reverse('character_resource_change',args=[self.person.pk])

    def exchange(self,source,target,amount):
        return self.client.post(self.url,{'action':'convert','from_coin':source,'to_coin':target,'amount':amount})

    def test_integer_exchange_retains_remainder(self):
        response=self.exchange('silver','gold','15')
        self.assertEqual(response.status_code,200)
        self.person.refresh_from_db()
        self.assertEqual((self.person.silver_coins,self.person.gold_coins),(5,1))
        self.assertEqual(response.json()['gold_total'],'1.5')

    def test_all_currency_pairs_conserve_total(self):
        names=[name for name,*_ in COINS]
        for source in names:
            for target in names:
                if source==target:continue
                for name in names:setattr(self.person,name+'_coins',1000 if name==source else 0)
                self.person.save()
                before=sum(getattr(self.person,name+'_coins')*rate for name,_,_,rate in COINS)
                self.assertEqual(self.exchange(source,target,1000).status_code,200)
                self.person.refresh_from_db()
                after=sum(getattr(self.person,name+'_coins')*rate for name,_,_,rate in COINS)
                self.assertEqual(before,after,(source,target))

    def test_invalid_or_insufficient_exchange_does_not_change_balance(self):
        for source,target,amount in [('silver','silver',10),('silver','gold',16),('silver','gold',1),('fake','gold',1),('silver','gold','-5')]:
            self.assertEqual(self.exchange(source,target,amount).status_code,400)
            self.person.refresh_from_db();self.assertEqual(self.person.silver_coins,15);self.assertEqual(self.person.gold_coins,0)
        self.client.force_login(self.other)
        self.assertEqual(self.exchange('silver','gold',10).status_code,404)
