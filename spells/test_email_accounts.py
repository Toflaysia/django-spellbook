import re
import uuid
from datetime import timedelta
from urllib.parse import urlsplit
from unittest.mock import patch
from django.test import TestCase,override_settings,Client
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core import mail,signing
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from spells.models import AccountEmail,Player
from spells.email_accounts import confirmation_token,send_confirmation

MAIL_SETTINGS={'EMAIL_BACKEND':'django.core.mail.backends.locmem.EmailBackend','SPELLBOOK_EMAIL_DELIVERY_ENABLED':True,'SPELLBOOK_SITE_URL':'https://spellbook.example','DEFAULT_FROM_EMAIL':'noreply@spellbook.example'}

@override_settings(**MAIL_SETTINGS)
class EmailAccountTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user=User.objects.create_user('mail-user',email='owner@example.com',password='Existing-Password-42')
        cls.other=User.objects.create_user('other-mail',email='other@example.com',password='Other-Password-42')
        cls.address=AccountEmail.objects.create(user=cls.user,email='owner@example.com')
        AccountEmail.objects.create(user=cls.other,email='other@example.com',verified_at=timezone.now())

    def test_html_registration_normalizes_and_requires_unique_email(self):
        url=reverse('register')
        data={'username':'new-mail-user','email':' New.Address@Example.COM ','password1':'Unique-Test-Password-42','password2':'Unique-Test-Password-42'}
        response=self.client.post(url,data)
        self.assertRedirects(response,reverse('account_email_page'))
        user=User.objects.get(username='new-mail-user')
        self.assertEqual(user.email,'new.address@example.com')
        self.assertTrue(Player.objects.filter(user=user).exists())
        self.assertIsNone(user.account_email.verified_at)
        self.assertEqual(len(mail.outbox),1)
        self.client.logout()
        data.update(username='duplicate-user',email='NEW.ADDRESS@EXAMPLE.COM')
        self.assertContains(self.client.post(url,data),'Этот email уже используется')
        self.assertFalse(User.objects.filter(username='duplicate-user').exists())
        data.update(username='no-email',email='')
        self.assertEqual(self.client.post(url,data).status_code,200)
        self.assertFalse(User.objects.filter(username='no-email').exists())

    def test_username_cannot_shadow_an_email_login(self):
        data={'username':'owner@example.com','email':'fresh@example.com','password1':'Unique-Test-Password-42','password2':'Unique-Test-Password-42'}
        self.assertContains(self.client.post(reverse('register'),data),'Имя пользователя укажи без @')
        self.assertFalse(User.objects.filter(username='owner@example.com').exists())

    def test_existing_username_and_verified_email_login(self):
        self.assertIsNotNone(authenticate(username='mail-user',password='Existing-Password-42'))
        self.assertIsNone(authenticate(username='owner@example.com',password='Existing-Password-42'))
        self.address.verified_at=timezone.now();self.address.save()
        self.assertIsNotNone(authenticate(username='OWNER@EXAMPLE.COM',password='Existing-Password-42'))
        response=self.client.post(reverse('login'),{'username':'OWNER@EXAMPLE.COM','password':'Existing-Password-42'})
        self.assertEqual(response.status_code,302)
        self.user.is_active=False;self.user.save()
        self.assertIsNone(authenticate(username='owner@example.com',password='Existing-Password-42'))

    def test_confirmation_requires_post_is_single_use_and_expires(self):
        token=confirmation_token(self.address);url=reverse('confirm_email',args=[token])
        self.assertContains(self.client.get(url),'Подтвердить email')
        self.address.refresh_from_db();self.assertIsNone(self.address.verified_at)
        self.assertContains(self.client.post(url),'Email подтверждён')
        self.address.refresh_from_db();self.assertIsNotNone(self.address.verified_at)
        self.assertContains(self.client.post(url),'Ссылка недействительна')
        self.assertContains(self.client.get(reverse('confirm_email',args=[token+'bad'])),'Ссылка недействительна')
        self.address.verified_at=None;self.address.confirmation_nonce=uuid.uuid4();self.address.save()
        with patch('django.core.signing.time.time',return_value=1000000):token=confirmation_token(self.address)
        with patch('django.core.signing.time.time',return_value=1000000+49*60*60):
            self.assertContains(self.client.get(reverse('confirm_email',args=[token])),'Ссылка недействительна')

    def test_change_requires_password_and_preserves_other_account(self):
        self.address.verified_at=timezone.now();self.address.save()
        old=confirmation_token(self.address)
        self.client.force_login(self.user)
        url=reverse('account_email_page')
        self.assertContains(self.client.post(url,{'email':'new@example.com','password':'wrong'}),'Неверный текущий пароль')
        self.address.refresh_from_db();self.assertEqual(self.address.email,'owner@example.com')
        self.assertContains(self.client.post(url,{'email':'OTHER@EXAMPLE.COM','password':'Existing-Password-42'}),'Этот email уже используется')
        response=self.client.post(url,{'email':'new@example.com','password':'Existing-Password-42','user':self.other.pk})
        self.assertEqual(response.status_code,302)
        self.address.refresh_from_db();self.user.refresh_from_db()
        self.assertEqual(self.address.email,'new@example.com');self.assertEqual(self.user.email,'new@example.com')
        self.assertIsNone(self.address.verified_at)
        self.assertEqual(AccountEmail.objects.get(user=self.other).email,'other@example.com')
        self.assertContains(self.client.get(reverse('confirm_email',args=[old])),'Ссылка недействительна')
        self.assertIsNone(authenticate(username='new@example.com',password='Existing-Password-42'))

    def test_confirmation_send_cooldown_failure_and_disabled_mail(self):
        self.assertEqual(send_confirmation(self.user),'sent')
        self.assertEqual(send_confirmation(self.user),'throttled')
        self.assertEqual(len(mail.outbox),1)
        self.address.refresh_from_db();self.address.confirmation_sent_at=None;self.address.save()
        with self.assertLogs('spells.email_accounts',level='ERROR'),patch('spells.email_accounts.send_mail',side_effect=OSError('offline')):
            self.assertEqual(send_confirmation(self.user),'failed')
        self.address.refresh_from_db();self.assertIsNone(self.address.confirmation_sent_at)
        with override_settings(SPELLBOOK_EMAIL_DELIVERY_ENABLED=False):
            self.assertEqual(send_confirmation(self.user),'unavailable')

    def test_reset_unknown_unverified_and_verified_response_and_host(self):
        url=reverse('password_reset')
        for email in ('unknown@example.com','owner@example.com'):
            self.assertRedirects(self.client.post(url,{'email':email}),reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox),0)
        self.address.verified_at=timezone.now();self.address.save()
        self.client.post(url,{'email':'OWNER@EXAMPLE.COM'},HTTP_HOST='testserver')
        self.assertEqual(len(mail.outbox),1)
        message=mail.outbox[0]
        self.assertEqual(message.to,['owner@example.com'])
        self.assertIn('https://spellbook.example/password-reset/',message.body)
        self.assertNotIn('testserver',message.body)
        self.client.post(url,{'email':'owner@example.com'})
        self.assertEqual(len(mail.outbox),1)
        link=re.search(r'https://spellbook.example/\S+',message.body)[0]
        response=self.client.get(urlsplit(link).path)
        self.assertEqual(response.status_code,302)
        response=self.client.post(response['Location'],{'new_password1':'Replacement-Password-42','new_password2':'Replacement-Password-42'})
        self.assertRedirects(response,reverse('password_reset_complete'))
        self.user.refresh_from_db();self.assertTrue(self.user.check_password('Replacement-Password-42'))
        self.assertContains(self.client.get(urlsplit(link).path),'Ссылка недействительна')

    def test_api_registration_and_duplicate_addresses(self):
        client=APIClient()
        data={'username':'api-mail','email':'Api@Example.COM','password':'Unique-Test-Password-42','password_confirm':'Unique-Test-Password-42'}
        response=client.post(reverse('spells:register'),data)
        self.assertEqual(response.status_code,201,response.data)
        self.assertEqual(response.data['email'],'api@example.com')
        self.assertEqual(response.data['email_confirmation_status'],'sent')
        data.update(username='another-api',email='API@EXAMPLE.COM')
        self.assertEqual(client.post(reverse('spells:register'),data).status_code,400)

    def test_settings_resend_and_confirmation_csrf(self):
        client=Client(enforce_csrf_checks=True)
        self.assertEqual(client.get(reverse('account_email_page')).status_code,302)
        client.force_login(self.user)
        self.assertEqual(client.post(reverse('account_email_page'),{'email':'x@example.com','password':'Existing-Password-42'}).status_code,403)
        self.assertEqual(client.post(reverse('resend_confirmation')).status_code,403)
        self.assertEqual(client.get(reverse('resend_confirmation')).status_code,405)
        token=confirmation_token(self.address)
        self.assertEqual(client.post(reverse('confirm_email',args=[token])).status_code,403)
