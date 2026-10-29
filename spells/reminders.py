"""Отправка наступивших напоминаний с защитой от одновременного запуска."""

import logging
from datetime import timedelta
from django.conf import settings
from django.core.mail import send_mail
from django.db.models import F, Q
from django.urls import reverse
from django.utils import timezone
from spells.models import HomePlan
from spells.email_accounts import site_url
from spells.templatetags.description_tags import description_text

logger = logging.getLogger(__name__)


def send_due_reminders(*, dry_run=False, limit=100, now=None):
    # Выбираем только невыполненные планы с включённым напоминанием и подтверждённой почтой.
    now = now or timezone.now()
    local = timezone.localtime(now)
    due = (
        HomePlan.objects.filter(
            email_reminder=True,
            is_done=False,
            user__is_active=True,
            user__account_email__verified_at__isnull=False,
        )
        .filter(
            Q(reminder_date__lt=local.date())
            | Q(
                reminder_date=local.date(),
                reminder_time__lte=local.time().replace(tzinfo=None),
            )
        )
        .exclude(email_sent_for_date=F("reminder_date"))
        .filter(
            Q(email_sending_started_at__isnull=True)
            | Q(email_sending_started_at__lt=now - timedelta(minutes=30))
        )
    )
    result = {"due": 0, "sent": 0, "failed": 0}
    if dry_run:
        result["due"] = due[:limit].count()
        return result
    if not settings.SPELLBOOK_EMAIL_DELIVERY_ENABLED:
        raise ValueError("Отправка писем не настроена. Заполни email_settings.json.")
    for plan in due.select_related("user__account_email").order_by(
        "reminder_date", "reminder_time", "pk"
    )[:limit]:
        # Отмечаем начало отправки перед SMTP, чтобы другой запуск не отправил тот же план одновременно.
        if not due.filter(pk=plan.pk).update(email_sending_started_at=now):
            continue
        result["due"] += 1
        try:
            text = (
                "Напоминание: "
                + plan.title
                + "\nДата: "
                + plan.reminder_date.strftime("%d.%m.%Y")
                + "\n\n"
                + description_text(plan.text)
                + "\n\nТвои планы: "
                + site_url()
                + reverse("home_page")
                + "#plans"
            )
            sent = send_mail(
                "Напоминание Spellbook",
                text,
                settings.DEFAULT_FROM_EMAIL,
                [plan.user.account_email.email],
            )
            if not sent:
                raise RuntimeError("Mail backend did not accept reminder")
        # Не отмечаем неудачное письмо как отправленное: следующий запуск должен повторить попытку.
        except Exception:
            HomePlan.objects.filter(pk=plan.pk, email_sending_started_at=now).update(
                email_sending_started_at=None
            )
            logger.exception("Plan reminder delivery failed for plan %s", plan.pk)
            result["failed"] += 1
        else:
            HomePlan.objects.filter(pk=plan.pk, email_sending_started_at=now).update(
                email_sent_at=timezone.now(),
                email_sent_for_date=plan.reminder_date,
                email_sending_started_at=None,
            )
            result["sent"] += 1
    return result
