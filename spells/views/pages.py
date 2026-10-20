from django.contrib.auth.models import AnonymousUser
from spells.spell_access import visible_spells, collected_spells, can_edit_spell
from django.http import Http404
from spells.class_access import scope_spell_classes
from spells.filters import SpellFilterForm
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from django.contrib.auth import login
from django.db import transaction
from django.db.models import Q
from spells.spell_import import build_spell_initial
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseBadRequest
from django.views.decorators.http import require_POST
from spells.forms import (
    CharacterCreateForm,
    CharacterEditForm,
    RegistrationForm,
    CustomSpellForm,
    SpellImportForm,
    SpellbookForm,
)
from spells.models import Person, Player, Spell, MagicSchool, Spellbook
from spells.spell_import import build_spell_initial

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
        user=request.user,
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
        user=request.user,
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
    group = request.GET.get('group', 'official')
    if group not in ('official', 'unofficial'):
        raise Http404('Раздел заклинаний не найден.')
    filters = SpellFilterForm(request.GET or None, user=request.user)
    objects = visible_spells(request.user).filter(is_official=group == 'official')
    if group == 'unofficial':
        objects = objects.filter(is_public=True)
    spells = filters.apply(objects).select_related("school", "time", "created_by__user").order_by("name", "pk")
    return render(request, "spells/spell_list.html", {
        "spells": spells, "spell_filters": filters, "spell_group": group,
        "search": request.GET.get("search", ""),
        "has_active_filters": any(request.GET.get(name) for name in filters.fields),
    })

def spell_detail_page(request, pk):
    spell = get_object_or_404(
        visible_spells(request.user)
        .select_related("school", "time", "created_by__user")
        .prefetch_related(
            "material_components",
            "aviable_classes",
        ),
        pk=pk,
    )

    scope_spell_classes(spell, request.user)
    is_saved = False

    if request.user.is_authenticated:
        is_saved = spell.saved_by_players.filter(
            user=request.user,
        ).exists()

    return render(
        request,
        "spells/spell_detail.html",
        {
            "spell": spell,
            "is_custom": not spell.is_official,
            "can_edit_spell": can_edit_spell(request.user, spell),
            "is_spell_author": bool(request.user.is_authenticated and spell.created_by_id and spell.created_by.user_id == request.user.pk and not spell.is_official),
            "is_saved": is_saved,
        },
    )
@login_required
@require_http_methods(["GET", "POST"])
def spell_create_page(request):
    form = CustomSpellForm(
        request.POST if request.method == "POST" else None,
        user=request.user,
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
    filters = SpellFilterForm(request.GET or None, mine=True, user=request.user)
    spells = filters.apply(collected_spells(request.user)).select_related("school", "time", "created_by__user").order_by("name", "pk")
    return render(request, "spells/my_spell_list.html", {
        "spells": spells, "spell_filters": filters,
        "search": request.GET.get("search", ""),
        "has_active_filters": any(request.GET.get(name) for name in filters.fields),
    })
@login_required
@require_http_methods(["GET", "POST"])
def spell_import_page(request):
    form = SpellImportForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
    )

    if request.method == "POST" and form.is_valid():
        try:
            initial = build_spell_initial(form.import_data, user=request.user)
        except (ValueError, TypeError, KeyError, RecursionError) as error:
            form.add_error('json_file', str(error))
            return render(request, 'spells/spell_import.html', {'form': form, 'official_import': False})
        spell_form = CustomSpellForm(initial=initial, user=request.user)

        return render(
            request,
            "spells/spell_form.html",
            {"form": spell_form, "import_warnings": initial.get("_import_warnings", [])},
        )

    return render(
        request,
        "spells/spell_import.html",
        {"form": form},
    )
@login_required
@require_http_methods(["GET", "POST"])
def spell_edit_page(request, pk):
    available_spells = Q(
        created_by__user=request.user,
        is_official=False,
    )

    if request.user.is_staff:
        available_spells |= Q(is_official=True)

    spell = get_object_or_404(
        Spell.objects.filter(available_spells),
        pk=pk,
    )

    form = CustomSpellForm(
        request.POST if request.method == "POST" else None,
        instance=spell,
        user=request.user,
    )

    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            form.save()

        return redirect("spell_detail_page", pk=spell.pk)

    return render(
        request,
        "spells/spell_form.html",
        {
            "form": form,
            "editing": True,
            "spell": spell,
        },
    )
