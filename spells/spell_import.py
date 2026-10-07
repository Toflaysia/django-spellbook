from html.parser import HTMLParser

from spells.models import MagicSchool, SpellTime


class DescriptionParser(HTMLParser):
    """Преобразует HTML-описание в обычный текст."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"p", "div", "br", "li"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"p", "div", "li"}:
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data)


def plain_text(value):
    if not isinstance(value, str):
        return ""

    parser = DescriptionParser()
    parser.feed(value)
    parser.close()

    lines = [
        line.strip()
        for line in "".join(parser.parts).splitlines()
        if line.strip()
    ]

    return "\n\n".join(lines)


def build_spell_initial(data):
    system = data["system"]

    def section(name):
        value = system.get(name)
        return value if isinstance(value, dict) else {}

    school_names = {
        "abj": "Ограждение",
        "con": "Вызов",
        "div": "Прорицание",
        "enc": "Очарование",
        "evo": "Воплощение",
        "ill": "Иллюзия",
        "nec": "Некромантия",
        "trs": "Преобразование",
    }

    activation_units = {
        "action": "действие",
        "bonus": "бонусное действие",
        "reaction": "реакция",
        "minute": "мин.",
        "hour": "ч.",
    }

    duration_units = {
        "round": "раунд.",
        "turn": "ход.",
        "minute": "мин.",
        "hour": "ч.",
        "day": "дн.",
    }

    description = plain_text(section("description").get("value"))
    materials = section("materials")
    material_text = plain_text(materials.get("value"))

    if material_text:
        description += f"\n\nМатериальные компоненты: {material_text}"

        if materials.get("consumed") is True:
            description += "\nКомпоненты расходуются."

        if materials.get("cost"):
            description += f"\nСтоимость компонентов: {materials['cost']} зм."

    activation = section("activation")
    activation_type = activation.get("type")
    activation_cost = activation.get("cost", 1)
    activation_label = activation_units.get(activation_type, "")

    if activation_cost == 1:
        time_text = {
            "action": "Действие",
            "bonus": "Бонусное действие",
            "reaction": "Реакция",
            "minute": "1 минута",
            "hour": "1 час",
        }.get(activation_type, "")
    else:
        time_text = (
            f"{activation_cost} {activation_label}"
            if activation_label else ""
        )

    duration = section("duration")
    duration_type = duration.get("units")

    if duration_type == "inst":
        duration_text = "Мгновенная"
    elif duration_type == "perm":
        duration_text = "Постоянная"
    else:
        duration_label = duration_units.get(duration_type, "")
        duration_text = (
            f"{duration.get('value', '')} {duration_label}".strip()
            if duration_label else ""
        )

    spell_range = section("range")
    range_type = spell_range.get("units")

    range_text = {
        "touch": "Касание",
        "self": "На себя",
        "any": "Неограниченная",
    }.get(range_type, "")

    if range_type in {"ft", "mi", "m", "km"}:
        range_label = {
            "ft": "футов",
            "mi": "миль",
            "m": "м",
            "km": "км",
        }[range_type]
        range_value = spell_range.get("value")

        if range_value is not None:
            range_text = f"{range_value} {range_label}"

    components = section("components")
    school_name = school_names.get(system.get("school"), "")

    school = (
        MagicSchool.objects.filter(name__iexact=school_name).first()
        if school_name else None
    )
    casting_time = (
        SpellTime.objects.filter(time__iexact=time_text).first()
        if time_text else None
    )

    return {
        "name": data["name"].strip(),
        "level": system.get("level", 0),
        "school": school.pk if school else None,
        "time": casting_time.pk if casting_time else None,
        "range": range_text,
        "duration": duration_text,
        "description": description.strip(),
        "verbal_component": components.get("vocal") is True,
        "somatic_component": components.get("somatic") is True,
        "ritual": components.get("ritual") is True,
        "concentration": components.get("concentration") is True,
        "source_book": (
            system.get("source")
            if isinstance(system.get("source"), str)
            else ""
        ),
    }