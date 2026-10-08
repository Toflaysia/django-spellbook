import json

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from spells.models import CharacterClass, Subclass
from spells.progression import TABLE_TYPES, preset_columns, validate_progression_columns


class ProgressionForm(forms.Form):
    table_type = forms.ChoiceField(label="Вид таблицы", choices=TABLE_TYPES)
    columns = forms.CharField(widget=forms.HiddenInput, required=False)

    def __init__(self, *args, character_class, subclass=None, **kwargs):
        self.is_subclass = subclass is not None
        target = subclass or character_class
        initial = {
            "table_type": character_class.progression_table_type,
            "columns": json.dumps(
                target.progression_columns or ([] if subclass else preset_columns(character_class.progression_table_type)),
                ensure_ascii=False,
            ),
        }
        super().__init__(*args, initial=initial, **kwargs)
        if subclass:
            self.fields.pop("table_type")

    def clean_columns(self):
        try:
            columns = json.loads(self.cleaned_data.get("columns") or "[]")
        except (ValueError, TypeError, RecursionError):
            raise forms.ValidationError("Неверный формат таблицы. Обнови страницу и повтори ввод.")
        validate_progression_columns(columns, subclass=self.is_subclass)
        return columns


@login_required
@require_http_methods(["GET", "POST"])
def class_table_edit_page(request, pk, entry_pk=None):
    if not request.user.is_staff:
        raise PermissionDenied
    character_class = get_object_or_404(CharacterClass, pk=pk)
    subclass = None
    if entry_pk is not None:
        subclass = get_object_or_404(Subclass, pk=entry_pk, character_class=character_class)
    target = subclass or character_class
    form = ProgressionForm(
        request.POST if request.method == "POST" else None,
        character_class=character_class, subclass=subclass,
    )
    return_url = reverse("class_detail_page", kwargs={"pk": character_class.pk})
    if subclass:
        return_url += f"?subclass={subclass.pk}"
    if request.method == "POST" and form.is_valid():
        target.progression_columns = form.cleaned_data["columns"]
        fields = ["progression_columns"]
        if not subclass:
            target.progression_table_type = form.cleaned_data["table_type"]
            fields.append("progression_table_type")
        target.save(update_fields=fields)
        return redirect(return_url)
    return render(request, "spells/progression_form.html", {
        "form": form, "character_class": character_class, "subclass": subclass,
        "return_url": return_url,
        "table_presets": {key: preset_columns(key) for key, _ in TABLE_TYPES},
    })
