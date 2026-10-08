from django import template
from django.utils.html import escape, linebreaks
from django.utils.safestring import mark_safe

from spells.description import DESCRIPTION_PREFIX, parse_description


register = template.Library()


@register.filter
def render_description(value):
    value = str(value or "")

    if not value.startswith(DESCRIPTION_PREFIX):
        return mark_safe(linebreaks(value, autoescape=True))

    try:
        blocks = parse_description(value)
    except (ValueError, TypeError, RecursionError):
        return mark_safe(linebreaks(value, autoescape=True))

    parts = []

    for block in blocks:
        if block["type"] == "text":
            parts.append(
                linebreaks(block["text"], autoescape=True)
            )
            continue

        parts.append(
            '<div class="description-display-table-wrapper">'
            '<table class="description-display-table"><tbody>'
        )

        for row in block["rows"]:
            parts.append("<tr>")

            for cell in row:
                escaped_cell = str(escape(cell))
                escaped_cell = escaped_cell.replace(
                    "\r\n", "\n"
                ).replace("\r", "\n").replace("\n", "<br>")

                parts.append(f"<td>{escaped_cell}</td>")

            parts.append("</tr>")

        parts.append("</tbody></table></div>")

    return mark_safe("".join(parts))