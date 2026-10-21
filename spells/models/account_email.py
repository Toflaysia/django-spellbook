import uuid
from django.conf import settings
from django.db import models


class AccountEmail(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='account_email')
    email = models.EmailField(unique=True, verbose_name='Email')
    verified_at = models.DateTimeField(null=True, blank=True, verbose_name='Подтверждён')
    confirmation_nonce = models.UUIDField(default=uuid.uuid4, editable=False)
    confirmation_sent_at = models.DateTimeField(null=True, blank=True)
    password_reset_sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.email
