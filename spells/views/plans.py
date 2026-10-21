from datetime import time
from spells.models import AccountEmail
from django import forms
from django.contrib.auth.decorators import login_required
from django.db.models import F
from django.urls import reverse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_http_methods
from spells.models import HomePlan, Person
from spells.description import DescriptionFormMixin

class PlanForm(DescriptionFormMixin, forms.ModelForm):
    description_field_names = ("text",)
    reminder_time=forms.TimeField(label='Время напоминания',required=False,initial=time(9,0),input_formats=['%H:%M'],widget=forms.TimeInput(format='%H:%M',attrs={'type':'text','placeholder':'ЧЧ:ММ','maxlength':'5','autocomplete':'off','data-reminder-time':''}))
    class Meta:
        model=HomePlan
        fields=['title','text','email_reminder','reminder_date','reminder_time']
        widgets={
            'title':forms.TextInput(attrs={'placeholder':'Что нужно сделать?'}),
            'text':forms.Textarea(attrs={'rows':3}),
            'reminder_date':forms.DateInput(format='%Y-%m-%d',attrs={'type':'date'}),
        }

    def __init__(self,*args,**kwargs):
        self.user=kwargs.pop('user',None)
        super().__init__(*args,**kwargs)
        self.fields['email_reminder'].help_text='Письмо придёт в выбранную дату. Нужен подтверждённый email.'
        verified=self.user is not None and AccountEmail.objects.filter(user=self.user,verified_at__isnull=False).exists()
        self.fields['email_reminder'].disabled=not verified
        self.fields['email_reminder'].widget.attrs['data-email-reminder']=''
        if not verified:
            self.initial['email_reminder']=False
            self.fields['email_reminder'].widget.attrs['title']='Сначала подтверди email в настройках аккаунта.'
        self.fields['reminder_date'].input_formats=['%Y-%m-%d']
        self.fields['reminder_date'].widget.attrs['data-reminder-date']=''

    def clean(self):
        data=super().clean()
        if self.fields['email_reminder'].disabled and self.data.get('email_reminder'):
            self.add_error('email_reminder','Сначала подтверди адрес на странице «Email и безопасность».')
        if data.get('email_reminder'):
            if not data.get('reminder_time') and 'reminder_time' not in self.errors:
                self.add_error('reminder_time','Укажи время в формате ЧЧ:ММ.')
            if not data.get('reminder_date'):self.add_error('reminder_date','Для письма укажи дату напоминания.')
            if not self.user or not AccountEmail.objects.filter(user=self.user,verified_at__isnull=False).exists():
                self.add_error('email_reminder','Сначала подтверди адрес на странице «Email и безопасность».')
        if not data.get('email_reminder') and not data.get('reminder_time'):
            data['reminder_time']=time(9,0)
        return data


def home_context(request, form=None):
    if not request.user.is_authenticated:
        return {}
    plans=HomePlan.objects.filter(user=request.user).order_by('is_done',F('reminder_date').asc(nulls_last=True),'-created_at','pk')
    return {'active_characters':Person.objects.filter(player__user=request.user,is_active=True).select_related('character_class').order_by('name','pk'), 'plans':plans,'plan_form':form if form is not None else PlanForm(user=request.user),'unfinished_plans':plans.filter(is_done=False).count()}

@login_required
@require_POST
def plan_create_page(request):
    form=PlanForm(request.POST,user=request.user)
    if form.is_valid():
        item=form.save(commit=False)
        item.user=request.user
        item.save()
        return redirect(reverse('home_page')+'#plans')
    return render(request,'spells/home.html',home_context(request,form))

@login_required
@require_http_methods(['GET','POST'])
def plan_edit_page(request,pk):
    item=get_object_or_404(HomePlan,pk=pk,user=request.user)
    form=PlanForm(request.POST if request.method=='POST' else None,instance=item,user=request.user)
    if request.method=='POST' and form.is_valid():
        form.save()
        return redirect(reverse('home_page')+'#plans')
    return render(request,'spells/plan_form.html',{'form':form,'plan':item})

@login_required
@require_POST
def plan_toggle_page(request,pk):
    # A single SQL update also handles rapid repeated requests consistently.
    from django.db.models import Case, When, Value, BooleanField
    item=get_object_or_404(HomePlan,pk=pk,user=request.user)
    HomePlan.objects.filter(pk=item.pk,user=request.user).update(is_done=Case(When(is_done=True,then=Value(False)),default=Value(True),output_field=BooleanField()))
    return redirect(reverse('home_page')+'#plans')

@login_required
@require_POST
def plan_delete_page(request,pk):
    item=get_object_or_404(HomePlan,pk=pk,user=request.user)
    item.delete()
    return redirect(reverse('home_page')+'#plans')