def home_page(request):
    from spells.views.plans import home_context
    return render(request, "spells/home.html", home_context(request))
@login_required
@require_http_methods(["POST"])
def spell_save_page(request, pk):
    spell = get_object_or_404(
        visible_spells(request.user), pk=pk,
    )

    player, _ = Player.objects.get_or_create(user=request.user)
    player.saved_spells.add(spell)

    return redirect("spell_detail_page", pk=spell.pk)
@login_required
@require_http_methods(["POST"])
def spell_unsave_page(request, pk):
    player = get_object_or_404(Player, user=request.user)

    spell = get_object_or_404(
        player.saved_spells,
        pk=pk,
    )

    player.saved_spells.remove(spell)

    return redirect("my_spell_list_page")
@login_required
@require_http_methods(["GET", "POST"])
def official_spell_import_page(request):
    if not request.user.is_staff:
        raise PermissionDenied

    form = SpellImportForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
    )

    if request.method == "POST" and form.is_valid():
        try:
            initial = build_spell_initial(form.import_data, user=AnonymousUser())
        except (ValueError, TypeError, KeyError, RecursionError) as error:
            form.add_error('json_file', str(error))
            return render(request, 'spells/spell_import.html', {'form': form, 'official_import': True})
        spell_form = CustomSpellForm(initial=initial, user=request.user)
        spell_form.fields.pop("is_public", None)

        return render(
            request,
            "spells/spell_form.html",
            {
                "form": spell_form,
                "import_warnings": initial.get("_import_warnings", []),
                "official_import": True,
            },
        )

    return render(
        request,
        "spells/spell_import.html",
        {
            "form": form,
            "official_import": True,
        },
    )


@login_required
@require_http_methods(["POST"])
def official_spell_create_page(request):
    if not request.user.is_staff:
        raise PermissionDenied

    form = CustomSpellForm(request.POST, user=request.user)
    form.fields.pop("is_public", None)

    if form.is_valid():
        with transaction.atomic():
            player, _ = Player.objects.get_or_create(
                user=request.user,
            )

            spell = form.save(commit=False)
            spell.created_by = player
            spell.is_official = True
            spell.save()
            form.save_m2m()

        return redirect("spell_detail_page", pk=spell.pk)

    return render(
        request,
        "spells/spell_form.html",
        {
            "form": form,
            "official_import": True,
        },
    )
@login_required
@require_http_methods(["GET", "POST"])
def spell_delete_page(request, pk):
    spell = get_object_or_404(
        Spell,
        pk=pk,
        created_by__user=request.user,
        is_official=False,
    )

    if request.method == "POST":
        spell.delete()
        return redirect("my_spell_list_page")

    return render(
        request,
        "spells/spell_confirm_delete.html",
        {"spell": spell},
    )
