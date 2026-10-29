from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST
from spells.models import Person, Effect, CharacterCondition, ConcentrationCheck
from spells.spell_access import visible_spells
from spells.combat import combat_state, end_concentration, roll_concentration
from spells.views.rests import integer


@login_required
@require_GET
def concentration_spell_search(request, pk):
    get_object_or_404(Person, pk=pk, player__user=request.user)
    spells = visible_spells(request.user).filter(concentration=True)
    search = request.GET.get('search', '').strip()[:150]
    if search:
        spells = spells.filter(name__icontains=search)
    return JsonResponse({'spells': [{'id': spell.pk, 'name': spell.name} for spell in spells.order_by('name', 'pk')[:30]]})


@login_required
@require_POST
def character_combat_change(request, pk):
    with transaction.atomic():
        person = get_object_or_404(Person.objects.select_for_update(), pk=pk, player__user=request.user)
        try:
            revision = integer(request.POST.get('revision'), 0, 2_000_000_000)
            if revision != person.combat_revision:
                return JsonResponse({'error': 'Данные изменились в другой вкладке. Проверь новые значения и повтори действие.', 'combat': combat_state(person, request.user)}, status=409)
            action = request.POST.get('action')
            if action == 'condition_add':
                condition = get_object_or_404(Effect, pk=integer(request.POST.get('condition_id'), 1, 2_000_000_000), category='COND')
                note = request.POST.get('note', '').strip()
                if len(note) > 200:
                    raise ValueError('Сократи заметку до 200 символов.')
                incapacitates = request.POST.get('incapacitates') == 'on'
                CharacterCondition.objects.update_or_create(person=person, condition=condition, defaults={'note': note, 'incapacitates': incapacitates})
                message = 'Состояние сохранено.'
                if incapacitates and person.concentration_name:
                    end_concentration(person)
                    message += ' Концентрация прекращена: персонаж лишён дееспособности.'
            elif action == 'condition_remove':
                row = get_object_or_404(CharacterCondition, person=person, pk=integer(request.POST.get('condition_row_id'), 1, 2_000_000_000))
                row.delete()
                message = 'Состояние снято.'
            elif action == 'concentration_start':
                if person.current_hit_points < 1:
                    raise ValueError('Для концентрации нужен хотя бы 1 хит.')
                if person.active_conditions.filter(incapacitates=True, condition__category='COND').exists():
                    raise ValueError('Сначала сними состояние, которое лишает дееспособности.')
                spell = get_object_or_404(visible_spells(request.user), pk=integer(request.POST.get('spell_id'), 1, 2_000_000_000), concentration=True)
                if person.concentration_name and request.POST.get('replace') != 'on':
                    raise ValueError('Подтверди замену текущей концентрации.')
                end_concentration(person)
                person.concentration_spell = spell
                person.concentration_name = spell.name
                message = 'Концентрация начата. Ячейка заклинания не расходуется этим действием.'
            elif action == 'concentration_end':
                end_concentration(person)
                message = 'Концентрация прекращена.'
            elif action in ('concentration_roll', 'concentration_manual'):
                check = get_object_or_404(ConcentrationCheck, person=person, pk=integer(request.POST.get('check_id'), 1, 2_000_000_000))
                if not person.concentration_name:
                    raise ValueError('Нет активной концентрации.')
                if action == 'concentration_roll':
                    message = roll_concentration(person, check, request.POST.get('mode'))
                else:
                    outcome = request.POST.get('outcome')
                    if outcome not in ('success', 'failure'):
                        raise ValueError('Укажи результат своего спасброска.')
                    if outcome == 'success':
                        check.delete()
                        message = 'Отмечен успешный спасбросок. Концентрация сохранена.'
                    else:
                        end_concentration(person)
                        message = 'Отмечен провал спасброска. Концентрация прекращена.'
            elif action == 'concentration_check_add':
                if not person.concentration_name:
                    raise ValueError('Нет активной концентрации.')
                dc = integer(request.POST.get('dc'), 1, 1_000_000_000)
                ConcentrationCheck.objects.create(person=person, dc=dc)
                message = 'Добавлена проверка концентрации.'
            else:
                raise ValueError('Неизвестное действие.')
        except ValueError as error:
            return JsonResponse({'error': str(error)}, status=400)
        person.combat_revision += 1
        person.save(update_fields=['combat_revision', 'concentration_spell', 'concentration_name', 'updated_at'])
        return JsonResponse({'message': message, 'combat': combat_state(person, request.user)})
