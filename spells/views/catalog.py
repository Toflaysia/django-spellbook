from spells.description import DescriptionModelForm
from django.core.paginator import Paginator
from django.db.models import Count
from django.utils.http import urlencode
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
            "is_regular",
        ],
    },
}


def get_catalog(slug):
    catalog = CATALOGS.get(slug)

    if catalog is None:
        raise Http404("Справочник не найден.")

    return catalog



class ClassFilterForm(forms.Form):
    magic_type = forms.ChoiceField(
        label="Магический тип", required=False,
        choices=[("", "Все типы"), *CharacterClass._meta.get_field("magic_type").choices],
    )
    hit_die = forms.TypedChoiceField(
        label="Кость хитов", required=False, coerce=int, empty_value=None,
        choices=[("", "Любая кость"), *CharacterClass._meta.get_field("hit_die").choices],
    )
    spellcasting_ability = forms.ChoiceField(
        label="Заклинательная характеристика", required=False,
        choices=[("", "Любая характеристика"), *CharacterClass._meta.get_field("spellcasting_ability").choices],
    )
    has_subclasses = forms.BooleanField(label="Есть подклассы", required=False)


class DamageTypeFilterForm(forms.Form):
    OPTIONS = [("", "Все варианты"), ("yes", "Да"), ("no", "Нет")]
    is_magic = forms.ChoiceField(label="Магический урон", required=False, choices=OPTIONS)
    is_regular = forms.ChoiceField(label="Обычный урон", required=False, choices=OPTIONS)


class EffectFilterForm(forms.Form):
    category = forms.ChoiceField(
        label="Категория", required=False,
        choices=[("", "Все категории"), ("none", "Без категории"), *Effect._meta.get_field("category").choices],
    )
    damage_type = forms.ChoiceField(label="Тип урона", required=False)
    duration = forms.CharField(
        label="Продолжительность", required=False, max_length=100,
        widget=forms.TextInput(attrs={"placeholder": "Например: минута"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["damage_type"].choices = [
            ("", "Все типы урона"), ("none", "Без типа урона"),
            *((str(item.pk), str(item)) for item in DamageType.objects.order_by("name", "pk")),
        ]


def catalog_list_page(request, slug):
    catalog = get_catalog(slug)
    search = request.GET.get("search", "").strip()
    objects = catalog["model"].objects.order_by(catalog["name_field"], "pk")
    if search:
        objects = objects.filter(**{f"{catalog['name_field']}__icontains": search})

    class_filters = None
    damage_filters = None
    effect_filters = None
    query = {"search": search} if search else {}
    has_active_filters = bool(search)
    if slug == "classes":
        class_filters = ClassFilterForm(request.GET or None)
        has_active_filters |= any(request.GET.get(name) for name in class_filters.fields)
        if class_filters.is_bound:
            if class_filters.is_valid():
                values = class_filters.cleaned_data
                for name in ("magic_type", "hit_die", "spellcasting_ability"):
                    if values[name]:
                        objects = objects.filter(**{name: values[name]})
                        query[name] = values[name]
                if values["spellcasting_ability"]:
                    # Non-casters have a default ability in the model, but do not cast spells.
                    objects = objects.exclude(magic_type="NC")
                if values["has_subclasses"]:
                    objects = objects.filter(subclasses__isnull=False)
                    query["has_subclasses"] = "1"
            else:
                objects = objects.none()
        objects = objects.annotate(subclass_count=Count("subclasses", distinct=True))

    if slug == "damage-types":
        damage_filters = DamageTypeFilterForm(request.GET or None)
        has_active_filters |= any(request.GET.get(name) for name in damage_filters.fields)
        if damage_filters.is_bound:
            if damage_filters.is_valid():
                for name, value in damage_filters.cleaned_data.items():
                    if value:
                        objects = objects.filter(**{name: value == "yes"})
                        query[name] = value
            else:
                objects = objects.none()

    if slug == "effects":
        objects = objects.select_related("damage_type")
        effect_filters = EffectFilterForm(request.GET or None)
        has_active_filters |= any(request.GET.get(name) for name in effect_filters.fields)
        if effect_filters.is_bound:
            if effect_filters.is_valid():
                values = effect_filters.cleaned_data
                if values["category"]:
                    objects = objects.filter(category="" if values["category"] == "none" else values["category"])
                if values["damage_type"]:
                    objects = objects.filter(damage_type__isnull=True) if values["damage_type"] == "none" else objects.filter(damage_type_id=int(values["damage_type"]))
                if values["duration"]:
                    objects = objects.filter(duration__icontains=values["duration"])
                query.update({name: value for name, value in values.items() if value})
            else:
                objects = objects.none()

    page = Paginator(objects, 24).get_page(request.GET.get("page"))
    entries = []
    for item in page.object_list:
        entry = {
            "pk": item.pk, "name": getattr(item, catalog["name_field"]),
            "description": item.description or "",
        }
        if slug == "classes":
            entry.update({
                "magic_type": item.get_magic_type_display(),
                "hit_die": item.get_hit_die_display(),
                "spellcasting_ability": item.get_spellcasting_ability_display() if item.magic_type != "NC" else "",
                "subclass_count": item.subclass_count,
            })
        if slug == "damage-types":
            entry.update(
                is_magic=item.is_magic, is_regular=item.is_regular,
                image_url=item.image.url if item.image else "",
            )
        if slug == "effects":
            entry.update(
                image_url=item.image.url if item.image else "",
                category=item.get_category_display(),
                damage_type=str(item.damage_type) if item.damage_type else "",
                duration=item.duration,
            )
        entries.append(entry)
    return render(request, "spells/catalog.html", {
        "catalog_title": catalog["title"], "slug": slug, "search": search,
        "entries": entries, "page": page, "class_filters": class_filters,
        "damage_filters": damage_filters, "effect_filters": effect_filters,
        "has_active_filters": has_active_filters, "page_query": urlencode(query),
    })


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
            "entry_image_url": item.image.url if slug in ("damage-types", "effects") and item.image else "",
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

    if catalog["model"] in (DamageType, Effect):
        fields.insert(1, "image")

    if catalog["model"] is MagicSchool:
        fields.append("color")

    return forms.modelform_factory(
        catalog["model"],
        form=DescriptionModelForm,
        fields=fields,
        widgets={
            "description": forms.Textarea(attrs={"rows": 6}),
            "image": forms.ClearableFileInput(attrs={"accept": "image/*"}),
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
        request.FILES if request.method == "POST" else None,
    )

    if request.method == "POST" and form.is_valid():
        item = form.save()
        if slug in ("damage-types", "effects"):
            return redirect("catalog_list_page", slug=slug)

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
        request.FILES if request.method == "POST" else None,
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

@login_required
@require_http_methods(["GET", "POST"])
def catalog_delete_page(request, slug, pk):
    if not request.user.is_staff:
        raise PermissionDenied
    if slug != "damage-types":
        raise Http404("Удаление этого справочника недоступно.")
    item = get_object_or_404(DamageType, pk=pk)
    if request.method == "POST":
        item.delete()
        return redirect("catalog_list_page", slug=slug)
    return render(request, "spells/damage_type_confirm_delete.html", {
        "item": item, "effects_count": item.effects.count(),
    })
