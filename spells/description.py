import json

from django import forms


DESCRIPTION_PREFIX = "SPELLBOOK_BLOCKS_V1:"


def parse_description(value):
    payload = json.loads(value[len(DESCRIPTION_PREFIX):])

    if not isinstance(payload, list):
        raise ValueError("Неверный формат описания.")

    blocks = []

    for block in payload:
        if not isinstance(block, dict):
            raise ValueError("Неверный блок описания.")

        if block.get("type") == "text":
            text = block.get("text")

            if not isinstance(text, str):
                raise ValueError("Неверный текст описания.")

            if text.strip():
                blocks.append({"type": "text", "text": text})

        elif block.get("type") == "table":
            rows = block.get("rows")

            if not isinstance(rows, list) or not 1 <= len(rows) <= 9:
                raise ValueError("В таблице должно быть от 1 до 9 строк.")

            column_count = None

            for row in rows:
                if not isinstance(row, list) or not 1 <= len(row) <= 9:
                    raise ValueError(
                        "В таблице должно быть от 1 до 9 столбцов."
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
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for name in self.description_field_names:
            if name in self.fields:
                self.fields[name].widget.attrs[
                    "data-description-editor"
                ] = "true"

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
                        "Проверь таблицы: максимальный размер — 9 × 9."
                    ),
                )
                continue

            has_content = any(
                (
                    block["type"] == "text"
                    and block["text"].strip()
                )
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
        css = {"all": ("spells/description_editor.css",)}
        js = ("spells/description_editor.js",)
