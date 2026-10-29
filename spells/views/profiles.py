from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404,redirect,render
from django.utils import timezone
from django.views.decorators.http import require_GET,require_http_methods
from spells.models import Player,Spell,CharacterClass
from spells.profile_forms import ProfileForm


@require_GET
def profile_page(request,pk):
    account=get_object_or_404(get_user_model(),pk=pk,is_active=True)
    profile=Player.objects.filter(user=account).first() or Player(user=account)
    spells=Spell.objects.filter(created_by__user=account).filter(Q(is_official=True)|Q(is_public=True)).order_by('name','pk')
    classes=CharacterClass.objects.filter(created_by__user=account,is_public=True).order_by('name','pk')
    tab='classes' if request.GET.get('tab')=='classes' else 'spells'
    page=Paginator(classes if tab=='classes' else spells,12).get_page(request.GET.get('page'))
    last_seen=profile.last_seen_at if profile.show_activity else None
    return render(request,'spells/profile.html',{
        'account':account,'profile':profile,'owner':request.user.is_authenticated and request.user.pk==account.pk,
        'spell_count':spells.count(),'class_count':classes.count(),'page_obj':page,'tab':tab,
        'last_seen':last_seen,'online':bool(last_seen and last_seen>=timezone.now()-timedelta(minutes=5)),
    })


@login_required
@require_GET
def my_profile_page(request):
    return redirect('profile_page',pk=request.user.pk)


@login_required
@require_http_methods(['GET','POST'])
def profile_edit_page(request):
    profile,_=Player.objects.get_or_create(user=request.user)
    form=ProfileForm(request.POST if request.method=='POST' else None,request.FILES if request.method=='POST' else None,instance=profile)
    if request.method=='POST' and form.is_valid():
        profile=form.save(commit=False)
        if profile.show_activity:profile.last_seen_at=timezone.now()
        profile.save()
        return redirect('profile_page',pk=request.user.pk)
    return render(request,'spells/profile_form.html',{'form':form})
