from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET
from spells.models import CharacterClass, ClassFeature
from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from spells.models import Subclass
from spells.models import ClassSection
from spells.description import DescriptionFormMixin

@require_GET
def class_detail_page(request, pk):
    character_class = get_object_or_404(CharacterClass, pk=pk)
    subclasses = character_class.subclasses.order_by("name", "pk")

    selected_subclass = None
    subclass_id = request.GET.get("subclass", "").strip()

    if subclass_id:
        if not subclass_id.isdigit() or len(subclass_id) > 10:
            raise Http404("Подкласс не найден.")

        selected_subclass = get_object_or_404(
            subclasses,
            pk=int(subclass_id),
        )

    available_features = Q(subclass__isnull=True)

    if selected_subclass:
        available_features |= Q(subclass=selected_subclass)

    features = list(
        ClassFeature.objects.filter(
            available_features,
            character_class=character_class,
        )
        .select_related("subclass")
        .order_by("level", "name", "pk")
    )

    features_by_level = {}

    for feature in features:
        for level in feature.acquisition_levels:
            features_by_level.setdefault(level, []).append(feature)

    levels = [
        {
            "level": level,
            "proficiency": 2 + (level - 1) // 4,
            "features": features_by_level.get(level, []),
        }
        for level in range(1, 21)
    ]

    return render(
        request,
        "spells/class_detail.html",
        {
            "character_class": character_class,
            "subclasses": subclasses,
            "selected_subclass": selected_subclass,
            "levels": levels,
            "features": features,
            "sections": list(character_class.sections.all()),
        },
    )
class SubclassForm(DescriptionFormMixin, forms.ModelForm):
    class Meta:
        model = Subclass
        fields = [
            "name",
            "description",
            "level_gained",
            "features_description",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "features_description": forms.Textarea(attrs={"rows": 5}),
        }
        labels = {
            "features_description": "Дополнительные сведения об умениях",
        }

    def clean_level_gained(self):
        level = self.cleaned_data["level_gained"]

        if self.instance.pk:
            if self.instance.features.filter(level__lt=level).exists():
                raise forms.ValidationError(
                    "У подкласса уже есть умения, получаемые раньше "
                    "этого уровня. Сначала измени уровни этих умений."
                )

        return level


