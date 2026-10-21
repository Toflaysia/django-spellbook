from spells.class_access import visible_classes
from django import forms
from django.db.models import Q
from spells.models import Spell, MagicSchool, CharacterClass, Effect, DamageType, SpellTime

YES_NO = [('', 'Все варианты'), ('yes', 'Да'), ('no', 'Нет')]

from spells.component_filters import COMPONENT_CHOICES, ComponentsSelect


class SpellFilterForm(forms.Form):
    components=forms.MultipleChoiceField(label="Компоненты",required=False,choices=COMPONENT_CHOICES,widget=ComponentsSelect)
    search = forms.CharField(label='Название', required=False, max_length=150, widget=forms.TextInput(attrs={'type': 'search', 'placeholder': 'Начни вводить название'}))
    level = forms.ChoiceField(label='Уровень', required=False, choices=[('', 'Все уровни'), ('0', 'Заговор'), *((str(n), f'Уровень {n}') for n in range(1,10))])
    school = forms.ModelChoiceField(label='Школа магии', required=False, queryset=MagicSchool.objects.none(), empty_label='Все школы')
    character_class = forms.ModelChoiceField(label='Класс', required=False, queryset=CharacterClass.objects.none(), empty_label='Все классы')
    time = forms.ModelChoiceField(label='Время накладывания', required=False, queryset=SpellTime.objects.none(), empty_label='Любое время')
    effect = forms.ModelChoiceField(label='Эффект', required=False, queryset=Effect.objects.none(), empty_label='Все эффекты')
    damage_type = forms.ModelChoiceField(label='Тип урона', required=False, queryset=DamageType.objects.none(), empty_label='Все типы урона')
    attack_type = forms.ChoiceField(label='Механика', required=False, choices=[('', 'Любая механика'), *Spell.AttackType.choices])
    concentration = forms.ChoiceField(label='Концентрация', required=False, choices=YES_NO)
    ritual = forms.ChoiceField(label='Ритуал', required=False, choices=YES_NO)
    origin = forms.ChoiceField(label='Источник записи', required=False, choices=[('', 'Все записи'), ('official', 'Официальные'), ('custom', 'Авторские')])

    def __init__(self, *args, mine=False, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        for name, model in [('school',MagicSchool), ('character_class',CharacterClass), ('time',SpellTime), ('effect',Effect), ('damage_type',DamageType)]:
            self.fields[name].queryset = model.objects.order_by('time' if name=='time' else 'name','pk')
        self.fields["character_class"].queryset = visible_classes(user).order_by("name","pk")
        if not mine:
            self.fields.pop('origin')

    @property
    def basic_fields(self):
        return [self[name] for name in ('search', 'level', 'school', 'components')]

    @property
    def advanced_fields(self):
        return [self[name] for name in self.fields if name not in ('search', 'level', 'school', 'components')]

    @property
    def advanced_count(self):
        return sum(bool(self.data.get(field.name)) for field in self.advanced_fields)

    @property
    def advanced_open(self):
        return bool(self.advanced_count or any(field.errors for field in self.advanced_fields))

    def apply(self, queryset):
        if not self.is_bound:
            return queryset
        if not self.is_valid():
            return queryset.none()
        values = self.cleaned_data
        for component in values['components']:
            if component=='material':queryset=queryset.exclude(material_components=[])
            else:queryset=queryset.filter(**{component+'_component':True})
        if values['search']:
            queryset = queryset.filter(name__icontains=values['search'])
        for name in ('level','school','time','attack_type'):
            if values[name] != '' and values[name] is not None:
                queryset = queryset.filter(**{name:values[name]})
        if values['character_class']:
            cls=values['character_class']
            queryset=queryset.filter(Q(aviable_classes=cls)|Q(aviable_subclasses__character_class=cls))
        if values['effect']:
            queryset=queryset.filter(effects=values['effect'])
        if values['damage_type']:
            queryset=queryset.filter(effects__damage_type=values['damage_type'])
        for name in ('concentration','ritual'):
            if values[name]:
                queryset=queryset.filter(**{name:values[name]=='yes'})
        if values.get('origin'):
            queryset=queryset.filter(is_official=values['origin']=='official')
        return queryset.distinct()

class ComponentFilterForm(forms.Form):
    is_consumable=forms.ChoiceField(label='Потребляемый',required=False,choices=YES_NO)
    is_focus=forms.ChoiceField(label='Фокусировка',required=False,choices=YES_NO)
    min_cost=forms.DecimalField(label='Стоимость от, зм',required=False,min_value=0,max_digits=7,decimal_places=2)
    max_cost=forms.DecimalField(label='Стоимость до, зм',required=False,min_value=0,max_digits=7,decimal_places=2)
    def clean(self):
        data=super().clean()
        if data.get('min_cost') is not None and data.get('max_cost') is not None and data['min_cost']>data['max_cost']:
            self.add_error('max_cost','Стоимость «до» должна быть не меньше стоимости «от».')
        return data

class SchoolFilterForm(forms.Form):
    has_spells=forms.ChoiceField(label='Есть официальные заклинания',required=False,choices=YES_NO)
    level=forms.ChoiceField(label='Уровень официального заклинания',required=False,choices=SpellFilterForm.base_fields['level'].choices)
