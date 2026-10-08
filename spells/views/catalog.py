from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.views.decorators.http import require_http_methods

from spells.models import (
    CharacterClass,
    DamageType,
    Effect,
    MagicSchool,
    MaterialComponent,
    SpellTime,
)


CATALOGS = {
    "schools": {
        "title": "Школы магии",
        "model": MagicSchool,
        "name_field": "name",
        "fields": [],
    },
    "effects": {
        "title": "Эффекты",
        "model": Effect,
        "name_field": "name",
        "fields": [
            "category",
            "duration",
            "damage_type",
        ],
    },
    "components": {
        "title": "Материальные компоненты",
        "model": MaterialComponent,
        "name_field": "name",
        "fields": [
            "cost",
            "is_consumable",
            "is_focus",
        ],
    },
    "casting-times": {
        "title": "Время накладывания",
        "model": SpellTime,
        "name_field": "time",
        "fields": [],
    },
    "classes": {
        "title": "Классы персонажей",
        "model": CharacterClass,
        "name_field": "name",
        "fields": [
            "magic_type",
            "hit_die",
            "spellcasting_ability",
        ],
    },
        "damage-types": {
        "title": "Типы урона",
        "model": DamageType,
        "name_field": "name",
        "fields": [
            "is_magic",
        ],
    },
}


def get_catalog(slug):
    catalog = CATALOGS.get(slug)

    if catalog is None:
        raise Http404("Справочник не найден.")

    return catalog


def catalog_list_page(request, slug):
    catalog = get_catalog(slug)
    search = request.GET.get("search", "").strip()

    objects = catalog["model"].objects.order_by(
        catalog["name_field"],
        "pk",
    )

    if search:
        objects = objects.filter(
            **{f"{catalog['name_field']}__icontains": search}
        )

    page = Paginator(objects, 24).get_page(request.GET.get("page"))

    entries = [
        {
            "pk": item.pk,
            "name": getattr(item, catalog["name_field"]),
            "description": item.description or "",
        }
        for item in page.object_list
    ]

    return render(
        request,
        "spells/catalog.html",
        {
            "catalog_title": catalog["title"],
            "slug": slug,
            "search": search,
            "entries": entries,
            "page": page,
        },
    )


def catalog_detail_page(request, slug, pk):
    if slug == "classes":
        return redirect("class_detail_page", pk=pk)
    catalog = get_catalog(slug)
    objects = catalog["model"].objects.all()

    if slug == "effects":
        objects = objects.select_related("damage_type")

    item = get_object_or_404(objects, pk=pk)

    attributes = []

    for field_name in catalog["fields"]:
        field = item._meta.get_field(field_name)
        value = getattr(item, field_name)

        if field.choices:
            value = getattr(item, f"get_{field_name}_display")()
        elif isinstance(value, bool):
            value = "Да" if value else "Нет"
        elif field_name == "cost" and value is not None:
            value = f"{value} зм"
        elif field_name == "damage_type" and value is not None:
            value = value.name

        if value is None or value == "":
            value = "Не указано"

        attributes.append({
            "label": field.verbose_name,
            "value": value,
        })

    return render(
        request,
        "spells/catalog.html",
        {
            "catalog_title": catalog["title"],
            "slug": slug,
            "detail": True,
            "entry_pk": item.pk,
            "entry_name": getattr(item, catalog["name_field"]),
            "description": item.description or "",
            "attributes": attributes,
        },
    )
def build_catalog_form(catalog):
    fields = [
        catalog["name_field"],
        "description",
        *catalog["fields"],
    ]

    if catalog["model"] is MagicSchool:
        fields.append("color")

    return forms.modelform_factory(
        catalog["model"],
        fields=fields,
        widgets={
            "description": forms.Textarea(attrs={"rows": 6}),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def catalog_create_page(request, slug):
    if not request.user.is_staff:
        raise PermissionDenied

    catalog = get_catalog(slug)
    form_class = build_catalog_form(catalog)

    form = form_class(
        request.POST if request.method == "POST" else None,
    )

    if request.method == "POST" and form.is_valid():
        item = form.save()

        return redirect(
            "catalog_detail_page",
            slug=slug,
            pk=item.pk,
        )

    return render(
        request,
        "spells/catalog_form.html",
        {
            "form": form,
            "catalog_title": catalog["title"],
            "slug": slug,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def catalog_edit_page(request, slug, pk):
    if not request.user.is_staff:
        raise PermissionDenied

    catalog = get_catalog(slug)
    item = get_object_or_404(catalog["model"], pk=pk)
    form_class = build_catalog_form(catalog)

    form = form_class(
        request.POST if request.method == "POST" else None,
        instance=item,
    )

    if request.method == "POST" and form.is_valid():
        form.save()

        return redirect(
            "catalog_detail_page",
            slug=slug,
            pk=item.pk,
        )

    return render(
        request,
        "spells/catalog_form.html",
        {
            "form": form,
            "catalog_title": catalog["title"],
            "slug": slug,
            "editing": True,
            "entry_pk": item.pk,
        },
    )