from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from spells.forms import CharacterCreateForm, CharacterEditForm
from spells.models import Person, Player


@login_required(login_url="/api-auth/login/")
def character_list_page(request):
    search = request.GET.get("search", "").strip()

    characters = Person.objects.filter(
        player__user=request.user,
    ).select_related("character_class")

    if search:
        characters = characters.filter(name__icontains=search)

    return render(
        request,
        "spells/character_list.html",
        {
            "characters": characters,
            "search": search,
        },
    )
@login_required(login_url="/api-auth/login/")
def character_create_page(request):
    form = CharacterCreateForm(
        request.POST if request.method == "POST" else None
    )

    if request.method == "POST" and form.is_valid():
        player, _ = Player.objects.get_or_create(user=request.user)

        character = form.save(commit=False)
        character.player = player
        character.current_hit_points = character.max_hit_points
        character.save()

        return redirect("character_list_page")

    return render(
        request,
        "spells/character_form.html",
        {"form": form},
    )
@login_required(login_url="/api-auth/login/")
def character_edit_page(request, pk):
    character = get_object_or_404(
        Person,
        pk=pk,
        player__user=request.user,
    )

    form = CharacterEditForm(
        request.POST if request.method == "POST" else None,
        instance=character,
    )

    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("character_list_page")

    return render(
        request,
        "spells/character_form.html",
        {
            "form": form,
            "editing": True,
        },
    )
@login_required(login_url="/api-auth/login/")
@require_http_methods(["GET", "POST"])
def character_delete_page(request, pk):
    character = get_object_or_404(
        Person,
        pk=pk,
        player__user=request.user,
    )

    if request.method == "POST":
        character.delete()
        return redirect("character_list_page")

    return render(
        request,
        "spells/character_confirm_delete.html",
        {"character": character},
    )