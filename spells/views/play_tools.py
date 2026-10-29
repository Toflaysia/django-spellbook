from copy import deepcopy
from spells.character_checks import ABILITIES, SKILLS
from spells.spell_access import visible_spells
from spells.class_access import scope_spell_classes
from spells.templatetags.description_tags import description_text
from spells.rests import rest_state
from spells.combat import combat_state, concentration_damage
import re
import secrets
from decimal import Decimal
from django import forms
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.http import require_GET, require_POST
from spells.description import DescriptionModelForm
from spells.models import Person, Spell, DamageType, Effect, MagicSchool, Trait

COINS = [('gold', 'Золотые', 'З', 100), ('silver', 'Серебряные', 'С', 10), ('copper', 'Медные', 'М', 1), ('platinum', 'Платиновые', 'П', 1000), ('electrum', 'Электрумовые', 'Э', 50)]
POTIONS = {'small': (2, 2, 'Обычное'), 'greater': (4, 4, 'Большое'), 'superior': (8, 8, 'Превосходное'), 'supreme': (10, 20, 'Высшее')}
MAX_AMOUNT = 1_000_000_000

def state(person):
    coins = {name: getattr(person, name + '_coins') for name, *_ in COINS}
    total = sum(coins[name]*rate for name, _, _, rate in COINS)
    return {'current':person.current_hit_points, 'maximum':person.max_hit_points, 'temporary':person.temporary_hit_points, 'coins':coins, 'gold_total':str(Decimal(total)/100)}

class EquipmentForm(DescriptionModelForm):
    description_field_names = ('equipment_description',)
    class Meta:
        model=Person
        fields=['equipment_description']
        widgets={'equipment_description':forms.Textarea(attrs={'rows':12})}

