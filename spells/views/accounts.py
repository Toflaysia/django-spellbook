from datetime import timedelta
from django.db.models import Q
import uuid
import logging
from urllib.parse import urlsplit
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.db import transaction, IntegrityError
from django.http import HttpResponseRedirect
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST
from spells.models import AccountEmail
from spells.account_forms import AccountEmailForm, VerifiedPasswordResetForm
from spells.email_accounts import address_from_token, send_confirmation, site_url

logger=logging.getLogger(__name__)


def confirmation_message(request, result):
    if result == 'sent':messages.success(request,'Письмо с подтверждением отправлено. Проверь почту.')
    elif result == 'throttled':messages.info(request,'Письмо уже запрошено. Повторить отправку можно через минуту.')
    elif result == 'unavailable':messages.warning(request,'Отправка писем пока не настроена. Адрес сохранён; подтвердить его можно будет после настройки почты администратором.')
    elif result == 'failed':messages.error(request,'Не удалось отправить письмо. Адрес сохранён. Попробуй повторить отправку позже.')


@login_required
@require_http_methods(['GET','POST'])
def account_email_page(request):
    address=AccountEmail.objects.filter(user=request.user).first()
    form=AccountEmailForm(request.POST if request.method=='POST' else None, user=request.user, initial={'email':address.email if address else request.user.email})
    if request.method=='POST' and form.is_valid():
        try:
            with transaction.atomic():
                address,created=AccountEmail.objects.get_or_create(user=request.user,defaults={'email':form.cleaned_data['email']})
                if not created and address.email!=form.cleaned_data['email']:
                    address.email=form.cleaned_data['email'];address.verified_at=None
                    address.confirmation_nonce=uuid.uuid4();address.confirmation_sent_at=None
                    address.save()
                request.user.email=address.email;request.user.save(update_fields=['email'])
        except IntegrityError:
            form.add_error('email','Этот email уже используется.')
        else:
            if address.verified_at:messages.success(request,'Email уже подтверждён.')
            else:confirmation_message(request,send_confirmation(request.user))
            return redirect('account_email_page')
    return render(request,'spells/account_email.html',{'form':form,'email_address':address,'mail_ready':settings.SPELLBOOK_EMAIL_DELIVERY_ENABLED})


@login_required
@require_POST
def resend_confirmation(request):
    if AccountEmail.objects.filter(user=request.user).exists():
        confirmation_message(request,send_confirmation(request.user))
    return redirect('account_email_page')


@require_http_methods(['GET','POST'])
def confirm_email(request,token):
    valid=False;confirmed=False
    try:
        address=address_from_token(token)
        valid=address.verified_at is None
        if request.method=='POST' and valid:
            confirmed=bool(AccountEmail.objects.filter(pk=address.pk,verified_at__isnull=True,confirmation_nonce=address.confirmation_nonce).update(verified_at=timezone.now(),confirmation_nonce=uuid.uuid4()))
            valid=False
    except (signing.BadSignature,AccountEmail.DoesNotExist,ValueError,KeyError,TypeError):
        pass
    return render(request,'spells/confirm_email.html',{'valid_token':valid,'confirmed':confirmed})


class EmailPasswordResetView(auth_views.PasswordResetView):
    form_class=VerifiedPasswordResetForm
    template_name='spells/password_reset_form.html'
    email_template_name='spells/emails/password_reset.txt'
    subject_template_name='spells/emails/password_reset_subject.txt'
    success_url=reverse_lazy('password_reset_done')

    def form_valid(self,form):
        users=list(form.get_users(form.cleaned_data['email']))
        address=AccountEmail.objects.filter(user=users[0]).first() if users else None
        now=timezone.now()
        ready=settings.SPELLBOOK_EMAIL_DELIVERY_ENABLED and address is not None
        if ready:
            ready=bool(AccountEmail.objects.filter(pk=address.pk).filter(Q(password_reset_sent_at__isnull=True)|Q(password_reset_sent_at__lte=now-timedelta(seconds=60))).update(password_reset_sent_at=now))
        if ready:
            parsed=urlsplit(site_url())
            try:
                form.save(use_https=parsed.scheme=='https', domain_override=parsed.netloc, email_template_name=self.email_template_name, subject_template_name=self.subject_template_name, from_email=settings.DEFAULT_FROM_EMAIL,request=self.request)
            except Exception:
                AccountEmail.objects.filter(pk=address.pk,password_reset_sent_at=now).update(password_reset_sent_at=None)
                logger.exception('Password reset delivery failed')
        # Same response for unknown, unverified and known addresses.
        return HttpResponseRedirect(self.get_success_url())
