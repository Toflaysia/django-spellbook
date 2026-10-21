from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from spells.models import AccountEmail
from spells.email_accounts import normalize_email, email_available


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.CharField(label='Email или имя пользователя', widget=forms.TextInput(attrs={'autocomplete':'username'}))


class AccountEmailForm(forms.Form):
    email = forms.EmailField(label='Email', max_length=254, widget=forms.EmailInput(attrs={'autocomplete':'email'}))
    password = forms.CharField(label='Текущий пароль', widget=forms.PasswordInput(attrs={'autocomplete':'current-password'}))

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_email(self):
        email = normalize_email(self.cleaned_data['email'])
        if not email_available(email, self.user):
            raise ValidationError('Этот email уже используется.')
        return email

    def clean_password(self):
        value = self.cleaned_data['password']
        if not self.user.check_password(value):
            raise ValidationError('Неверный текущий пароль.')
        return value


class VerifiedPasswordResetForm(PasswordResetForm):
    def get_users(self, email):
        return User.objects.filter(email__iexact=normalize_email(email), account_email__email=normalize_email(email), account_email__verified_at__isnull=False, is_active=True).exclude(password__startswith='!')
