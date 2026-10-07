from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from django.contrib.auth import login
from django.db import transaction
from django.db.models import Q

from spells.forms import (
    CharacterCreateForm,
    CharacterEditForm,
    RegistrationForm,
    CustomSpellForm,
)
from spells.models import Person, Player, Spell, MagicSchool


@login_required
def character_list_page(request):
    search = request.GET.get("search", "").strip()
    level = request.GET.get("level", "")

    if level not in [str(value) for value in range(10)]:
        level = ""
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
@login_required
def character_create_page(request):
    form = CharacterCreateForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
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
@login_required
def character_edit_page(request, pk):
    character = get_object_or_404(
        Person,
        pk=pk,
        player__user=request.user,
    )

    form = CharacterEditForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
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
@login_required
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
@require_http_methods(["GET", "POST"])
def register_page(request):
    if request.user.is_authenticated:
        return redirect("character_list_page")

    form = RegistrationForm(
        request.POST if request.method == "POST" else None
    )

    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save()
            Player.objects.create(user=user)

        login(request, user)
        return redirect("character_list_page")

    return render(
        request,
        "spells/register.html",
        {"form": form},
    )
def spell_list_page(request):
    search = request.GET.get("search", "").strip()
    level = request.GET.get("level", "")
    school = request.GET.get("school", "")

    schools = MagicSchool.objects.order_by("name")

    if level not in [str(value) for value in range(10)]:
        level = ""

    school_ids = {str(pk) for pk in schools.values_list("pk", flat=True)}

    if school not in school_ids:
        school = ""

    spells = Spell.objects.filter(
        is_official=True,
    ).select_related("school", "time")

    if search:
        spells = spells.filter(name__icontains=search)

    if level:
        spells = spells.filter(level=int(level))

    if school:
        spells = spells.filter(school_id=int(school))

    return render(
        request,
        "spells/spell_list.html",
        {
            "spells": spells,
            "search": search,
            "level": level,
            "levels": range(10),
            "school": school,
            "schools": schools,
        },
    )
def spell_detail_page(request, pk):
    available_spells = Q(is_official=True)

    if request.user.is_authenticated:
        available_spells |= Q(
            created_by__user=request.user,
            is_official=False,
        )

    spell = get_object_or_404(
        Spell.objects.filter(available_spells)
        .select_related("school", "time")
        .prefetch_related(
            "material_components",
            "aviable_classes",
        ),
        pk=pk,
    )

    return render(
        request,
        "spells/spell_detail.html",
        {
            "spell": spell,
            "is_custom": not spell.is_official,
        },
    )
    return render(
        request,
        "spells/spell_detail.html",
        {"spell": spell},
    )
@login_required
@require_http_methods(["GET", "POST"])
def spell_create_page(request):
    form = CustomSpellForm(
        request.POST if request.method == "POST" else None
    )

    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            player, _ = Player.objects.get_or_create(
                user=request.user,
            )

            spell = form.save(commit=False)
            spell.created_by = player
            spell.is_official = False
            spell.save()

            form.save_m2m()

        return redirect("my_spell_list_page")

    return render(
        request,
        "spells/spell_form.html",
        {"form": form},
    )
@login_required
def my_spell_list_page(request):
    search = request.GET.get("search", "").strip()

    spells = Spell.objects.filter(
        created_by__user=request.user,
        is_official=False,
    ).select_related("school", "time")

    if search:
        spells = spells.filter(name__icontains=search)

    return render(
        request,
        "spells/my_spell_list.html",
        {
            "spells": spells,
            "search": search,
        },
    )