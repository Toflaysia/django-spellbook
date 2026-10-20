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
    class Meta:
        model=HomePlan
        fields=['title','text','reminder_date']
        widgets={
            'title':forms.TextInput(attrs={'placeholder':'Что нужно сделать?'}),
            'text':forms.Textarea(attrs={'rows':3}),
            'reminder_date':forms.DateInput(format='%Y-%m-%d',attrs={'type':'date'}),
        }

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['reminder_date'].input_formats=['%Y-%m-%d']
        self.fields['reminder_date'].help_text='Дата необязательна. Напоминание появится на главной странице.'


def home_context(request, form=None):
    if not request.user.is_authenticated:
        return {}
    plans=HomePlan.objects.filter(user=request.user).order_by('is_done',F('reminder_date').asc(nulls_last=True),'-created_at','pk')
    return {'active_characters':Person.objects.filter(player__user=request.user,is_active=True).select_related('character_class').order_by('name','pk'), 'plans':plans,'plan_form':form if form is not None else PlanForm(),'unfinished_plans':plans.filter(is_done=False).count()}

@login_required
@require_POST
def plan_create_page(request):
    form=PlanForm(request.POST)
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
    form=PlanForm(request.POST if request.method=='POST' else None,instance=item)
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
