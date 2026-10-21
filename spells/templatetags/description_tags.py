import re
from urllib.parse import unquote
from django.urls import reverse
from django import template
from django.utils.html import escape, linebreaks
from django.utils.safestring import mark_safe

from spells.description import DESCRIPTION_PREFIX, parse_description


register = template.Library()


INLINE_LINK = re.compile(r"\[\[(spell|damage|condition|school|dice|trait|effect|class|component|time):([^\]|\n]{1,160})\|([^\]\n]*)\]\]")
CATALOG_LINK_KINDS = {'damage': 'damage-types', 'condition': 'effects', 'school': 'schools', 'trait': 'traits', 'effect': 'effects', 'class': 'classes', 'component': 'components', 'time': 'casting-times'}


def token_label(match):
    return unquote(match[3]) or unquote(match[2])


def linked_text(value):
    parts = []
    last = 0
    for match in INLINE_LINK.finditer(value):
        parts.append(str(escape(value[last:match.start()])))
        kind, identifier, label = match[1], unquote(match[2]), token_label(match)
        if kind == 'dice':
            if (len(identifier) <= 120 and re.fullmatch(r'[0-9dDkKhHlL+\s-]+', identifier)
                    and re.search(r'd\d', identifier, re.IGNORECASE)):
                parts.append(f'<button type="button" class="description-dice-link" data-dice-expression="{escape(identifier)}" title="Бросить {escape(identifier)}">{escape(label)}</button>')
            else:
                parts.append(str(escape(match[0])))
        elif kind == 'component':
            parts.append(str(escape(label)))
        elif re.fullmatch(r'\d{1,10}', identifier):
            pk = int(identifier)
            if kind == 'spell':
                url = reverse('spell_detail_page', args=[pk])
                attrs = f'data-spell-id="{pk}"'
            else:
                slug = CATALOG_LINK_KINDS[kind]
                url = reverse('catalog_detail_page', args=['conditions' if kind == 'condition' else slug, pk])
                attrs = "" if kind in ("trait", "effect", "class", "component", "time") else f'data-catalog-kind="{slug}" data-catalog-id="{pk}"'
            parts.append(f'<a class="description-spell-link" {attrs} href="{url}">{escape(label)}</a>')
        else:
            parts.append(str(escape(match[0])))
        last = match.end()
    parts.append(str(escape(value[last:])))
    return "".join(parts)

def linked_paragraphs(value):
    return linebreaks(linked_text(value), autoescape=False)

@register.filter
def render_description(value):
    value = str(value or "")

    if not value.startswith(DESCRIPTION_PREFIX):
        return mark_safe(linked_paragraphs(value))

    try:
        blocks = parse_description(value)
    except (ValueError, TypeError, RecursionError):
        return mark_safe(linked_paragraphs(value))

    parts = []

    for block in blocks:
        if block["type"] == "text":
            parts.append(
                linked_paragraphs(block["text"])
            )
            continue

        if block["type"] == "rule":
            parts.append('<hr class="description-rule">')
            continue
        if block["type"] == "heading":
            parts.append('<h3>' + linked_text(block["text"]) + '</h3>')
            continue
        if block["type"] == "quote":
            parts.append('<blockquote>' + linked_paragraphs(block["text"]) + '</blockquote>')
            continue
        if block["type"] == "list":
            parts.append('<ul>' + ''.join('<li>' + linked_text(item) + '</li>' for item in block["items"]) + '</ul>')
            continue

        parts.append(
            '<div class="description-display-table-wrapper">'
            '<table class="description-display-table"><tbody>'
        )

        for row in block["rows"]:
            parts.append("<tr>")

            for cell in row:
                escaped_cell = linked_text(cell)
                escaped_cell = escaped_cell.replace(
                    "\r\n", "\n"
                ).replace("\r", "\n").replace("\n", "<br>")

                parts.append(f"<td>{escaped_cell}</td>")

            parts.append("</tr>")

        parts.append("</tbody></table></div>")

    return mark_safe("".join(parts))

@register.filter
def description_text(value):
    value = str(value or "")
    if not value.startswith(DESCRIPTION_PREFIX):
        return INLINE_LINK.sub(token_label, value)
    try:
        blocks = parse_description(value)
    except (ValueError, TypeError, RecursionError):
        return value
    text = "\n".join(
        block["text"] if block["type"] in ("text", "heading", "quote") else
        "" if block["type"] == "rule" else
        "\n".join(block["items"]) if block["type"] == "list" else
        "\n".join(" | ".join(row) for row in block["rows"])
        for block in blocks
    )

    return INLINE_LINK.sub(token_label, text)
