from spells.abilities import (
    change_ability_resource,
    toggle_optional_feature,
    resource_snapshot,
)
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from spells.models import Person, Spellbook, CharacterResource
from spells.rests import rest_state, spend_hit_die, finish_rest
from spells.views.play_tools import state
from spells.combat import combat_state


def integer(value, low, high):
    # Не принимаем дробные, отрицательные и слишком большие числа даже при обходе HTML-ограничений.
    if (
        not isinstance(value, str)
        or not value.isascii()
        or not value.isdigit()
        or len(value) > 10
        or not low <= int(value) <= high
    ):
        raise ValueError("Укажи допустимое целое число.")
    return int(value)


@login_required
@require_POST
def character_rest_change(request, pk):
    # Все изменения отдыха, ресурсов и здоровья сохраняются вместе. Ошибка откатывает транзакцию.
    with transaction.atomic():
        # Фильтр по владельцу обязателен: знание номера персонажа не даёт права его менять.
        person = get_object_or_404(
            Person.objects.select_for_update().select_related(
                "character_class", "second_class"
            ),
            pk=pk,
            player__user=request.user,
        )
        try:
            revision = integer(request.POST.get("revision"), 0, 2_000_000_000)
            # Старая открытая вкладка не должна повторно потратить ресурс: возвращаем свежие значения.
            if revision != person.rest_revision:
                return JsonResponse(
                    {
                        "error": "Данные изменились в другой вкладке. Проверь обновлённые значения и повтори действие.",
                        "rest": rest_state(person),
                        "health": state(person),
                        "combat": combat_state(person, request.user),
                    },
                    status=409,
                )
            action = request.POST.get("action")
            if action == "spend_hit_die":
                message = spend_hit_die(
                    person, integer(request.POST.get("die"), 2, 100)
                )
            elif action in ("short_rest", "long_rest"):
                ids = [
                    integer(value, 1, 2_000_000_000)
                    for value in request.POST.getlist("book_ids")
                ]
                books = list(
                    Spellbook.objects.select_for_update().filter(
                        owner=person, pk__in=ids
                    )
                )
                if len(books) != len(set(ids)):
                    raise ValueError("Выбери только спеллбуки этого персонажа.")
                recovery = (
                    {
                        str(row["die"]): integer(
                            request.POST.get("recover_" + str(row["die"]), "0"),
                            0,
                            row["spent"],
                        )
                        for row in rest_state(person)["dice"]
                    }
                    if action == "long_rest"
                    else None
                )
                message = finish_rest(
                    person,
                    "long" if action == "long_rest" else "short",
                    books,
                    recovery,
                )
            elif action in ("ability_spend", "ability_restore"):
                message = change_ability_resource(
                    person,
                    request.POST.get("key"),
                    integer(request.POST.get("quantity", "1"), 1, 9999),
                    restore=action == "ability_restore",
                )
            elif action == "ability_toggle":
                enabled = request.POST.get("enabled")
                if enabled not in ("true", "false"):
                    raise ValueError("Укажи выбор умения.")
                toggle_optional_feature(
                    person,
                    integer(request.POST.get("feature_id"), 1, 2_000_000_000),
                    enabled == "true",
                )
                message = "Выбор умения сохранён."
            elif action == "resource_create":
                name = request.POST.get("name", "").strip()
                maximum = integer(request.POST.get("maximum"), 1, 9999)
                policy = request.POST.get("refresh_on")
                if (
                    not name
                    or len(name) > 80
                    or policy not in ("short", "long", "manual")
                ):
                    raise ValueError(
                        "Проверь название и способ восстановления ресурса."
                    )
                CharacterResource.objects.create(
                    person=person,
                    name=name,
                    maximum=maximum,
                    current=maximum,
                    refresh_on=policy,
                )
                message = "Ресурс добавлен."
            elif action in ("resource_change", "resource_delete"):
                resource = get_object_or_404(
                    CharacterResource.objects.select_for_update(),
                    person=person,
                    pk=integer(request.POST.get("resource_id"), 1, 2_000_000_000),
                )
                _, adopted = resource_snapshot(person)
                if resource.source_key or resource.pk in adopted:
                    raise ValueError("Этот ресурс управляется умением класса.")
                if action == "resource_delete":
                    resource.delete()
                    message = "Ресурс удалён."
                else:
                    operation = request.POST.get("operation")
                    if operation not in ("spend", "restore"):
                        raise ValueError("Выбери действие с ресурсом.")
                    value = resource.current + (-1 if operation == "spend" else 1)
                    if not 0 <= value <= resource.maximum:
                        raise ValueError("Значение ресурса уже достигло границы.")
                    resource.current = value
                    resource.save(update_fields=["current"])
                    message = "Ресурс обновлён."
            else:
                raise ValueError("Неизвестное действие отдыха.")
            # Версия меняется после успешного действия, поэтому повтор старого запроса будет отклонён.
            person.rest_revision += 1
            person.save(
                update_fields=[
                    "current_hit_points",
                    "temporary_hit_points",
                    "spent_hit_dice",
                    "last_short_rest_at",
                    "last_long_rest_at",
                    "rest_revision",
                    "combat_revision",
                    "concentration_spell",
                    "concentration_name",
                    "updated_at",
                ]
            )
        except ValueError as error:
            return JsonResponse({"error": str(error)}, status=400)
        return JsonResponse(
            {
                "message": message,
                "rest": rest_state(person),
                "health": state(person),
                "combat": combat_state(person, request.user),
            }
        )
