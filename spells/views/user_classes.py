from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from spells.models import CharacterClass, Player
from spells.views.catalog import build_catalog_form, CATALOGS


@login_required
@require_http_methods(['GET','POST'])
def user_class_create_page(request):
    player, _ = Player.objects.get_or_create(user=request.user)
    item = CharacterClass(created_by=player, is_official=False)
    form_class = build_catalog_form(CATALOGS['classes'], user_class=True)
    form = form_class(request.POST or None, request.FILES or None, instance=item)
    if request.method == 'POST' and form.is_valid():
        item = form.save()
        return redirect('class_detail_page', pk=item.pk)
    return render(request, 'spells/catalog_form.html', {
        'form': form, 'catalog_title': 'Мой класс', 'slug': 'classes',
        'cancel_url': reverse('catalog_list_page', args=['classes']) + '?group=mine',
    })
