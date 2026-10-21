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


def _foundry_initial(data):
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

    from spells.materials import normalize_materials
    material_items=normalize_materials([{'name':material_text,'cost':materials.get('cost')}] if material_text or materials.get('cost') else [])
    # Foundry uses zero as the default when no monetary requirement is specified.
    for item in material_items:
        if item['cost'] is not None and float(item['cost']) == 0:item['cost']=None

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
        "material_components": material_items,
        "ritual": components.get("ritual") is True,
        "concentration": components.get("concentration") is True,
        "source_book": (
            system.get("source")
            if isinstance(system.get("source"), str)
            else ""
        ),
    }


def validate_spell_payload(data):
    if not isinstance(data, dict):
        raise ValueError('Запись должна быть объектом JSON.')
    if data.get('type', 'spell') != 'spell':
        raise ValueError('Эта запись не является заклинанием.')
    if not isinstance(data.get('name'), str) or not data['name'].strip():
        raise ValueError('В записи отсутствует название заклинания.')
    if 'system' in data and not isinstance(data['system'], dict):
        raise ValueError('Раздел system должен быть объектом JSON.')


def _native_initial(data, user):
    from spells.models import DamageType, Effect, Subclass
    from spells.class_access import visible_classes
    fields=('name','level','range','duration','concentration','ritual','verbal_component',
            'somatic_component','description','higher_level','attack_type',
            'saving_throw_ability','source_book','page_number')
    initial={name:data[name] for name in fields if name in data}
    for name in ('concentration','ritual','verbal_component','somatic_component'):
        if name in initial and not isinstance(initial[name], bool):
            raise ValueError('Поле '+name+' должно содержать true или false.')
    initial['name']=data['name'].strip()
    def resolve(value,objects,field,label):
        if value in (None,''):return None
        if isinstance(value,bool) or not isinstance(value,(str,int)):
            raise ValueError(label+': укажи ID или название.')
        if isinstance(value,int):matches=list(objects.filter(pk=value).values_list('pk',flat=True)[:2])
        else:
            from spells.import_links import key
            matches=[pk for pk,name in objects.values_list('pk',field) if key(name)==key(value)]
        if len(matches)!=1:raise ValueError(label+': «'+str(value)+'» не найдено или неоднозначно.')
        return matches[0]
    for name,model,field,label in [('school',MagicSchool,'name','Школа магии'),('time',SpellTime,'time','Время накладывания')]:
        initial[name]=resolve(data.get(name),model.objects.all(),field,label)
    classes=visible_classes(user)
    for name,objects,label in [('effects',Effect.objects.all(),'Эффекты'),('aviable_classes',classes,'Классы'),
                               ('aviable_subclasses',Subclass.objects.filter(character_class__in=classes),'Подклассы')]:
        if name in data:
            if not isinstance(data[name],list):raise ValueError(label+': нужен список ID или названий.')
            initial[name]=[resolve(value,objects,'name',label) for value in data[name]]
    from spells.materials import normalize_materials
    value=data.get('material_components',data.get('materials',data.get('material_component',[])))
    if isinstance(value,str) and ('material_cost' in data or 'material_component_cost' in data):
        value={'name':value,'cost':data.get('material_cost',data.get('material_component_cost'))}
    initial['material_components']=normalize_materials(value)
    return initial


def build_spell_initial(data, user=None, *, linker=None, auto_links=True):
    validate_spell_payload(data)
    initial=_foundry_initial(data) if 'system' in data else _native_initial(data,user)
    initial.setdefault('level', 0)
    initial.setdefault('attack_type', 'NONE')
    if 'system' in data:
        system=data['system']
        extra=system.get('higher_level',system.get('higherLevel',''))
        if isinstance(extra,str):initial['higher_level']=plain_text(extra)
    for name in ('description','higher_level'):
        value=initial.get(name,'')
        if not isinstance(value,str):raise ValueError('Поле '+name+' должно содержать текст.')
        from spells.description import DESCRIPTION_PREFIX,parse_description
        if len(value)>100000:raise ValueError('Описание длиннее 100 000 символов.')
        if value.startswith(DESCRIPTION_PREFIX):parse_description(value)
        elif 'system' not in data:value=plain_text(value)
        initial[name]=value
    if auto_links:
        from spells.import_links import ImportLinker
        linker=linker or ImportLinker(user)
        for name in ('description','higher_level'):initial[name]=linker.description(initial[name])
        initial['_import_warnings']=sorted(linker.warnings)
    return initial