class ClassFeatureForm(DescriptionFormMixin, forms.ModelForm):
    levels = forms.CharField(
        label="Уровни получения",
        help_text="Укажи уровни через запятую. Например: 3, 7, 10.",
        widget=forms.TextInput(
            attrs={"placeholder": "3, 7, 10"}
        ),
    )

    class Meta:
        model = ClassFeature
        fields = [
            "name",
            "levels",
            "subclass",
            "description",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 7}),
        }

    def __init__(self, *args, character_class, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["subclass"].queryset = (
            character_class.subclasses.order_by("name", "pk")
        )
        self.fields["subclass"].empty_label = "Общее умение класса"

        if not self.is_bound:
            self.initial["levels"] = ", ".join(
                str(level)
                for level in self.instance.acquisition_levels
            )

    def clean_levels(self):
        text = self.cleaned_data["levels"]
        parts = text.split(",")

        try:
            levels = [int(part.strip()) for part in parts]
        except ValueError:
            raise forms.ValidationError(
                "Укажи целые числа через запятую. Например: 3, 7, 10."
            )

        if any(level < 1 or level > 20 for level in levels):
            raise forms.ValidationError(
                "Каждый уровень должен быть от 1 до 20."
            )

        return sorted(set(levels))

    def clean(self):
        cleaned_data = super().clean()
        levels = cleaned_data.get("levels")

        if levels:
            self.instance.level = levels[0]

        return cleaned_data

def save_class_entry(request, pk, kind, entry_pk=None):
    if not request.user.is_staff:
        raise PermissionDenied

    character_class = get_object_or_404(CharacterClass, pk=pk)

    if kind == "subclass":
        model = Subclass
        form_class = SubclassForm
        title = "подкласса"
    else:
        model = ClassFeature
        form_class = ClassFeatureForm
        title = "умения"

    if entry_pk is not None:
        item = get_object_or_404(
            model,
            pk=entry_pk,
            character_class=character_class,
        )
    else:
        item = model(character_class=character_class)

    form_kwargs = {
        "instance": item,
    }

    if kind == "feature":
        form_kwargs["character_class"] = character_class

    form = form_class(
        request.POST if request.method == "POST" else None,
        **form_kwargs,
    )

    cancel_url = reverse(
        "class_detail_page",
        kwargs={"pk": character_class.pk},
    )

    if request.method == "POST" and form.is_valid():
        item = form.save()

        if kind == "subclass":
            subclass_id = item.pk
        else:
            subclass_id = item.subclass_id

        target_url = cancel_url

        if subclass_id:
            target_url += f"?subclass={subclass_id}"

        return redirect(target_url)

    return render(
        request,
        "spells/class_entry_form.html",
        {
            "form": form,
            "character_class": character_class,
            "entry_type": title,
            "editing": entry_pk is not None,
            "cancel_url": cancel_url,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def subclass_create_page(request, pk):
    return save_class_entry(request, pk, "subclass")


@login_required
@require_http_methods(["GET", "POST"])
def subclass_edit_page(request, pk, entry_pk):
    return save_class_entry(request, pk, "subclass", entry_pk)


@login_required
@require_http_methods(["GET", "POST"])
def class_feature_create_page(request, pk):
    return save_class_entry(request, pk, "feature")


@login_required
@require_http_methods(["GET", "POST"])
def class_feature_edit_page(request, pk, entry_pk):
    return save_class_entry(request, pk, "feature", entry_pk)

@login_required
@require_http_methods(["GET", "POST"])
def class_feature_delete_page(request, pk, entry_pk):
    if not request.user.is_staff:
        raise PermissionDenied

    character_class = get_object_or_404(CharacterClass, pk=pk)

    feature = get_object_or_404(
        ClassFeature.objects.select_related("subclass"),
        pk=entry_pk,
        character_class=character_class,
    )

    return_url = reverse(
        "class_detail_page",
        kwargs={"pk": character_class.pk},
    )

    if feature.subclass_id:
        return_url += f"?subclass={feature.subclass_id}"

    if request.method == "POST":
        feature.delete()
        return redirect(return_url)

    return render(
        request,
        "spells/class_feature_confirm_delete.html",
        {
            "character_class": character_class,
            "feature": feature,
            "return_url": return_url,
        },
    )
class ClassSectionForm(DescriptionFormMixin, forms.ModelForm):
    class Meta:
        model = ClassSection
        fields = [
            "title",
            "position",
            "description",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 12}),
        }


def save_class_section(request, pk, entry_pk=None):
    if not request.user.is_staff:
        raise PermissionDenied

    character_class = get_object_or_404(CharacterClass, pk=pk)

    if entry_pk is not None:
        section = get_object_or_404(
            ClassSection,
            pk=entry_pk,
            character_class=character_class,
        )
    else:
        section = ClassSection(character_class=character_class)

    form = ClassSectionForm(
        request.POST if request.method == "POST" else None,
        instance=section,
    )

    return_url = reverse(
        "class_detail_page",
        kwargs={"pk": character_class.pk},
    )

    if request.method == "POST" and form.is_valid():
        section = form.save()
        return redirect(f"{return_url}#class-section-{section.pk}")

    return render(
        request,
        "spells/class_entry_form.html",
        {
            "form": form,
            "character_class": character_class,
            "entry_type": "раздела",
            "editing": entry_pk is not None,
            "cancel_url": return_url,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def class_section_create_page(request, pk):
    return save_class_section(request, pk)


@login_required
@require_http_methods(["GET", "POST"])
def class_section_edit_page(request, pk, entry_pk):
    return save_class_section(request, pk, entry_pk)

@login_required
@require_http_methods(["GET", "POST"])
def class_section_delete_page(request, pk, entry_pk):
    if not request.user.is_staff:
        raise PermissionDenied

    character_class = get_object_or_404(CharacterClass, pk=pk)

    section = get_object_or_404(
        ClassSection,
        pk=entry_pk,
        character_class=character_class,
    )

    return_url = reverse(
        "class_detail_page",
        kwargs={"pk": character_class.pk},
    )

    if request.method == "POST":
        section.delete()
        return redirect(return_url)

    return render(
        request,
        "spells/class_section_confirm_delete.html",
        {
            "character_class": character_class,
            "section": section,
            "return_url": return_url,
        },
    )