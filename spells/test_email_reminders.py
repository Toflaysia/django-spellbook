from datetime import datetime,time,timedelta
from io import StringIO
from unittest.mock import patch
from django.test import TestCase,override_settings
from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.utils import timezone
from spells.models import AccountEmail,HomePlan
from spells.reminders import send_due_reminders
from spells.views.plans import PlanForm

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',SPELLBOOK_EMAIL_DELIVERY_ENABLED=True,SPELLBOOK_SITE_URL='https://spellbook.example',DEFAULT_FROM_EMAIL='noreply@example.com')
class EmailReminderTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('reminder-user',email='reminder@example.com')
        self.address=AccountEmail.objects.create(user=self.user,email=self.user.email,verified_at=timezone.now())
        self.now=timezone.make_aware(datetime(2026,10,20,10,0))
        self.plan=HomePlan.objects.create(user=self.user,title='Подготовить игру',text='Бросить [[dice:2d6|2к6]].',email_reminder=True,reminder_date=self.now.date(),reminder_time=time(9,0))

    def test_due_once_private_recipient_and_rescheduled_date(self):
        result=send_due_reminders(now=self.now)
        self.assertEqual(result,{'due':1,'sent':1,'failed':0})
        self.assertEqual(mail.outbox[0].to,['reminder@example.com'])
        self.assertIn('Подготовить игру',mail.outbox[0].body)
        self.assertIn('2к6',mail.outbox[0].body)
        self.assertNotIn('[[dice:',mail.outbox[0].body)
        self.assertEqual(send_due_reminders(now=self.now)['sent'],0)
        self.plan.refresh_from_db();self.assertEqual(self.plan.email_sent_for_date,self.plan.reminder_date)
        self.plan.reminder_date-=timedelta(days=1);self.plan.save()
        self.assertEqual(send_due_reminders(now=self.now)['sent'],1)

    def test_not_yet_due_done_and_unverified_are_not_sent(self):
        self.plan.reminder_time=time(11,0);self.plan.save()
        self.assertEqual(send_due_reminders(now=self.now)['sent'],0)
        self.plan.reminder_time=time(9,0);self.plan.is_done=True;self.plan.save()
        self.assertEqual(send_due_reminders(now=self.now)['sent'],0)
        self.plan.is_done=False;self.plan.save()
        self.address.verified_at=None;self.address.save()
        self.assertEqual(send_due_reminders(now=self.now)['sent'],0)
        self.address.verified_at=timezone.now();self.address.save()
        self.user.is_active=False;self.user.save()
        self.assertEqual(send_due_reminders(now=self.now)['sent'],0)

    def test_delivery_error_retries_and_concurrent_claim_is_skipped(self):
        with self.assertLogs('spells.reminders',level='ERROR'),patch('spells.reminders.send_mail',side_effect=OSError('offline')):
            self.assertEqual(send_due_reminders(now=self.now)['failed'],1)
        self.plan.refresh_from_db();self.assertIsNone(self.plan.email_sent_at);self.assertIsNone(self.plan.email_sending_started_at)
        self.plan.email_sending_started_at=self.now;self.plan.save()
        self.assertEqual(send_due_reminders(now=self.now)['sent'],0)
        self.plan.email_sending_started_at=self.now-timedelta(minutes=31);self.plan.save()
        self.assertEqual(send_due_reminders(now=self.now)['sent'],1)

    def test_form_requires_verified_email_date_and_defaults_time(self):
        self.address.verified_at=None;self.address.save()
        form=PlanForm({'title':'План','email_reminder':'on'},user=self.user)
        self.assertTrue(form.fields['email_reminder'].disabled)
        self.assertFalse(form.is_valid());self.assertIn('email_reminder',form.errors)
        self.address.verified_at=timezone.now();self.address.save()
        form=PlanForm({'title':'План','email_reminder':'on','reminder_date':'2026-10-20'},user=self.user)
        self.assertFalse(form.fields['email_reminder'].disabled)
        self.assertFalse(form.is_valid());self.assertIn('reminder_time',form.errors)
        form=PlanForm({'title':'План','email_reminder':'on','reminder_date':'2026-10-20','reminder_time':'17:30'},user=self.user)
        self.assertTrue(form.is_valid(),form.errors)
        self.assertEqual(form.cleaned_data['reminder_time'],time(17,30))
        self.assertEqual(form.fields['reminder_time'].widget.input_type,'text')
        self.assertIn('Письмо придёт',form.fields['email_reminder'].help_text)
        form=PlanForm({'title':'Без письма'},user=self.user)
        self.assertTrue(form.is_valid(),form.errors)

    def test_dry_run_and_disabled_delivery_never_send(self):
        self.plan.reminder_date=timezone.localdate()-timedelta(days=1);self.plan.save()
        output=StringIO()
        call_command('send_plan_reminders','--dry-run',stdout=output)
        self.assertIn('Отправлено: 0',output.getvalue())
        self.assertEqual(len(mail.outbox),0)
        with override_settings(SPELLBOOK_EMAIL_DELIVERY_ENABLED=False):
            with self.assertRaises(ValueError):send_due_reminders()
