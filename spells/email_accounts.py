"""Email identity and confirmation without changing existing user accounts."""
import logging
import uuid
from datetime import timedelta
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.backends import ModelBackend
from django.core import signing
from django.core.mail import send_mail
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from spells.models import AccountEmail

logger = logging.getLogger(__name__)
CONFIRM_SALT = 'spellbook.confirm-email.v1'


def normalize_email(value):
    return value.strip().casefold()


def email_available(value, user=None):
    addresses = AccountEmail.objects.filter(email=normalize_email(value))
    users = User.objects.filter(Q(email__iexact=normalize_email(value))|Q(username__iexact=normalize_email(value)))
    if user is not None:
        addresses = addresses.exclude(user=user)
        users = users.exclude(pk=user.pk)
    return not addresses.exists() and not users.exists()


def site_url():
    return settings.SPELLBOOK_SITE_URL.rstrip('/')


def confirmation_token(address):
    return signing.dumps({'id': address.pk, 'nonce': str(address.confirmation_nonce)}, salt=CONFIRM_SALT)


def address_from_token(token):
    data = signing.loads(token, salt=CONFIRM_SALT, max_age=48*60*60)
    return AccountEmail.objects.select_related('user').get(pk=data['id'], confirmation_nonce=data['nonce'], user__is_active=True)


def send_confirmation(user):
    if not settings.SPELLBOOK_EMAIL_DELIVERY_ENABLED:
        return 'unavailable'
    address = AccountEmail.objects.get(user=user)
    if address.verified_at:
        return 'verified'
    now = timezone.now()
    claimed = AccountEmail.objects.filter(pk=address.pk, verified_at__isnull=True).filter(
        Q(confirmation_sent_at__isnull=True) | Q(confirmation_sent_at__lte=now-timedelta(seconds=60))
    ).update(confirmation_nonce=uuid.uuid4(), confirmation_sent_at=now)
    if not claimed:
        return 'throttled'
    address.refresh_from_db()
    token = confirmation_token(address)
    url = site_url()+reverse('confirm_email', args=[token])
    try:
        sent = send_mail('Подтверди email в Spellbook', 'Привет, '+user.username+'!\n\nПодтверди свой email:\n'+url+'\n\nСсылка действует 48 часов. Если ты не запрашивал письмо, просто проигнорируй его.', settings.DEFAULT_FROM_EMAIL, [address.email])
        if not sent:
            raise RuntimeError('Mail backend did not accept the message')
    except Exception:
        AccountEmail.objects.filter(pk=address.pk, confirmation_nonce=address.confirmation_nonce).update(confirmation_sent_at=None)
        logger.exception('Email confirmation delivery failed for account %s', user.pk)
        return 'failed'
    return 'sent'


class EmailOrUsernameBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        identity = username.strip()
        user = User.objects.filter(username=identity).first()
        if user is None:
            address = AccountEmail.objects.select_related('user').filter(email=normalize_email(identity), verified_at__isnull=False).first()
            user = address.user if address else None
        if user is None:
            User().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