@login_required
def spellbook_list_page(request):
    search = request.GET.get("search", "").strip()

    spellbooks = (
        Spellbook.objects.filter(
            owner__player__user=request.user,
        )
        .select_related("owner")
        .prefetch_related("spells")
    )

    if search:
        spellbooks = spellbooks.filter(
            Q(name__icontains=search)
            | Q(owner__name__icontains=search)
        )

    return render(
        request,
        "spells/spellbook_list.html",
        {
            "spellbooks": spellbooks,
            "search": search,
            "has_characters": Person.objects.filter(
                player__user=request.user,
            ).exists(),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def spellbook_create_page(request):
    initial = {}
    owner = None
    if request.GET.get("owner"):
        owner = get_object_or_404(Person, pk=request.GET["owner"] if request.GET["owner"].isdigit() and len(request.GET["owner"]) <= 10 else 0, player__user=request.user)
        initial["owner"] = owner.pk
    form = SpellbookForm(
        request.POST if request.method == "POST" else None,
        user=request.user,
        initial=initial,
    )

    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            spellbook = form.save(commit=False)

            for level in range(1, 10):
                setattr(
                    spellbook,
                    f"current_spell_slots_{level}",
                    getattr(spellbook, f"max_spell_slots_{level}"),
                )

            spellbook.warlock_current_slots = spellbook.warlock_max_slots
            spellbook.save()
            form.save_m2m()

        return redirect("spellbook_list_page")

    return render(
        request,
        "spells/spellbook_form.html",
        {"form": form, "return_character": owner},
    )
@login_required
def spellbook_detail_page(request, pk):
    spellbook = get_object_or_404(
        Spellbook.objects.select_related("owner").prefetch_related("spells"),
        pk=pk,
        owner__player__user=request.user,
    )

    slots = [
        {
            "level": level,
            "current": getattr(spellbook, f"current_spell_slots_{level}"),
            "maximum": getattr(spellbook, f"max_spell_slots_{level}"),
        }
        for level in range(1, 10)
        if getattr(spellbook, f"max_spell_slots_{level}") > 0
    ]

    return render(
        request,
        "spells/spellbook_detail.html",
        {
            "spellbook": spellbook,
            "spells": spellbook.spells.filter(pk__in=visible_spells(request.user)).order_by("level", "name"),
            "slots": slots,
        },
    )
@login_required
@require_POST
def spellbook_slot_change_page(request, pk):
    slot = request.POST.get("slot")
    action = request.POST.get("action")

    if action not in ("spend", "restore"):
        return HttpResponseBadRequest("Неизвестное действие.")

    if slot == "warlock":
        current_field = "warlock_current_slots"
        maximum_field = "warlock_max_slots"
    elif slot in [str(level) for level in range(1, 10)]:
        current_field = f"current_spell_slots_{slot}"
        maximum_field = f"max_spell_slots_{slot}"
    else:
        return HttpResponseBadRequest("Неизвестный уровень ячеек.")

    with transaction.atomic():
        spellbook = get_object_or_404(
            Spellbook.objects.select_for_update(),
            pk=pk,
            owner__player__user=request.user,
        )

        current = getattr(spellbook, current_field)
        maximum = getattr(spellbook, maximum_field)

        if action == "spend" and current > 0:
            setattr(spellbook, current_field, current - 1)
            spellbook.save(update_fields=[current_field])
        elif action == "restore" and current < maximum:
            setattr(spellbook, current_field, current + 1)
            spellbook.save(update_fields=[current_field])

    return redirect("spellbook_detail_page", pk=pk)
@login_required
@require_http_methods(["GET", "POST"])
def spellbook_edit_page(request, pk):
    with transaction.atomic():
        spellbook = get_object_or_404(
            Spellbook.objects.select_for_update(),
            pk=pk,
            owner__player__user=request.user,
        )

        form = SpellbookForm(
            request.POST if request.method == "POST" else None,
            instance=spellbook,
            user=request.user,
        )

        if request.method == "POST" and form.is_valid():
            spellbook = form.save(commit=False)

            for level in range(1, 10):
                current_field = f"current_spell_slots_{level}"
                maximum_field = f"max_spell_slots_{level}"

                setattr(
                    spellbook,
                    current_field,
                    min(
                        getattr(spellbook, current_field),
                        getattr(spellbook, maximum_field),
                    ),
                )

            spellbook.warlock_current_slots = min(
                spellbook.warlock_current_slots,
                spellbook.warlock_max_slots,
            )

            spellbook.save()
            form.save_m2m()

            return redirect("spellbook_detail_page", pk=spellbook.pk)

    return render(
        request,
        "spells/spellbook_form.html",
        {
            "form": form,
            "editing": True,
            "spellbook": spellbook,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def spellbook_delete_page(request, pk):
    spellbook = get_object_or_404(
        Spellbook,
        pk=pk,
        owner__player__user=request.user,
    )

    if request.method == "POST":
        spellbook.delete()
        return redirect("spellbook_list_page")

    return render(
        request,
        "spells/spellbook_confirm_delete.html",
        {"spellbook": spellbook},
    )