@login_required
@require_GET
def character_detail_page(request, pk):
    person=get_object_or_404(Person.objects.select_related('character_class','subclass'),pk=pk,player__user=request.user)
    checks=person.computed_checks
    ability_cards=[]
    for name,label in ABILITIES.items():
        save=next(row for row in checks['saves'] if row['key']==name)
        skills=[row for row in checks['skills'] if next(item[2] for item in SKILLS if item[0]==row['key'])==name]
        ability_cards.append({'key':name,'label':label,'score':getattr(person,name),'modifier':(getattr(person,name)-10)//2,'save':save,'skills':skills})
    return render(request,'spells/character_detail.html',{
        'character_spellbooks':person.spellbooks.order_by('name','pk'),
        'character':person, 'equipment_form':EquipmentForm(instance=person), 'coin_types':COINS,
        'coins_display':[(name,label,symbol,getattr(person,name+'_coins')) for name,label,symbol,_ in COINS],
        'character_state':state(person), 'rest_state':rest_state(person),
        'combat_state':combat_state(person, request.user),
        'condition_catalog':[{'id':condition.pk,'name':condition.name,'description':description_text(condition.description)} for condition in Effect.objects.filter(category='COND').order_by('name','pk')],
        'checks':checks, 'ability_cards':ability_cards,
        'abilities':[(name,person._meta.get_field(name).verbose_name,getattr(person,name),(getattr(person,name)-10)//2) for name in ('strength','dexterity','constitution','intelligence','wisdom','charisma')],
    })

def amount(value):
    value=str(value).strip()
    if len(value)>100 or not re.fullmatch(r'\d+(?:\s*[+-]\s*\d+)*',value):
        raise ValueError('Введи целое число или сумму, например 10+5.')
    result=0
    for term in re.findall(r'[+-]?\s*\d+',value):
        result+=int(term.replace(' ',''))
    if not 0<=result<=MAX_AMOUNT:
        raise ValueError('Значение должно быть от 0 до 1 000 000 000.')
    return result

@login_required
@require_POST
def character_resource_change(request, pk):
    with transaction.atomic():
        person=get_object_or_404(Person.objects.select_for_update(),pk=pk,player__user=request.user)
        action=request.POST.get('action','')
        note='Сохранено.'
        try:
            if action=='active':
                selected=request.POST.get('is_active')
                if selected not in ('true','false'):
                    raise ValueError('Укажи статус персонажа.')
                person.is_active=selected=='true'
                person.save(update_fields=['is_active','updated_at'])
            elif action=='training':
                group=request.POST.get('group')
                key=request.POST.get('key')
                training=request.POST.get('training')
                allowed={row[0] for row in SKILLS} if group=='skills' else set(ABILITIES) if group=='saves' else set()
                choices={'none','proficient','expertise','half'} if group=='skills' else {'none','proficient'}
                if key not in allowed or training not in choices:
                    raise ValueError('Неверный навык или степень владения.')
                config=deepcopy(person.check_settings or {})
                config.setdefault(group,{}).setdefault(key,{})['training']=training
                person.check_settings=config
                person.save(update_fields=['check_settings','updated_at'])
                return JsonResponse({'checks':person.computed_checks,'message':'Владение сохранено.'})
            elif action=='check_bonus':
                group=request.POST.get('group')
                key=request.POST.get('key')
                allowed={row[0] for row in SKILLS} if group=='skills' else set(ABILITIES) if group=='saves' else set()
                raw=request.POST.get('bonus','')
                if key not in allowed or not re.fullmatch(r'[+-]?\d{1,4}',raw):
                    raise ValueError('Укажи целый бонус от −1000 до 1000.')
                value=int(raw)
                if not -1000<=value<=1000:
                    raise ValueError('Укажи целый бонус от −1000 до 1000.')
                config=deepcopy(person.check_settings or {})
                config.setdefault(group,{}).setdefault(key,{})['bonus']=value
                person.check_settings=config
                person.save(update_fields=['check_settings','updated_at'])
                return JsonResponse({'checks':person.computed_checks,'message':'Бонус сохранён.'})
            elif action=='equipment':
                form=EquipmentForm(request.POST,instance=person)
                if not form.is_valid():
                    return JsonResponse({'error':'Проверь описание снаряжения.','errors':form.errors},status=400)
                form.save()
            elif action in ('heal','damage','temporary','maximum','potion'):
                value=amount(request.POST.get('amount','0')) if action!='potion' else 0
                if action=='potion':
                    potion=request.POST.get('potion')
                    if potion not in POTIONS:
                        raise ValueError('Выбери зелье.')
                    count,bonus,label=POTIONS[potion]
                    rolls=[secrets.randbelow(4)+1 for _ in range(count)]
                    value=sum(rolls)+bonus
                    note=f'{label} зелье: {" + ".join(map(str,rolls))} + {bonus} = {value} хитов.'
                if action in ('heal','potion'):
                    before=person.current_hit_points
                    person.current_hit_points=min(person.max_hit_points,person.current_hit_points+value)
                    note+=f' Восстановлено: {person.current_hit_points-before}.'
                elif action=='damage':
                    absorbed=min(person.temporary_hit_points,value)
                    person.temporary_hit_points-=absorbed
                    person.current_hit_points=max(0,person.current_hit_points-(value-absorbed))
                    note+=concentration_damage(person,value)
                elif action=='temporary':
                    person.temporary_hit_points=max(person.temporary_hit_points,value)
                    note='Временные хиты сохранены. Они не складываются: используется большее значение.'
                elif action=='maximum':
                    if value<1:
                        raise ValueError('Максимум хитов должен быть больше нуля.')
                    person.max_hit_points=value
                    person.current_hit_points=min(person.current_hit_points,value)
                person.rest_revision+=1
                person.save(update_fields=['current_hit_points','temporary_hit_points','max_hit_points','rest_revision','combat_revision','concentration_spell','concentration_name','updated_at'])
            elif action == 'convert':
                rates={name:rate for name,_,_,rate in COINS}
                source=request.POST.get('from_coin','')
                target=request.POST.get('to_coin','')
                if source not in rates or target not in rates or source == target:
                    raise ValueError('Выбери два разных типа монет.')
                value=amount(request.POST.get('amount',''))
                if value>getattr(person,source+'_coins'):
                    raise ValueError('Недостаточно монет для обмена.')
                received=value*rates[source]//rates[target]
                if received == 0:
                    raise ValueError('Этого количества недостаточно для одной монеты выбранного типа.')
                spent=received*rates[target]//rates[source]
                if getattr(person,target+'_coins')+received>MAX_AMOUNT:
                    raise ValueError('Слишком много монет после обмена.')
                setattr(person,source+'_coins',getattr(person,source+'_coins')-spent)
                setattr(person,target+'_coins',getattr(person,target+'_coins')+received)
                person.save(update_fields=[source+'_coins',target+'_coins','updated_at'])
                note=f'Обмен сохранён: списано {spent}, получено {received}.'
                if value-spent:
                    note+=f' Остаток {value-spent} исходных монет сохранён в кошельке.'
            elif action in ('take','give','coin_set'):
                coin=request.POST.get('coin','')
                if coin not in {name for name,*_ in COINS}:
                    raise ValueError('Выбери монеты.')
                value=amount(request.POST.get('amount',''))
                field=coin+'_coins'
                existing=getattr(person,field)
                new=value if action=='coin_set' else existing+(value if action=='take' else -value)
                if new<0:
                    raise ValueError('Недостаточно монет этого типа.')
                if new>MAX_AMOUNT:
                    raise ValueError('Слишком много монет.')
                setattr(person,field,new)
                person.save(update_fields=[field,'updated_at'])
            else:
                raise ValueError('Неизвестное действие.')
        except ValueError as error:
            return JsonResponse({'error':str(error)},status=400)
    return JsonResponse({**state(person),'message':note,'combat':combat_state(person,request.user)})

def available_spells(request):
    return visible_spells(request.user)

@require_GET
def spell_link_search(request):
    search=request.GET.get('search','').strip()[:150]
    spells=available_spells(request)
    if search:
        spells=spells.filter(name__icontains=search)
    spells=spells.order_by('name','pk')[:30]
    return JsonResponse({'spells':[{'id':s.pk,'name':s.name,'level':s.level} for s in spells]})

@require_GET
def spell_preview(request,pk):
    spell=get_object_or_404(available_spells(request).select_related('school','time','created_by__user').prefetch_related('aviable_classes','effects'),pk=pk)
    scope_spell_classes(spell, request.user)
    return render(request,'spells/includes/spell_preview.html',{'spell':spell})


LINK_CATALOGS = {
    'damage-types': (DamageType, 'Тип урона'),
    'effects': (Effect, 'Состояние'),  # Compatibility with existing preview links.
    'conditions': (Effect, 'Состояние'),
    'schools': (MagicSchool, 'Школа магии'),
    'traits': (Trait, 'Черта'),
}


def linked_catalog(slug):
    if slug not in LINK_CATALOGS:
        raise Http404('Справочник не найден.')
    model, title = LINK_CATALOGS[slug]
    objects = model.objects.all()
    if slug in ('effects', 'conditions'):
        objects = objects.filter(category='COND').select_related('damage_type')
    return objects, title


@require_GET
def catalog_link_search(request, slug):
    objects, title = linked_catalog(slug)
    search = request.GET.get('search', '').strip()[:150]
    if search:
        objects = objects.filter(name__icontains=search)
    return JsonResponse({'items': [
        {'id': item.pk, 'name': item.name}
        for item in objects.order_by('name', 'pk')[:30]
    ]})


@require_GET
def catalog_preview(request, slug, pk):
    if slug == "traits":
        raise Http404("Черты открываются на странице справочника.")
    objects, title = linked_catalog(slug)
    item = get_object_or_404(objects, pk=pk)
    return render(request, 'spells/includes/catalog_preview.html', {
        'item': item, 'catalog_kind': slug, 'catalog_title': title,
    })
