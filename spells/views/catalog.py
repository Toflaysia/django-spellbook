from spells.class_access import visible_classes, require_class_editor, can_edit_class
from spells.models import Trait
import re
from spells.filters import ComponentFilterForm, SchoolFilterForm
from spells.description import DescriptionModelForm
from django.core.paginator import Paginator
from django.db.models import Count
from django.utils.http import urlencode
from django.urls import reverse
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
    Spell,
)


def school_color(value):
    return value if isinstance(value,str) and re.fullmatch(r"#[0-9a-fA-F]{6}",value) else "#3498db"

CATALOGS = {
    "traits": {"title": "Черты", "model": Trait, "name_field": "name", "fields": ["prerequisites"]},
    "schools": {
        "title": "Школы магии",
        "model": MagicSchool,
        "name_field": "name",
        "fields": [],
    },
    "conditions": {
        "title": "Состояния", "model": Effect, "name_field": "name",
        "fields": ["duration", "damage_type"],
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



def catalog_objects(slug):
    objects = get_catalog(slug)["model"].objects.all()
    if slug == "conditions":
        return objects.filter(category="COND")
    if slug == "effects":
        return objects.exclude(category="COND")
    return objects


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
    objects = catalog_objects(slug).order_by(catalog["name_field"], "pk")
    if search:
        objects = objects.filter(**{f"{catalog['name_field']}__icontains": search})

    extra_filters = None
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

    if slug in ("effects", "conditions"):
        objects = objects.select_related("damage_type")
        effect_filters = EffectFilterForm(request.GET or None)
        if slug == "conditions":
            effect_filters.fields.pop("category")
        else:
            effect_filters.fields["category"].choices = [(value, label) for value, label in effect_filters.fields["category"].choices if value != "COND"]
        has_active_filters |= any(request.GET.get(name) for name in effect_filters.fields)
        if effect_filters.is_bound:
            if effect_filters.is_valid():
                values = effect_filters.cleaned_data
                if values.get("category"):
                    objects = objects.filter(category="" if values["category"] == "none" else values["category"])
                if values["damage_type"]:
                    objects = objects.filter(damage_type__isnull=True) if values["damage_type"] == "none" else objects.filter(damage_type_id=int(values["damage_type"]))
                if values["duration"]:
                    objects = objects.filter(duration__icontains=values["duration"])
                query.update({name: value for name, value in values.items() if value})
            else:
                objects = objects.none()

    if slug in ("components", "schools"):
        extra_filters = (ComponentFilterForm if slug == "components" else SchoolFilterForm)(request.GET or None)
        has_active_filters |= any(request.GET.get(name) for name in extra_filters.fields)
        if extra_filters.is_bound:
            if extra_filters.is_valid():
                values = extra_filters.cleaned_data
                if slug == "components":
                    for name in ("is_consumable", "is_focus"):
                        if values[name]:
                            objects = objects.filter(**{name: values[name] == "yes"})
                    for name, lookup in (("min_cost", "cost__gte"), ("max_cost", "cost__lte")):
                        if values[name] is not None:
                            objects = objects.filter(**{lookup: values[name]})
                else:
                    official = Spell.objects.filter(is_official=True, school__isnull=False)
                    if values["has_spells"]:
                        ids = official.values_list("school_id", flat=True)
                        objects = objects.filter(pk__in=ids) if values["has_spells"] == "yes" else objects.exclude(pk__in=ids)
                    if values["level"]:
                        objects = objects.filter(pk__in=official.filter(level=values["level"]).values_list("school_id", flat=True))
                query.update({name: value for name, value in values.items() if value not in ("", None)})
            else:
                objects = objects.none()

    class_group = ''
    if slug == 'classes':
        objects = objects.filter(pk__in=visible_classes(request.user)).select_related('created_by__user')
        class_group = request.GET.get('group', 'official')
        if class_group not in ('official', 'unofficial', 'mine'):
            raise Http404('Раздел классов не найден.')
        if class_group == 'official':
            objects = objects.filter(created_by__isnull=True, is_official=True)
        elif class_group == 'mine':
            objects = objects.filter(created_by__user=request.user) if request.user.is_authenticated else objects.none()
        else:
            objects = objects.filter(is_official=False)
            if request.user.is_authenticated:
                objects = objects.exclude(created_by__user=request.user)
        if 'group' in request.GET or class_group != 'official':
            query['group'] = class_group

    page = Paginator(objects, 24).get_page(request.GET.get("page"))
    entries = []
    for item in page.object_list:
        entry = {
            "pk": item.pk, "name": getattr(item, catalog["name_field"]),
            "description": item.description or "",
        }
        if slug == "schools":
            entry["color"] = school_color(item.color)
            entry["image_url"] = item.image.url if item.image else ""
        if slug == "classes":
            entry.update({
                "magic_type": item.get_magic_type_display(),
                "hit_die": item.get_hit_die_display(),
                "spellcasting_ability": item.get_spellcasting_ability_display() if item.magic_type != "NC" else "",
                "subclass_count": item.subclass_count,
                "image_url": item.display_image_url, "author": str(item.created_by) if item.created_by_id else "",
                "is_public": item.is_public, "can_edit": can_edit_class(request.user, item),
            })
        if slug == "damage-types":
            entry.update(
                is_magic=item.is_magic, is_regular=item.is_regular,
                image_url=item.image.url if item.image else "",
            )
        if slug in ("effects", "conditions"):
            entry.update(
                image_url=item.image.url if item.image else "",
                category=item.get_category_display(),
                damage_type=str(item.damage_type) if item.damage_type else "",
                duration=item.duration,
            )
        entries.append(entry)
    return render(request, "spells/catalog.html", {
        "catalog_title": catalog["title"], "slug": slug, "search": search,
        "class_group": class_group, "entries": entries, "page": page, "class_filters": class_filters,
        "extra_filters": extra_filters, "damage_filters": damage_filters, "effect_filters": effect_filters,
        "has_active_filters": has_active_filters, "page_query": urlencode(query),
    })


def catalog_detail_page(request, slug, pk):
    if slug == "classes":
        return redirect("class_detail_page", pk=pk)
    catalog = get_catalog(slug)
    if slug == "effects" and Effect.objects.filter(pk=pk, category="COND").exists():
        return redirect("catalog_detail_page", slug="conditions", pk=pk)
    objects = catalog_objects(slug)

    if slug in ("effects", "conditions"):
        objects = objects.select_related("damage_type")

    item = get_object_or_404(objects, pk=pk)

    attributes = []

    for field_name in catalog["fields"]:
        if field_name == "color":
            continue
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
            "school_color": school_color(item.color) if slug == "schools" else "",
            "entry_image_url": item.image.url if slug in ("damage-types", "effects", "conditions", "schools") and item.image else "",
            "description": item.description or "",
            "attributes": attributes,
        },
    )
