import json

from django import forms
from django.templatetags.static import static


DESCRIPTION_PREFIX = "SPELLBOOK_BLOCKS_V1:"


def parse_description(value):
    payload = json.loads(value[len(DESCRIPTION_PREFIX):])

    if not isinstance(payload, list):
        raise ValueError("Неверный формат описания.")

    blocks = []

    for block in payload:
        if not isinstance(block, dict):
            raise ValueError("Неверный блок описания.")

        if block.get("type") in ("text", "heading", "quote"):
            text = block.get("text")

            if not isinstance(text, str):
                raise ValueError("Неверный текст описания.")

            if text.strip():
                blocks.append({"type": block["type"], "text": text})

        elif block.get("type") == "rule":
            blocks.append({"type": "rule"})

        elif block.get("type") == "list":
            items = block.get("items")
            if not isinstance(items, list) or any(not isinstance(item, str) for item in items):
                raise ValueError("Неверный список.")
            items = [item for item in items if item.strip()]
            if items:
                blocks.append({"type": "list", "items": items})

        elif block.get("type") == "table":
            rows = block.get("rows")

            if not isinstance(rows, list) or not rows:
                raise ValueError("В таблице должна быть хотя бы одна строка.")

            column_count = None

            for row in rows:
                if not isinstance(row, list) or not row:
                    raise ValueError(
                        "В таблице должен быть хотя бы один столбец."
                    )

                if column_count is None:
                    column_count = len(row)
                elif len(row) != column_count:
                    raise ValueError(
                        "Во всех строках должно быть одинаковое "
                        "количество столбцов."
                    )

                if any(not isinstance(cell, str) for cell in row):
                    raise ValueError("Ячейки должны содержать текст.")

            blocks.append({"type": "table", "rows": rows})

        else:
            raise ValueError("Неизвестный блок описания.")

    return blocks


class DescriptionFormMixin:
    description_field_names = (
        "description",
        "features_description",
        "higher_level",
        "equipment_description",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for name in self.description_field_names:
            if name in self.fields:
                self.fields[name].widget.attrs[
                    "data-description-editor"
                ] = "true"
                from django.urls import reverse
                self.fields[name].widget.attrs["data-spell-search-url"] = reverse("spell_link_search")
                self.fields[name].widget.attrs["data-spell-preview-url"] = reverse("spell_preview", args=[0])
                self.fields[name].widget.attrs["data-catalog-search-url"] = reverse("catalog_link_search", args=['schools'])
                self.fields[name].widget.attrs["data-catalog-preview-url"] = reverse("catalog_preview", args=['schools', 0])

    def clean(self):
        cleaned_data = super().clean()

        for name in self.description_field_names:
            value = cleaned_data.get(name)

            if not isinstance(value, str):
                continue

            if not value.startswith(DESCRIPTION_PREFIX):
                continue

            try:
                blocks = parse_description(value)
            except (ValueError, TypeError, RecursionError):
                self.add_error(
                    name,
                    forms.ValidationError(
                        "Не удалось сохранить описание. "
                        "Проверь формат блоков и одинаковое количество ячеек в строках таблиц."
                    ),
                )
                continue

            has_content = any(
                (
                    block["type"] in ("text", "heading", "quote")
                    and block["text"].strip()
                )
                or (block["type"] == "list" and any(item.strip() for item in block["items"]))
                or (
                    block["type"] == "table"
                    and any(
                        cell.strip()
                        for row in block["rows"]
                        for cell in row
                    )
                )
                for block in blocks
            )

            if self.fields[name].required and not has_content:
                self.add_error(name, "Заполни описание.")
                continue

            cleaned_data[name] = (
                DESCRIPTION_PREFIX
                + json.dumps(blocks, ensure_ascii=False)
                if blocks else ""
            )

        return cleaned_data

class DescriptionModelForm(DescriptionFormMixin, forms.ModelForm):
    class Media:
        css = {"all": (static("spells/description_editor.css") + "?v=20261020-json-import", static("spells/play_tools.css") + "?v=20261021-neutral-dice")}
        js = (static("spells/play_tools.js") + "?v=20261020-json-import", static("spells/description_editor.js") + "?v=20261020-json-import")