def build_catalog_form(catalog, *, user_class=False):
    fields = [
        catalog["name_field"],
        "description",
        *catalog["fields"],
    ]

    if catalog["model"] is CharacterClass:
        fields.extend(["is_public"] if user_class else ["is_official"])

    if catalog["model"] in (DamageType, Effect, MagicSchool, CharacterClass):
        fields.insert(1, "image")

    if catalog["model"] is MagicSchool:
        fields.append("color")

    form_class = forms.modelform_factory(
        catalog["model"],
        form=DescriptionModelForm,
        fields=fields,
        widgets={
            "description": forms.Textarea(attrs={"rows": 6}),
            "image": forms.ClearableFileInput(attrs={"accept": "image/*"}),
        },
    )
    if catalog["model"] is CharacterClass:
        def clean_name(self):
            name = self.cleaned_data['name'].strip()
            existing = CharacterClass.objects.filter(name=name, created_by_id=self.instance.created_by_id).exclude(pk=self.instance.pk)
            if existing.exists():
                raise forms.ValidationError('Класс с таким названием уже существует у этого автора.')
            return name
        form_class.clean_name = clean_name
    if catalog is CATALOGS["effects"]:
        form_class.base_fields["category"].choices = [(value, label) for value, label in form_class.base_fields["category"].choices if value != "COND"]
    if catalog["model"] is MagicSchool:
        form_class.base_fields["color"] = forms.RegexField(regex=r"^#[0-9a-fA-F]{6}$", label="Цвет школы магии", initial="#3498db", widget=forms.TextInput(attrs={"placeholder":"#7C3AED", "maxlength":7, "pattern":"#[0-9a-fA-F]{6}", "autocomplete":"off"}), error_messages={"invalid":"Укажи цвет в формате #RRGGBB."})
    return form_class


@login_required
@require_http_methods(["GET", "POST"])
def catalog_create_page(request, slug):
    if not request.user.is_staff:
        raise PermissionDenied

    catalog = get_catalog(slug)
    form_class = build_catalog_form(catalog)

    kwargs = {'instance': Effect(category='COND')} if slug == 'conditions' else {}
    class_group = ''
    if slug == 'classes':
        class_group = request.GET.get('group', 'official')
        if class_group == 'mine':
            return redirect('user_class_create_page')
        if class_group not in ('official', 'unofficial'):
            raise Http404('Раздел классов не найден.')
        kwargs['instance'] = CharacterClass(is_official=class_group == 'official')
    form = form_class(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
        **kwargs,
    )
    if class_group == 'unofficial':
        form.fields.pop('is_official')

    if request.method == "POST" and form.is_valid():
        item = form.save()
        if slug in ("damage-types", "effects", "conditions"):
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
            "cancel_url": reverse('catalog_list_page', args=[slug]) + ('?group=' + class_group if class_group else ''),
            "school_color": school_color(form["color"].value()) if slug == "schools" else "",
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def catalog_edit_page(request, slug, pk):
    catalog = get_catalog(slug)
    if slug == "effects" and Effect.objects.filter(pk=pk, category="COND").exists():
        return redirect("catalog_edit_page", slug="conditions", pk=pk)
    item = get_object_or_404(visible_classes(request.user) if slug == "classes" else catalog_objects(slug), pk=pk)
    if slug == 'classes':
        require_class_editor(request.user, item)
    elif not request.user.is_staff:
        raise PermissionDenied
    form_class = build_catalog_form(catalog, user_class=slug == 'classes' and item.created_by_id is not None)

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
            "school_color": school_color(form["color"].value()) if slug == "schools" else "",
        },
    )

@login_required
@require_http_methods(["GET", "POST"])
def catalog_delete_page(request, slug, pk):
    if not request.user.is_staff:
        raise PermissionDenied
    if slug not in ("damage-types", "traits"):
        raise Http404("Удаление этого справочника недоступно.")
    item = get_object_or_404(get_catalog(slug)["model"], pk=pk)
    if request.method == "POST":
        item.delete()
        return redirect("catalog_list_page", slug=slug)
    return render(request, "spells/catalog_confirm_delete.html" if slug == "traits" else "spells/damage_type_confirm_delete.html", {
        "slug": slug,
        "item": item, "effects_count": item.effects.count() if slug == "damage-types" else 0,
    })
